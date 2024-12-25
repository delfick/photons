import asyncio
import random

import attrs
import pytest
import sanic
from interactor.commander.store import Command, Store, reg
from interactor.errors import InteractorError
from photons_transport.comms.base import Communication
from photons_web_server import commander

store = Store(strcs_register=reg)


@attrs.define
class WithSerial:
    serial: str


@attrs.define
class V1Body:
    command: str
    args: dict[str, object]


@pytest.fixture()
async def server(server_wrapper, final_future: asyncio.Future, sender: Communication):
    async with server_wrapper(store, sender, final_future) as server:
        yield server


@store.command
class Commands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.commands, "/v1/lifx/command", methods=["PUT"], name="commands")
        routes.ws(kls.commands_ws, "/v1/ws", name="websocket")

    async def commands_ws(
        self,
        respond: commander.Responder,
        message: commander.Message,
    ) -> bool | None:
        _body = self.create(V1Body, message.body["body"])
        route_transformer = self.meta.retrieve_one(
            commander.RouteTransformer, "route_transformer", type_cache=reg.type_cache
        )
        store = self.meta.retrieve_one(Store, "store", type_cache=reg.type_cache)
        result = await self.commands(
            respond.progress,
            message.request,
            _body=_body,
            route_transformer=route_transformer,
            store=store,
        )
        await respond(result.raw_body)
        return None

    async def commands(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: V1Body,
        route_transformer: commander.RouteTransformer,
        store: Store,
    ) -> commander.Response:
        assert _body.command in self.known_routes
        with route_transformer.instantiate_route(
            request, self.__class__, route := self.known_routes[_body.command]
        ) as route:
            use = store.determine_http_args_and_kwargs(
                self.meta, route, progress, request, [], {"_body_raw": _body.args}
            )
            return await route(*use)

    async def test_done_progress(
        self, progress: commander.Progress, request: commander.Request, /, _body: WithSerial
    ) -> commander.Response:
        await progress(None, serial=_body.serial)
        return sanic.json({"serial": _body.serial})

    async def test_no_error(
        self, progress: commander.Progress, request: commander.Request, /, _body: WithSerial
    ) -> commander.Response:
        await progress("hello", serial=_body.serial)
        await progress("there")
        return sanic.json({"serial": _body.serial})

    async def test_error(
        self, progress: commander.Progress, request: commander.Request, /, _body: WithSerial
    ) -> commander.Response:
        await progress(Exception("Nope"), serial=_body.serial)
        await progress(ValueError("Yeap"))

        class Problem(InteractorError):
            desc = "a problem"

        await progress(Problem("wat", one=1), serial=_body.serial)
        return sanic.json({"serial": _body.serial})

    known_routes = {
        "test_done_progress": test_done_progress,
        "test_no_error": test_no_error,
        "test_error": test_error,
    }


class TestCommands:

    def command(self, command):
        serial = "d073d5{:06d}".format(random.randrange(1, 9999))
        cmd = {"command": command, "args": {"serial": serial}}
        return cmd, serial

    async def test_it_has_progress_cb_functionality_for_http(self, server):
        command, serial = self.command("test_no_error")
        await server.assertCommand(
            "/v1/lifx/command", command, status=200, json_output={"serial": serial}
        )

        command, serial = self.command("test_error")
        await server.assertCommand(
            "/v1/lifx/command", command, status=200, json_output={"serial": serial}
        )

        command, serial = self.command("test_done_progress")
        await server.assertCommand(
            "/v1/lifx/command", command, status=200, json_output={"serial": serial}
        )

    async def test_it_has_progress_cb_functionality_for_websockets(self, server):
        async with server.ws_stream() as stream:

            # Done progress
            command, serial = self.command("test_done_progress")
            await stream.create("/v1/lifx/command", command)
            await stream.check_reply({"progress": {"done": True, "serial": serial}})
            await stream.check_reply({"serial": serial})

            # No error
            command, serial = self.command("test_no_error")
            await stream.create("/v1/lifx/command", command)
            await stream.check_reply({"progress": {"info": "hello", "serial": serial}})
            await stream.check_reply({"progress": {"info": "there"}})
            await stream.check_reply({"serial": serial})

            # With error
            command, serial = self.command("test_error")
            await stream.create("/v1/lifx/command", command)
            await stream.check_reply(
                {"progress": {"error": "Nope", "error_code": "Exception", "serial": serial}}
            )
            await stream.check_reply({"progress": {"error": "Yeap", "error_code": "ValueError"}})
            await stream.check_reply(
                {
                    "progress": {
                        "error": {"message": "a problem. wat", "one": 1},
                        "error_code": "Problem",
                        "serial": serial,
                    }
                }
            )
            await stream.check_reply({"serial": serial})
