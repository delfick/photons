import attrs
import strcs
from interactor.commander.store import Command, Store, reg, store
from photons_web_server import commander

strcs.Meta


@attrs.define
class LegacyBody:
    command: str
    args: dict[str, object] = attrs.field(factory=dict)


@store.command
class LegacyCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.http(kls.legacy_put, "/v1/lifx/command", methods=["PUT"], name="v1_lifx_command_put")
        routes.ws(kls.legacy_ws, "/v1/ws", name="v1_lifx_ws")

    async def legacy_put(
        self,
        progress: commander.Progress,
        request: commander.Request,
        /,
        _body: LegacyBody,
        _meta: object,
        store: Store,
        route_transformer: commander.RouteTransformer,
    ) -> commander.Response:
        return await store.run_v1_http(
            progress,
            request,
            command=_body.command,
            args=_body.args,
            _meta=_meta,
            route_transformer=route_transformer,
        )

    async def legacy_ws(
        self,
        wssend: commander.WSSender,
        message: commander.Message,
    ) -> bool | None:
        route_transformer = self.meta.retrieve_one(
            commander.RouteTransformer, type_cache=reg.type_cache
        )
        assert wssend.progress is not None
        store = self.meta.retrieve_one(Store, "store", type_cache=reg.type_cache)
        return await store.run_v1_ws(
            wssend, message, _meta=self.meta, route_transformer=route_transformer
        )
