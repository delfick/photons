import abc
import asyncio
import logging
import sys
import time
import typing as tp
from contextlib import contextmanager
from functools import wraps
from textwrap import dedent

import attrs
import sanic.exceptions
import socketio
from attrs import define
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from sanic import Websocket
from sanic.models.handler_types import RouteHandler
from sanic.request import Request
from sanic.request.types import json_loads
from sanic.response import BaseHTTPResponse as Response
from sanic.response import HTTPResponse
from sanic.response.types import json_dumps
from typing_extensions import Self

from .messages import TBO, ErrorMessage, ExcO, ExcTypO
from .messages import TProgressMessageMaker as Progress
from .messages import TReprer
from .messages import TResponseMaker as Responder
from .messages import reprer

try:
    import ulid
except ImportError:
    raise PhotonsAppError(
        dedent(
            """
        The photons_web_server addon only works if you have sanic installed in your environment

        This can be done with::

            > python -m pip install "lifx-photons-core[web-server]"
    """
        )
    )

log = logging.getLogger("photons_web_server.server")


class InvalidRequest(Exception):
    pass


class InternalServerError(Exception):
    pass


class NeedOneData(Exception):
    pass


class WSRequestLogger(tp.Protocol):
    def __call__(
        self,
        request: Request,
        first: tp.Any,
        *,
        title: str = "Websocket Request",
        **extra_lc_context,
    ) -> None: ...


class ResponseLogger(tp.Protocol):
    def __call__(self, request: Request, response: Response, **extra_lc_context) -> None: ...


@attrs.frozen
class SocketioRoomEvent:
    lock: asyncio.Lock
    sio: socketio.AsyncServer
    sid: str
    data: tuple[object]
    event: str

    async def emit(self, event: str, *data: object, default: TReprer) -> None:
        async with self.lock:
            ds: list[object] = []
            for d in data:
                if isinstance(data, dict):
                    ds.append(json_loads(json_dumps(d, default=default)))
                else:
                    ds.append(d)
            await self.sio.emit(event, tuple(ds), to=self.sid)


@define
class Message:
    id: str
    body: dict[str, object]
    request: Request
    stream_fut: asyncio.Future
    message_fut: asyncio.Future

    @property
    def stream_id(self) -> str:
        return self.request.ctx.request_identifier

    @classmethod
    @contextmanager
    def unknown(
        cls, request: Request, stream_fut: asyncio.Future, body: object
    ) -> tp.Generator["Message", None, None]:
        with hp.ChildOfFuture(
            stream_fut, name="Message(unknown)::unknown[message_fut]"
        ) as message_fut:
            yield cls(
                id="unknown",
                body=tp.cast(dict, body),
                request=request,
                stream_fut=stream_fut,
                message_fut=message_fut,
            )

    @classmethod
    @contextmanager
    def create(
        cls, message_id: str, body: dict, request: Request, stream_fut: asyncio.Future
    ) -> tp.Generator["Message", None, None]:
        with hp.ChildOfFuture(
            stream_fut, name=f"Message({message_id})::create[message_fut]"
        ) as message_fut:
            yield cls(
                id=message_id,
                body=body,
                request=request,
                stream_fut=stream_fut,
                message_fut=message_fut,
            )


class WrappedWebsocketHandler(tp.Protocol):
    async def __call__(self, respond: Responder, message: Message) -> bool | None: ...


WrappedWebsocketHandlerOnClass: tp.TypeAlias = tp.Callable[
    [tp.Any, Responder, Message], tp.Coroutine[tp.Any, tp.Any, bool | None]
]

WrappedSocketioHandlerOnClass: tp.TypeAlias = tp.Callable[
    [tp.Any, Responder, Message], tp.Coroutine[tp.Any, tp.Any, bool | None]
]

T_Handler = tp.TypeVar("T_Handler", WrappedWebsocketHandlerOnClass, WrappedSocketioHandlerOnClass)
T_Transport = tp.TypeVar("T_Transport")


