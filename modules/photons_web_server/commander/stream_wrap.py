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


class WSRequestLogger(tp.Protocol):
    def __call__(self, request: Request, first: tp.Any, **extra_lc_context) -> None: ...


class ResponseLogger(tp.Protocol):
    def __call__(self, request: Request, response: Response, **extra_lc_context) -> None: ...


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


class WSSender:
    _progress: Progress | None

    def __init__(
        self,
        ws: Websocket,
        reprer: TReprer,
        message: Message,
        progress: Progress | None = None,
    ):
        self.ws = ws
        self._reprer = reprer
        self._message = message
        self._progress = progress

    def with_progress(self, progress: Progress) -> "WSSender":
        return WSSender(self.ws, self._reprer, self._message, progress=progress)

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

        await self.ws.send(json_dumps(msg, default=self._reprer))

    async def progress(self, message: tp.Any, do_log=True, **kwargs) -> dict:
        info = message
        if self._progress is not None:
            info = await self._progress(message, do_log=do_log, **kwargs)

        await self(info, progress=True)
        return info


class WebsocketWrap:
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

    def message_from_exc(
        self, message: Message, exc_type: ExcTypO, exc: ExcO, tb: TBO
    ) -> ErrorMessage | Exception:
        return InternalServerError("Internal Server Error")

    def make_responder(
        self,
        ws: Websocket,
        reprer: TReprer,
        message: Message,
    ) -> Responder:
        return WSSender(
            ws,
            reprer,
            message,
        )

    def __call__(self, handler: WrappedWebsocketHandler) -> RouteHandler:
        @wraps(handler)
        async def handle(request: Request, ws: Websocket):
            from .store import WithCommanderClass

            await ws.send(json_dumps({"message_id": "__server_time__", "reply": time.time()}))

            if request.route and not isinstance(request.route.handler, WithCommanderClass):
                if isinstance(handler, WithCommanderClass):
                    request.route.handler.__commander_class__ = handler.__commander_class__

            with self.a_stream_fut(request) as stream_fut:
                async with hp.TaskHolder(
                    stream_fut, name="WebsocketWrap::__call__[tasks]"
                ) as tasks:
                    with hp.ChildOfFuture(
                        stream_fut, name="WebsocketWrap::__call__[loop_stop]"
                    ) as loop_stop:
                        try:
                            while True:
                                if loop_stop.done():
                                    break

                                await self.handle_next(
                                    loop_stop, tasks, handler, request, stream_fut, ws
                                )
                        finally:
                            await ws.close()

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

    async def handle_next(
        self,
        loop_stop: asyncio.Future,
        tasks: hp.TaskHolder,
        handler: WrappedWebsocketHandler,
        request: Request,
        stream_fut: asyncio.Future,
        ws: Websocket,
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

        async def process():
            with Message.create(message_id, body, request, stream_fut) as message:
                status = 500
                respond = self.make_responder(ws, self.reprer, message)

                try:
                    if await handler(respond=respond, message=message) is False:
                        loop_stop.cancel()
                    status = 200
                except:
                    request.ctx.exc_info = sys.exc_info()
                    try:
                        res = self.message_from_exc(message, *request.ctx.exc_info)
                        if isinstance(res, ErrorMessage):
                            await respond({"error_code": res.error_code, "error": res.error})
                        else:
                            await respond(res)
                    except sanic.exceptions.WebsocketClosed:
                        loop_stop.cancel()
                finally:
                    self.log_response(request, HTTPResponse(status=status), message_id=message.id)

        tasks.add(process())
