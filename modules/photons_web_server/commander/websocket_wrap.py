import asyncio
import logging
import typing as tp

from sanic import Websocket
from sanic.request import Request
from sanic.response import BaseHTTPResponse as Response

from .messages import TReprer, reprer

log = logging.getLogger("photons_web_server.server")


class WSRequestLogger(tp.Protocol):
    def __call__(self, request: Request, first: tp.Any, **extra_lc_context) -> None: ...


class ResponseLogger(tp.Protocol):
    def __call__(self, request: Request, response: Response, **extra_lc_context) -> None: ...


class WrappedWebsocketHandler(tp.Protocol):
    async def __call__(
        self, request: Request, ws: Websocket, body: dict, message_id: str
    ) -> bool | None: ...


class WSSender:
    def __init__(self, request: Request, ws: Websocket, reprer: TReprer, message_id: str):
        self.ws = ws
        self.reprer = reprer

    async def __call__(self, res: dict) -> None: ...


class WebsocketWrap:
    def __init__(
        self,
        final_future: asyncio.Future,
        log_ws_request: WSRequestLogger,
        log_response: ResponseLogger,
        reprer: TReprer = reprer,
    ):
        self.reprer = reprer
        self.final_future = final_future
        self.log_response = log_response
        self.log_ws_request = log_ws_request

    def __call__(
        self, handler: WrappedWebsocketHandler
    ) -> tp.Callable[[Request, Websocket], None]: ...
