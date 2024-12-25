import asyncio
from textwrap import dedent
from typing import ClassVar

import attrs
import pytest
import sanic
import strcs
from interactor.commander import helpers as ihp
from interactor.commander.commands.help import HelpCommands
from interactor.commander.commands.legacy import LegacyCommands
from interactor.commander.store import Command, Store, _WithV1Http, reg
from photons_transport.comms.base import Communication
from photons_web_server import commander

store2 = Store(strcs_register=reg)


@attrs.define
class WithSerial:
    serial: str


@attrs.define
class V1Body:
    command: str
    args: dict[str, object]


@attrs.define(kw_only=True)
class Body:
    one: int = 20

    two: str

    three: bool = True

    class Docs:
        one: str = """
        one is the first number

        it is the best number
        """

        two: str = """
        two is the second best number
        """


@store2.command
class Commands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.test, "/v2/test", methods=["PUT"], name="test")

    async def test(
        self, progress: commander.Progress, request: commander.Request, /, _body: Body
    ) -> commander.Response:
        """
        A test command to test help output
        """
        return sanic.json(attrs.asdict(_body))

    known_routes = {"test": test}

    implements_v1_commands: ClassVar[set[str]] = {"test"}

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None

        return ihp.v1_help_text_from_body(
            doc=cls.test.__doc__, body_typ=strcs.Type.create(Body, cache=type_cache)
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
            body = self.create(Body, args)
            return await self.test(progress, request, _body=body)


store2.command(LegacyCommands)
store2.command(HelpCommands)


@pytest.fixture()
async def server2(server_wrapper, final_future: asyncio.Future, sender: Communication):
    async with server_wrapper(store2, sender, final_future) as server:
        yield server


class TestCommands:
    class TestV1:
        async def test_it_has_a_help_command(self, server2):
            want = dedent(
                """
            Command test
            ============

            A test command to test help output

            Arguments
            ---------

            one: int (default 20)
                one is the first number

                it is the best number

            two: str (required)
                two is the second best number
            """
            ).lstrip()

            await server2.assertCommand(
                "/v1/lifx/command",
                {"command": "help", "args": {"command": "test"}},
                text_output=want,
            )

        async def test_it_works_for_all_commands_as_200(self, server):
            available: set[str] = set()
            for cmd in server.server.store.commands:
                if isinstance(cmd, _WithV1Http):
                    available |= cmd.implements_v1_commands

            for command in sorted(available):
                await server.assertCommand(
                    "/v1/lifx/command", {"command": "help", "args": {"command": command}}
                )
