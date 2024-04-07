from typing import ClassVar, Self

import attrs
import sanic
import strcs
from interactor.commander import helpers as ihp
from interactor.commander import selector
from interactor.commander.devices import DeviceFinder
from interactor.commander.store import Command, Store, store
from photons_canvas.theme import ApplyTheme
from photons_control.transform import PowerToggle, Transformer
from photons_web_server import commander


@attrs.define(slots=False, kw_only=True)
class Timeout:
    timeout: selector.Timeout = attrs.field(default=20)


@attrs.define(slots=False, kw_only=True)
class PacketArgs:
    pkt_type: selector.PacketType

    pkt_args: dict[str, object] = attrs.field(factory=dict)

    class Docs:
        pkt_type: str = """
        The type of packet to send to the lights. This can be a number or
        the name of the packet as known by the photons framework.

        A list of what's available can be found at
        https://photons.delfick.com/interacting/packets.html
        """

        pkt_args: str = """
        A dictionary of fields that make up the payload of the packet we
        are sending to the lights.
        """


@attrs.define(slots=False, kw_only=True)
class PowerToggleArgs:
    duration: float = 1.0
    """Duration of the toggle"""

    group: bool = False
    """Whether to treat the lights as a group"""

    class Docs:
        duration: str = """Duration of the toggle"""

        group: str = """Whether to treat the lights as a group"""


@attrs.define(slots=False, kw_only=True)
class TransformArgs:
    transform: dict[str, object]

    transform_options: dict[str, object] = attrs.field(factory=dict)

    class Docs:
        transform: str = """
        A dictionary of what options to use to transform the lights with.

        For example,
        ``{"power": "on", "color": "red"}``

        Or,
        ``{"color": "blue", "effect": "breathe", "cycles": 5}``
        """

        transform_options: str = """
        A dictionay of options that modify the way the tranform
        is performed:

        keep_brightness
            Ignore brightness options in the request

        transition_color
            If the light is off and we power on, setting this to True will mean the
            color of the light is not set to the new color before we make it appear
            to be on. This defaults to False, which means it will appear to turn on
            with the new color
        """


@attrs.define(slots=False, kw_only=True)
class ApplyThemeArgs:
    theme_options: dict[str, object]

    class Docs:
        theme_options: str = """Any options to give to applying a theme"""


@attrs.define(slots=False, kw_only=True)
class V1(Timeout):
    matcher: selector.Matcher


@attrs.define(slots=False, kw_only=True)
class V1Packet(V1, PacketArgs): ...


@attrs.define(slots=False, kw_only=True)
class V1PowerToggle(V1, PowerToggleArgs): ...


@attrs.define(slots=False, kw_only=True)
class V1Transform(V1, TransformArgs): ...


@attrs.define(slots=False, kw_only=True)
class V1ApplyTheme(V1, ApplyThemeArgs): ...


@attrs.define(slots=False, kw_only=True)
class Params:
    timeout: int = -1

    def update_from_put_body(self, body: Timeout) -> Self:
        if self.timeout == -1:
            return attrs.evolve(self, timeout=body.timeout)
        else:
            return self


@attrs.define(slots=False, kw_only=True)
class Body:
    selector: selector.Selector
    command: str
    timeout: int = -1


@attrs.define(slots=False, kw_only=True)
class PacketBody(Body, PacketArgs):
    command: str = ""


@attrs.define(slots=False, kw_only=True)
class PowerToggleBody(Body, PowerToggleArgs):
    command: str = ""


@attrs.define(slots=False, kw_only=True)
class TransformBody(Body, TransformArgs):
    command: str = ""


@attrs.define(slots=False, kw_only=True)
class ApplyThemeBody(Body, ApplyThemeArgs):
    command: str = ""


