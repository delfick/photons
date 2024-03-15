from typing import ClassVar

import attrs
import sanic
import strcs
from interactor.commander import helpers as ihp
from interactor.commander.errors import NoSuchCommand
from interactor.commander.store import Command, Store, _WithV1Http, reg, store
from photons_web_server import commander


@attrs.define
class HelpBody:
    command: str = "help"

    class Docs:
        command: str = """The command to show help for"""


@attrs.define
class HelpParams:
    command: str = "help"

    class Docs:
        command: str = """The command to show help for"""


@store.command
class HelpCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.help, "/v2/help", name="v2_help_get")

    async def help(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: HelpBody,
        _params: HelpParams,
        store: Store,
        version: str = "v2",
    ) -> commander.Response:
        """
        Display the documentation for the specified command
        """
        if version == "v2":
            return sanic.text("v2 commands aren't complete yet")

        command = _params.command
        if _body.command != "help":
            command = _body.command

        return sanic.text(self._help_for(store, command))

    implements_v1_commands: ClassVar[set[str]] = {"help"}

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None

        return ihp.v1_help_text_from_body(
            doc=cls.help.__doc__, body_typ=strcs.Type.create(HelpBody, cache=type_cache)
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
            return await self.help(
                progress,
                request,
                _body=self.create(HelpBody, args),
                _params=HelpParams(),
                store=meta.retrieve_one(Store, "store", type_cache=reg.type_cache),
                version="v1",
            )

    def _help_for(self, store: Store, command: str) -> str:
        available_commands = set()
        command_klses: list[_WithV1Http] = []
        for cmd in store.commands:
            if isinstance(cmd, _WithV1Http):
                command_klses.append(cmd)
                available_commands = available_commands | cmd.implements_v1_commands

        help_txt: str | None = None
        for kls in command_klses:
            help_txt = kls.help_for_v1_command(command, store.strcs_register.type_cache)
            if help_txt is not None:
                break

        if help_txt is None:
            raise NoSuchCommand(wanted=command, available=sorted(available_commands))

        extra = ""
        if command == "help":
            names = "\n".join(f" * {name}" for name in available_commands)
            extra = f"\nAvailable commands:\n{names}"

        header = f"Command {command}"
        return f"{header}\n{'=' * len(header)}\n{help_txt}{extra}"