class Sender(tp.Generic[T_Transport], abc.ABC):
    _progress: Progress | None

    def __init__(
        self,
        transport: T_Transport,
        reprer: TReprer,
        message: Message,
        progress: Progress | None = None,
    ):
        self.transport = transport
        self._reprer = reprer
        self._message = message
        self._progress = progress

    @abc.abstractmethod
    def _send_response(self, msg: dict[str, object]) -> None: ...

    def with_progress(self, progress: Progress) -> Self:
        return self.__class__(self.transport, self._reprer, self._message, progress=progress)

    async def __call__(self, res: BaseException | object, progress: bool = False) -> None:
        msg = {
            "message_id": self._message.id,
            "request_identifier": self._message.request.ctx.request_identifier,
        }
        if isinstance(res, BaseException):
            res = {"error": res, "error_code": type(res).__name__}

        if hasattr(res, "as_dict"):
            res = res.as_dict()

        if progress:
            msg["progress"] = res
        else:
            msg["reply"] = res
            if isinstance(res, dict):
                if "error" in res:
                    error = res.pop("error")
                    if not isinstance(error, dict):
                        if attrs.has(type(error)):
                            error = attrs.asdict(error)
                        elif hasattr(error, "as_dict"):
                            error = error.as_dict()
                        else:
                            error = str(error)
                    msg["reply"]["error"] = error

        await self._send_response(msg)

    async def progress(self, message: tp.Any, do_log=True, **kwargs) -> dict:
        info = message
        if self._progress is not None:
            info = await self._progress(message, do_log=do_log, **kwargs)

        await self(info, progress=True)
        return info


class WSSender(Sender[Websocket]):
    async def _send_response(self, msg: dict[str, object]) -> None:
        await self.transport.send(json_dumps(msg, default=self._reprer))


class SocketioSender(Sender[SocketioRoomEvent]):
    async def _send_response(self, msg: dict[str, object]) -> None:
        if "progress" in msg:
            await self.transport.emit("progress", msg, default=self._reprer)
        elif "reply" in msg:
            if isinstance(msg["reply"], dict) and "error" in msg["reply"]:
                await self.transport.emit("error", msg, default=self._reprer)
            else:
                await self.transport.emit("reply", msg, default=self._reprer)


class StreamWrap(tp.Generic[T_Handler, T_Transport], abc.ABC):
    setup: tp.Callable

    def __init__(
        self,
        final_future: asyncio.Future,
        log_ws_request: WSRequestLogger,
        log_response: ResponseLogger,
        *args,
        reprer: TReprer = reprer,
        **kwargs,
    ):
        self.reprer = reprer
        self.final_future = final_future
        self.log_response = log_response
        self.log_ws_request = log_ws_request
        if hasattr(self, "setup"):
            self.setup(*args, **kwargs)

    @abc.abstractmethod
    def message_from_exc(
        self, message: Message, exc_type: ExcTypO, exc: ExcO, tb: TBO
    ) -> ErrorMessage | Exception: ...

    @abc.abstractmethod
    def make_responder(
        self,
        transport: T_Transport,
        reprer: TReprer,
        message: Message,
    ) -> Responder: ...

    @abc.abstractmethod
    async def _send_server_time(self, transport: T_Transport) -> None: ...

    @abc.abstractmethod
    async def handle_request(
        self,
        handler: T_Handler,
        request: Request,
        transport: T_Transport,
        tasks: hp.TaskHolder,
        stream_fut: asyncio.Future,
    ) -> None: ...

    def __call__(self, handler: T_Handler) -> RouteHandler:
        @wraps(handler)
        async def handle(request: Request, transport: T_Transport):
            from .store import WithCommanderClass

            await self._send_server_time(transport)

            if request.route and not isinstance(request.route.handler, WithCommanderClass):
                if isinstance(handler, WithCommanderClass):
                    request.ctx.__commander_class__ = handler.__commander_class__

            with self.a_stream_fut(request) as stream_fut:
                async with hp.TaskHolder(
                    stream_fut, name="WebsocketWrap::__call__[tasks]"
                ) as tasks:
                    await self.handle_request(handler, request, transport, tasks, stream_fut)

        return handle

    @contextmanager
    def a_stream_fut(self, request: Request) -> tp.Generator[asyncio.Future, None, None]:
        if hasattr(request.ctx, "stream_fut"):
            yield request.ctx.request_future
            return

        with hp.ChildOfFuture(
            self.final_future, name="WebsocketWrap::a_stream_fut[stream_fut]"
        ) as stream_fut:
            request.ctx.request_future = stream_fut
            yield stream_fut

    async def _process(
        self,
        handler: T_Handler,
        transport: T_Transport,
        message_id: str,
        body: dict[str, object],
        request: Request,
        stream_fut: asyncio.Future,
    ) -> bool | None:
        with Message.create(message_id, body, request, stream_fut) as message:
            status = 500
            respond = self.make_responder(transport, self.reprer, message)

            try:
                result = await handler(respond=respond, message=message)
                status = 200
                return result
            except:
                request.ctx.exc_info = sys.exc_info()
                res = self.message_from_exc(message, *request.ctx.exc_info)
                if isinstance(res, ErrorMessage):
                    await respond({"error_code": res.error_code, "error": res.error})
                else:
                    await respond(res)
            finally:
                self.log_response(request, HTTPResponse(status=status), message_id=message.id)


