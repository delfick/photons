# coding: spec

import asyncio
import socket
import sys
import time
import typing as tp
from contextlib import asynccontextmanager

import aiohttp
import pytest
import sanic
from alt_pytest_asyncio.plugin import OverrideLoop
from photons_app import helpers as hp
from photons_app.collector import Collector
from photons_web_server.server import Server, WebServerTask
from sanic import Sanic, Websocket
from sanic.config import Config
from sanic.request import Request
from sanic.response import HTTPResponse


@asynccontextmanager
async def make_server(ServerKls: tp.Type[Server]):
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


describe "Task":

    it "Runs the server", collector: Collector:

        called = []

        p = pytest.helpers.free_port()

        def stop(request: Request) -> tp.Optional[HTTPResponse]:
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

            server: tp.Optional[Server] = None
            lp: tp.Optional[asyncio.AbstractEventLoop] = None

            async def before_init(app: Sanic, loop: asyncio.AbstractEventLoop):
                called.append(("sanic_before_init", app, loop))

            async def after_init(app: Sanic, loop: asyncio.AbstractEventLoop):
                called.append(("sanic_after_init", app, loop))

            async def before_shutdown(app: Sanic, loop: asyncio.AbstractEventLoop):
                called.append(("sanic_before_shutdown", app, loop))

            async def after_shutdown(app: Sanic, loop: asyncio.AbstractEventLoop):
                called.append(("sanic_after_shutdown", app, loop))

            def stop(request: Request) -> tp.Optional[HTTPResponse]:
                called.append("stopcalled")
                task.photons_app.graceful_final_future.set_result(True)
                return sanic.text("stopped")

            async def long(request: Request) -> tp.Optional[HTTPResponse]:
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

            def route(request: Request) -> tp.Optional[HTTPResponse]:
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

            async def route(request: Request) -> tp.Optional[HTTPResponse]:
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

            async def route(request: Request) -> tp.Optional[HTTPResponse]:
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
