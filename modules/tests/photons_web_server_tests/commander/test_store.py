# coding: spec
import asyncio
import time
import types
import typing as tp
from collections import defaultdict
from textwrap import dedent
from unittest.mock import ANY

import attrs
import pytest
import sanic
import strcs
from attrs import define
from delfick_project.errors import DelfickError
from photons_app import helpers as hp
from photons_web_server import pytest_helpers as pws_thp
from photons_web_server.commander import (
    Command,
    Message,
    Progress,
    RouteTransformer,
    Store,
    WSSender,
)
from photons_web_server.server import Server
from sanic.request import Request
from sanic.response import HTTPResponse as Response


class Between:
    compare: object | None

    def __init__(self, frm: float, to: float):
        self.frm = frm
        self.to = to
        self.compare = None

    def __eq__(self, compare: object) -> bool:
        self.compare = compare
        if not isinstance(self.compare, float):
            return False
        return self.frm <= self.compare <= self.to

    def __repr__(self) -> str:
        if self.compare is None:
            return f"<Between {self.frm} and {self.to}/>"
        else:
            return repr(self.compare)


describe "Store":
    async it "makes it easy to add routes to particular methods of new instances of the command", final_future: asyncio.Future, fake_event_loop:
        made: list[tuple[Command, int]] = []

        store = Store()

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route1, "route1/<one:int>")
                routes.http(kls.route2, "route2", methods=["PUT"])

            def route1(s, progress: Progress, request: Request, /, one: int) -> Response | None:
                made.append((s, one))
                return sanic.text("route1")

            def route2(s, progress: Progress, request: Request, /) -> Response | None:
                made.append((s, -1))
                return sanic.text("route2")

        async def setup_routes(server: Server) -> None:
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res1 = await srv.start_request("GET", "/route1/20")
            res2 = await srv.start_request("PUT", "/route2", {"command": "one"})

        assert (await res1.text()) == "route1"
        assert (await res2.text()) == "route2"

        assert made == [(pytest.helpers.IsInstance(C), 20), (pytest.helpers.IsInstance(C), -1)]
        assert made[0][0] is not made[1][0]

    async it "supports async routes", final_future: asyncio.Future, fake_event_loop:
        made: list[object] = []
        done_things = hp.create_future()

        store = Store()
        time_at_wait = 0

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route1, "route1")

            async def route1(s, progress: Progress, request: Request, /) -> Response | None:
                async def things():
                    t = time.time()
                    await hp.wait_for_first_future(s.request_future)
                    made.append(int(time.time() - t))
                    done_things.set_result(True)

                made.append(s.server.tasks.add(things()))

                nonlocal time_at_wait
                time_at_wait = time.time()
                await asyncio.sleep(3)
                return sanic.text("route1")

        async def setup_routes(server: Server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res1 = await srv.start_request("GET", "/route1")

        assert (await res1.text()) == "route1"
        await done_things

        assert made == [pytest.helpers.IsInstance(asyncio.Task), 3]
        assert time.time() == 3 + time_at_wait

    async it "can do dependency injection based on signature args", final_future: asyncio.Future, fake_event_loop:
        store = Store()

        class Thing: ...

        original_thing = Thing()

        @attrs.define
        class SyncBody:
            one: int
            two: str

        @attrs.define
        class SyncParams:
            three: str
            four: list[str]

        called: list[tuple[object, ...]] = []

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.async_route, "async_route")
                routes.http(kls.sync_route, "sync_route", methods=["PUT"])

            async def async_route(
                s, progress: Progress, request: Request, /, _meta: strcs.Meta, thing: Thing
            ) -> Response | None:
                called.append(("async_route", _meta, thing))
                return sanic.text("async_route")

            async def sync_route(
                s,
                progress: Progress,
                request: Request,
                /,
                _body: SyncBody,
                _params: SyncParams,
                thing: Thing,
            ) -> Response | None:
                called.append(("sync_route", _body, _params, thing))
                return sanic.text("sync_route")

        meta = strcs.Meta({"thing": original_thing})

        async def setup_routes(server: Server):
            store.register_commands(server.server_stop_future, meta, server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res1 = await srv.start_request("GET", "/async_route")
            res2 = await srv.start_request(
                "PUT", "/sync_route?three=3&four=thing&four=stuff", {"one": 2, "two": "blah"}
            )

        assert (await res1.text()) == "async_route"
        assert (await res2.text()) == "sync_route"

        class IsMeta:
            def __eq__(self, o: object) -> bool:
                assert (
                    isinstance(o, strcs.Meta)
                    and all(o.data[k] == v for k, v in meta.data.items())
                    and o is not meta
                )
                return True

        assert called == [
            ("async_route", IsMeta(), original_thing),
            (
                "sync_route",
                SyncBody(one=2, two="blah"),
                SyncParams(three="3", four=["thing", "stuff"]),
                original_thing,
            ),
        ]

    async it "provides the ability to turn a function on a Command class into a bound method", final_future: asyncio.Future, fake_event_loop:
        store = Store()

        @attrs.define
        class Thing:
            param: str

        @store.command
        class COther(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route2, "route2")

            async def route2(
                s, progress: Progress, request: Request, /, thing: Thing
            ) -> Response | None:
                return sanic.text(thing.param)

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route1, "route1")

            async def route1(
                s, progress: Progress, request: Request, /, route_transformer: RouteTransformer
            ) -> Response | None:
                with route_transformer.instantiate_route(request, COther, COther.route2) as route:
                    return await route(progress, request, thing=Thing(param="blah"))

        async def setup_routes(server: Server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res1 = await srv.start_request("GET", "/route1")

        assert (await res1.text()) == "blah"

    async it "understands when the route itself raises a CancelledError", final_future: asyncio.Future, fake_event_loop:
        store = Store()

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route1, "route1")

            async def route1(s, progress: Progress, request: Request, /) -> Response | None:
                fut = hp.create_future()
                fut.cancel()
                await fut
                return sanic.text("route1")

        async def setup_routes(server: Server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res1 = await srv.start_request("GET", "/route1")

        assert (
            await res1.text()
        ) == '{"error_code":"RequestCancelled","error":"Request was cancelled"}'
        assert res1.content_type == "application/json"

    async it "server stopping is a 503 cancelled", final_future: asyncio.Future, fake_event_loop:
        store = Store()

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route1, "route1")

            async def route1(s, progress: Progress, request: Request, /) -> Response | None:
                await hp.create_future()
                return sanic.text("route1")

        async def setup_routes(server: Server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            t1 = srv.start_request("GET", "/route1")
            await asyncio.sleep(5)

        assert 5 < time.time() < 6
        res = await t1
        assert (
            (await res.text())
            == dedent(
                """
            ⚠️ 503 — Service Unavailable
            ============================
            Cancelled
            """
            ).strip()
            + "\n\n"
        )

    async it "understands when the route was cancelled above the route", final_future: asyncio.Future, fake_event_loop:
        store = Store()

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                wrapped = routes.wrap_http(kls.route1)

                async def my_route(request: Request) -> Response | None:
                    task = routes.server.tasks.add(wrapped(request))
                    await asyncio.sleep(5)
                    task.cancel()
                    await task
                    return None

                routes.app.add_route(my_route, "route1")

            async def route1(s, progress: Progress, request: Request, /) -> Response | None:
                await asyncio.sleep(20)
                return sanic.text("route1")

        async def setup_routes(server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            t1 = srv.start_request("GET", "/route1")
            await asyncio.sleep(5)

        assert 5 < time.time() < 6
        res = await t1
        assert (
            (await res.text())
            == dedent(
                """
            ⚠️ 503 — Service Unavailable
            ============================
            Cancelled
            """
            ).strip()
            + "\n\n"
        )

    async it "logs random exceptions and returns InternalServerError", final_future: asyncio.Future, fake_event_loop, caplog:
        identifier: str
        store = Store()
        error = ValueError("NUP")

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route1, "route1")

            def route1(s, progress: Progress, request: Request, /) -> Response | None:
                nonlocal identifier
                identifier = request.ctx.request_identifier
                raise error

        async def setup_routes(server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res1 = await srv.start_request("GET", "/route1")

        assert (
            await res1.text()
        ) == '{"error_code":"InternalServerError","error":"Internal Server Error"}'
        assert res1.content_type == "application/json"

        assert len(caplog.records) > 3
        record = caplog.records[-2]
        assert (
            record.message == f"{{'request_identifier': '{identifier}', 'msg': 'ValueError: NUP'}}"
        )
        assert record.name == "photons_web_server_tests.commander.test_store:C:route1"
        assert record.exc_info == (
            ValueError,
            error,
            pytest.helpers.IsInstance(types.TracebackType),
        )

    async it "is easy to log things in route", final_future: asyncio.Future, fake_event_loop, caplog:
        identifier: str
        store = Store()

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route1, "route1")

            def route1(s, progress: Progress, request: Request, /) -> Response | None:
                nonlocal identifier
                identifier = request.ctx.request_identifier
                s.log.info(s.lc("Hello there", one=2))
                return sanic.text("hi")

        async def setup_routes(server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res1 = await srv.start_request("GET", "/route1")

        assert (await res1.text()) == "hi"

        assert len(caplog.records) > 3
        record = caplog.records[-2]
        assert (
            record.message
            == f"{{'request_identifier': '{identifier}', 'msg': 'Hello there', 'one': 2}}"
        )
        assert record.name == "photons_web_server_tests.commander.test_store:C:route1"
        assert record.exc_info is None

    async it "is possible to have progress messages on a http handler", final_future: asyncio.Future, fake_event_loop, caplog:
        identifier: str
        store = Store()

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.http(kls.route1, "route1")

            async def route1(s, progress: Progress, request: Request, /) -> Response | None:
                nonlocal identifier
                identifier = request.ctx.request_identifier
                await progress("hi", there=True)
                await progress(ValueError("asdf"))
                return sanic.text("hi")

        async def setup_routes(server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res1 = await srv.start_request("GET", "/route1")

        assert (await res1.text()) == "hi"

        assert len(caplog.records) > 4
        record = caplog.records[-3]
        assert (
            record.message
            == f"{{'request_identifier': '{identifier}', 'msg': 'progress', 'info': 'hi', 'there': True}}"
        )
        assert record.name == "photons_web_server_tests.commander.test_store:C:route1"
        assert record.exc_info is None

        record = caplog.records[-2]
        assert (
            record.message
            == f"{{'request_identifier': '{identifier}', 'msg': 'progress', 'error_code': 'ValueError', 'error': 'asdf'}}"
        )
        assert record.name == "photons_web_server_tests.commander.test_store:C:route1"
        assert record.exc_info is None

    async it "supports websocket commands", final_future: asyncio.Future, fake_event_loop, caplog:
        store = Store()
        identifiers: set[str] = set()

        RI1 = pws_thp.IdentifierMatch(identifiers)
        MI11 = pws_thp.IdentifierMatch(identifiers)
        MI12 = pws_thp.IdentifierMatch(identifiers)
        MI13 = pws_thp.IdentifierMatch(identifiers)
        MI14 = pws_thp.IdentifierMatch(identifiers)

        RI2 = pws_thp.IdentifierMatch(identifiers)
        MI21 = pws_thp.IdentifierMatch(identifiers)
        MI22 = pws_thp.IdentifierMatch(identifiers)
        MI23 = pws_thp.IdentifierMatch(identifiers)
        MI24 = pws_thp.IdentifierMatch(identifiers)
        MI25 = pws_thp.IdentifierMatch(identifiers)

        by_stream_id: dict[str, int] = defaultdict(int)

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.ws(kls.adder, "adder")

            async def adder(
                s,
                wssend: WSSender,
                message: Message,
            ) -> bool | None:
                if message.body["command"] == "echo":
                    await wssend(message.body["echo"])
                if message.body["command"] == "totals":
                    await wssend.progress(dict(by_stream_id))
                elif message.body["command"] == "add":
                    add = tp.cast(int, message.body.get("add", 0))
                    identifier = message.request.ctx.request_identifier
                    assert identifier == message.stream_id
                    await wssend.progress("added", was=by_stream_id[message.stream_id], adding=add)
                    by_stream_id[message.stream_id] += add
                elif message.body["command"] == "stop":
                    await wssend("stopped!")
                    return False

                return None

        async def setup_routes(server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res: list[dict | str] = []
            async with srv.stream("/adder") as stream:
                res.append(await stream.recv())
                await stream.send({"command": "totals"})
                res.append(await stream.recv())
                await stream.send({"command": "add", "add": 10})
                res.append(await stream.recv())
                await stream.send({"command": "add", "add": 30})
                res.append(await stream.recv())
                await stream.send({"command": "stop"})
                res.append(await stream.recv())
                res.append(await stream.recv())
                res.append("__BREAK__")

            async with srv.stream("/adder") as stream:
                res.append(await stream.recv())
                await stream.send({"command": "echo", "echo": "echo"})
                res.append(await stream.recv())
                await stream.send({"command": "totals"})
                res.append(await stream.recv())
                await stream.send({"command": "add", "add": 10})
                res.append(await stream.recv())
                await stream.send({"command": "totals"})
                res.append(await stream.recv())
                await stream.send({"command": "stop"})
                res.append(await stream.recv())
                res.append(await stream.recv())
                res.append("__OVER__")

        assert res[:9] == [
            {"message_id": "__server_time__", "reply": ANY},
            {
                "message_id": MI11,
                "request_identifier": RI1,
                "progress": {},
            },
            {
                "message_id": MI12,
                "request_identifier": RI1,
                "progress": {"info": "added", "was": 0, "adding": 10},
            },
            {
                "message_id": MI13,
                "request_identifier": RI1,
                "progress": {"info": "added", "was": 10, "adding": 30},
            },
            {
                "message_id": MI14,
                "request_identifier": RI1,
                "reply": "stopped!",
            },
            None,
            "__BREAK__",
            {"message_id": "__server_time__", "reply": ANY},
            {
                "message_id": MI21,
                "request_identifier": RI2,
                "reply": "echo",
            },
        ]
        assert res[9:] == [
            {
                "message_id": MI22,
                "request_identifier": RI2,
                "progress": {RI1: 40},
            },
            {
                "message_id": MI23,
                "request_identifier": RI2,
                "progress": {"info": "added", "was": 0, "adding": 10},
            },
            {
                "message_id": MI24,
                "request_identifier": RI2,
                "progress": {RI1: 40, RI2: 10},
            },
            {
                "message_id": MI25,
                "request_identifier": RI2,
                "reply": "stopped!",
            },
            None,
            "__OVER__",
        ]

        records = [r.msg for r in caplog.records if isinstance(r.msg, dict)]
        assert records == [
            {
                "request_identifier": RI1,
                "message_id": MI11,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "totals"},
            },
            {
                "request_identifier": RI1,
                "message_id": MI11,
                "msg": "progress",
            },
            {
                "request_identifier": RI1,
                "message_id": MI11,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI1,
                "message_id": MI12,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "add", "add": 10},
            },
            {
                "request_identifier": RI1,
                "message_id": MI12,
                "msg": "progress",
                "info": "added",
                "was": 0,
                "adding": 10,
            },
            {
                "request_identifier": RI1,
                "message_id": MI12,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI1,
                "message_id": MI13,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "add", "add": 30},
            },
            {
                "request_identifier": RI1,
                "message_id": MI13,
                "msg": "progress",
                "info": "added",
                "was": 10,
                "adding": 30,
            },
            {
                "request_identifier": RI1,
                "message_id": MI13,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI1,
                "message_id": MI14,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "stop"},
            },
            {
                "request_identifier": RI1,
                "message_id": MI14,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI2,
                "message_id": MI21,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "echo", "echo": "echo"},
            },
            {
                "request_identifier": RI2,
                "message_id": MI21,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI2,
                "message_id": MI22,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "totals"},
            },
            {
                "request_identifier": RI2,
                "message_id": MI22,
                "msg": "progress",
                RI1: 40,
            },
            {
                "request_identifier": RI2,
                "message_id": MI22,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI2,
                "message_id": MI23,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "add", "add": 10},
            },
            {
                "request_identifier": RI2,
                "message_id": MI23,
                "msg": "progress",
                "info": "added",
                "was": 0,
                "adding": 10,
            },
            {
                "request_identifier": RI2,
                "message_id": MI23,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI2,
                "message_id": MI24,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "totals"},
            },
            {
                "request_identifier": RI2,
                "message_id": MI24,
                "msg": "progress",
                RI1: 40,
                RI2: 10,
            },
            {
                "request_identifier": RI2,
                "message_id": MI24,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI2,
                "message_id": MI25,
                "msg": "Websocket Request",
                "method": "GET",
                "uri": "/adder",
                "scheme": "ws",
                "remote_addr": "",
                "body": {"command": "stop"},
            },
            {
                "request_identifier": RI2,
                "message_id": MI25,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
        ]

    async it "supports message from exc from commands", final_future: asyncio.Future, fake_event_loop, caplog:
        store = Store()
        identifiers: set[str] = set()

        RI1 = pws_thp.IdentifierMatch(identifiers)
        MI1 = pws_thp.IdentifierMatch(identifiers)
        MI2 = pws_thp.IdentifierMatch(identifiers)
        MI3 = pws_thp.IdentifierMatch(identifiers)

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.ws(kls.excs, "excs")

            async def excs(
                s,
                wssend: WSSender,
                message: Message,
            ) -> bool | None:
                if message.body["command"] == "valueerror":
                    raise ValueError("nup")
                if message.body["command"] == "delfickerror":

                    class MyError(DelfickError):
                        desc = "my error"

                    raise MyError("hello there", mate=True)
                if message.body["command"] == "attrserror":

                    @define
                    class TheError(Exception):
                        one: int
                        two: str

                    raise TheError(one=2, two="two")

                return None

        async def setup_routes(server):
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            async with srv.stream("/excs") as stream:
                await stream.send({"command": "valueerror"})
                assert (await stream.recv())["message_id"] == "__server_time__"
                assert await stream.recv() == {
                    "request_identifier": RI1,
                    "message_id": MI1,
                    "error_code": "InternalServerError",
                    "error": "Internal Server Error",
                }
                await stream.send({"command": "delfickerror"})
                assert await stream.recv() == {
                    "request_identifier": RI1,
                    "message_id": MI2,
                    "error_code": "MyError",
                    "error": {"message": "my error. hello there", "mate": True},
                }
                await stream.send({"command": "attrserror"})
                assert await stream.recv() == {
                    "request_identifier": RI1,
                    "message_id": MI3,
                    "error_code": "TheError",
                    "error": {"one": 2, "two": "two"},
                }
