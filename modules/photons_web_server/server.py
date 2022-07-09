import asyncio
import inspect
import logging
import time
import typing as tp
import uuid
from textwrap import dedent

from delfick_project.option_merge import MergedOptions
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_app.tasks.tasks import GracefulTask
from photons_web_server.commander import REQUEST_IDENTIFIER_HEADER
from sanic.request import Request
from sanic.response import BaseHTTPResponse as Response
from sanic.server import AsyncioServer

try:
    import sanic
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

    async def make_create_server_kwargs(self, host, port, kwargs) -> dict:
        return {
            k: v
            for k, v in dict(
                host=host,
                port=port,
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
            self.sanic_server_name, config=self.make_config(), log_config=self.make_log_config()
        )

    async def setup(self, **kwargs) -> None:
        pass

    async def setup_routes(self) -> None:
        self.app.config.ACCESS_LOG = False
        self.app.register_middleware(self.create_request_id, "request")
        self.app.register_middleware(self.log_request, "request")
        self.app.register_middleware(self.log_response, "response")

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
            await self.finished()
            await self.after_stop()

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
                    tasks.append(self.tasks.add(conn.websocket.close_connection()))
                else:
                    conn.close()

            await hp.wait_for_all_futures(*tasks, name="Server::finished[wait_for_websockets]")
            await self.server.close()
            await self.server.wait_closed()

    def create_request_id(self, request: Request) -> None:
        request.ctx.interactor_request_start = time.time()
        if REQUEST_IDENTIFIER_HEADER not in request.headers:
            request.headers[REQUEST_IDENTIFIER_HEADER] = str(uuid.uuid4())

    def log_request(self, request: Request) -> None:
        path = None
        command = None
        if isinstance(request.json, dict) and "command" in request.json:
            path = request.ctx.commander_path = request.json.get("path", None)
            command = request.ctx.commander_command = request.json["command"]

            if command == "status":
                return

        remote_addr = request.remote_addr
        identifier = request.headers[REQUEST_IDENTIFIER_HEADER]

        matcher = None
        if (
            isinstance(request.json, dict)
            and isinstance(request.json.get("args"), dict)
            and "matcher" in request.json["args"]
        ):
            matcher = request.json["args"]["matcher"]

        log.info(
            hp.lc(
                "Command",
                method=request.method,
                uri=request.path,
                path=path,
                command=command,
                matcher=matcher,
                remote_addr=remote_addr,
                request_identifier=identifier,
            )
        )

    def log_response(self, request: Request, response: Response) -> None:
        took = time.time() - request.ctx.interactor_request_start
        command = getattr(request.ctx, "commander_command", None)
        remote_addr = request.remote_addr
        identifier = request.headers[REQUEST_IDENTIFIER_HEADER]

        if command != "status":
            method = "error"
            if response.status < 400:
                method = "info"

            getattr(log, method)(
                hp.lc(
                    "Response",
                    method=request.method,
                    uri=request.path,
                    status=response.status,
                    command=command,
                    remote_addr=remote_addr,
                    took_seconds=round(took, 2),
                    request_identifier=identifier,
                )
            )


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
