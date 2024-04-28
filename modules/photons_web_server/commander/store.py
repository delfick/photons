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
import socketio
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
from .messages import TReprer
from .messages import TResponseMaker as Responder
from .messages import get_logger, get_logger_name, reprer
from .routes import Route
from .stream_wrap import (
    Message,
    SocketioRoomEvent,
    SocketioSender,
    SocketioWrap,
    Websocket,
    WebsocketWrap,
    WrappedSocketioHandlerOnClass,
    WrappedWebsocketHandlerOnClass,
    WSSender,
)

if tp.TYPE_CHECKING:
    from photons_web_server.server import Server

P = tp.ParamSpec("P")
T = tp.TypeVar("T")
R = tp.TypeVar("R")
C = tp.TypeVar("C", bound="Command")
C_Other = tp.TypeVar("C_Other", bound="Command")


@attrs.define
class NoSocketIOServerSetup(Exception):
    pass


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

    def make_responder(
        self,
        transport: Websocket,
        reprer: TReprer,
        message: Message,
    ) -> Responder:
        return WSSender(
            transport,
            reprer,
            message,
            self.instance.progress_message_maker(
                lc=self.instance.lc.using(message_id=message.id),
                logger_name=self.instance.logger_name,
            ),
        )


class CommandSocketioWrap(SocketioWrap):
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

    def make_responder(
        self,
        transport: Websocket,
        reprer: TReprer,
        message: Message,
    ) -> Responder:
        return SocketioSender(
            transport,
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
        self.meta = meta.clone({"route_transformer": self})
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

    def sio(self, event: str, method: WrappedSocketioHandlerOnClass) -> RouteHandler:
        return self.store.sio.on(event)(
            self.wrap_sio(method, specific_event=None if event == "*" else event)
        )

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

    def wrap_sio(
        self, method: WrappedSocketioHandlerOnClass, specific_event: str | None
    ) -> RouteHandler:
        @wraps(method)
        async def handle(sid: str, *data: object):
            if specific_event is None:
                event = sid
                sid = data[0]
                assert isinstance(sid, str)
            else:
                event = specific_event

            async with self.store.sio.session(sid) as session:
                if "lock" not in session:
                    session["lock"] = asyncio.Lock()

            room = SocketioRoomEvent(
                lock=session["lock"], sio=self.store.sio, sid=sid, data=data, event=event
            )
            request = self.store.sio.get_environ(sid)["sanic.request"]

            with self._an_instance(request, method) as (_, instance):
                handler = CommandSocketioWrap(
                    self.final_future,
                    self.server.log_ws_request,
                    self.server.log_response,
                    reprer=self.reprer,
                    instance=instance,
                    message_from_exc_maker=self.message_from_exc_maker,
                )(partial(method, instance))
                return await handler(request, room)

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
    def instantiate_route(
        self, request: Request, kls: type["Command"], method: tp.Callable[P, R]
    ) -> tp.Generator[tp.Callable[P, R], None, None]:
        with self._an_instance(request, method, kls=kls) as (_, instance):
            route = getattr(instance, method.__name__)
            route_name = f"{route.__func__.__module__}.{route.__func__.__qualname__}"
            method_name = f"{method.__module__}.{method.__qualname__}"
            assert route_name == method_name
            yield route

    @tp.overload
    @contextmanager
    def _an_instance(
        self, request: Request, method: tp.Callable[..., object], kls: type[C_Other]
    ) -> tp.Generator[tuple[str, C_Other], None, None]: ...

    @tp.overload
    @contextmanager
    def _an_instance(
        self, request: Request, method: tp.Callable[..., object], kls: None
    ) -> tp.Generator[tuple[str, C], None, None]: ...

    @contextmanager
    def _an_instance(
        self, request: Request, method: tp.Callable[..., object], kls: type["Command"] | None = None
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

        if kls is None:
            kls = self.kls

        with self.a_request_future(request, name) as request_future:
            instance = kls(
                request_future,
                request,
                self.store,
                self.meta.clone(),
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
        title: str = "Websocket Request",
    ):
        info = kls.log_ws_request_dict(request, identifier, dct, first, exc_info)
        if not info:
            return

        get_logger(1).info(lc(title, **info, body=first))

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
    _sio: socketio.AsyncServer | None = None

    def __init__(self, *, strcs_register: strcs.CreateRegister | None = None) -> None:
        self.commands: list[type[Command]] = []
        if strcs_register is None:
            strcs_register = strcs.CreateRegister()
        self.strcs_register = strcs_register

    @property
    def sio(self) -> socketio.AsyncServer:
        if self._sio is None:
            raise NoSocketIOServerSetup()
        return self._sio

    def add_sio_server(self, sio: socketio.AsyncServer) -> None:
        self._sio = sio

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

        if (
            values
            and values[0].kind is inspect.Parameter.POSITIONAL_ONLY
            and values[0].name == "self"
            and values[0].annotation is inspect._empty
        ):
            values.pop(0)

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
                try:
                    use.append(
                        self.strcs_register.create(
                            nxt.annotation, kwargs.pop(nxt.name, strcs.NotSpecified), meta=meta
                        )
                    )
                except (TypeError, ValueError) as e:
                    raise NotEnoughArgs(
                        reason="request expected more positional arguments than it got"
                    ) from e

                continue

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
        body_raw: dict[str, object] = {}
        params_raw: dict[str, object] = {}

        if any(nxt.name in ("_body", "_body_raw") for nxt in values):
            if "_body_raw" in kwargs and isinstance(kwargs["_body_raw"], dict):
                body_raw.update(kwargs["_body_raw"])
            elif request.content_type == "application/json":
                body_raw = request.json
            else:
                for k, v in request.form.items():
                    if len(v) == 1:
                        v = v[0]
                    body_raw[k] = v

        if any(nxt.name in ("_params", "_params_raw") for nxt in values):
            if "_params_raw" in kwargs and isinstance(kwargs["_params_raw"], dict):
                params_raw.update(kwargs["_params_raw"])
            else:
                for k, v in request.args.items():
                    if len(v) == 1:
                        v = v[0]
                    params_raw[k] = v

        for nxt in values:
            if nxt.name == "_params":
                yield self.strcs_register.create(nxt.annotation, params_raw, meta=meta)

            elif nxt.name == "_params_raw":
                yield params_raw

            elif nxt.name == "_body":
                yield self.strcs_register.create(nxt.annotation, body_raw, meta=meta)

            elif nxt.name == "_body_raw":
                yield body_raw

            elif nxt.name == "_meta":
                yield meta

            elif nxt.name in kwargs:
                yield self.strcs_register.create(nxt.annotation, kwargs.pop(nxt.name), meta=meta)

            else:
                yield meta.retrieve_one(
                    nxt.annotation,
                    nxt.name,
                    default=nxt.default,
                    type_cache=self.strcs_register.type_cache,
                )
