# coding: spec

from textwrap import dedent
from unittest import mock

import pytest
from delfick_project.norms import dictobj, sb
from interactor.commander.store import load_commands, store
from photons_app import helpers as hp


@pytest.fixture(autouse=True)
def TCommand(store_clone):
    @store_clone.command("test")
    class TCommand(store_clone.Command):
        """
        A test command to test help output
        """

        one = dictobj.Field(
            sb.integer_spec,
            default=20,
            help="""
                one is the first number

                it is the best number
            """,
        )

        two = dictobj.Field(
            sb.string_spec, wrapper=sb.required, help="two is the second best number"
        )

        three = dictobj.Field(sb.boolean, default=True)

        async def execute(self):
            return self.as_dict()

    return TCommand


@pytest.fixture()
def store_clone():
    load_commands()
    return store.clone()


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


@pytest.fixture()
async def sender(devices, final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture()
async def server(store_clone, server_wrapper, sender, final_future, FakeTime, MockedCallLater):
    with FakeTime() as t:
        async with MockedCallLater(t):
            async with server_wrapper(store_clone, sender, final_future) as server:
                yield server


describe "commands":
    async it "has a help command", server:
        want = dedent(
            """
        Command test
        ============

        A test command to test help output

        Arguments
        ---------

        one: integer (default 20)
        \tone is the first number

        \tit is the best number

        two: string (required)
        \ttwo is the second best number
        """
        ).lstrip()

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "help", "args": {"command": "test"}},
            text_output=want.encode(),
        )

    async it "has a test command", server:
        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "test"},
            status=400,
            json_output={
                "error": {
                    "errors": [
                        {
                            "message": "Bad value. Expected a value but got none",
                            "meta": "{path=body.args.two}",
                        }
                    ],
                    "message": "Bad value",
                    "meta": "{path=body.args}",
                },
                "error_code": "BadSpecValue",
                "status": 400,
            },
        )

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "test", "args": {"one": 1, "two": "TWO", "three": True}},
            json_output={"one": 1, "two": "TWO", "three": True},
        )

    async it "has websocket commands", server, responses:
        async with server.ws_stream() as stream:
            # Invalid path
            await stream.create("/blah", {"stuff": True})
            error = "Specified path is invalid"
            await stream.check_reply(
                {
                    "error": error,
                    "wanted": "/blah",
                    "available": ["/v1/lifx/command"],
                    "status": 404,
                }
            )

            # invalid command
            await stream.create("/v1/lifx/command", {"command": "nope"})
            reply = await stream.check_reply(mock.ANY)
            assert "test" in reply["error"]["available"]
            reply["error"]["available"] = ["test"]

            assert reply == {
                "error": {
                    "message": "Bad value. Unknown command",
                    "wanted": "nope",
                    "meta": "{path=body.command}",
                    "available": ["test"],
                },
                "error_code": "BadSpecValue",
                "status": 400,
            }

            # valid command
            args = {"one": 1, "two": "TWO", "three": True}
            await stream.create("/v1/lifx/command", {"command": "test", "args": args})
            await stream.check_reply(args)

            # another valid command
            await stream.create(
                "/v1/lifx/command",
                {"command": "query", "args": {"pkt_type": 101}},
            )
            await stream.check_reply(responses.light_state_responses)
