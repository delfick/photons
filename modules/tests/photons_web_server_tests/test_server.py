# coding: spec

import asyncio
import json
import socket
import sys
import time
import types
import typing as tp
from contextlib import asynccontextmanager
from unittest import mock

import aiohttp
import pytest
import sanic
from alt_pytest_asyncio.plugin import OverrideLoop
from delfick_project.logging import LogContext
from photons_app import helpers as hp
from photons_app.collector import Collector
from photons_web_server import pytest_helpers as pws_thp
from photons_web_server.commander import (
    Command,
    Message,
    ProgressMessageMaker,
    WithCommanderClass,
)
from photons_web_server.commander.messages import ExcInfo, get_logger
from photons_web_server.commander.websocket_wrap import WSSender
from photons_web_server.server import Server, WebServerTask
from sanic import Sanic, Websocket
from sanic.config import Config
from sanic.request import Request
from sanic.response import BaseHTTPResponse as Response
from sanic.response import HTTPResponse


@asynccontextmanager
async def make_server(ServerKls: type[Server]):
    stop_future = hp.create_future(name="::make_server[stop_future]")
    final_future = hp.create_future(name="::make_server[final_future]")
    try:
        async with hp.TaskHolder(final_future, name="::make_server[ts]") as ts:
            yield ServerKls(ts, final_future, stop_future)
    finally:
        stop_future.cancel()
        final_future.cancel()


@pytest.fixture()
def collector():
    with OverrideLoop(new_loop=False):
        collector = Collector()
        collector.prepare(None, {})
        yield collector


@pytest.fixture()
def used_port():
    port = pytest.helpers.free_port()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.bind(("0.0.0.0", port))
        sock.listen(0)
        yield port
    finally:
        sock.close()


class IsTraceback:
    traceback: object | None

    def __init__(self):
        self.traceback = None

    def __eq__(self, other: object) -> bool:
        self.traceback = other
        return isinstance(self.traceback, types.TracebackType)

    def __repr__(self) -> str:
        if self.traceback is not None:
            return repr(self.traceback)
        else:
            return "<TRACEBACK>"


class Between:
    compare: object | None

    def __init__(self, frm: float, to: float):
        self.frm = frm
        self.to = to
        self.compare = None

    def __eq__(self, compare: object) -> bool:
        self.compare = compare
        if not isinstance(self.compare, float):
            return False
        return self.frm <= self.compare <= self.to

    def __repr__(self) -> str:
        if self.compare is None:
            return f"<Between {self.frm} and {self.to}/>"
        else:
            return repr(self.compare)


describe "Task":

    it "Runs the server", collector: Collector:

        called = []

        p = pytest.helpers.free_port()

        def stop(request: Request, /) -> HTTPResponse | None:
            task.photons_app.graceful_final_future.set_result(True)
            return sanic.text("stop")

        class S(Server):
            async def after_start(self) -> None:
                async with aiohttp.ClientSession() as session:
                    await session.put(f"http://127.0.0.1:{p}/stopme")

                called.append("ran")

            async def setup_routes(self):
                await super().setup_routes()
                self.app.add_route(stop, "stopme", methods=["PUT"])

        class T(WebServerTask):
            port = p
            ServerKls = S

        task = T.create(collector)
        hp.get_event_loop().call_later(5, task.photons_app.graceful_final_future.cancel)
        task.run_loop(collector=collector)
        assert called == ["ran"]

