import asyncio
import typing as tp

from delfick_project.logging import LogContext
from photons_app import helpers as hp
from photons_web_server.commander.messages import ExcInfo
from sanic import Sanic
from sanic.request import Request
from sanic.response import BaseHTTPResponse as Response
from strcs import Meta

from .messages import TProgressMessageMaker, TReprer, get_logger


@tp.runtime_checkable
class WithCommanderClass(tp.Protocol):
    __commander_class__: type["Command"]


class Command:
    def __init__(
        self,
        final_future: asyncio.Future,
        meta: Meta,
        app: Sanic,
        reprer: TReprer,
        progress: TProgressMessageMaker,
        identifier: str,
    ):
        self.app = app
        self.meta = meta
        self.reprer = reprer
        self.progress = progress
        self.identifier = identifier
        self.final_future = final_future

        self.lc = hp.lc.using(request_identifier=self.identifier)
        self.log = get_logger(stack_level=1)

    @classmethod
    def log_request_dict(
        kls,
        request: Request,
        identifier: str,
        dct: dict,
        exc_info: tp.Optional[ExcInfo] = None,
    ) -> tp.Optional[dict]:
        return dct

    @classmethod
    def log_request(
        kls,
        lc: LogContext,
        request: Request,
        identifier: str,
        dct: dict,
        exc_info: tp.Optional[ExcInfo] = None,
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
        exc_info: tp.Optional[ExcInfo] = None,
    ) -> tp.Optional[dict]:
        return dct

    @classmethod
    def log_ws_request(
        kls,
        lc: LogContext,
        request: Request,
        identifier: str,
        dct: dict,
        first: dict,
        exc_info: tp.Optional[ExcInfo] = None,
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
        exc_info: tp.Optional[ExcInfo] = None,
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
        exc_info: tp.Optional[ExcInfo] = None,
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


class Store: ...
