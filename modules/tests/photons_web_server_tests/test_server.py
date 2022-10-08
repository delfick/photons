# coding: spec

import asyncio
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
from photons_web_server.commander import Command, WithCommanderClass
from photons_web_server.commander.messages import ExcInfo, get_logger
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

        def stop(request: Request) -> HTTPResponse | None:
            task.photons_app.graceful_final_future.set_result(True)
            return None

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

            def stop(request: Request) -> HTTPResponse | None:
                called.append("stopcalled")
                task.photons_app.graceful_final_future.set_result(True)
                return sanic.text("stopped")

            async def long(request: Request) -> HTTPResponse | None:
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

            def route(request: Request) -> HTTPResponse | None:
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

            async def route(request: Request) -> HTTPResponse | None:
                started.set_result(True)
                await hp.create_future()
                return sanic.text("route")

            async def ws(request: Request, ws: Websocket):
                got = await ws.recv()
                assert got == "HI"
                await ws.send(got)
                startedws.set_result(True)
                await hp.create_future()

            async def setup_routes(server):
                server.app.add_route(route, "route", methods=["PUT"])
                server.app.add_websocket_route(ws, "stream")

            async with pytest.helpers.WebServerRoutes(final_future, setup_routes) as srv:
                req = srv.start_request("PUT", "/route")
                wsreq = srv.run_stream("/stream", "HI")
                await started
                await startedws
                assert time.time() < 0.3
                fake_time.set(0)
                srv.stop()
                await hp.wait_for_all_futures(req, wsreq)
                assert time.time() == 15

            with pytest.raises(aiohttp.client_exceptions.ServerDisconnectedError):
                await req
            assert await wsreq == ["HI"]

        async it "waits for requests based on sanic config GRACEFUL_SHUTDOWN_TIMEOUT", final_future: asyncio.Future, collector: Collector, fake_event_loop, fake_time:
            started = hp.create_future()

            async def route(request: Request) -> HTTPResponse | None:
                started.set_result(True)
                await hp.create_future()
                return sanic.text("route")

            async def setup_routes(server):
                server.app.add_route(route, "route", methods=["PUT"])

            class Config(Server.Config):
                GRACEFUL_SHUTDOWN_TIMEOUT = 7

            server_properties = {"Config": Config}

            async with pytest.helpers.WebServerRoutes(
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

            async def route(request: Request) -> HTTPResponse | None:
                await asyncio.sleep(2)
                return sanic.text("route")

            async def ws(request: Request, ws: Websocket, first: dict):
                assert first == {"command": "two", "path": "/route"}
                await asyncio.sleep(6)

            async def setup_routes(server):
                server.app.add_route(route, "route", methods=["PUT"])
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pytest.helpers.WebServerRoutes(final_future, setup_routes) as srv:
                await srv.start_request("PUT", "/route", {"command": "one"})
                await srv.run_stream("/stream", {"command": "two", "path": "/route"})
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
                    "request_identifier": mock.ANY,
                },
                {
                    "msg": "Response",
                    "method": "PUT",
                    "uri": "/route",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(1.0, 3.0),
                    "request_identifier": mock.ANY,
                },
                {
                    "msg": "Websocket Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "request_identifier": mock.ANY,
                    "body": {"command": "two", "path": "/route"},
                },
                {
                    "msg": "Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(5.0, 7.0),
                    "request_identifier": mock.ANY,
                },
            ]

            assert records[0]["request_identifier"] == records[1]["request_identifier"]
            assert all(
                r["request_identifier"] == records[-1]["request_identifier"] for r in records[2:]
            )

        async it "lets the handler hook into the logging", final_future: asyncio.Future, collector: Collector, fake_event_loop, caplog:
            called: list[object] = []
            expected_called: list[object] = []

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
                        )
                    )
                    called.append((request, exc_info))

                @classmethod
                def log_ws_request(
                    kls,
                    lc: LogContext,
                    request: Request,
                    identifier: str,
                    dct: dict,
                    first: dict | None = None,
                    exc_info: ExcInfo | None = None,
                ):
                    assert identifier == lc.context["request_identifier"]
                    get_logger(1).info(lc("Test WS Request", **dct, body=first))

            async def route_error(request: Request) -> HTTPResponse | None:
                error = ValueError("asdf")
                expected_called.append((request, (ValueError, error, IsTraceback())))
                raise error

            async def route(request: Request) -> HTTPResponse | None:
                expected_called.append((request, None))
                return sanic.text("hi")

            async def ws(request: Request, ws: Websocket, first: dict):
                assert first == {"command": mock.ANY, "path": "/route"}
                assert first["command"] in ("two", "three")
                if first["command"] == "three":
                    error = TypeError("HI")
                    expected_called.append((request, (TypeError, error, IsTraceback())))
                    raise error
                else:
                    expected_called.append((request, None))

            async def setup_routes(server: Server):
                tp.cast(WithCommanderClass, ws).__commander_class__ = C
                tp.cast(WithCommanderClass, route).__commander_class__ = C
                tp.cast(WithCommanderClass, route_error).__commander_class__ = C

                server.app.add_route(route, "route", methods=["PUT"])
                server.app.add_route(route_error, "route_error", methods=["PUT"])
                server.app.add_websocket_route(server.wrap_websocket_handler(ws), "stream")

            async with pytest.helpers.WebServerRoutes(final_future, setup_routes) as srv:
                await srv.start_request("PUT", "/route", {"command": "one"})
                await srv.start_request("PUT", "/route_error", {"command": "one"})
                unknown = await srv.start_request("GET", "/unknown_route")
                await srv.run_stream("/stream", {"command": "two", "path": "/route"})
                await srv.run_stream("/stream", {"command": "three", "path": "/route"})
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

            identifiers = set()

            class IdentifierMatch:
                identifier: str | None

                def __init__(self, *, count=2):
                    self.identifier = None
                    self.count = count

                def __eq__(self, other: object) -> bool:
                    if self.identifier is None:
                        assert other not in identifiers
                        assert isinstance(other, str)
                        identifiers.add(other)
                        self.identifier = other
                        return True

                    return self.identifier == other

                def __repr__(self) -> str:
                    if self.identifier is None:
                        return "<IDENTIFIER>"
                    else:
                        return repr(self.identifier)

            Ident1 = IdentifierMatch()
            Ident2 = IdentifierMatch()
            Ident3 = IdentifierMatch()
            WSIdent1 = IdentifierMatch()
            WSIdent2 = IdentifierMatch()

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
                    "msg": "Test WS Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": {"command": "two", "path": "/route"},
                },
                {
                    "request_identifier": WSIdent1,
                    "msg": "Test Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 200,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
                {
                    "request_identifier": WSIdent2,
                    "msg": "Test WS Request",
                    "method": "GET",
                    "uri": "/stream",
                    "scheme": "ws",
                    "remote_addr": "",
                    "body": {"command": "three", "path": "/route"},
                },
                {
                    "request_identifier": WSIdent2,
                    "msg": "Test Response",
                    "method": "GET",
                    "uri": "/stream",
                    "status": 500,
                    "remote_addr": "",
                    "took_seconds": Between(0.0, 1.0),
                },
            ]

            assert called == expected_called
