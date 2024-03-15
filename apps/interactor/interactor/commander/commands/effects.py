import enum
from typing import ClassVar, Self

import attrs
import sanic
import strcs
from interactor.commander import helpers as ihp
from interactor.commander import selector
from interactor.commander.devices import DeviceFinder
from interactor.commander.store import Command, Store, reg, store
from photons_canvas.theme import ApplyTheme
from photons_control.multizone import SetZonesEffect
from photons_control.planner import Skip
from photons_control.script import FromGeneratorPerSerial
from photons_control.tile import SetTileEffect
from photons_messages.enums import MultiZoneEffectType, TileEffectType
from photons_web_server import commander


@attrs.define(slots=False, kw_only=True)
class EffectsRunOptions:
    apply_theme: bool = False

    theme_options: dict[str, object] = attrs.field(factory=dict)

    matrix_animation: selector.TileEffectTypeValue

    matrix_options: dict[str, object] | None = None

    linear_animation: selector.MultiZoneEffectTypeValue

    linear_options: dict[str, object] | None = None

    class Docs:
        apply_theme: str = """Whether to apply a theme to the devices before running an animation"""

        theme_options: str = """Any options to give to applying a theme"""

        matrix_animation: str = """
        The animation to run for matrix devices.

        This can be FLAME, MORPH or OFF.

        If you don't supply this these devices will not run any animation"
        """

        matrix_options: str = """
        Any options to give to the matrix animation. For example duration
        """

        linear_animation: str = """
        The animation to run for linear devices.

        Currently only MOVE or OFF are supported

        If you don't supply this these devices will not run any animation"
        """

        linear_options: str = """
        Options for the linear firmware effect:

        - speed: duration in seconds to complete one cycle of the effect
        - duration: time in seconds the effect will run.
        - direction: either "left" or "right" (default: "right")

        If duration is not specified or set to 0, the effect will run
        until it is manually stopped.
        """


@attrs.define(slots=False, kw_only=True)
class EffectsStopOptions:
    apply_theme: bool = False

    theme_options: dict[str, object] = attrs.field(factory=dict)

    stop_matrix: bool = True

    matrix_options: dict[str, object] | None = None

    stop_linear: bool = True

    linear_options: dict[str, object] | None = None

    class Docs:
        apply_theme: str = """Whether to apply a theme to the devices before running an animation"""

        theme_options: str = """Any options to give to applying a theme"""

        stop_matrix: str = """Whether to stop any matrix animations"""

        matrix_options: str = """
        Any options to give to the matrix animation. For example duration
        """

        stop_linear: str = """Whether to stop any linear animations"""

        linear_options: str = """
        Options for the linear firmware effect:

        - speed: duration in seconds to complete one cycle of the effect
        - duration: time in seconds the effect will run.
        - direction: either "left" or "right" (default: "right")

        If duration is not specified or set to 0, the effect will run
        until it is manually stopped.
        """


@attrs.define(kw_only=True)
class V1Effects:
    matcher: selector.Matcher
    timeout: selector.Timeout = attrs.field(default=20)


@attrs.define(kw_only=True)
class V1EffectsRun(V1Effects, EffectsRunOptions): ...


@attrs.define(kw_only=True)
class V1EffectsStop(V1Effects, EffectsStopOptions): ...


@attrs.define(kw_only=True)
class EffectsBody:
    selector: selector.Selector
    command: str
    timeout: int = -1


@attrs.define(kw_only=True)
class EffectsRunBody(EffectsBody, EffectsRunOptions): ...


@attrs.define(kw_only=True)
class EffectsStopBody(EffectsBody, EffectsStopOptions): ...


@attrs.define(kw_only=True)
class EffectsParams:
    timeout: int = -1

    def update_from_put_body(self, body: EffectsBody) -> Self:
        if self.timeout == -1:
            return attrs.evolve(self, timeout=body.timeout)
        else:
            return self


