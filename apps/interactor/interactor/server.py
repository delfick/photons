from interactor.request_handlers import CommandHandler, WSHandler
from interactor.commander.animations import Animations

from photons_app import helpers as hp

from photons_control.device_finder import DeviceFinderDaemon, Finder

from whirlwind.commander import Commander
from whirlwind.server import Server
import tornado.web
import logging
import time
import uuid

log = logging.getLogger("interactor.server")

REQUEST_IDENTIFIER_HEADER = "X-Request-ID"


class Commander(Commander):
    def peek_valid_request(self, meta, command, path, body):
        request = meta.everything["request_handler"].request

        if isinstance(body, dict) and "command" in body:
            request.__whirlwind_commander_command__ = body["command"]

            if body["command"] == "status":
                return

        command = getattr(request, "__whirlwind_commander_command__", None)
        remote_ip = request.remote_ip
        identifier = request.headers[REQUEST_IDENTIFIER_HEADER]

        matcher = None
        if (
            isinstance(body, dict)
            and isinstance(body.get("args"), dict)
            and "matcher" in body["args"]
        ):
            matcher = body["args"]["matcher"]

        log.info(
            hp.lc(
                "Command",
                method=request.method,
                uri=request.uri,
                path=path,
                command=command,
                matcher=matcher,
                remote_ip=remote_ip,
                request_identifier=identifier,
            )
        )


class WithRequestTracing:
    def __init__(self, app):
        self.app = app

    def __call__(self, request):
        request.__interactor_request_start__ = time.time()
        if REQUEST_IDENTIFIER_HEADER not in request.headers:
            request.headers[REQUEST_IDENTIFIER_HEADER] = str(uuid.uuid4())
        return self.app(request)


class OutputRequestID(tornado.web.OutputTransform):
    def __init__(self, request):
        self.request = request
        self.identifier = request.headers[REQUEST_IDENTIFIER_HEADER]
        super().__init__(request)

    def transform_first_chunk(self, status_code, headers, chunk, finishing):
        headers[REQUEST_IDENTIFIER_HEADER] = self.identifier

        request = self.request
        took = time.time() - request.__interactor_request_start__
        command = getattr(request, "__whirlwind_commander_command__", None)
        remote_ip = request.remote_ip
        identifier = request.headers[REQUEST_IDENTIFIER_HEADER]

        if command != "status":
            method = "error"
            if status_code < 400:
                method = "info"

            getattr(log, method)(
                hp.lc(
                    "Response",
                    method=request.method,
                    uri=request.uri,
                    status=status_code,
                    command=command,
                    remote_ip=remote_ip,
                    took_seconds=round(took, 2),
                    request_identifier=identifier,
                )
            )

        return super().transform_first_chunk(status_code, headers, chunk, finishing)


class Server(Server):
    def __init__(self, final_future, *, server_end_future, store=None):
        super().__init__(final_future, server_end_future=server_end_future)

        if store is None:
            from interactor.commander.store import store, load_commands

            load_commands()

        self.store = store
        self.wsconnections = {}

    async def wait_for_end(self):
        await hp.wait_for_all_futures(self.server_end_future, name="Server::wait_for_end")

    def make_application(self, *args, **kwargs):
        app = super().make_application(*args, **kwargs)
        app.add_transform(OutputRequestID)
        return WithRequestTracing(app)

    def tornado_routes(self):
        return [
            ("/v1/lifx/command", CommandHandler, {"commander": self.commander}),
            (
                "/v1/ws",
                WSHandler,
                {
                    "commander": self.commander,
                    "server_time": time.time(),
                    "final_future": self.server_end_future,
                    "wsconnections": self.wsconnections,
                },
            ),
        ]

    async def setup(self, server_options, *, tasks, sender, cleaners, animation_options=None):
        self.sender = sender
        self.cleaners = cleaners
        self.server_options = server_options
        self.animation_options = animation_options

        self.tasks = tasks
        self.tasks._merged_options_formattable = True

        self.db_queue = __import__("interactor.database.db_queue").database.db_queue.DBQueue(
            self.final_future, 5, lambda exc: 1, self.server_options.database.uri
        )
        self.cleaners.append(self.db_queue.finish)
        self.db_queue.start()

        self.finder = Finder(sender, final_future=self.final_future)
        self.finder._merged_options_formattable = True
        self.cleaners.append(self.finder.finish)

        self.daemon = DeviceFinderDaemon(sender, finder=self.finder)
        self.cleaners.append(self.daemon.finish)
        await self.daemon.start()

        self.animations = Animations(
            self.final_future, self.tasks, self.sender, self.animation_options
        )
        self.animations._merged_options_formattable = True

        self.commander = Commander(
            self.store,
            tasks=self.tasks,
            sender=self.sender,
            finder=self.finder,
            db_queue=self.db_queue,
            animations=self.animations,
            final_future=self.final_future,
            server_options=self.server_options,
        )

    async def cleanup(self):
        self.tasks.add(self.animations.stop())
        await hp.wait_for_all_futures(
            *self.wsconnections.values(), name="Server::cleanup[wait_for_wsconnections]"
        )
