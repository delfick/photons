from typing import ClassVar

import sanic
import strcs
from interactor.commander.store import Command, store
from photons_web_server import commander


@store.command
class StatusCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.status, "/v2/status", name="v2_status_get")
        routes.http(kls.status, "/v1/lifx/status", name="v1_status_get")

    async def status(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
    ) -> commander.Response:
        return sanic.json({"on": True})

    implements_v1_commands: ClassVar[set[str]] = {"status"}

    @classmethod
    def help_for_v1_command(cls, command: str, type_cache: strcs.TypeCache) -> str | None:
        if command not in cls.implements_v1_commands:
            return None
        return 'Return {"on": True}'

    async def run_v1_http(
        self,
        progress: commander.Progress,
        request: commander.Request,
        *,
        command: str,
        args: dict[str, object],
        meta: strcs.Meta,
    ) -> commander.Response | None:
        if command in self.implements_v1_commands:
            return await self.status(progress, request)
