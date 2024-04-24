import asyncio
import inspect
import logging
import sys
import time
import typing as tp
from textwrap import dedent

from delfick_project.option_merge import MergedOptions
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_app.tasks.tasks import GracefulTask
from photons_web_server.commander import (
    REQUEST_IDENTIFIER_HEADER,
    Command,
    WebsocketWrap,
    WrappedWebsocketHandler,
)
from photons_web_server.commander.messages import ErrorMessage, catch_ErrorMessage
from sanic.models.handler_types import RouteHandler
from sanic.request import Request
from sanic.response import BaseHTTPResponse as Response
from sanic.server import AsyncioServer
from sanic.server.protocols.websocket_protocol import WebSocketProtocol

try:
    import sanic
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

from sanic.config import Config as SanicConfig

log = logging.getLogger("photons_web_server.server")


class CouldntStart(PhotonsAppError):
    desc = "Couldn't start the server"


class CouldntCreate(PhotonsAppError):
    desc = "Couldn't create the server"


class Server:
    server: AsyncioServer

    sanic_server_name = "photons_web_server"

    class Config(SanicConfig):
        pass

    def __init__(
        self,
        task_holder: hp.TaskHolder,
        final_future: asyncio.Future,
        server_stop_future: asyncio.Future,
    ):
        self.lc = hp.lc.using()
        self.tasks = task_holder
        self.final_future = final_future
        self.server_stop_future = server_stop_future

    async def before_start(self) -> None:
        await self.server.before_start()

    async def after_start(self) -> None:
        await self.server.after_start()

    async def before_stop(self) -> None:
        await self.server.before_stop()

    async def after_stop(self) -> None:
        await self.server.after_stop()

    def make_config(self) -> Config:
        return self.Config()

    def make_log_config(self) -> dict:
        return {"version": 1, "disable_existing_loggers": False}

    async def make_create_server_kwargs(self, host: str, port: int, kwargs: dict) -> dict:
        return {
            k: v
            for k, v in dict(
                host=host,
                port=port,
                protocol=WebSocketProtocol,
                **MergedOptions.using(
                    kwargs,
                    {
                        "return_asyncio_server": True,
                        "asyncio_server_kwargs": {"start_serving": False},
                    },
                ).as_dict(),
            ).items()
            if k in inspect.signature(self.app.create_server).parameters
        }

    @hp.memoized_property[sanic.Sanic]
    def app(self) -> sanic.Sanic:
        return sanic.Sanic(
            self.sanic_server_name,
            config=self.make_config(),
            log_config=self.make_log_config(),
            strict_slashes=True,
        )

    async def setup(self, **kwargs) -> None:
        pass

    async def setup_routes(self) -> None:
        self.app.config.ACCESS_LOG = False
        self.app.register_middleware(self.create_request_id, "request")
        self.app.register_middleware(self.log_request, "request")
        self.app.exception(Exception)(self.attach_exception)
        self.app.register_middleware(self.log_response, "response")
        self.app.error_handler.add(ErrorMessage, catch_ErrorMessage)

    async def serve(self, host, port, **kwargs) -> None:
        create_server_kwargs = await self.make_create_server_kwargs(host, port, kwargs)

        await self.setup(**kwargs)
        await self.setup_routes()

        made = await self.app.create_server(**create_server_kwargs)
        if made is None:
            raise CouldntCreate()

        self.server = made

        try:
            self.connections = self.server.connections

            await self.server.startup()
            await self.before_start()
            await self.server.start_serving()

            if not self.server.is_serving():
                raise CouldntStart(host=host, port=port)

            self.tasks.add(self.server.serve_forever())
            self.tasks.add(self.after_start())

            await hp.wait_for_all_futures(
                self.server_stop_future, name="Server::serve[wait_for_stop]"
            )
        finally:
            exc_info = sys.exc_info()
            await self.finished()
            try:
                await self.after_stop()
            except sanic.exceptions.SanicException:
                if exc_info:
                    raise exc_info[1]
                else:
                    raise

    async def finished(self) -> None:
        if not hasattr(self, "server"):
            return

        await self.before_stop()
        if self.server.is_serving():

            for connection in self.connections:
                connection.close_if_idle()

            async with hp.tick(0.1, max_time=self.app.config.GRACEFUL_SHUTDOWN_TIMEOUT) as ticker:
                async for _ in ticker:
                    if not self.connections:
                        break

            tasks = []
            for conn in self.connections:
                if hasattr(conn, "websocket") and conn.websocket:
                    tasks.append(self.tasks.add(conn.websocket.close()))
                else:
                    conn.close()

            await hp.wait_for_all_futures(*tasks, name="Server::finished[wait_for_websockets]")
            await self.server.close()
            await self.server.wait_closed()

    def wrap_websocket_handler(self, handler: WrappedWebsocketHandler) -> RouteHandler:
        wrap = WebsocketWrap(self.server_stop_future, self.log_ws_request, self.log_response)
        return wrap(handler)

    def create_request_id(self, request: Request) -> None:
        request.ctx.interactor_request_start = time.time()
        if REQUEST_IDENTIFIER_HEADER not in request.headers:
            request.headers[REQUEST_IDENTIFIER_HEADER] = str(ulid.new())
        request.ctx.request_identifier = request.headers[REQUEST_IDENTIFIER_HEADER]

    def attach_exception(self, request: Request, exception: BaseException) -> None:
        request.ctx.exc_info = (type(exception), exception, exception.__traceback__)

    def log_request_dict(
        self, request: Request, remote_addr: str, identifier: str
    ) -> dict[str, tp.Any] | None:
        return dict(
            method=request.method,
            uri=request.path,
            scheme=request.scheme,
            remote_addr=remote_addr,
        )

    def log_request(self, request: Request, **extra_lc_context) -> None:
        method = "info"
        if getattr(request, "route", None) and getattr(request.route.ctx, "only_debug_logs", False):
            method = "debug"

        if request.scheme == "ws":
            return

        remote_addr = request.remote_addr
        identifier = request.ctx.request_identifier

        dct = self.log_request_dict(request, remote_addr, identifier)
        if dct is None:
            return

        lc = self.lc.using(request_identifier=identifier, **extra_lc_context)

        for cmd in self.maybe_commander(request):
            cmd.log_request(lc, request, identifier, dct)
            return

        getattr(log, method)(lc("Request", **dct))

    def log_ws_request(
        self, request: Request, first: tp.Any, title: str = "Websocket Request", **extra_lc_context
    ) -> None:
        remote_addr = request.remote_addr
        identifier = request.ctx.request_identifier

        dct = self.log_request_dict(request, remote_addr, identifier)
        if dct is None:
            return

        lc = self.lc.using(request_identifier=identifier, **extra_lc_context)

        for cmd in self.maybe_commander(request):
            cmd.log_ws_request(lc, request, identifier, dct, first, title=title)
            return

        log.info(lc(title, **dct, body=first))

    def log_response(self, request: Request, response: Response, **extra_lc_context) -> None:
        exc_info = getattr(request.ctx, "exc_info", None)
        took = time.time() - request.ctx.interactor_request_start
        remote_addr = request.remote_addr
        identifier = request.ctx.request_identifier

        lc = self.lc.using(request_identifier=identifier, **extra_lc_context)

        for cmd in self.maybe_commander(request):
            cmd.log_response(lc, request, response, identifier, took, exc_info)
            return

        method = "error"
        if response.status < 400:
            method = "info"

        if getattr(request, "route", None) and getattr(request.route.ctx, "only_debug_logs", False):
            method = "debug"

        getattr(log, method)(
            lc(
                "Response",
                method=request.method,
                uri=request.path,
                status=response.status,
                remote_addr=remote_addr,
                took_seconds=round(took, 2),
            ),
            exc_info=exc_info,
        )

    def maybe_commander(self, request: Request) -> tp.Generator[type[Command], None, None]:
        if hasattr(request, "route") and request.route is not None:
            handler = request.route.handler
            cmd = getattr(handler, "__commander_class__", None)
            if cmd is None:
                cmd = getattr(request.ctx, "__commander_class__", None)

            if cmd is not None:
                if isinstance(cmd, type) and issubclass(cmd, Command):
                    yield cmd


class WebServerTask(GracefulTask):
    port = 8000
    host = "0.0.0.0"
    ServerKls = Server

    @hp.asynccontextmanager
    async def server_kwargs(self) -> tp.AsyncGenerator[dict, None]:
        yield {}

    async def execute_task(self, graceful_final_future: asyncio.Future, **kwargs) -> None:
        async with self.server_kwargs() as server_kwargs:
            await self.ServerKls(
                self.task_holder,
                self.photons_app.final_future,
                graceful_final_future,
            ).serve(self.host, self.port, **server_kwargs)


__all__ = ["CouldntStart", "Server", "WebServerTask"]
