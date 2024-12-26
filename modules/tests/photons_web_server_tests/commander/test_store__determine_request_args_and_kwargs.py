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


class TestDeterminingRequestArgsAndKwargs:
    @pytest.fixture
    def store(self) -> Store:
        return Store(strcs_register=register)

    @pytest.fixture
    def progress(self) -> Progress:
        return ProgressMessageMaker(lc=lc(), logger_name="test")

    async def test_it_can_pass_in_progress_and_request(self, store: Store, progress: Progress, app: sanic.Sanic):
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, /) -> None:
            called.append((progress, request))
            return None

        use = store.determine_http_args_and_kwargs(strcs.Meta(), route, progress, request, [1, 2], {1: 2})
        assert use == [progress, request]

    async def test_it_can_regcreate_missing_positionals_with_NotSpecified(self, store: Store, progress: Progress, app: sanic.Sanic):
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, thing: Thing, /) -> None:
            called.append((progress, request, thing))
            return None

        use = store.determine_http_args_and_kwargs(strcs.Meta(), route, progress, request, [], {})
        assert use == [progress, request, Thing(val="-1")]

    async def test_it_can_pass_in_progress_and_request_when_no_annotations(self, store: Store, progress: Progress, app: sanic.Sanic):
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress, request, /):
            called.append((progress, request))
            return None

        use = store.determine_http_args_and_kwargs(strcs.Meta(), route, progress, request, [1, 2], {1: 2})
        assert use == [progress, request]

    async def test_it_complains_if_first_argument_isnt_annotated_as_Progress(self, store: Store, progress: Progress, app: sanic.Sanic):
        request, _ = await app.asgi_client.get("/")

        def route(request: Request, progress: Progress, /) -> None:
            return None

        with pytest.raises(IncorrectPositionalArgument):
            store.determine_http_args_and_kwargs(strcs.Meta(), route, progress, request, [1, 2], {1: 2})

        def route2(progress: Progress, other: int, /) -> None:
            return None

        with pytest.raises(IncorrectPositionalArgument):
            store.determine_http_args_and_kwargs(strcs.Meta(), route2, progress, request, [1, 2], {1: 2})

    async def test_it_can_pass_in_positional_args(self, store: Store, progress: Progress, app: sanic.Sanic):
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, one: int, /, two: int, three: str) -> None:
            called.append((progress, request))
            return None

        use = store.determine_http_args_and_kwargs(strcs.Meta(), route, progress, request, [1, 2], {"four": "six", "three": "five"})
        assert use == [progress, request, 1, 2, "five"]

    async def test_it_will_not_try_to_get_positional_only_from_meta(self, store: Store, progress: Progress, app: sanic.Sanic):
        request, _ = await app.asgi_client.get("/")

        def route(progress: Progress, request: Request, one: int, /, two: int, three: str) -> None:
            return None

        with pytest.raises(NotEnoughArgs):
            store.determine_http_args_and_kwargs(strcs.Meta({"one": 1}), route, progress, request, [], {})

    async def test_it_will_use_default_if_positional_only_has_no_arg(self, store: Store, progress: Progress, app: sanic.Sanic):
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, one: int = 10, /) -> None:
            called.append((progress, request))
            return None

        use = store.determine_http_args_and_kwargs(strcs.Meta({"one": 1}), route, progress, request, [], {})
        assert use == [progress, request, 10]

    async def test_it_can_get_the_meta_object(self, store: Store, progress: Progress, app: sanic.Sanic):
        request, _ = await app.asgi_client.get("/")

        called: list[tuple[Progress, Request]] = []

        def route(progress: Progress, request: Request, /, _meta: strcs.Meta) -> None:
            called.append((progress, request, meta))
            return None

        meta = strcs.Meta({"one": 1})
        use = store.determine_http_args_and_kwargs(meta, route, progress, request, [], {})
        assert use == [progress, request, meta]
