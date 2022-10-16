import time
import typing as tp

from interactor.commander.animations import Animations
from interactor.database import DB
from photons_app import helpers as hp
from photons_control.device_finder import DeviceFinderDaemon, Finder
from photons_web_server.commander import Store
from photons_web_server.server import Server
from sanic.request import Request
from strcs import Meta


class Server(Server):
    store: Store | None

    async def setup(
        self, *, options, sender, cleaners, store: Store | None = None, animation_options=None
    ):
        if store is None:
            from interactor.commander.store import load_commands, store

            load_commands()

        self.store = store
        self.sender = sender
        self.cleaners = cleaners
        self.wsconnections = {}
        self.server_options = options
        self.animation_options = animation_options

        self.database = DB(self.server_options.database.uri)
        self.database._merged_options_formattable = True
        self.cleaners.append(self.database.finish)

        self.finder = Finder(sender, final_future=self.final_future)
        self.cleaners.append(self.finder.finish)

        self.daemon = DeviceFinderDaemon(
            sender, finder=self.finder, **self.server_options.daemon_options
        )
        self.cleaners.append(self.daemon.finish)

        self.animations = Animations(
            self.final_future, self.tasks, self.sender, self.animation_options
        )
        self.meta = (
            Meta(
                dict(
                    tasks=self.tasks,
                    sender=self.sender,
                    finder=self.finder,
                    zeroconf=self.server_options.zeroconf,
                    database=self.database,
                    animations=self.animations,
                    final_future=self.final_future,
                    server_options=self.server_options,
                )
            ),
        )

        self.app.ctx.server = self
        self.app.ctx.server_time = time.time()
        self.app.ctx.server_options = self.server_options

    async def setup_routes(self):
        await super().setup_routes()
        self.app.add_route(self.commander.http_handler, "/v1/lifx/command", methods=["PUT"])
        self.app.add_websocket_route(
            self.wrap_websocket_handler(self.commander.ws_handler), "/v1/ws"
        )
        self.store.register_commands(self.server_stop_future, self.meta, self.app, self)

    async def before_start(self):
        await self.server_options.zeroconf.start(
            self.tasks, self.server_options.host, self.server_options.port, self.sender, self.finder
        )
        await self.database.start()
        await self.daemon.start()

    async def before_stop(self):
        self.tasks.add(self.animations.stop())
        self.tasks.add(self.server_options.zeroconf.finish())
        await hp.wait_for_all_futures(
            *self.wsconnections.values(), name="Server::cleanup[wait_for_wsconnections]"
        )

    def log_request_dict(
        self, request: Request, remote_addr: str, identifier: str
    ) -> dict[str, tp.Any] | None:
        matcher = None
        if (
            isinstance(request.json, dict)
            and isinstance(request.json.get("args"), dict)
            and "matcher" in request.json["args"]
        ):
            matcher = request.json["args"]["matcher"]

        return {
            **super().log_request_dict(request, remote_addr, identifier),
            "matcher": matcher,
        }
