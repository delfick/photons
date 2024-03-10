# coding: spec

import attrs
import pytest
import sanic
import strcs
from delfick_project.logging import lc
from photons_web_server.commander import (
    IncorrectPositionalArgument,
    NotEnoughArgs,
    Progress,
    ProgressMessageMaker,
    Request,
    Response,
    Store,
)

register = strcs.CreateRegister()
creator = register.make_decorator()


@attrs.define
class MetaObjectOne:
    string_value: str


@attrs.define
class MetaObjectTwo:
    int_value: int


@attrs.define
class Thing:
    val: str


@creator(Thing)
def make_thing(val: object, /) -> strcs.ConvertResponse[Thing]:
    if isinstance(val, int):
        return {"val": f"DOUBLED: {val * 2}"}
    elif val is strcs.NotSpecified:
        return {"val": -1}

    return None


@pytest.fixture
def app() -> sanic.Sanic:
    app = sanic.Sanic("test")

    @app.route("/")
    def index(request: Request) -> Response:
        return sanic.text("hi")

    return app


describe "Determining request args and kwargs":

    @pytest.fixture
    def store(self) -> Store:
        return Store(strcs_register=register)

    @pytest.fixture
    def progress(self) -> Progress:
        return ProgressMessageMaker(lc=lc(), logger_name="test")

    async it "can pass in progress and request", store: Store, progress: Progress, app: sanic.Sanic:
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, /) -> None:
            called.append((progress, request))
            return None

        use = store.determine_http_args_and_kwargs(
            strcs.Meta(), route, progress, request, [1, 2], {1: 2}
        )
        assert use == [progress, request]

    async it "can pass in progress and request when no annotations", store: Store, progress: Progress, app: sanic.Sanic:
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress, request, /):
            called.append((progress, request))
            return None

        use = store.determine_http_args_and_kwargs(
            strcs.Meta(), route, progress, request, [1, 2], {1: 2}
        )
        assert use == [progress, request]

    async it "complains if first argument isn't annotated as Progress", store: Store, progress: Progress, app: sanic.Sanic:
        request, _ = await app.asgi_client.get("/")

        def route(request: Request, progress: Progress, /) -> None:
            return None

        with pytest.raises(IncorrectPositionalArgument):
            store.determine_http_args_and_kwargs(
                strcs.Meta(), route, progress, request, [1, 2], {1: 2}
            )

        def route2(progress: Progress, other: int, /) -> None:
            return None

        with pytest.raises(IncorrectPositionalArgument):
            store.determine_http_args_and_kwargs(
                strcs.Meta(), route2, progress, request, [1, 2], {1: 2}
            )

    async it "can pass in positional args", store: Store, progress: Progress, app: sanic.Sanic:
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, one: int, /, two: int, three: str) -> None:
            called.append((progress, request))
            return None

        use = store.determine_http_args_and_kwargs(
            strcs.Meta(), route, progress, request, [1, 2], {"four": "six", "three": "five"}
        )
        assert use == [progress, request, 1, 2, "five"]

    async it "will not try to get positional_only from meta", store: Store, progress: Progress, app: sanic.Sanic:
        request, _ = await app.asgi_client.get("/")

        def route(progress: Progress, request: Request, one: int, /, two: int, three: str) -> None:
            return None

        with pytest.raises(NotEnoughArgs):
            store.determine_http_args_and_kwargs(
                strcs.Meta({"one": 1}), route, progress, request, [], {}
            )

    async it "will use default if positional only has no arg", store: Store, progress: Progress, app: sanic.Sanic:
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, one: int = 10, /) -> None:
            called.append((progress, request))
            return None

        use = store.determine_http_args_and_kwargs(
            strcs.Meta({"one": 1}), route, progress, request, [], {}
        )
        assert use == [progress, request, 10]

    async it "can get the meta object", store: Store, progress: Progress, app: sanic.Sanic:
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, /, _meta: strcs.Meta) -> None:
            called.append((progress, request, meta))
            return None

        meta = strcs.Meta({"one": 1})
        use = store.determine_http_args_and_kwargs(meta, route, progress, request, [], {})
        assert use == [progress, request, meta]
