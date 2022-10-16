import asyncio
import json
import typing as tp

import aiohttp
import pytest
import websockets
from photons_app import helpers as hp
from photons_web_server.server import Server
from sanic import Sanic


def pytest_configure(config):
    pytest.helpers.register(WebServerRoutes)
    pytest.helpers.register(IsInstance)


@pytest.fixture()
def call_from_conftest():
    def call_from_conftest(cb):
        return cb()

    return call_from_conftest


@pytest.fixture(autouse=True, scope="module")
def sanic_test_mode():
    Sanic.test_mode = True


@pytest.fixture()
def fake_time(FakeTime):
    with FakeTime() as t:
        yield t


@pytest.fixture()
async def fake_event_loop(MockedCallLater, fake_time):
    async with MockedCallLater(fake_time) as m:
        yield m


@pytest.fixture()
def final_future() -> tp.Generator[asyncio.Future, None, None]:
    fut = hp.create_future(name="conftest::final_future")
    try:
        yield fut
    finally:
        fut.cancel()


class IsInstance:
    got: object | None

    def __init__(self, kls: type):
        self.got = None
        self.kls = kls

    def __eq__(self, other: object) -> bool:
        self.got = other
        return isinstance(other, self.kls)

    def __repr__(self) -> str:
        if self.got is None:
            return f"<INSTANCE OF {self.kls}>"
        else:
            return repr(self.got)


class WebServerRoutes(hp.AsyncCMMixin):
    def __init__(
        self,
        final_future: asyncio.Future,
        setup_routes: tp.Callable[["WebServerRoutes"], None] | None = None,
        server_properties: dict | None = None,
    ):
        self.final_future = final_future
        self.setup_routes = setup_routes
        self.server_properties = server_properties
        if self.server_properties is None:
            self.server_properties = {}

        self.task_holder = hp.TaskHolder(
            self.final_future, name="WebServerRoutes::__init__[task_holder]"
        )
        self.graceful_final_future = hp.create_future(
            name="WebServerRoutes::__init__[graceful_final_future]"
        )

    async def start(self, kls: type[Server] = Server):
        assert self.server_properties is not None
        WithProperties = type("S", (kls,), self.server_properties)  # type: tp.Any

        class S(WithProperties):
            async def setup_routes(s):
                await super().setup_routes()
                await self.setup_routes(s)

        await self.task_holder.start()

        self.server = S(
            self.task_holder,
            self.final_future,
            self.graceful_final_future,
        )

        self.port = pytest.helpers.free_port()
        self.serve_task = hp.get_event_loop().create_task(self.server.serve("127.0.0.1", self.port))
        try:
            await pytest.helpers.wait_for_port(self.port)
        except AssertionError:
            await self.serve_task
            raise
        return self

    def stop(self):
        self.graceful_final_future.cancel()

    def start_request(self, method: str, route: str, body: dict | None = None) -> asyncio.Task:
        async def request() -> aiohttp.ClientResponse:
            async with aiohttp.ClientSession() as session:
                return await getattr(session, method.lower())(
                    f"http://127.0.0.1:{self.port}{route}", json=body
                )

        return hp.get_event_loop().create_task(request())

    def run_stream(self, route: str, *items):
        async def stream():
            res = []
            async with websockets.connect(f"ws://127.0.0.1:{self.port}{route}") as websocket:
                for item in items:
                    if not isinstance(item, str):
                        await websocket.send(json.dumps(item))
                    else:
                        await websocket.send(item)

                while True:
                    try:
                        res.append(await websocket.recv())
                    except websockets.exceptions.ConnectionClosedOK:
                        break
            return res

        return hp.get_event_loop().create_task(stream())

    async def finish(self, exc_typ=None, exc=None, tb=None):
        self.graceful_final_future.cancel()
        hp.get_event_loop().call_later(20, self.serve_task.cancel)
        await hp.wait_for_all_futures(self.serve_task)
        try:
            await self.server.finished()
        except:
            self.final_future.cancel()
            await self.task_holder.finish()
