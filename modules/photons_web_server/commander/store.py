import asyncio
import logging
import typing as tp

from delfick_project.logging import LogContext
from photons_app import helpers as hp
from photons_web_server.commander.messages import ExcInfo
from sanic import Sanic
from sanic.request import Request
from sanic.response import BaseHTTPResponse as Response
from strcs import Meta

from .messages import (
    MessageFromExc,
    ProgressMessageMaker,
    TMessageFromExc,
    TProgressMessageMaker,
    TReprer,
    get_logger,
    reprer,
)

if tp.TYPE_CHECKING:
    from photons_web_server.server import Server

C = tp.TypeVar("C", bound="Command")


class RouteTransformer(tp.Generic[C]):
    def __init__(
        self,
        store: "Store",
        kls: type[C],
        final_future: asyncio.Future,
        meta: Meta,
        app: Sanic,
        server: "Server",
        reprer: TReprer,
        message_from_exc_maker: type[TMessageFromExc],
        progress_message_maker: type[TProgressMessageMaker],
    ):
        self.kls = kls
        self.app = app
        self.meta = meta
        self.store = store
        self.server = server
        self.reprer = reprer
        self.final_future = final_future
        self.message_from_exc_maker = message_from_exc_maker
        self.progress_message_maker = progress_message_maker


@tp.runtime_checkable
class WithCommanderClass(tp.Protocol):
    __commander_class__: type["Command"]


class Command:
    def __init__(
        self,
        final_future: asyncio.Future,
        request: Request,
        store: "Store",
        meta: Meta,
        app: Sanic,
        server: "Server",
        reprer: TReprer,
        progress: TProgressMessageMaker,
        identifier: str,
        logger: logging.Logger,
    ):
        self.app = app
        self.meta = meta
        self.store = store
        self.server = server
        self.reprer = reprer
        self.request = request
        self._progress = progress
        self.identifier = identifier
        self.final_future = final_future

        self.lc = hp.lc.using(request_identifier=self.identifier)
        self.log = logger

    @classmethod
    def add_routes(kls, routes: RouteTransformer) -> None:
        pass

    @classmethod
    def log_request_dict(
        kls,
        request: Request,
        identifier: str,
        dct: dict,
        exc_info: ExcInfo = None,
    ) -> dict | None:
        return dct

    @classmethod
    def log_request(
        kls,
        lc: LogContext,
        request: Request,
        identifier: str,
        dct: dict,
        exc_info: ExcInfo = None,
    ):
        info = kls.log_request_dict(request, identifier, dct, exc_info)
        if not info:
            return

        get_logger(1).info(lc("Request", **info))

    @classmethod
    def log_ws_request_dict(
        kls,
        request: Request,
        identifier: str,
        dct: dict,
        first: dict,
        exc_info: ExcInfo = None,
    ) -> dict | None:
        return dct

    @classmethod
    def log_ws_request(
        kls,
        lc: LogContext,
        request: Request,
        identifier: str,
        dct: dict,
        first: dict,
        exc_info: ExcInfo = None,
    ):
        info = kls.log_ws_request_dict(request, identifier, dct, first, exc_info)
        if not info:
            return

        get_logger(1).info(lc("Websocket Request", **info, body=first))

    @classmethod
    def log_response_dict(
        kls,
        level: str,
        request: Request,
        response: Response,
        identifier: str,
        took: float,
        exc_info: ExcInfo = None,
    ) -> dict:
        return dict(
            method=request.method,
            uri=request.path,
            status=response.status,
            remote_addr=request.remote_addr,
            took_seconds=round(took, 2),
            request_identifier=identifier,
        )

    @classmethod
    def log_response(
        kls,
        lc: LogContext,
        request: Request,
        response: Response,
        identifier: str,
        took: float,
        exc_info: ExcInfo = None,
    ) -> None:
        level = "error"
        if response.status < 400:
            level = "info"

        info = kls.log_response_dict(level, request, response, identifier, took, exc_info)
        if not info:
            return

        getattr(get_logger(1), level)(
            lc("Response", **info),
            exc_info=exc_info,
        )


class Store:
    def register_commands(
        self,
        final_future: asyncio.Future,
        meta: Meta,
        app: Sanic,
        server: "Server",
        reprer: TReprer = reprer,
        message_from_exc: type[TMessageFromExc] = MessageFromExc,
        progress_message_maker: type[TProgressMessageMaker] = ProgressMessageMaker,
    ) -> None: ...