@store.command
class EffectsCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.effects_put, "/v2/effects", methods=["PUT"], name="v2_effects_put")

        routes.http(kls.effects_put, "/v2/effects/run", methods=["PUT"], name="v2_effects_run_put")
        routes.http(
            kls.effects_put, "/v2/effects/stop", methods=["PUT"], name="v2_effects_stop_put"
        )

        routes.http(
            kls.effects_put, "/v2/effects/status", methods=["GET"], name="v2_effects_status_put"
        )

    async def effects_run(
        self,
        progress: commander.Progress,
        request: commander.Request,
        selector: selector.Selector,
        /,
        _body: EffectsRunBody,
        _params: EffectsParams,
    ) -> commander.Response:
        """
        Start or stop a firmware animation on devices that support them
        """
        _params = _params.update_from_put_body(_body)
        devices = self.create(DeviceFinder, {"selector": selector, "timeout": _params.timeout})

        async def gen(reference, afr, **kwargs):
            if _body.apply_theme:
                yield ApplyTheme.msg(_body.theme_options)

            if _body.matrix_animation.effect:
                yield SetTileEffect(_body.matrix_animation.effect, **(_body.matrix_options or {}))

            if _body.linear_animation.effect:
                yield SetZonesEffect(_body.linear_animation.effect, **(_body.linear_options or {}))

        return sanic.json(
            (await devices.send(FromGeneratorPerSerial(gen), add_replies=False)).as_dict()
        )

    async def effects_stop(
        self,
        progress: commander.Progress,
        request: commander.Request,
        selector: selector.Selector,
        /,
        _body: EffectsStopBody,
        _params: EffectsParams,
    ) -> commander.Response:
        """
        Stop any firmware effects on devices.
        """
        _params = _params.update_from_put_body(_body)
        devices = self.create(DeviceFinder, {"selector": selector, "timeout": _params.timeout})

        async def gen(reference, afr, **kwargs):
            if _body.apply_theme:
                yield ApplyTheme.msg(_body.theme_options)

            if _body.stop_matrix:
                yield SetTileEffect(TileEffectType.OFF, palette=[], **(_body.matrix_options or {}))

            if _body.stop_linear:
                yield SetZonesEffect(MultiZoneEffectType.OFF, **(_body.linear_options or {}))

        return sanic.json(
            (await devices.send(FromGeneratorPerSerial(gen), add_replies=False)).as_dict()
        )

    async def effects_status(
        self,
        progress: commander.Progress,
        request: commander.Request,
        selector: selector.Selector,
        /,
        _params: EffectsParams,
    ) -> commander.Response:
        """
        Returns the current status of effects on devices that support them
        """
        devices = self.create(DeviceFinder, {"selector": selector, "timeout": _params.timeout})
        plans = devices.sender.make_plans("capability", "firmware_effects")
        devices.sender.gatherer.clear_cache()

        serials = await devices.serials
        result = ihp.ResultBuilder()
        result.add_serials(serials)

        def convert(d):
            for k, v in list(d.items()):
                if isinstance(v, enum.Enum):
                    d[k] = v.name

            if "palette" in d:
                d["palette"] = [c.as_dict() for c in d["palette"]]

            return d

        async for serial, complete, info in devices.sender.gatherer.gather_per_serial(
            plans, serials, error_catcher=result.error, message_timeout=_params.timeout
        ):
            if not complete:
                continue

            cap = info["capability"]["cap"]
            final = {
                "product": {
                    "pid": cap.product.pid,
                    "vid": cap.product.vendor.vid,
                    "cap": convert(cap.as_dict()),
                    "name": cap.product.name,
                },
                "effect": {"type": "SKIP"},
            }

            effects = info["firmware_effects"]
            if effects is not Skip:
                final["effect"]["type"] = effects["type"].name
                final["effect"]["options"] = convert(effects["options"])

            result.result["results"][serial] = final

        return sanic.json(result.as_dict())

    known_routes = {"run": effects_run, "stop": effects_stop, "status": effects_status}

    async def effects_put(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: EffectsBody,
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

        if command == "effects/run":
            body = reg.create(EffectsRunBody, _body_raw, meta=_meta)
            params = reg.create(EffectsParams, _params_raw, meta=_meta).update_from_put_body(body)
            return route(progress, request, body.selector, _body=body, _params=params)
        elif command == "effects/stop":
            body = reg.create(EffectsStopBody, _body_raw, meta=_meta)
            params = reg.create(EffectsParams, _params_raw, meta=_meta).update_from_put_body(body)
            return route(progress, request, body.selector, _body=body, _params=params)
        else:
            body = reg.create(EffectsBody, _body_raw, meta=_meta)
            params = reg.create(EffectsParams, _params_raw, meta=_meta).update_from_put_body(body)
            return route(progress, request, body.selector, _params=params)

    implements_v1_commands: ClassVar[set[str]] = {"effects/run", "effects/stop", "effects/status"}

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None

        doc = cls.known_routes[command.split("/")[1]].__doc__
        if command == "effects/run":
            body_kls = V1EffectsRun
        elif command == "effects/stop":
            body_kls = V1EffectsStop
        elif command == "effects/status":
            body_kls = V1Effects
        else:
            return doc

        return ihp.v1_help_text_from_body(
            doc=doc,
            body_typ=strcs.Type.create(body_kls, cache=type_cache),
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
            if command == "effects/run":
                body = reg.create(V1EffectsRun, args, meta=meta)
                match = reg.create(selector.Selector, body.matcher.raw, meta=meta)
                _params = EffectsParams(timeout=body.timeout.value)
                return await self.effects_run(progress, request, match, _body=body, _params=_params)
            elif command == "effects/stop":
                body = reg.create(V1EffectsStop, args, meta=meta)
                match = reg.create(selector.Selector, body.matcher.raw, meta=meta)
                _params = EffectsParams(timeout=body.timeout.value)
                return await self.effects_stop(
                    progress, request, match, _body=body, _params=_params
                )
            elif command == "effects/status":
                body = reg.create(V1Effects, args, meta=meta)
                match = reg.create(selector.Selector, body.matcher.raw, meta=meta)
                _params = EffectsParams(timeout=body.timeout.value)
                return await self.effects_status(progress, request, match, _params=_params)
