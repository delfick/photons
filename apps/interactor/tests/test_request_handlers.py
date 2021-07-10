# coding: spec

from interactor.request_handlers import WSHandler
from interactor.commander import helpers as ihp
from interactor.server import Server

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from unittest import mock
import pytest
import types
import uuid


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
            original_tornado_routes = Server.tornado_routes

            def tornado_routes(s):
                routes = original_tornado_routes(s)
                routes[1] = ("/v1/ws", self.Handler, routes[1][-1])
                return routes

            self.patch = mock.patch.object(Server, "tornado_routes", tornado_routes)
            self.patch.start()

            self.wrapper = server_wrapper(None, sender, final_future)
            await self.wrapper.start()
            return self.wrapper

        async def finish(self, exc_typ=None, exc=None, tb=None):
            if hasattr(self, "wrapper"):
                await self.wrapper.finish()
            if hasattr(self, "patch"):
                self.patch.stop()

    return Maker


describe "SimpleWebSocketBase":
    async it "can handle a ResultBuilder", server_maker:

        class Handler(WSHandler):
            async def process_message(s, path, body, message_id, message_key, progress_cb):
                return ihp.ResultBuilder(serials=["d073d5000001"])

        async with server_maker(Handler) as server:
            connection = await server.ws_connect()

            msg_id = str(uuid.uuid1())
            await server.ws_write(connection, {"path": "/thing", "body": {}, "message_id": msg_id})
            assert await server.ws_read(connection) == {
                "message_id": msg_id,
                "reply": {"results": {"d073d5000001": "ok"}},
            }

    async it "can process replies", server_maker:
        replies = []

        error1 = ValueError("Bad things happen")
        error2 = PhotonsAppError("Stuff")
        error3 = TypeError("NOPE")
        error4 = PhotonsAppError("Blah")
        error5 = PhotonsAppError("things", serial="d073d5000001")

        class Handler(WSHandler):
            def process_reply(s, msg, exc_info=None):
                replies.append((msg, exc_info))

            async def process_message(s, path, body, message_id, message_key, progress_cb):
                if path == "/no_error":
                    return {"success": True}
                elif path == "/internal_error":
                    raise error1
                elif path == "/builder_error":
                    builder = ihp.ResultBuilder(["d073d5000001"])
                    builder.error(error2)
                    s.reply({"progress": {"error": "progress"}}, message_id=message_id)
                    return builder
                elif path == "/builder_serial_error":
                    builder = ihp.ResultBuilder(["d073d5000001"])
                    try:
                        raise error5
                    except Exception as e:
                        builder.error(e)
                    return builder
                elif path == "/builder_internal_error":
                    builder = ihp.ResultBuilder(["d073d5000001"])
                    try:
                        raise error3
                    except Exception as error:
                        builder.error(error)
                    return builder
                elif path == "/error":
                    raise error4

        async with server_maker(Handler) as server:
            connection = await server.ws_connect()

            ##################
            ### NO_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection, {"path": "/no_error", "body": {}, "message_id": msg_id}
            )
            assert await server.ws_read(connection) == {
                "message_id": msg_id,
                "reply": {"success": True},
            }

            ##################
            ### INTERNAL_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection, {"path": "/internal_error", "body": {}, "message_id": msg_id}
            )
            assert await server.ws_read(connection) == {
                "message_id": msg_id,
                "reply": {
                    "error": "Internal Server Error",
                    "error_code": "InternalServerError",
                    "status": 500,
                },
            }

            ##################
            ### BUILDER_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection, {"path": "/builder_error", "body": {}, "message_id": msg_id}
            )
            assert await server.ws_read(connection) == {
                "message_id": msg_id,
                "reply": {"progress": {"error": "progress"}},
            }

            assert await server.ws_read(connection) == {
                "message_id": msg_id,
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
            ### BUILDER_SERIAL_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection, {"path": "/builder_serial_error", "body": {}, "message_id": msg_id}
            )

            assert await server.ws_read(connection) == {
                "message_id": msg_id,
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
            ### BUILDER_INTERNAL_ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection,
                {"path": "/builder_internal_error", "body": {}, "message_id": msg_id},
            )
            assert await server.ws_read(connection) == {
                "message_id": msg_id,
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
            ### ERROR

            msg_id = str(uuid.uuid1())
            await server.ws_write(connection, {"path": "/error", "body": {}, "message_id": msg_id})
            assert await server.ws_read(connection) == {
                "message_id": msg_id,
                "reply": {
                    "error": {"message": "Blah"},
                    "error_code": "PhotonsAppError",
                    "status": 400,
                },
            }

        class ATraceback:
            def __eq__(s, other):
                return isinstance(other, types.TracebackType)

        want = [
            ({"success": True}, None),
            (
                {
                    "status": 500,
                    "error": "Internal Server Error",
                    "error_code": "InternalServerError",
                },
                (ValueError, error1, ATraceback()),
            ),
            ({"progress": {"error": "progress"}}, None),
            (
                {
                    "results": {"d073d5000001": "ok"},
                    "errors": [
                        {
                            "error": {"message": "Stuff"},
                            "error_code": "PhotonsAppError",
                            "status": 400,
                        }
                    ],
                },
                None,
            ),
            (
                {
                    "results": {
                        "d073d5000001": {
                            "error": {"message": "things"},
                            "error_code": "PhotonsAppError",
                            "status": 400,
                        }
                    }
                },
                None,
            ),
            (
                {
                    "results": {"d073d5000001": "ok"},
                    "errors": [
                        {
                            "error": "Internal Server Error",
                            "error_code": "InternalServerError",
                            "status": 500,
                        }
                    ],
                },
                None,
            ),
            (
                {"error": {"message": "Blah"}, "error_code": "PhotonsAppError", "status": 400},
                (PhotonsAppError, error4, ATraceback()),
            ),
        ]

        for i, (g, w) in enumerate(zip(replies, want)):
            if g != w:
                print(f"Incorrect reply: {i}")
                print(f"GOT : {g}")
                print(f"WANT: {w}")

        assert replies == want
