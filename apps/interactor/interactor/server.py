import asyncio
import time
import typing as tp

import strcs
from interactor.commander.animations import Animations
from interactor.database import DB
from photons_app import helpers as hp
from photons_app.registers import ReferenceResolverRegister
from photons_control.device_finder import DeviceFinderDaemon, Finder
from photons_web_server import commander
from photons_web_server.server import Server
from sanic.request import Request


class InteractorMessageFromExc(commander.MessageFromExc):
    def modify_error_dict(
        self,
        exc_type: commander.store.ExcTypO,
        exc: commander.store.ExcO,
        tb: commander.store.TBO,
        dct: dict[str, object],
    ) -> dict[str, object]:
        if exc_type is strcs.errors.UnableToConvert:
            if isinstance(dct.get("into"), dict):
                into = dct["into"]
                for k in ("cache", "_memoized_cache", "disassemble"):
                    if k in into:
                        del into[k]
        return dct


class InteractorServer(Server):
    store: commander.Store | None

    async def setup(
        self,
        *,
        options,
        sender,
        cleaners,
        store: commander.Store | None = None,
        animation_options=None,
        reference_resolver_register: ReferenceResolverRegister,
    ):
        if store is None:
            from interactor.commander.store import load_commands, store

            load_commands()

        self.store = store
        self.sender = sender
        self.cleaners = cleaners
        self.wsconnections: dict[str, asyncio.Future] = {}
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

        self.meta = strcs.Meta(
            dict(
                tasks=self.tasks,
                sender=self.sender,
                finder=self.finder,
                zeroconf=self.server_options.zeroconf,
                reference_resolver_register=reference_resolver_register,
                database=self.database,
                animations=self.animations,
                final_future=self.final_future,
                server_options=self.server_options,
                store=self.store,
            )
        )

        self.app.ctx.server = self
        self.app.ctx.server_time = time.time()
        self.app.ctx.server_options = self.server_options

    async def setup_routes(self):
        await super().setup_routes()
        self.store.register_commands(
            self.server_stop_future,
            self.meta,
            self.app,
            self,
            message_from_exc=InteractorMessageFromExc,
        )

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
        key = "matcher"
        add_command: dict[str, str] = {}

        if request.content_type == "application/json":
            if not request.json:
                return super().log_request_dict(request, remote_addr, identifier)

            if command := request.json.get("command"):
                add_command["command"] = command

            if isinstance(request.json.get("args"), dict) and "matcher" in request.json["args"]:
                matcher = request.json["args"]["matcher"]
            elif "selector" in request.json:
                matcher = request.json["selector"]
                key = "selector"
        else:
            if form_command := request.form.get("command"):
                add_command["command"] = form_command[0]

            if "selector" in request.form:
                matcher = request.form["selector"][0]
                key = "selector"

        return {
            **super().log_request_dict(request, remote_addr, identifier),
            key: matcher,
            **add_command,
        }