@store.command
class ControlCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.control_put, "/v2/control", methods=["PUT"], name="v2_control_put")

        for name, route in kls.known_routes.items():
            routes.http(
                route,
                f"/v2/control/{name}/<selector>",
                methods=["PUT"],
                name=f"v2_control_{name}_put",
            )

    async def control_query(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: PacketBody,
        _params: Params,
    ) -> commander.Response:
        """
        Send a pkt to devices and return the result
        """
        _params = _params.update_from_put_body(_body)
        devices = self.create(
            DeviceFinder, {"selector": _body.selector, "timeout": _params.timeout}
        )
        msg = ihp.make_message(_body.pkt_type.value, _body.pkt_args)
        return sanic.json((await devices.send(msg)).as_dict())

    async def control_set(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: PacketBody,
        _params: Params,
    ) -> commander.Response:
        """
        Send a pkt to devices. This is the same as query except res_required is False
        and results aren't returned
        """
        _params = _params.update_from_put_body(_body)
        devices = self.create(
            DeviceFinder, {"selector": _body.selector, "timeout": _params.timeout}
        )
        msg = ihp.make_message(_body.pkt_type.value, _body.pkt_args)
        msg.res_required = False
        return sanic.json((await devices.send(msg)).as_dict())

    async def control_power_toggle(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: PowerToggleBody,
        _params: Params,
    ) -> commander.Response:
        """
        Toggle the power of the lights you specify
        """
        _params = _params.update_from_put_body(_body)
        devices = self.create(
            DeviceFinder, {"selector": _body.selector, "timeout": _params.timeout}
        )
        kwargs = {"duration": _body.duration, "group": _body.group}
        msg = PowerToggle(**kwargs)
        return sanic.json((await devices.send(msg, add_replies=False)).as_dict())

    async def control_transform(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: TransformBody,
        _params: Params,
    ) -> commander.Response:
        """
        Apply a http api like transformation to the lights
        """
        _params = _params.update_from_put_body(_body)
        devices = self.create(
            DeviceFinder, {"selector": _body.selector, "timeout": _params.timeout}
        )
        msg = Transformer.using(_body.transform, **_body.transform_options)
        return sanic.json((await devices.send(msg, add_replies=False)).as_dict())

    async def control_apply_theme(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: ApplyThemeBody,
        _params: Params,
    ) -> commander.Response:
        """
        Apply a selection of colours to your devices

        All ``theme_options`` are optional and include:

        colors - A list of colours
            Colors may be words like "red", "blue", etc. Or may be [h, s, b, k] arrays
            where each part is optional.

        duration - a float
            How long in seconds to take to apply the theme

        overrides - dictionary of hue, saturation, brightness and kelvin
            This will override all colours used when applying the theme
        """
        _params = _params.update_from_put_body(_body)
        devices = self.create(
            DeviceFinder, {"selector": _body.selector, "timeout": _params.timeout}
        )
        return sanic.json(
            (await devices.send(ApplyTheme.msg(_body.theme_options), add_replies=False)).as_dict()
        )

    known_routes = {
        "query": control_query,
        "set": control_set,
        "power_toggle": control_power_toggle,
        "transform": control_transform,
        "apply_theme": control_apply_theme,
    }

    async def control_put(
        self, progress: commander.Progress, request: commander.Request, /, _body: Body, store: Store
    ) -> commander.Response | None:
        route = self.known_routes.get(command := _body.command)

        if route is None:
            raise sanic.BadRequest(
                message=f"Unknown command '{command}', available: {sorted(self.known_routes)}"
            )

        use = store.determine_http_args_and_kwargs(self.meta, route, progress, request, [], {})
        return await getattr(self, route.__name__)(*use)

    implements_v1_commands: ClassVar[set[str]] = {
        "query",
        "set",
        "power_toggle",
        "transform",
        "apply_theme",
    }

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None

        doc = cls.known_routes[command].__doc__
        if command in ("query", "set"):
            body_kls = V1Packet
        elif command == "power_toggle":
            body_kls = V1PowerToggle
        elif command == "transform":
            body_kls = V1Transform
        elif command == "apply_theme":
            body_kls = V1ApplyTheme
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
        if command in ("query", "set"):
            v1body = self.create(V1Packet, args)
            match = self.create(selector.Selector, v1body.matcher.raw)
            _params = Params(timeout=v1body.timeout.value).update_from_put_body(v1body)
            body = self.create(
                PacketBody,
                {
                    **{f.name: getattr(v1body, f.name) for f in attrs.fields(v1body.__class__)},
                    "timeout": v1body.timeout.value,
                    "selector": match,
                },
            )
            if command == "query":
                return await self.control_query(progress, request, _body=body, _params=_params)
            else:
                return await self.control_set(progress, request, _body=body, _params=_params)

        elif command == "power_toggle":
            v1body = self.create(V1PowerToggle, args)
            match = self.create(selector.Selector, v1body.matcher.raw)
            _params = Params(timeout=v1body.timeout.value).update_from_put_body(v1body)
            body = self.create(
                PowerToggleBody,
                {
                    **{f.name: getattr(v1body, f.name) for f in attrs.fields(v1body.__class__)},
                    "timeout": v1body.timeout.value,
                    "selector": match,
                },
            )
            return await self.control_power_toggle(progress, request, _body=body, _params=_params)

        elif command == "transform":
            v1body = self.create(V1Transform, args)
            match = self.create(selector.Selector, v1body.matcher.raw)
            _params = Params(timeout=v1body.timeout.value).update_from_put_body(v1body)
            body = self.create(
                TransformBody,
                {
                    **{f.name: getattr(v1body, f.name) for f in attrs.fields(v1body.__class__)},
                    "timeout": v1body.timeout.value,
                    "selector": match,
                },
            )
            return await self.control_transform(progress, request, _body=body, _params=_params)

        elif command == "apply_theme":
            v1body = self.create(V1ApplyTheme, args)
            match = self.create(selector.Selector, v1body.matcher.raw)
            _params = Params(timeout=v1body.timeout.value).update_from_put_body(v1body)
            body = self.create(
                ApplyThemeBody,
                {
                    **{f.name: getattr(v1body, f.name) for f in attrs.fields(v1body.__class__)},
                    "timeout": v1body.timeout.value,
                    "selector": match,
                },
            )
            return await self.control_apply_theme(progress, request, _body=body, _params=_params)
