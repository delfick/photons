import attrs
from interactor.commander.store import Command, reg, store
from photons_web_server import commander


@attrs.define
class SIOBody:
    path: str
    method: str = "GET"
    body: dict[str, object] = attrs.field(factory=dict)
    params: dict[str, object] = attrs.field(factory=dict)


@attrs.define
class InvalidRoute(Exception):
    pass


@store.command
class SIOCommands(Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.sio("command", kls.respond)

    async def respond(
        self,
        respond: commander.Responder,
        message: commander.Message,
    ) -> None:
        route_transformer = self.meta.retrieve_one(
            commander.RouteTransformer, type_cache=reg.type_cache
        )
        body = self.create(SIOBody, message.body)
        route = route_transformer.app.router.resolve(path=body.path, method=body.method)
        if not route:
            await respond(InvalidRoute())

        handler = route[0].handler
        if not route or not (cmd := getattr(handler, "__commander_class__", None)):
            await respond(InvalidRoute())
            return

        with route_transformer.instantiate_route(message.request, cmd, handler) as route:
            route_args = self.store.determine_http_args_and_kwargs(
                self.meta,
                route,
                respond.progress,
                message.request,
                (),
                {"_body_raw": body.body, "_params_raw": body.params},
            )
            response = await route(*route_args)
            await respond(response.raw_body)
            return
