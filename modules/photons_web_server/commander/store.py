import asyncio
import inspect
import logging
import sys
import typing as tp
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from functools import partial, wraps

import attrs
import sanic.exceptions
import strcs
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
    TBO,
    ErrorMessage,
    ExcO,
    ExcTypO,
    MessageFromExc,
    ProgressMessageMaker,
    TMessageFromExc,
)
from .messages import TProgressMessageMaker as Progress
from .messages import TReprer, get_logger, get_logger_name, reprer
from .routes import Route
from .websocket_wrap import (
    Message,
    Websocket,
    WebsocketWrap,
    WrappedWebsocketHandlerOnClass,
    WSSender,
)

if tp.TYPE_CHECKING:
    from photons_web_server.server import Server

P = tp.ParamSpec("P")
T = tp.TypeVar("T")
R = tp.TypeVar("R")
C = tp.TypeVar("C", bound="Command")


@attrs.define
class NotEnoughArgs(Exception):
    reason: str


@attrs.define
class IncorrectPositionalArgument(Exception):
    reason: str


@tp.runtime_checkable
class WithCommanderClass(tp.Protocol):
    __commander_class__: type["Command"]


class CommandWebsocketWrap(WebsocketWrap):
    lc: LogContext
    logger_name: str
    instance: "Command"
    message_from_exc_maker: type[TMessageFromExc]

    def setup(self, *, instance: "Command", message_from_exc_maker: type[TMessageFromExc]):
        self.instance = instance
        self.message_from_exc_maker = message_from_exc_maker

    def message_from_exc(
        self, message: Message, exc_type: ExcTypO, exc: ExcO, tb: TBO
    ) -> ErrorMessage | Exception:
        return self.message_from_exc_maker(
            lc=self.instance.lc.using(message_id=message.id), logger_name=self.instance.logger_name
        )(exc_type, exc, tb)

    def make_wssend(
        self,
        ws: Websocket,
        reprer: TReprer,
        message: Message,
    ) -> WSSender:
        return WSSender(
            ws,
            reprer,
            message,
            self.instance.progress_message_maker(
                lc=self.instance.lc.using(message_id=message.id),
                logger_name=self.instance.logger_name,
            ),
        )


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
        progress_message_maker: type[Progress],
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

    if tp.TYPE_CHECKING:

        def ws(
            self,
            method: WrappedWebsocketHandlerOnClass,
            uri: str,
            host: None | str | list[str] = None,
            strict_slashes: None | bool = None,
            subprotocols: None | list[str] = None,
            version: None | int | str | float = None,
            name: None | str = None,
            apply: bool = True,
            version_prefix: str = "/v",
            error_format: None | str = None,
            websocket: bool = True,
            unquote: bool = False,
            static: bool = False,
            **ctx_kwargs: tp.Any,
        ) -> RouteHandler: ...

    else:

        def ws(
            self,
            method: WrappedWebsocketHandlerOnClass,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> RouteHandler:
            return self.app.add_websocket_route(self.wrap_ws(method), *args, **kwargs)

    @contextmanager
    def a_request_future(
        self, request: Request, name: str
    ) -> tp.Generator[asyncio.Future, None, None]:
        if hasattr(request.ctx, "request_future"):
            yield request.ctx.request_future
            return

        with hp.ChildOfFuture(self.final_future, name="{name}[request_future]") as request_future:
            request.ctx.request_future = request_future
            yield request_future

    def wrap_ws(self, method: WrappedWebsocketHandlerOnClass) -> RouteHandler:
        @wraps(method)
        async def handle(request: Request, ws: Websocket):
            with self._an_instance(request, method) as (_, instance):
                handler = CommandWebsocketWrap(
                    self.final_future,
                    self.server.log_ws_request,
                    self.server.log_response,
                    reprer=self.reprer,
                    instance=instance,
                    message_from_exc_maker=self.message_from_exc_maker,
                )(partial(method, instance))
                return await handler(request, ws)

        return handle

    def wrap_http(self, method: tp.Callable) -> RouteHandler:
        @wraps(method)
        async def route(request: Request, *args: tp.Any, **kwargs: tp.Any) -> Response | None:
            with self._an_instance(request, method) as (name, instance):
                ret = False
                try:
                    route = partial(method, instance)
                    progress = instance.progress_message_maker(
                        lc=instance.lc, logger_name=instance.logger_name
                    )
                    route_args = self.store.determine_http_args_and_kwargs(
                        instance.meta, route, progress, request, args, kwargs
                    )

                    if inspect.iscoroutinefunction(route):
                        t = hp.async_as_background(route(*route_args))
                        await hp.wait_for_first_future(
                            t,
                            instance.request_future,
                            name=f"{name}[run_route]",
                        )
                        if t.cancelled():
                            ret = True

                        t.cancel()
                        return await t
                    else:
                        return route(*route_args)
                except (asyncio.CancelledError, Exception):
                    exc_info = sys.exc_info()
                    if ret or exc_info[0] is not asyncio.CancelledError:
                        raise self.message_from_exc_maker(
                            lc=instance.lc, logger_name=instance.logger_name
                        )(*exc_info)

                    if exc_info[0] is asyncio.CancelledError:
                        raise sanic.exceptions.ServiceUnavailable("Cancelled")

                    raise

        tp.cast(WithCommanderClass, route).__commander_class__ = self.kls
        return tp.cast(RouteHandler, route)

    @contextmanager
    def _an_instance(
        self, request: Request, method: tp.Callable
    ) -> tp.Generator[tuple[str, C], None, None]:
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

        with self.a_request_future(request, name) as request_future:
            instance = self.kls(
                request_future,
                request,
                self.store,
                self.meta,
                self.app,
                self.server,
                self.reprer,
                self.progress_message_maker,
                identifier=request.headers[REQUEST_IDENTIFIER_HEADER],
                lc=lc,
                logger_name=logger_name,
                logger=logger,
            )
            yield name, instance


class Command:
    def __init__(
        self,
        request_future: asyncio.Future,
        request: Request,
        store: "Store",
        meta: Meta,
        app: Sanic,
        server: "Server",
        reprer: TReprer,
        progress_message_maker: type[Progress],
        identifier: str,
        *,
        lc: LogContext,
        logger: logging.Logger,
        logger_name: str,
    ):
        self.lc = lc
        self.app = app
        self.meta = meta
        self.store = store
        self.server = server
        self.reprer = reprer
        self.request = request
        self.logger_name = logger_name
        self.identifier = identifier
        self.request_future = request_future
        self.progress_message_maker = progress_message_maker

        self.log = logger
        self.setup()

    def setup(self) -> None: ...

    @classmethod
    def add_routes(kls, routes: RouteTransformer) -> None:
        pass

    def create(
        self,
        typ: type[T] | strcs.Type[T],
        value: object = strcs.NotSpecified,
        meta: Meta | None = None,
        once_only_creator: strcs.ConvertFunction[T] | None = None,
    ) -> T:
        if meta is None:
            meta = self.meta
        return self.store.strcs_register.create(
            typ, value, meta=meta, once_only_creator=once_only_creator
        )

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
    def __init__(self, *, strcs_register: strcs.CreateRegister | None = None) -> None:
        self.commands: list[type[Command]] = []
        if strcs_register is None:
            strcs_register = strcs.CreateRegister()
        self.strcs_register = strcs_register

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
        progress_message_maker: type[Progress] = ProgressMessageMaker,
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

    def determine_http_args_and_kwargs(
        self,
        meta: Meta,
        route: Route,
        progress: Progress,
        request: Request,
        args: Sequence[object],
        kwargs: dict[str, object],
    ) -> list[object]:
        signature = inspect.signature(route)
        values = list(signature.parameters.values())
        use: list[object] = []

        if values and values[0].kind is inspect.Parameter.POSITIONAL_ONLY:
            nxt = values.pop(0)
            if nxt.annotation not in (inspect._empty, Progress):
                raise IncorrectPositionalArgument(
                    "First positional only argument must be a progress object"
                )
            use.append(progress)

        if values and values[0].kind is inspect.Parameter.POSITIONAL_ONLY:
            nxt = values.pop(0)
            if nxt.annotation not in (inspect._empty, Request):
                raise IncorrectPositionalArgument(
                    "Second positional only argument must be a request object"
                )
            use.append(request)

        remaining_args = list(args)

        while values:
            nxt = values.pop(0)
            if remaining_args:
                use.append(
                    self.strcs_register.create(nxt.annotation, remaining_args.pop(0), meta=meta)
                )
                continue

            if nxt.kind is not inspect.Parameter.POSITIONAL_ONLY:
                values.insert(0, nxt)
                break

            if nxt.default is inspect._empty:
                raise NotEnoughArgs(reason="request expected more positional arguments than it got")

            use.append(self.strcs_register.create(nxt.annotation, nxt.default, meta=meta))

        use.extend(self._determine_keyword_args_and_kwargs(values, meta, request, kwargs))
        return use

    def _determine_keyword_args_and_kwargs(
        self,
        values: Sequence[inspect.Parameter],
        meta: strcs.Meta,
        request: Request,
        kwargs: dict[str, object],
    ) -> Iterator[object]:
        for nxt in values:
            if nxt.name == "_params":
                final: dict[str, object] = {}
                for k, v in request.args.items():
                    if len(v) == 1:
                        v = v[0]
                    final[k] = v
                yield self.strcs_register.create(nxt.annotation, final, meta=meta)

            elif nxt.name == "_body":
                if request.content_type == "application/json":
                    final = request.json
                else:
                    final: dict[str, object] = {}
                    for k, v in request.form.items():
                        if len(v) == 1:
                            v = v[0]
                        final[k] = v
                yield self.strcs_register.create(nxt.annotation, final, meta=meta)

            elif nxt.name in kwargs:
                yield self.strcs_register.create(nxt.annotation, kwargs.pop(nxt.name), meta=meta)

            else:
                yield meta.retrieve_one(
                    nxt.annotation,
                    nxt.name,
                    default=nxt.default,
                    type_cache=self.strcs_register.type_cache,
                )
