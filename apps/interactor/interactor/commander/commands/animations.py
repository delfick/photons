import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated, ClassVar

import attrs
import sanic
import strcs
from delfick_project.norms import sb
from interactor.commander import helpers as ihp
from interactor.commander import selector
from interactor.commander.animations import Animations
from interactor.commander.devices import DeviceFinder
from interactor.commander.store import Command, Store, reg, store
from photons_web_server import commander


@attrs.define
class WithCommand:
    command: str


def make_str_or_list(value: object, /) -> strcs.ConvertResponse[list[str]]:
    if value is strcs.NotSpecified:
        return []
    elif isinstance(value, str):
        return [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    else:
        return None


@attrs.define
class V1AnimationBodyNotStart:
    animation_name: str | None = None

    identity: str | None = None

    pause: Annotated[list[str], strcs.Ann(creator=make_str_or_list)] = attrs.field(factory=list)

    resume: Annotated[list[str], strcs.Ann(creator=make_str_or_list)] = attrs.field(factory=list)

    stop: Annotated[list[str], strcs.Ann(creator=make_str_or_list)] = attrs.field(factory=list)

    class Docs:
        animation_name: str = """Optionally the specific name of an animation to get help about"""

        identity: str = """optional identity of a specific animation you want info for"""

        pause: str = """The animation identities to pause"""

        resume: str = """The animation identities to resume"""

        stop: str = """The animation identities to stop"""


@attrs.define(slots=False, kw_only=True)
class AnimationStartBody:
    animations: object | None = None

    run_options: dict[str, object] | None = None

    identity: str | None = None

    class Docs:
        animations: str = """The animations options!"""

        run_options: str = """The options for animations in general"""

        identity: str = """Optional identity for the animation"""


class TimeoutParams:
    timeout: int = -1


@attrs.define(slots=False, kw_only=True)
class V2AnimationStartBody(AnimationStartBody):
    selector: selector.Selector
    timeout: int = -1


@attrs.define(slots=False, kw_only=True)
class V1AnimationStartBody(AnimationStartBody):
    matcher: selector.Matcher
    timeout: selector.Timeout = attrs.field(default=20)


@attrs.define
class AnimationHelpBody:
    animation_name: str | None = None

    class Docs:
        animation_name: str = """Optionally the specific name of an animation to get help about"""


@attrs.define
class AnimationHelpParams:
    animation_name: str | None = None

    class Docs:
        animation_name: str = """Optionally the specific name of an animation to get help about"""


@attrs.define
class AnimationIdentitiesBody:
    identities: list[str] = attrs.field(factory=list)

    collapse_on_one: bool = True

    class Docs:
        identities: str = """List of identities to operate on"""

        collapse_on_one: str = """
        Whether to turn the result into a dictionary if only one identity is provided
        """


@attrs.define
class AnimationIdentitiesParams:
    identities: list[str] = attrs.field(factory=list)

    collapse_on_one: bool = True

    class Docs:
        identities: str = """List of identities to operate on"""

        collapse_on_one: str = """
        Whether to turn the result into a dictionary if only one identity is provided
        """


@store.command
class AnimationCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.animation_put, "/v2/animation", name="v2_animation_put")

        routes.http(
            kls.animation_help, "/v2/animation/help", methods=["GET"], name="v2_animation_help_get"
        )

        for name, route in kls.known_routes.items():
            routes.http(
                route,
                f"/v2/animation/{name}",
                methods=["PUT"],
                name=f"v2_animation_{name}",
            )

    async def animation_help(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        animations: Animations,
        _body: AnimationHelpBody,
        _params: AnimationHelpParams,
    ) -> commander.Response:
        """
        Return help information for animations
        """
        return sanic.json(await animations.help(_body.animation_name or _params.animation_name))

    async def animation_info(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        animations: Animations,
        _body: AnimationIdentitiesBody,
        _params: AnimationIdentitiesParams,
    ) -> commander.Response:
        """
        Return information about running animations
        """

        async def run(identities: list[str]) -> list[dict[str, object]] | dict[str, object]:
            if identities:
                return [animations.info(expand=True, identity=identity) for identity in identities]
            else:
                return animations.info(expand=True)

        def expand(obj: object) -> object:
            if hasattr(obj, "as_dict"):
                return expand(obj.as_dict())

            elif isinstance(obj, list | set):
                lresult: list[object] = []
                for item in obj:
                    lresult.append(expand(item))
                return lresult

            elif isinstance(obj, dict):
                dresult: dict[str, object] = {}
                for k, v in obj.items():
                    dresult[k] = expand(v)
                return dresult
            elif isinstance(obj, int | float | str | bool):
                return obj
            else:
                return repr(obj)

        return sanic.json(expand(await self._run_across_identities(_body, _params, run)))

    async def animation_start(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        animations: Animations,
        _body: V2AnimationStartBody,
        _params: TimeoutParams,
    ) -> commander.Response:
        """
        Start an animation

        For example::

            PUT /v1/lifx/command {
              "command": "animation/start",
              "args": {
                "matcher": {"label": "wall"},
                "animations": [["balls", {"num_seconds": 5}], "dice"],
                "run_options": {"reinstate_on_end": true, "animation_limit": 3}
              }
            }

            PUT /v2/animation/start {
              "selector": {"label": "wall"},
              "animations": [["balls", {"num_seconds": 5}], "dice"],
              "run_options": {"reinstate_on_end": true, "animation_limit": 3}
            }
        """
        identity = _body.identity
        if identity is None:
            identity = secrets.token_urlsafe(6)

        device_finder = self.create(
            DeviceFinder, {"selector": _body.selector, "timeout": _params.timeout}
        )

        return sanic.json(
            await animations.start(
                identity,
                await device_finder.device_finder,
                run_options=_body.run_options,
                animations=_body.animations or sb.NotSpecified,
            )
        )

    async def animation_pause(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        animations: Animations,
        _body: AnimationIdentitiesBody,
        _params: AnimationIdentitiesParams,
    ) -> commander.Response:
        """
        Pause an animation
        """

        async def run(identities: list[str]) -> list[dict[str, object]]:
            return await animations.pause(*identities)

        return sanic.json(await self._run_across_identities(_body, _params, run))

    async def animation_resume(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        animations: Animations,
        _body: AnimationIdentitiesBody,
        _params: AnimationIdentitiesParams,
    ) -> commander.Response:
        """
        Resume an animation
        """

        async def run(identities: list[str]) -> list[dict[str, object]]:
            return await animations.resume(*identities)

        return sanic.json(await self._run_across_identities(_body, _params, run))

    async def animation_stop(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        animations: Animations,
        _body: AnimationIdentitiesBody,
        _params: AnimationIdentitiesParams,
    ) -> commander.Response:
        """
        Stop an animation
        """

        async def run(identities: list[str]) -> list[dict[str, object]]:
            return await animations.stop(*identities)

        return sanic.json(await self._run_across_identities(_body, _params, run))

    known_routes = {
        "help": animation_help,
        "info": animation_info,
        "start": animation_start,
        "pause": animation_pause,
        "resume": animation_resume,
        "stop": animation_stop,
    }

    async def animation_put(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: WithCommand,
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

        use = store.determine_http_args_and_kwargs(self.meta, route, progress, request, [], {})
        return await getattr(self, route.__name__)(*use)

    implements_v1_commands: ClassVar[set[str]] = {
        "animation/help",
        "animation/info",
        "animation/start",
        "animation/pause",
        "animation/resume",
        "animation/stop",
    }

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None

        doc = cls.known_routes[command.split("/")[1]].__doc__
        if command == "animation/start":
            return ihp.v1_help_text_from_body(
                doc=doc,
                body_typ=strcs.Type.create(V1AnimationStartBody, cache=type_cache),
            )
        else:
            return ihp.v1_help_text_from_body(
                doc=doc,
                body_typ=strcs.Type.create(V1AnimationBodyNotStart, cache=type_cache),
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
            if command == "animation/start":
                v1body = self.create(V1AnimationStartBody, args)
                body_raw = dict(args)
                body_raw["selector"] = self.create(selector.Selector, v1body.matcher.raw)
                body_raw["timeout"] = v1body.timeout.value
            else:
                v1body = self.create(V1AnimationBodyNotStart, args)
                body_raw = dict(args)
                if command == "animation/info":
                    body_raw["identities"] = (
                        [v1body.identity] if v1body.identity is not None else []
                    )
                elif command == "animation/pause":
                    body_raw["identities"] = v1body.pause
                elif command == "animation/resume":
                    body_raw["identities"] = v1body.resume
                elif command == "animation/stop":
                    body_raw["identities"] = v1body.stop

            store = meta.retrieve_one(Store, "store", type_cache=reg.type_cache)
            route = self.known_routes[command.split("/")[1]]
            use = store.determine_http_args_and_kwargs(
                self.meta, route, progress, request, [], {"_body_raw": body_raw}
            )
            return await getattr(self, route.__name__)(*use)

    async def _run_across_identities(
        self,
        body: AnimationIdentitiesBody,
        params: AnimationIdentitiesParams,
        run: Callable[[list[str]], Awaitable[list[dict[str, object]] | dict[str, object]]],
    ) -> list[dict[str, object]] | dict[str, object]:
        identities = sorted(set(params.identities) | set(body.identities))
        collapse_on_one = params.collapse_on_one or body.collapse_on_one
        info = await run(identities)
        if len(identities) == 1 and collapse_on_one and isinstance(info, list):
            return info[0]
        else:
            return info