describe "Server":
    describe "The sanic app":
        async it "has config that we've provided":

            class MyConfig(Config):
                pass

            class MyServer(Server):
                Config = MyConfig

            async with make_server(MyServer) as server:
                assert isinstance(server.app.config, MyConfig)
                assert server.app.name == "photons_web_server"

        async it "has server name we've provided":

            class MyServer(Server):
                sanic_server_name = "my_server_is_better_than_yours"

            async with make_server(MyServer) as server:
                assert isinstance(server.app.config, Config)
                assert server.app.name == "my_server_is_better_than_yours"

    describe "lifecycle":
        it "has own lifecycle methods that use sanic life cycle methods", collector: Collector:
            called: list[object] = []
            calledlong = hp.create_future()
            p = pytest.helpers.free_port()

            server: Server | None = None
            lp: asyncio.AbstractEventLoop | None = None

            async def before_init(app: Sanic, loop: asyncio.AbstractEventLoop):
                called.append(("sanic_before_init", app, loop))

            async def after_init(app: Sanic, loop: asyncio.AbstractEventLoop):
                called.append(("sanic_after_init", app, loop))

            async def before_shutdown(app: Sanic, loop: asyncio.AbstractEventLoop):
                called.append(("sanic_before_shutdown", app, loop))

            async def after_shutdown(app: Sanic, loop: asyncio.AbstractEventLoop):
                called.append(("sanic_after_shutdown", app, loop))

            def stop(request: Request, /) -> HTTPResponse | None:
                called.append("stopcalled")
                task.photons_app.graceful_final_future.set_result(True)
                return sanic.text("stopped")

            async def long(request: Request, /) -> HTTPResponse | None:
                called.append("longreq")
                calledlong.cancel()
                try:
                    await asyncio.sleep(0.05)
                finally:
                    called.append(("longreqstopped", sys.exc_info()[0]))
                    return sanic.text("long")

            class S(Server):
                async def setup(self):
                    nonlocal lp, server
                    lp = hp.get_event_loop()
                    server = self

                    self.app.signal("server.init.before")(before_init)
                    self.app.signal("server.init.after")(after_init)
                    self.app.signal("server.shutdown.before")(before_shutdown)
                    self.app.signal("server.shutdown.after")(after_shutdown)

                async def before_start(self) -> None:
                    await super().before_start()
                    called.append("before_start")

                async def after_start(self) -> None:
                    await super().after_start()
                    called.append("after_start")

                    async def call(path):
                        async with aiohttp.ClientSession() as session:
                            await session.put(f"http://127.0.0.1:{p}/{path}")

                    self.tasks.add(call("long"))
                    await hp.wait_for_first_future(calledlong, name="S::after_start")
                    self.tasks.add(call("stopme"))

                async def before_stop(self) -> None:
                    await super().before_stop()
                    called.append("after_stop")

                async def after_stop(self) -> None:
                    await super().after_stop()
                    called.append("after_stop")

                async def setup_routes(self):
                    await super().setup_routes()
                    self.app.add_route(stop, "stopme", methods=["PUT"])
                    self.app.add_route(long, "long", methods=["PUT"])

            class T(WebServerTask):
                port = p
                ServerKls = S

            task = T.create(collector)
            hp.get_event_loop().call_later(5, task.photons_app.graceful_final_future.cancel)
            task.run_loop(collector=collector)

            assert server is not None

            assert called == [
                ("sanic_before_init", server.app, lp),
                "before_start",
                ("sanic_after_init", server.app, lp),
                "after_start",
                "longreq",
                "stopcalled",
                ("sanic_before_shutdown", server.app, lp),
                "after_stop",
                ("longreqstopped", None),
                ("sanic_after_shutdown", server.app, lp),
                "after_stop",
            ]

        it "fails if the server wants a port already in use", used_port: int, collector: Collector:

            def route(request: Request, /) -> HTTPResponse | None:
                return sanic.text("route")

            class S(Server):
                async def setup_routes(self):
                    await super().setup_routes()
                    self.app.add_route(route, "route", methods=["PUT"])

            class T(WebServerTask):
                port = used_port
                ServerKls = S

            task = T.create(collector)
            hp.get_event_loop().call_later(5, task.photons_app.graceful_final_future.cancel)

            with pytest.raises(OSError):
                task.run_loop(collector=collector)

        it "fails if the server can't be created", collector: Collector:
            p = pytest.helpers.free_port()

            class S(Server):
                async def setup_routes(self):
                    await super().setup_routes()
                    raise ValueError("nup")

            class T(WebServerTask):
                port = p
                ServerKls = S

            task = T.create(collector)
            hp.get_event_loop().call_later(5, task.photons_app.graceful_final_future.cancel)

            with pytest.raises(ValueError):
                task.run_loop(collector=collector)

    describe "stopping server":

        async it "waits for requests based on a default 15 second timeout from sanic", final_future: asyncio.Future, collector: Collector, fake_event_loop, fake_time:
            started = hp.create_future()
            startedws = hp.create_future()

            async def route(request: Request, /) -> HTTPResponse | None:
                started.set_result(True)
                await hp.create_future()
                return sanic.text("route")

            async def ws(request: Request, ws: Websocket):
                got = await ws.recv()
                assert got == "HI"
                await ws.send(json.dumps({"got": got}))
                startedws.set_result(True)
                await hp.create_future()

            async def setup_routes(server):
                server.app.add_route(route, "route", methods=["PUT"])
                server.app.add_websocket_route(ws, "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                req = srv.start_request("PUT", "/route")
                wsres: list[dict] = []

                async def run_stream():
                    async with srv.stream("/stream") as stream:
                        await stream.send("HI")
                        wsres.append(await stream.recv())
                        wsres.append(await stream.recv())

                wsreq = hp.get_event_loop().create_task(run_stream())

                await started
                await startedws
                assert time.time() < 0.3
                time_now = time.time()
                srv.stop()
                await hp.wait_for_all_futures(req, wsreq)
                assert time.time() == time_now + 15

            with pytest.raises(aiohttp.client_exceptions.ServerDisconnectedError):
                await req
            assert wsres == [{"got": "HI"}, None]

        async it "waits for requests based on sanic config GRACEFUL_SHUTDOWN_TIMEOUT", final_future: asyncio.Future, collector: Collector, fake_event_loop, fake_time:
            started = hp.create_future()

            async def route(request: Request, /) -> HTTPResponse | None:
                started.set_result(True)
                await hp.create_future()
                return sanic.text("route")

            async def setup_routes(server):
                server.app.add_route(route, "route", methods=["PUT"])

            class Config(Server.Config):
                GRACEFUL_SHUTDOWN_TIMEOUT = 7

            server_properties = {"Config": Config}

            async with pws_thp.WebServerRoutes(
                final_future, setup_routes, server_properties
            ) as srv:
                req = srv.start_request("PUT", "/route")
                await started
                assert time.time() < 0.3
                fake_time.set(0)
                srv.stop()
                await hp.wait_for_all_futures(req)
                assert time.time() == 7

            with pytest.raises(aiohttp.client_exceptions.ServerDisconnectedError):
                await req

    describe "logging":

        async it "records commands and responses", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            identifiers: set[str] = set()

            Ident1 = pws_thp.IdentifierMatch(identifiers)
            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM1 = pws_thp.IdentifierMatch(identifiers)

            async def route(request: Request, /) -> HTTPResponse | None:
                await asyncio.sleep(2)
                return sanic.text("route")

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                assert message.body == {"command": "two", "path": "/route"}
                await asyncio.sleep(6)
                await wssend({"got": "two"})
                return False

            async def setup_routes(server):
                server.app.add_route(route, "route", methods=["PUT"])
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                await srv.start_request("PUT", "/route", {"command": "one"})
                async with srv.stream("/stream") as stream:
                    await stream.send({"command": "two", "path": "/route"})
                    assert await stream.recv() == {
                        "reply": {"got": "two"},
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                    }
                srv.stop()

            records = [
                r.msg
                for r in caplog.records
                if isinstance(r.msg, dict)
                and any(m in r.msg["msg"] for m in ("Response", "Request"))
            ]

            assert records == [
                {
                    "msg": "Request",
                    "method": "PUT",
                    "uri": "/route",
                    "scheme": "http",
                    "remote_addr": "",
                    "request_identifier": Ident1,
                },
                {
                    "msg": "Response",
                    "method": "PUT",
                    "uri": "/route",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(1.0, 3.0),
                    "request_identifier": Ident1,
                },
                {
                    "msg": "Websocket Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "request_identifier": WSIdent1,
                    "body": {"command": "two", "path": "/route"},
                    "message_id": WSIdentM1,
                },
                {
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(5.0, 7.0),
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                },
            ]

            assert records[0]["request_identifier"] == records[1]["request_identifier"]
            assert all(
                r["request_identifier"] == records[-1]["request_identifier"] for r in records[2:]
            )

        async it "lets the handler hook into the logging", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            called: list[object] = []
            expected_called: list[object] = []

            identifiers: set[str] = set()

            Ident1 = pws_thp.IdentifierMatch(identifiers)
            Ident2 = pws_thp.IdentifierMatch(identifiers)
            Ident3 = pws_thp.IdentifierMatch(identifiers)
            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM1 = pws_thp.IdentifierMatch(identifiers)

            WSIdent2 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM2 = pws_thp.IdentifierMatch(identifiers)

            class C(Command):
                @classmethod
                def log_request(
                    kls,
                    lc: LogContext,
                    request: Request,
                    identifier: str,
                    dct: dict,
                    exc_info: ExcInfo = None,
                ):
                    assert identifier == lc.context["request_identifier"]
                    get_logger(1).info(lc("Test Request", dct=dct))

                @classmethod
                def log_response(
                    kls,
                    lc: LogContext,
                    request: Request,
                    response: Response,
                    identifier: str,
                    took: float,
                    exc_info: ExcInfo = None,
                ):
                    assert identifier == lc.context["request_identifier"]
                    get_logger(1).info(
                        lc(
                            "Test Response",
                            method=request.method,
                            uri=request.path,
                            status=response.status,
                            remote_addr=request.remote_addr,
                            took_seconds=took,
                        ),
                        exc_info=exc_info,
                    )
                    called.append((request, exc_info))

                @classmethod
                def log_ws_request(
                    kls,
                    lc: LogContext,
                    request: Request,
                    identifier: str,
                    dct: dict,
                    body: dict | None = None,
                    exc_info: ExcInfo | None = None,
                ):
                    assert identifier == lc.context["request_identifier"]
                    get_logger(1).info(lc("Test WS Request", **dct, body=body), exc_info=exc_info)

            async def route_error(request: Request, /) -> HTTPResponse | None:
                error = ValueError("asdf")
                expected_called.append((request, (ValueError, error, IsTraceback())))
                raise error

            async def route(request: Request, /) -> HTTPResponse | None:
                expected_called.append((request, None))
                return sanic.text("hi")

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                assert message.body == {"command": mock.ANY, "path": "/route"}
                assert message.body["command"] in ("two", "three")
                if message.body["command"] == "three":
                    await wssend({"got": "three"})
                    error = TypeError("HI")
                    expected_called.append((message.request, (TypeError, error, IsTraceback())))
                    raise error
                else:
                    await wssend({"got": "notthree"})
                    expected_called.append((message.request, None))
                    return False

            async def setup_routes(server: Server):
                tp.cast(WithCommanderClass, ws).__commander_class__ = C
                tp.cast(WithCommanderClass, route).__commander_class__ = C
                tp.cast(WithCommanderClass, route_error).__commander_class__ = C

                server.app.add_route(route, "route", methods=["PUT"])
                server.app.add_route(route_error, "route_error", methods=["PUT"])
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                await srv.start_request("PUT", "/route", {"command": "one"})
                await srv.start_request("PUT", "/route_error", {"command": "one"})
                unknown = await srv.start_request("GET", "/unknown_route")
                async with srv.stream("/stream") as stream:
                    await stream.send({"command": "two", "path": "/route"})
                    assert await stream.recv() == {
                        "reply": {"got": "notthree"},
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                    }
                async with srv.stream("/stream") as stream:
                    await stream.send({"command": "three", "path": "/route"})
                    assert await stream.recv() == {
                        "reply": {"got": "three"},
                        "request_identifier": WSIdent2,
                        "message_id": WSIdentM2,
                    }
                srv.stop()

                assert (await unknown.text()).startswith(
                    "⚠️ 404 — Not Found\n==================\nRequested URL /unknown_route not found"
                )

            records = [
                r.msg
                for r in caplog.records
                if isinstance(r.msg, dict)
                and any(m in r.msg["msg"] for m in ("Response", "Request"))
            ]

            assert records == [
                {
                    "request_identifier": Ident1,
                    "msg": "Test Request",
                    "dct": {"method": "PUT", "uri": "/route", "scheme": "http", "remote_addr": ""},
                },
                {
                    "request_identifier": Ident1,
                    "msg": "Test Response",
                    "method": "PUT",
                    "uri": "/route",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
                {
                    "request_identifier": Ident2,
                    "msg": "Test Request",
                    "dct": {
                        "method": "PUT",
                        "uri": "/route_error",
                        "scheme": "http",
                        "remote_addr": "",
                    },
                },
                {
                    "request_identifier": Ident2,
                    "msg": "Test Response",
                    "method": "PUT",
                    "uri": "/route_error",
                    "status": 500,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
                {
                    "request_identifier": Ident3,
                    "msg": "Request",
                    "method": "GET",
                    "uri": "/unknown_route",
                    "scheme": "http",
                    "remote_addr": "",
                },
                {
                    "request_identifier": Ident3,
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/unknown_route",
                    "status": 404,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Test WS Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": {"command": "two", "path": "/route"},
                },
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Test Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
                {
                    "request_identifier": WSIdent2,
                    "message_id": WSIdentM2,
                    "msg": "Test WS Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": {"command": "three", "path": "/route"},
                },
                {
                    "request_identifier": WSIdent2,
                    "message_id": WSIdentM2,
                    "msg": "Test Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 500,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
            ]

            assert called == expected_called

    describe "websocket streams":

        async it "can send progress messages", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            identifiers: set[str] = set()

            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM1 = pws_thp.IdentifierMatch(identifiers)

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                await wssend.progress(message.body["echo"])
                return False

            async def setup_routes(server):
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                async with srv.stream("/stream") as stream:
                    await stream.send({"echo": "there"})
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                        "progress": "there",
                    }
                    await stream.recv() is None

        async it "can provide a progress callback", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            identifiers: set[str] = set()
            progress = pytest.helpers.AsyncMock(
                name="progress", return_value={"ret": "from progress"}
            )

            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM1 = pws_thp.IdentifierMatch(identifiers)

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                wssend = wssend.with_progress(tp.cast(ProgressMessageMaker, progress))
                await wssend.progress(message.body["echo"], one=1, two=2)
                return False

            async def setup_routes(server):
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                async with srv.stream("/stream") as stream:
                    await stream.send({"echo": "there"})
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                        "progress": {"ret": "from progress"},
                    }
                    await stream.recv() is None

            progress.assert_called_once_with("there", do_log=True, one=1, two=2)

        async it "complains if the message isn't valid json", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            identifiers: set[str] = set()

            WSIdent1 = pws_thp.IdentifierMatch(identifiers)

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                raise AssertionError("Never reaches here")

            async def setup_routes(server):
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                async with srv.stream("/stream") as stream:
                    await stream.send("[")
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": "unknown",
                        "error": "failed to interpret json",
                        "error_code": "InvalidRequest",
                    }
                    await stream.send("{")
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": "unknown",
                        "error": "failed to interpret json",
                        "error_code": "InvalidRequest",
                    }

            records = [r.msg for r in caplog.records if isinstance(r.msg, dict)]

            assert records == [
                {
                    "request_identifier": WSIdent1,
                    "msg": "Websocket Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": None,
                },
                {
                    "request_identifier": WSIdent1,
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 500,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
                {
                    "request_identifier": WSIdent1,
                    "msg": "Websocket Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": None,
                },
                {
                    "request_identifier": WSIdent1,
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 500,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
            ]

        async it "can use message id that is provided", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            identifiers: set[str] = set()

            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM1 = "my amazing message id"

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                assert message.id == "my amazing message id"
                await wssend({"echo": "".join(reversed(tp.cast(str, message.body["echo"])))})
                return False

            async def setup_routes(server):
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                async with srv.stream("/stream") as stream:
                    await stream.send({"message_id": WSIdentM1, "echo": "there"})
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                        "reply": {"echo": "ereht"},
                    }
                    assert await stream.recv() is None

            records = [r.msg for r in caplog.records if isinstance(r.msg, dict)]

            assert records == [
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Websocket Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": {"message_id": WSIdentM1, "echo": "there"},
                },
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
            ]

        async it "can not override the request identifier", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            identifiers: set[str] = set()

            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            PWSIdent1 = "my amazing request id"
            WSIdentM1 = pws_thp.IdentifierMatch(identifiers)

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                assert message.request.ctx.request_identifier != PWSIdent1
                await wssend({"echo": "".join(reversed(tp.cast(str, message.body["echo"])))})
                return False

            async def setup_routes(server):
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                async with srv.stream("/stream") as stream:
                    await stream.send({"request_identifier": PWSIdent1, "echo": "there"})
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                        "reply": {"echo": "ereht"},
                    }
                    assert await stream.recv() is None

            assert PWSIdent1 != WSIdent1

            records = [r.msg for r in caplog.records if isinstance(r.msg, dict)]

            assert records == [
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Websocket Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": {"request_identifier": PWSIdent1, "echo": "there"},
                },
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
            ]

        async it "only stops connection upon returning False", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            async with pytest.helpers.FutureDominoes(expected=11) as futs:
                start = hp.create_future()
                identifiers: set[str] = set()

                WSIdent1 = pws_thp.IdentifierMatch(identifiers)
                WSIdent2 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM1 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM2 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM3 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM4 = pws_thp.IdentifierMatch(identifiers)

                async def ws(wssend: WSSender, message: Message) -> bool | None:
                    assert "command" in message.body
                    if message.body["command"] == "echo":
                        assert "value" in message.body
                        assert isinstance(message.body["wait"], list)
                        await futs[message.body["wait"][0]]
                        await wssend({"value": message.body["value"]})
                        await futs[message.body["wait"][1]]
                        await wssend({"value": message.body["value"]})
                        return None
                    else:
                        assert message.body["command"] == "stop"
                        return False

                async def setup_routes(server):
                    server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

                async def stream1(streamer: hp.ResultStreamer) -> tp.AsyncIterable[dict]:
                    await start
                    async with srv.stream("/stream") as stream:
                        count = 0
                        await futs[1]
                        await stream.send({"command": "echo", "value": "one", "wait": [2, 5]})
                        await stream.send({"command": "echo", "value": "two", "wait": [4, 7]})

                        while True:
                            nxt = await stream.recv()
                            yield nxt
                            count += 1
                            if count == 4:
                                break

                        await stream.send({"command": "stop"})
                        nxt = await stream.recv()
                        assert nxt is None
                        await futs[10]

                async def stream2(streamer: hp.ResultStreamer) -> tp.AsyncIterator[dict]:
                    await start

                    async with srv.stream("/stream") as stream:
                        count = 0
                        await stream.send({"command": "echo", "value": "three", "wait": [3, 8]})
                        await stream.send({"command": "echo", "value": "four", "wait": [6, 9]})

                        while True:
                            nxt = await stream.recv()
                            yield nxt
                            count += 1
                            if count == 4:
                                break

                        await stream.send({"command": "stop"})
                        nxt = await stream.recv()
                        assert nxt is None
                        await futs[11]

                results: list[dict] = []
                async with hp.ResultStreamer(final_future) as streamer:
                    async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                        await streamer.add_generator(stream1(streamer))
                        await streamer.add_generator(stream2(streamer))
                        streamer.no_more_work()

                        start.set_result(True)

                        async for result in streamer:
                            if not result.successful:
                                raise result.value

                            assert isinstance(result.value, dict)
                            results.append(result.value)

                        srv.stop()

                assert results == [
                    {
                        "message_id": WSIdentM1,
                        "request_identifier": WSIdent1,
                        "reply": {"value": "one"},
                    },
                    {
                        "message_id": WSIdentM2,
                        "request_identifier": WSIdent2,
                        "reply": {"value": "three"},
                    },
                    {
                        "message_id": WSIdentM3,
                        "request_identifier": WSIdent1,
                        "reply": {"value": "two"},
                    },
                    {
                        "message_id": WSIdentM1,
                        "request_identifier": WSIdent1,
                        "reply": {"value": "one"},
                    },
                    {
                        "message_id": WSIdentM4,
                        "request_identifier": WSIdent2,
                        "reply": {"value": "four"},
                    },
                    {
                        "message_id": WSIdentM3,
                        "request_identifier": WSIdent1,
                        "reply": {"value": "two"},
                    },
                    {
                        "message_id": WSIdentM2,
                        "request_identifier": WSIdent2,
                        "reply": {"value": "three"},
                    },
                    {
                        "message_id": WSIdentM4,
                        "request_identifier": WSIdent2,
                        "reply": {"value": "four"},
                    },
                ]

        async it "doesn't close connection on an exception", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            async with pytest.helpers.FutureDominoes(expected=7) as futs:
                identifiers: set[str] = set()

                WSIdent1 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM1 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM2 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM3 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM4 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM5 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM6 = pws_thp.IdentifierMatch(identifiers)
                WSIdentM7 = pws_thp.IdentifierMatch(identifiers)

                async def ws(wssend: WSSender, message: Message) -> bool | None:
                    if "fut" in message.body:
                        await futs[message.body["fut"]]
                        await wssend(message.body["fut"])
                    else:
                        await wssend("stop")
                    if "error" in message.body:
                        raise Exception(message.body["error"])

                    if "stop" in message.body:
                        return False
                    else:
                        return None

                async def setup_routes(server):
                    server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

                results: list[dict] = []
                async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                    async with srv.stream("/stream") as stream:
                        await stream.send({"fut": 1})
                        await stream.send({"fut": 2, "error": "stuff"})
                        await stream.send({"fut": 3})
                        await stream.send({"fut": 4})
                        await stream.send({"fut": 5, "error": "things"})
                        await stream.send({"fut": 6})
                        await futs[7]
                        await stream.send({"stop": True})

                        while True:
                            nxt = await stream.recv()
                            if nxt is None:
                                break
                            results.append(nxt)
                            pass

                    srv.stop()

                assert results == [
                    {
                        "message_id": WSIdentM1,
                        "request_identifier": WSIdent1,
                        "reply": 1,
                    },
                    {
                        "message_id": WSIdentM2,
                        "request_identifier": WSIdent1,
                        "reply": 2,
                    },
                    {
                        "message_id": WSIdentM2,
                        "request_identifier": WSIdent1,
                        "error": "Internal Server Error",
                        "error_code": "InternalServerError",
                    },
                    {
                        "message_id": WSIdentM3,
                        "request_identifier": WSIdent1,
                        "reply": 3,
                    },
                    {
                        "message_id": WSIdentM4,
                        "request_identifier": WSIdent1,
                        "reply": 4,
                    },
                    {
                        "message_id": WSIdentM5,
                        "request_identifier": WSIdent1,
                        "reply": 5,
                    },
                    {
                        "message_id": WSIdentM5,
                        "request_identifier": WSIdent1,
                        "error": "Internal Server Error",
                        "error_code": "InternalServerError",
                    },
                    {
                        "message_id": WSIdentM6,
                        "request_identifier": WSIdent1,
                        "reply": 6,
                    },
                    {
                        "message_id": WSIdentM7,
                        "request_identifier": WSIdent1,
                        "reply": "stop",
                    },
                ]

        async it "doesn't cause havoc if couldn't handle because connection closed", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            called: list[str] = []
            identifiers: set[str] = set()

            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM1 = pws_thp.IdentifierMatch(identifiers)

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                await wssend("one")
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    called.append("cancelled")
                try:
                    await wssend("two")
                except sanic.exceptions.WebsocketClosed:
                    called.append("closed")
                    raise
                return None

            async def setup_routes(server):
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                async with srv.stream("/stream") as stream:
                    await stream.send({})
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                        "reply": "one",
                    }
                srv.stop()

            records = [r.msg for r in caplog.records if isinstance(r.msg, dict)]

            assert records == [
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Websocket Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": {},
                },
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 500,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
            ]
            assert called == ["cancelled", "closed"]

        async it "logs response if abruptly closed", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            identifiers: set[str] = set()

            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM1 = pws_thp.IdentifierMatch(identifiers)

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                await wssend("one")
                await asyncio.sleep(10)
                return None

            async def setup_routes(server):
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                async with srv.stream("/stream") as stream:
                    await stream.send({})
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                        "reply": "one",
                    }
                srv.stop()

            records = [r.msg for r in caplog.records if isinstance(r.msg, dict)]

            assert records == [
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Websocket Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": {},
                },
                {
                    "request_identifier": WSIdent1,
                    "message_id": WSIdentM1,
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 500,
                    "remote_addr": "",
                    "took_seconds": Between(0, 1.0),
                },
            ]

        async it "has access to a future representing the stream", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            called: list[object] = []
            identifiers: set[str] = set()

            WSIdent1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM1 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM2 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM3 = pws_thp.IdentifierMatch(identifiers)
            WSIdentM4 = pws_thp.IdentifierMatch(identifiers)

            async def ws(wssend: WSSender, message: Message) -> bool | None:
                called.append(("before", message.body["id"]))
                try:
                    match message.body["command"]:
                        case "wait":
                            await message.stream_fut
                            called.append(("after", message.body["id"]))
                        case "echo":
                            await wssend("".join(reversed(tp.cast(str, message.body["echo"]))))
                        case "stop":
                            return False
                        case _:
                            raise AssertionError(f"Unknown command, {message.body['command']}")
                finally:
                    called.append(("after", message.body["id"]))

                return None

            async def setup_routes(server):
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
                async with srv.stream("/stream") as stream:
                    await stream.send({"command": "echo", "echo": "hello", "id": 1})
                    await stream.send({"command": "echo", "echo": "there", "id": 2})
                    await stream.send({"command": "wait", "id": 3})
                    await stream.send({"command": "echo", "echo": "mate", "id": 4})
                    await stream.send({"command": "wait", "id": 5})

                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM1,
                        "reply": "olleh",
                    }
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM2,
                        "reply": "ereht",
                    }
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM3,
                        "reply": "etam",
                    }
                    await asyncio.sleep(5)
                    assert called == [
                        ("before", 1),
                        ("after", 1),
                        ("before", 2),
                        ("after", 2),
                        ("before", 3),
                        ("before", 4),
                        ("after", 4),
                        ("before", 5),
                    ]

                    await stream.send({"command": "echo", "echo": "blah", "id": 6})
                    await stream.send({"command": "stop", "id": 7})
                    await asyncio.sleep(5)
                    assert called == [
                        ("before", 1),
                        ("after", 1),
                        ("before", 2),
                        ("after", 2),
                        ("before", 3),
                        ("before", 4),
                        ("after", 4),
                        ("before", 5),
                        ("before", 6),
                        ("after", 6),
                        ("before", 7),
                        ("after", 7),
                        ("after", 3),
                        ("after", 5),
                    ]
                    assert await stream.recv() == {
                        "request_identifier": WSIdent1,
                        "message_id": WSIdentM4,
                        "reply": "halb",
                    }

                srv.stop()

            assert called == [
                ("before", 1),
                ("after", 1),
                ("before", 2),
                ("after", 2),
                ("before", 3),
                ("before", 4),
                ("after", 4),
                ("before", 5),
                ("before", 6),
                ("after", 6),
                ("before", 7),
                ("after", 7),
                ("after", 3),
                ("after", 5),
            ]
