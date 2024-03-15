from typing import ClassVar, Protocol, runtime_checkable

import attrs
import sanic
import strcs
from photons_web_server import commander

reg = strcs.CreateRegister()
creator = reg.make_decorator()


@attrs.define(kw_only=True)
class NoSuchPath(Exception):
    error: str = "Specified path is invalid"
    wanted: str
    available: list[str]


@attrs.define(kw_only=True)
class InvalidBody(Exception):
    error: str = "Body must be a dictionary with string command and dictionary args"
    command_type: str = ""
    args_type: str = ""
    body_type: str = ""


@attrs.define(kw_only=True)
class NoSuchCommand(Exception):
    error: str = "Specified command is unknown"
    wanted: str
    available: list[str]


@runtime_checkable
class _WithV1Http(Protocol):
    implements_v1_commands: ClassVar[set[str]]

    @classmethod
    def help_for_v1_command(cls, command: str) -> str | None: ...

    async def run_v1_http(
        self,
        *,
        command: str,
        args: dict[str, object],
        progress: commander.Progress,
        request: commander.Request,
    ) -> commander.Response | None: ...


class Store(commander.Store):
    async def run_v1_http(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _meta: strcs.Meta,
        command: str,
        args: dict[str, object],
        route_transformer: commander.RouteTransformer,
    ) -> commander.Response:
        for cmd in self.commands:
            if isinstance(cmd, _WithV1Http) and command in cmd.implements_v1_commands:
                with route_transformer.instantiate_route(request, cmd, cmd.run_v1_http) as route:
                    response = await route(
                        command=command,
                        args=args,
                        progress=progress,
                        request=request,
                        meta=_meta,
                    )
                if response is not None:
                    return response

        raise sanic.BadRequest(message=f"Unknown command '{command}'")

    async def run_v1_ws(
        self,
        wssend: commander.WSSender,
        message: commander.Message,
        /,
        _meta: strcs.Meta,
        route_transformer: commander.RouteTransformer,
    ) -> bool | None:
        path = message.body.get("path")
        if path != "/v1/lifx/command":
            await wssend(NoSuchPath(wanted=path, available=["/v1/lifx/command"]))
            return None

        body = message.body.get("body")
        if not isinstance(body, dict):
            await wssend(InvalidBody(body_type=repr(type(body))))
            return None

        command = body.get("command")
        args = body.get("args")
        if args is None:
            args = {}

        if not isinstance(command, str) or not isinstance(args, dict) or not command:
            await wssend(
                InvalidBody(
                    body_type=repr(type(body)),
                    command_type=repr(type(command)),
                    args_type=repr(type(args)),
                )
            )
            return None

        available_commands: set[str] = set()
        for cmd in self.commands:
            if isinstance(cmd, _WithV1Http):
                available_commands |= cmd.implements_v1_commands
                if command in cmd.implements_v1_commands:
                    with route_transformer.instantiate_route(
                        message.request, cmd, cmd.run_v1_http
                    ) as route:
                        response = await route(
                            command=command,
                            args=args,
                            progress=wssend.progress,
                            request=message.request,
                            meta=_meta,
                        )
                        await wssend(response.raw_body)
                        return None

        await wssend(NoSuchCommand(wanted=command, available=sorted(available_commands)))


store = Store(strcs_register=reg)

Command = commander.Command


def load_commands():
    __import__("interactor.commander.commands")
