from arranger.request_handlers.command import WSHandler
from arranger.arranger import Arranger

from photons_app import helpers as hp

from tornado.web import StaticFileHandler
from whirlwind.commander import Commander
from whirlwind.server import Server
import logging
import time

log = logging.getLogger("arranger.server")


class NoCacheStaticFileHandler(StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")


class Server(Server):
    def __init__(self, final_future, store=None):
        if store is None:
            from arranger.commander.store import store, load_commands

            load_commands()

        self.store = store
        self.final_future = final_future
        self.wsconnections = {}

    def tornado_routes(self):
        return [
            (
                "/v1/ws",
                WSHandler,
                {
                    "commander": self.commander,
                    "server_time": time.time(),
                    "final_future": self.final_future,
                    "wsconnections": self.wsconnections,
                },
            ),
            (
                r"/(.*)",
                NoCacheStaticFileHandler,
                {"path": self.server_options.assets.dist, "default_filename": "index.html"},
            ),
        ]

    async def setup(self, server_options, ts, sender, reference, cleaners):
        self.sender = sender
        self.cleaners = cleaners
        self.server_options = server_options

        self.tasks = ts
        self.tasks._merged_options_formattable = True
        self.cleaners.append(self.tasks.finish)

        self.arranger = Arranger(
            self.final_future, self.sender, reference, server_options.animation_options, cleaners
        )
        self.arranger._merged_options_formattable = True
        self.tasks.add(self.arranger.run())

        self.commander = Commander(
            self.store,
            tasks=self.tasks,
            arranger=self.arranger,
            final_future=self.final_future,
            server_options=self.server_options,
        )

    async def cleanup(self):
        await hp.wait_for_all_futures(
            *self.wsconnections.values(), name="Server::cleanup[wait_for_wsconnections]"
        )
