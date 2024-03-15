from typing import ClassVar, Self

import attrs
import sanic
import strcs
from delfick_project.option_merge import MergedOptions
from interactor.commander import helpers as ihp
from interactor.commander import selector
from interactor.commander.devices import DeviceFinder
from interactor.commander.store import Command, Store, reg, store
from photons_control.clean import ChangeCleanCycle
from photons_control.planner import Skip
from photons_web_server import commander


@attrs.define
class V1Clean:
    matcher: selector.Matcher
    timeout: selector.Timeout = attrs.field(default=20)


@attrs.define
class V1CleanStart(V1Clean):
    duration_s: int = 0

    class Docs:
        duration_s: str = """(optional) duration of the cleaning cycle, in seconds"""


@attrs.define
class CleanBody:
    selector: selector.Selector
    command: str
    timeout: int = -1


@attrs.define
class CleanParams:
    timeout: int = -1

    def update_from_put_body(self, body: CleanBody) -> Self:
        if self.timeout == -1:
            return attrs.evolve(self, timeout=body.timeout)
        else:
            return self


@attrs.define
class CleanStartBody(CleanBody):
    command: str = attrs.field(init=False, default="clean/start")
    duration_s: int = 0


@attrs.define
class CleanStartParams(CleanParams):
    duration_s: int = 0

    def update_from_put_body(self, body: CleanStartBody) -> Self:
        if self.duration_s == 0:
            return attrs.evolve(self, duration_s=body.duration_s)
        else:
            return self


@store.command
class CleanCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.clean_put, "/v2/clean", methods=["PUT"], name="v2_clean_put")

        for name, route in kls.known_routes.items():
            routes.http(
                route,
                f"/v2/clean/{name}/<selector>",
                methods=["GET"],
                name=f"v2_clean_{name}_select",
            )
            routes.http(route, f"/v2/clean/{name}", methods=["GET"], name=f"v2_clean_{name}_all")

    async def clean_start(
        self,
        progress: commander.Progress,
        request: commander.Request,
        selector: selector.Selector,
        /,
        _params: CleanStartParams,
    ) -> commander.Response:
        """
        Starts a cleaning cycle on the specified HEV device(s). Will use
        the default duration if a duration is not provided.
        """
        devices = self.create(DeviceFinder, {"selector": selector, "timeout": _params.timeout})
        return sanic.json(
            (
                await devices.send(
                    ChangeCleanCycle(enable=True, duration_s=_params.duration_s), add_replies=False
                )
            ).as_dict()
        )

    async def clean_stop(
        self,
        progress: commander.Progress,
        request: commander.Request,
        selector: selector.Selector,
        /,
        _params: CleanParams,
    ) -> commander.Response:
        """
        Stops a cleaning cycle on the specified HEV-enabled device(s). The device
        will revert back to the power state it was in before the cleaning cycle
        started.
        """
        devices = self.create(DeviceFinder, {"selector": selector, "timeout": _params.timeout})
        return sanic.json(
            (await devices.send(ChangeCleanCycle(enable=False), add_replies=False)).as_dict()
        )

    async def clean_status(
        self,
        progress: commander.Progress,
        request: commander.Request,
        selector: selector.Selector,
        /,
        _params: CleanParams,
    ) -> commander.Response:
        """
        Returns the current state and default configuration for an HEV enabled
        device
        """
        devices = self.create(DeviceFinder, {"selector": selector, "timeout": _params.timeout})
        plans = devices.sender.make_plans("hev_status", "hev_config")

        serials = await devices.serials
        result = ihp.ResultBuilder()

        got = await devices.sender.gatherer.gather_all(
            plans, serials, error_catcher=result.error, message_timeout=_params.timeout
        )

        for serial, (complete, info) in got.items():
            if not complete:
                continue

            if info["hev_status"] is Skip:
                continue

            if "hev_status" in info and "hev_config" in info:
                # Create a copy so we don't corrupt the gatherer cache
                final = result.result["results"][serial] = {}
                final["status"] = MergedOptions.using(info["hev_status"]).as_dict()
                final["status"]["last"]["result"] = final["status"]["last"]["result"].name
                final["config"] = info["hev_config"]

        return sanic.json(result.as_dict())

    known_routes = {"start": clean_start, "stop": clean_stop, "status": clean_status}

    async def clean_put(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: CleanBody,
        _body_raw: dict[str, object],
        _params_raw: dict[str, object],
        _meta: strcs.Meta,
        store: Store,
    ) -> commander.Response | None:
        route = self.known_routes.get(command := _body.command)

        if route is None:
            raise sanic.BadRequest(
                message=f"Unknown command '{command}', available: {sorted(self.known_routes)}"
            )

        if command == "clean/start":
            body = reg.create(CleanStartBody, _body_raw, meta=_meta)
            params = reg.create(CleanStartParams, _params_raw, meta=_meta).update_from_put_body(
                body
            )
            return route(progress, request, body.selector, _params=params)
        else:
            body = reg.create(CleanBody, _body_raw, meta=_meta)
            params = reg.create(CleanParams, _params_raw, meta=_meta).update_from_put_body(body)
            return route(progress, request, body.selector, _params=params)

    implements_v1_commands: ClassVar[set[str]] = {"clean/start", "clean/stop", "clean/status"}

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None

        doc = cls.known_routes[command.split("/")[1]].__doc__
        if command == "clean/start":
            return ihp.v1_help_text_from_body(
                doc=doc,
                body_typ=strcs.Type.create(V1CleanStart, cache=type_cache),
            )
        else:
            return ihp.v1_help_text_from_body(
                doc=doc,
                body_typ=strcs.Type.create(V1Clean, cache=type_cache),
            )

    async def run_v1_http(
        self,
        progress: commander.Progress,
        request: commander.Request,
        *,
        command: str,
        args: dict[str, object],
        meta: strcs.Meta,
    ) -> commander.Response | None:
        if command in self.implements_v1_commands:
            if command == "clean/start":
                body = reg.create(V1CleanStart, args, meta=meta)
                match = reg.create(selector.Selector, body.matcher.raw, meta=meta)
                _params = CleanStartParams(timeout=body.timeout.value, duration_s=body.duration_s)
                return await self.clean_start(progress, request, match, _params=_params)
            else:
                body = reg.create(V1Clean, args, meta=meta)
                match = reg.create(selector.Selector, body.matcher.raw, meta=meta)
                _params = CleanParams(timeout=body.timeout.value)
                if command == "clean/stop":
                    return await self.clean_stop(progress, request, match, _params=_params)
                elif command == "clean/status":
                    return await self.clean_status(progress, request, match, _params=_params)