class WebsocketWrap(StreamWrap[WrappedWebsocketHandler, Websocket]):
    def message_from_exc(
        self, message: Message, exc_type: ExcTypO, exc: ExcO, tb: TBO
    ) -> ErrorMessage | Exception:
        return InternalServerError("Internal Server Error")

    def make_responder(
        self,
        transport: Websocket,
        reprer: TReprer,
        message: Message,
    ) -> Responder:
        return WSSender(transport, reprer, message)

    async def _send_server_time(self, transport: Websocket) -> None:
        await transport.send(json_dumps({"message_id": "__server_time__", "reply": time.time()}))

    async def handle_request(
        self,
        handler: WrappedWebsocketHandler,
        request: Request,
        transport: Websocket,
        tasks: hp.TaskHolder,
        stream_fut: asyncio.Future,
    ) -> None:
        with hp.ChildOfFuture(stream_fut, name="WebsocketWrap::__call__[loop_stop]") as loop_stop:
            try:
                while True:
                    if loop_stop.done():
                        break

                    await self.handle_next(
                        loop_stop, tasks, handler, request, stream_fut, transport
                    )
            finally:
                await transport.close()

    async def handle_next(
        self,
        loop_stop: asyncio.Future,
        tasks: hp.TaskHolder,
        handler: WrappedWebsocketHandler,
        request: Request,
        stream_fut: asyncio.Future,
        ws: T_Transport,
    ) -> None:
        get_nxt = tasks.add(ws.recv())
        await hp.wait_for_first_future(
            get_nxt, loop_stop, name="WebsocketWrap::handle_next[wait_for_nxt]"
        )

        if loop_stop.done():
            await ws.close()
            return

        try:
            nxt = await get_nxt
        except asyncio.CancelledError:
            raise
        except:
            request.ctx.exc_info = sys.exc_info()
            loop_stop.cancel()
            self.log_ws_request(request, None)
            self.log_response(request, HTTPResponse(status=500))
            raise

        try:
            body = json_loads(nxt)
        except (ValueError, TypeError):
            request.ctx.exc_info = sys.exc_info()
            self.log_ws_request(request, None)
            self.log_response(request, HTTPResponse(status=500))
            with Message.unknown(request, stream_fut, nxt) as message:
                respond = self.make_responder(ws, self.reprer, message)
                await respond(InvalidRequest("failed to interpret json"))
            return

        if not isinstance(body, dict):
            body = {"body": body}

        if "message_id" not in body:
            message_id = str(ulid.new())
        else:
            message_id = body["message_id"]

        try:
            self.log_ws_request(request, body, message_id=message_id)
        except Exception:
            log.exception("Failed to log websocket request")

        async def process() -> None:
            try:
                if (
                    await self._process(handler, ws, message_id, body, request, stream_fut)
                ) is False:
                    loop_stop.cancel()
            except sanic.exceptions.WebsocketClosed:
                loop_stop.cancel()

        tasks.add(process())


class SocketioWrap(StreamWrap[WrappedSocketioHandlerOnClass, str]):
    def message_from_exc(
        self, message: Message, exc_type: ExcTypO, exc: ExcO, tb: TBO
    ) -> ErrorMessage | Exception:
        return InternalServerError("Internal Server Error")

    def make_responder(
        self,
        transport: SocketioRoomEvent,
        reprer: TReprer,
        message: Message,
    ) -> Responder:
        return SocketioSender(transport, reprer, message)

    async def _send_server_time(self, transport: SocketioRoomEvent) -> None:
        # Don't send server_time here cause this fires per message
        pass

    async def handle_request(
        self,
        handler: WrappedSocketioHandlerOnClass,
        request: Request,
        transport: SocketioRoomEvent,
        tasks: hp.TaskHolder,
        stream_fut: asyncio.Future,
    ) -> None:
        try:
            if len(transport.data) != 1:
                raise NeedOneData()
        except NeedOneData:
            request.ctx.exc_info = sys.exc_info()
            self.log_ws_request(request, None)
            self.log_response(request, HTTPResponse(status=500))
            with Message.unknown(request, stream_fut, transport.data) as message:
                respond = self.make_responder(transport, self.reprer, message)
                await respond(InvalidRequest("didn't have exactly one piece of data"))
            return

        body = transport.data[0]
        if not isinstance(body, dict):
            body = {"body": body}

        if "message_id" not in body:
            message_id = str(ulid.new())
        else:
            message_id = body["message_id"]

        try:
            self.log_ws_request(
                request,
                {"event": transport.event, "data": body},
                message_id=message_id,
                title="Socketio Event",
            )
        except Exception:
            log.exception("Failed to log socketio request")

        tasks.add(self._process(handler, transport, message_id, body, request, stream_fut))
