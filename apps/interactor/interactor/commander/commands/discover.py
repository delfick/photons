from typing import ClassVar

import attrs
import sanic
import strcs
from interactor.commander import helpers as ihp
from interactor.commander import selector
from interactor.commander.devices import DeviceFinder
from interactor.commander.store import Command, reg, store
from photons_web_server import commander


@attrs.define
class V1Discover:
    matcher: selector.Matcher
    timeout: selector.Timeout = attrs.field(default=20)

    just_serials: bool = attrs.field(default=False)

    class Docs:
        just_serials: str = """
        Just return a list of serials instead of all the information per device
        """


@attrs.define
class DiscoverParams:
    timeout: int = -1


@attrs.define
class DiscoverBody:
    selector: selector.Selector
    command: str = "serials"
    timeout: int = -1

    def discover_params(self, params: DiscoverParams) -> DiscoverParams:
        timeout = self.timeout
        if timeout == -1:
            timeout = params.timeout
        return DiscoverParams(timeout=timeout)


@store.command
class DiscoverCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.discover_put, "/v2/discover", methods=["PUT"], name="v2_discover_put")

        for name, route in kls.known_routes.items():
            routes.http(
                route,
                f"/v2/discover/{name}/<selector>",
                methods=["GET"],
                name=f"v2_discover_{name}",
            )
            routes.http(
                route, f"/v2/discover/{name}", methods=["GET"], name=f"v2_discover_{name}_all"
            )

    async def discover_serials(
        self,
        progress: commander.Progress,
        request: commander.Request,
        selector: selector.Selector,
        /,
        _params: DiscoverParams,
    ) -> commander.Response:
        """
        Display serials about all the devices that can be found on the network
        """
        devices = self.create(DeviceFinder, {"selector": selector, "timeout": _params.timeout})
        return sanic.json(await devices.serials)

    async def discover_info(
        self,
        progress: commander.Progress,
        request: commander.Request,
        selector: selector.Selector,
        /,
        _params: DiscoverParams,
    ) -> commander.Response:
        """
        Display information about all the devices that can be found on the network
        """
        devices = self.create(DeviceFinder, {"selector": selector, "timeout": _params.timeout})
        return sanic.json({device.serial: device.info for device in await devices.devices})

    known_routes = {
        "info": discover_info,
        "serials": discover_serials,
    }

    async def discover_put(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: DiscoverBody,
        _params: DiscoverParams,
    ) -> commander.Response | None:
        route = self.known_routes.get(command := _body.command)

        if route is None:
            raise sanic.BadRequest(
                message=f"Unknown command '{command}', available: {sorted(self.known_routes)}"
            )

        return await getattr(self, route.__name__)(
            progress, request, _body.selector, _params=_body.discover_params(_params)
        )

    implements_v1_commands: ClassVar[set[str]] = {"discover"}

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None

        return ihp.v1_help_text_from_body(
            doc=cls.discover_info.__doc__,
            body_typ=strcs.Type.create(V1Discover, cache=type_cache),
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
        if command == "discover":
            body = reg.create(V1Discover, args, meta=meta)
            match = reg.create(selector.Selector, body.matcher.raw, meta=meta)
            _params = DiscoverParams(timeout=body.timeout.value)

            if body.just_serials:
                return await self.discover_serials(progress, request, match, _params=_params)
            else:
                return await self.discover_info(progress, request, match, _params=_params)
