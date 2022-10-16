import asyncio
import inspect
import logging
import sys
import typing as tp
from contextlib import contextmanager
from functools import wraps

import sanic.exceptions
from delfick_project.logging import LogContext
from photons_app import helpers as hp
from photons_web_server.commander.const import REQUEST_IDENTIFIER_HEADER
from photons_web_server.commander.messages import ExcInfo
from sanic import Sanic
from sanic.models.handler_types import RouteHandler
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
    get_logger_name,
    reprer,
)

if tp.TYPE_CHECKING:
    from photons_web_server.server import Server

P = tp.ParamSpec("P")
T = tp.TypeVar("T")
R = tp.TypeVar("R")
C = tp.TypeVar("C", bound="Command")


@tp.runtime_checkable
class WithCommanderClass(tp.Protocol):
    __commander_class__: type["Command"]


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

    if tp.TYPE_CHECKING:

        def http(
            self,
            method: tp.Callable,
            uri: str,
            methods: tp.Iterable[str] = frozenset({"GET"}),
            host: None | str | list[str] = None,
            strict_slashes: None | bool = None,
            version: None | int | str | float = None,
            name: None | str = None,
            stream: bool = False,
            version_prefix: str = "/v",
            error_format: None | str = None,
            ignore_body: bool = False,
            apply: bool = True,
            subprotocols: None | list[str] = None,
            websocket: bool = False,
            unquote: bool = False,
            static: bool = False,
            **ctx_kwargs: tp.Any,
        ) -> RouteHandler: ...

    else:

        def http(self, method: tp.Callable, *args, **kwargs) -> RouteHandler:
            return self.app.add_route(self.wrap_http(method), *args, **kwargs)

    @contextmanager
    def a_final_future(
        self, request: Request, name: str
    ) -> tp.Generator[asyncio.Future, None, None]:
        if hasattr(request.ctx, "final_future"):
            yield request.ctx.final_future
            return

        with hp.ChildOfFuture(
            self.final_future, name="{name}[request_final_future]"
        ) as final_future:
            request.ctx.final_future = final_future
            yield final_future

    def wrap_http(self, method: tp.Callable) -> RouteHandler:
        @wraps(method)
        async def route(request: Request, *args: tp.Any, **kwargs: tp.Any) -> Response | None:
            with self._an_instance(request, method) as (lc, name, logger_name, instance):
                ret = False
                try:
                    route = getattr(instance, method.__name__)
                    if inspect.iscoroutinefunction(route):
                        t = hp.async_as_background(route(request, *args, **kwargs))
                        await hp.wait_for_first_future(
                            t,
                            instance.final_future,
                            name=f"{name}[run_route]",
                        )
                        if t.cancelled():
                            ret = True

                        t.cancel()
                        return await t
                    else:
                        return route(request, *args, **kwargs)
                except:
                    exc_info = sys.exc_info()
                    if ret or exc_info[0] is not asyncio.CancelledError:
                        raise self.message_from_exc_maker(lc=lc, logger_name=logger_name)(*exc_info)

                    if exc_info[0] is asyncio.CancelledError:
                        raise sanic.exceptions.ServiceUnavailable("Cancelled")

                    raise

        tp.cast(WithCommanderClass, route).__commander_class__ = self.kls
        return tp.cast(RouteHandler, route)

    @contextmanager
    def _an_instance(
        self, request: Request, method: tp.Callable
    ) -> tp.Generator[tuple[LogContext, str, str, C], None, None]:
        name = f"RouteTransformer::__call__({self.kls.__name__}:{method.__name__})"

        lc = hp.lc.using(
            **(
                {}
                if not hasattr(request.ctx, "request_identifier")
                else {"request_identifier": request.ctx.request_identifier}
            )
        )

        logger_name = get_logger_name(method=method)
        logger = logging.getLogger(logger_name)

        with self.a_final_future(request, name) as final_future:
            instance = self.kls(
                final_future,
                request,
                self.store,
                self.meta,
                self.app,
                self.server,
                self.reprer,
                self.progress_message_maker(lc=lc, logger_name=logger_name),
                identifier=request.headers[REQUEST_IDENTIFIER_HEADER],
                logger=logger,
            )
            yield lc, name, logger_name, instance


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

    async def progress_cb(self, message: tp.Any, do_log=True, **kwargs) -> dict:
        return await self._progress(message, do_log=do_log, **kwargs)

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
    def __init__(self) -> None:
        self.commands: list[type[Command]] = []

    def command(self, command: type[Command]) -> type[Command]:
        self.commands.append(command)
        return command

    def register_commands(
        self,
        final_future: asyncio.Future,
        meta: Meta,
        app: Sanic,
        server: "Server",
        reprer: TReprer = reprer,
        message_from_exc: type[TMessageFromExc] = MessageFromExc,
        progress_message_maker: type[TProgressMessageMaker] = ProgressMessageMaker,
    ) -> None:
        for kls in self.commands:
            kls.add_routes(
                RouteTransformer(
                    self,
                    kls,
                    final_future,
                    meta,
                    app,
                    server,
                    reprer,
                    message_from_exc,
                    progress_message_maker,
                )
            )
