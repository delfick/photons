import asyncio
import time
from collections.abc import Callable

import strcs
from photons_app import helpers as hp
from photons_app.special import SpecialReference
from photons_transport.comms.base import Communication
from photons_web_server import commander
from photons_web_server.server import Server
from sanic.request import Request
from sanic.response import BaseHTTPResponse as Response

from arranger.arranger import Arranger
from arranger.commander.parts import PartRouter
from arranger.options import Options


class ArrangerMessageFromExc(commander.MessageFromExc):
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


class ArrangerServer(Server):
    store: commander.Store | None

    async def setup(
        self,
        *,
        reference: SpecialReference,
        sender: Communication,
        options: Options,
        cleaners: list[Callable[[], None]],
        store: commander.Store | None = None,
    ):
        if store is None:
            from arranger.commander.store import load_commands, store

            load_commands()

        self.store = store
        self.sender = sender
        self.cleaners = cleaners
        self.server_options = options
        self.wsconnections: dict[str, asyncio.Future] = {}

        self.arranger = Arranger(self.final_future, self.sender, reference, options.animation_options, cleaners)
        self.tasks.add(self.arranger.run())

        self.meta = strcs.Meta(
            dict(
                tasks=self.tasks,
                arranger=self.arranger,
                final_future=self.final_future,
                server_options=self.server_options,
                part_router=PartRouter(),
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
            message_from_exc=ArrangerMessageFromExc,
        )

        self.app.static("/", self.server_options.assets.dist, index="index.html")

    async def before_stop(self):
        await hp.wait_for_all_futures(*self.wsconnections.values(), name="Server::cleanup[wait_for_wsconnections]")

    def log_ws_request(
        self,
        request: Request,
        first: object,
        *,
        title: str = "Websocket Request",
        **extra_lc_context,
    ) -> None:
        if first == {"path": "__tick__"}:
            request.ctx.is_tick = True
            return
        else:
            return super().log_ws_request(request, first, title=title, **extra_lc_context)

    def log_response(self, request: Request, response: Response, **extra_lc_context) -> None:
        if hasattr(request.ctx, "is_tick"):
            return
        else:
            return super().log_response(request, response, **extra_lc_context)
