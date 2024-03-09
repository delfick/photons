import uuid

import pytest
from interactor.commander import helpers as ihp
from interactor.server import Server
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_web_server.commander import Message, WSSender


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
def server_maker(server_wrapper, final_future, sender):
    class Maker(hp.AsyncCMMixin):
        def __init__(self, Handler):
            self.Handler = Handler

        async def start(self):
            class ModifiedServer(Server):
                async def setup_routes(ss):
                    await super(Server, ss).setup_routes()
                    ss.app.add_websocket_route(ss.wrap_websocket_handler(self.Handler), "/v1/ws")

            self.wrapper = server_wrapper(
                None,
                sender,
                final_future,
                ServerKls=ModifiedServer,
            )

            await self.wrapper.start()
            return self.wrapper

        async def finish(self, exc_typ=None, exc=None, tb=None):
            if hasattr(self, "wrapper"):
                await self.wrapper.finish()

    return Maker


class TestSimpleWebSocketBase:
    async def test_it_can_handle_a_ResultBuilder(self, server_maker):
        async def Handler(wssend: WSSender, message: Message) -> bool | None:
            await wssend(ihp.ResultBuilder(serials=["d073d5000001"]))
            return None

        async with server_maker(Handler) as server:
            connection = await server.ws_connect()

            msg_id = str(uuid.uuid1())
            await server.ws_write(connection, {"path": "/thing", "body": {}, "message_id": msg_id})
            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "reply": {"results": {"d073d5000001": "ok"}},
            }

    async def test_it_can_process_replies(self, server_maker):
        error1 = ValueError("Bad things happen")
        error2 = PhotonsAppError("Stuff")
        error3 = TypeError("NOPE")
        error4 = PhotonsAppError("Blah")
        error5 = PhotonsAppError("things", serial="d073d5000001")

        async def Handler(wssend: WSSender, message: Message) -> bool | None:
            path = message.body["path"]
            if path == "/no_error":
                await wssend({"success": True})
            elif path == "/internal_error":
                raise error1
            elif path == "/builder_error":
                builder = ihp.ResultBuilder(["d073d5000001"])
                builder.error(error2)
                await wssend.progress({"error": "progress"})
                await wssend(builder)
            elif path == "/builder_serial_error":
                builder = ihp.ResultBuilder(["d073d5000001"])
                try:
                    raise error5
                except Exception as e:
                    builder.error(e)
                await wssend(builder)
            elif path == "/builder_internal_error":
                builder = ihp.ResultBuilder(["d073d5000001"])
                try:
                    raise error3
                except Exception as error:
                    builder.error(error)
                await wssend(builder)
            elif path == "/error":
                await wssend(error4)

            return None

        async with server_maker(Handler) as server:
            connection = await server.ws_connect()

            ##################
            # NO_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection, {"path": "/no_error", "body": {}, "message_id": msg_id}
            )
            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "reply": {"success": True},
            }

            ##################
            # INTERNAL_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection, {"path": "/internal_error", "body": {}, "message_id": msg_id}
            )
            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "error": "Internal Server Error",
                "error_code": "InternalServerError",
            }

            ##################
            # BUILDER_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection, {"path": "/builder_error", "body": {}, "message_id": msg_id}
            )
            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "progress": {"error": "progress"},
            }

            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "reply": {
                    "results": {"d073d5000001": "ok"},
                    "errors": [
                        {
                            "error": {"message": "Stuff"},
                            "error_code": "PhotonsAppError",
                            "status": 400,
                        }
                    ],
                },
            }

            ##################
            # BUILDER_SERIAL_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection, {"path": "/builder_serial_error", "body": {}, "message_id": msg_id}
            )

            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "reply": {
                    "results": {
                        "d073d5000001": {
                            "error": {"message": "things"},
                            "error_code": "PhotonsAppError",
                            "status": 400,
                        }
                    }
                },
            }

            ##################
            # BUILDER_INTERNAL_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection,
                {"path": "/builder_internal_error", "body": {}, "message_id": msg_id},
            )
            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "reply": {
                    "results": {"d073d5000001": "ok"},
                    "errors": [
                        {
                            "error": "Internal Server Error",
                            "error_code": "InternalServerError",
                            "status": 500,
                        }
                    ],
                },
            }

            ##################
            # ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(connection, {"path": "/error", "body": {}, "message_id": msg_id})
            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "error": '"Blah"',
                "error_code": "PhotonsAppError",
            }
