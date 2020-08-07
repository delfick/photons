from interactor.request_handlers import CommandHandler, WSHandler

from photons_app import helpers as hp

from photons_control.device_finder import DeviceFinderDaemon, Finder

from whirlwind.commander import Commander
from whirlwind.server import Server
import logging
import time

log = logging.getLogger("interactor.server")


class Server(Server):
    def __init__(self, final_future, store=None):
        if store is None:
            from interactor.commander.store import store, load_commands

            load_commands()

        self.store = store
        self.final_future = final_future
        self.wsconnections = {}

    def tornado_routes(self):
        return [
            ("/v1/lifx/command", CommandHandler, {"commander": self.commander}),
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
        ]

    async def setup(self, server_options, sender, cleaners):
        self.sender = sender
        self.cleaners = cleaners
        self.server_options = server_options

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

        self.commander = Commander(
            self.store,
            sender=self.sender,
            finder=self.finder,
            db_queue=self.db_queue,
            final_future=self.final_future,
            server_options=self.server_options,
        )

    async def cleanup(self):
        await hp.wait_for_all_futures(
            *self.wsconnections.values(), name="Server::cleanup[wait_for_wsconnections]"
        )
