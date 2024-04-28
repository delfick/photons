import asyncio
import json
import types
import typing as tp

import aiohttp
import pytest
import socketio
import websockets
import websockets.client
from photons_app import helpers as hp
from photons_web_server.server import Server


class IdentifierMatch:
    identifier: str | None

    def __init__(self, identifiers: set, *, count=2):
        self.identifier = None
        self.identifiers = identifiers
        self.count = count

    def __hash__(self) -> int:
        assert self.identifier is not None
        return hash(self.identifier)

    def __eq__(self, other: object) -> bool:
        if self.identifier is None:
            assert other not in self.identifiers
            assert isinstance(other, str)
            self.identifiers.add(other)
            self.identifier = other
            return True

        return self.identifier == other

    def __repr__(self) -> str:
        if self.identifier is None:
            return "<IDENTIFIER>"
        else:
            return repr(self.identifier)


class SocketioStream(hp.AsyncCMMixin):
    _sio: socketio.AsyncSimpleClient

    def __init__(self, address: str, socketio_path: str) -> None:
        self.address = address
        self.socketio_path = socketio_path

    async def start(self) -> "Stream":
        self._sio = socketio.AsyncSimpleClient()
        await self._sio.connect(self.address, socketio_path=self.socketio_path)
        return self

    async def finish(
        self,
        exc_type: type[BaseException] | None = None,
        exc: BaseException | None = None,
        tb: types.TracebackType | None = None,
    ):
        if hasattr(self, "_sio"):
            await self._sio.disconnect()
            del self._sio

    async def emit(self, event: str, data: dict[str, object]) -> None:
        if not hasattr(self, "_sio"):
            raise AssertionError("Need to use SocketioStream in a context manager")

        await self._sio.emit(event, data)

    async def recv(self) -> dict | None:
        event = await self._sio.receive()
        assert isinstance(event, list)
        if len(event) == 1:
            event, data = event[0], {}
        else:
            event, data = event

        return {"event": event, "data": data}


class Stream(hp.AsyncCMMixin):
    _websocket: websockets.client.WebSocketClientProtocol

    def __init__(self, address: str):
        self.address = address

    async def start(self) -> "Stream":
        self._websocket = await websockets.client.connect(self.address)
        return self

    async def finish(
        self,
        exc_type: type[BaseException] | None = None,
        exc: BaseException | None = None,
        tb: types.TracebackType | None = None,
    ):
        if hasattr(self, "_websocket"):
            await self._websocket.close()
            del self._websocket

    async def send(self, item: str | dict | list) -> None:
        if not hasattr(self, "_websocket"):
            raise AssertionError("Need to use Stream in a context manager")

        if not isinstance(item, str):
            await self._websocket.send(json.dumps(item))
        else:
            await self._websocket.send(item)

    async def recv(self) -> dict | None:
        try:
            got: str | bytes = await self._websocket.recv()
        except websockets.exceptions.ConnectionClosedOK:
            return None

        if got is None:
            raise AssertionError("Got None back from the stream, except a dictionary")

        if isinstance(got, bytes):
            got = got.decode()

        res = json.loads(got)
        if not isinstance(res, dict):
            raise AssertionError(f"Expected a dictionary from stream, got {res}")

        return res


class WebServerRoutes(hp.AsyncCMMixin):
    def __init__(
        self,
        final_future: asyncio.Future,
        setup_routes: tp.Callable[[Server], tp.Coroutine[None, None, None]] | None = None,
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

    async def start(self, kls: type[Server] = Server) -> "WebServerRoutes":
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

    def stop(self) -> None:
        self.graceful_final_future.cancel()

    def start_request(
        self, method: str, route: str, body: dict | None = None
    ) -> asyncio.Task[aiohttp.ClientResponse]:
        async def request() -> aiohttp.ClientResponse:
            async with aiohttp.ClientSession() as session:
                return await getattr(session, method.lower())(
                    f"http://127.0.0.1:{self.port}{route}", json=body
                )

        return hp.get_event_loop().create_task(request())

    def stream(self, route: str, *items) -> Stream:
        return Stream(f"ws://127.0.0.1:{self.port}{route}")

    def sio_stream(self, route: str) -> SocketioStream:
        return SocketioStream(f"http://127.0.0.1:{self.port}", route)

    async def finish(
        self,
        exc_typ: type[BaseException] | None = None,
        exc: BaseException | None = None,
        tb: types.TracebackType | None = None,
    ) -> None:
        self.graceful_final_future.cancel()
        hp.get_event_loop().call_later(20, self.serve_task.cancel)
        await hp.wait_for_all_futures(self.serve_task)
        try:
            await self.server.finished()
        except:
            self.final_future.cancel()
            await self.task_holder.finish()
