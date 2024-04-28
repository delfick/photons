# coding: spec

import asyncio
import typing as tp
from collections import defaultdict
from unittest.mock import ANY

import socketio
import strcs
from attrs import define
from photons_web_server import pytest_helpers as pws_thp
from photons_web_server.commander import (
    Command,
    Message,
    Responder,
    RouteTransformer,
    Store,
)


@define
class AnError(Exception):
    pass


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


describe "Store with sio":
    async it "supports sio commands", final_future: asyncio.Future, fake_event_loop, caplog:
        store = Store()

        sio = socketio.AsyncServer(async_mode="sanic")
        store.add_sio_server(sio)

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

        by_stream_id: dict[str, int] = defaultdict(int)

        @store.command
        class C(Command):
            @classmethod
            def add_routes(kls, routes: RouteTransformer) -> None:
                routes.sio("command", kls.respond)

            async def respond(
                s,
                respond: Responder,
                message: Message,
            ) -> bool | None:
                if message.body["command"] == "echo":
                    await respond(message.body["echo"])
                if message.body["command"] == "totals":
                    await respond.progress(dict(by_stream_id))
                if message.body["command"] == "error":
                    await respond(AnError())
                elif message.body["command"] == "add":
                    add = tp.cast(int, message.body.get("add", 0))
                    identifier = message.request.ctx.request_identifier
                    assert identifier == message.stream_id
                    await respond.progress("added", was=by_stream_id[message.stream_id], adding=add)
                    by_stream_id[message.stream_id] += add

                return None

        async def setup_routes(server):
            sio.attach(server.app, socketio_path="adder")
            store.register_commands(server.server_stop_future, strcs.Meta(), server.app, server)

        async with pws_thp.WebServerRoutes(final_future, setup_routes) as srv:
            res: list[dict | str] = []
            async with srv.sio_stream("/adder") as stream:
                await stream.emit("command", {"command": "totals"})
                res.append(await stream.recv())
                await stream.emit("command", {"command": "add", "add": 10})
                res.append(await stream.recv())
                await stream.emit("command", {"command": "add", "add": 30})
                res.append(await stream.recv())
                await stream.emit("command", {"command": "error"})
                res.append(await stream.recv())
                res.append("__BREAK__")

            async with srv.sio_stream("/adder") as stream:
                await stream.emit("command", {"command": "echo", "echo": "echo"})
                res.append(await stream.recv())
                await stream.emit("command", {"command": "totals"})
                res.append(await stream.recv())
                await stream.emit("command", {"command": "add", "add": 10})
                res.append(await stream.recv())
                await stream.emit("command", {"command": "totals"})
                res.append(await stream.recv())
                res.append("__OVER__")

        assert res[:6] == [
            {
                "event": "progress",
                "data": {
                    "message_id": MI11,
                    "request_identifier": RI1,
                    "progress": {},
                },
            },
            {
                "event": "progress",
                "data": {
                    "message_id": MI12,
                    "request_identifier": RI1,
                    "progress": {"info": "added", "was": 0, "adding": 10},
                },
            },
            {
                "event": "progress",
                "data": {
                    "message_id": MI13,
                    "request_identifier": RI1,
                    "progress": {"info": "added", "was": 10, "adding": 30},
                },
            },
            {
                "event": "error",
                "data": {
                    "message_id": MI14,
                    "request_identifier": RI1,
                    "reply": {"error": {}, "error_code": "AnError"},
                },
            },
            "__BREAK__",
            {
                "event": "reply",
                "data": {
                    "message_id": MI21,
                    "request_identifier": RI2,
                    "reply": "echo",
                },
            },
        ]
        assert res[6:] == [
            {
                "event": "progress",
                "data": {
                    "message_id": MI22,
                    "request_identifier": RI2,
                    "progress": {RI1: 40},
                },
            },
            {
                "event": "progress",
                "data": {
                    "message_id": MI23,
                    "request_identifier": RI2,
                    "progress": {"info": "added", "was": 0, "adding": 10},
                },
            },
            {
                "event": "progress",
                "data": {
                    "message_id": MI24,
                    "request_identifier": RI2,
                    "progress": {RI1: 40, RI2: 10},
                },
            },
            "__OVER__",
        ]

        records = [r.msg for r in caplog.records if isinstance(r.msg, dict)]
        assert records[2:] == [
            {
                "request_identifier": RI1,
                "message_id": MI11,
                "msg": "Socketio Event",
                "method": "GET",
                "uri": "/adder/",
                "scheme": "http",
                "remote_addr": "",
                "body": {"event": "command", "data": {"command": "totals"}},
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
                "uri": "/adder/",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI1,
                "message_id": MI12,
                "msg": "Socketio Event",
                "method": "GET",
                "uri": "/adder/",
                "scheme": "http",
                "remote_addr": "",
                "body": {"event": "command", "data": {"command": "add", "add": 10}},
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
                "uri": "/adder/",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI1,
                "message_id": MI13,
                "msg": "Socketio Event",
                "method": "GET",
                "uri": "/adder/",
                "scheme": "http",
                "remote_addr": "",
                "body": {"event": "command", "data": {"command": "add", "add": 30}},
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
                "uri": "/adder/",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI1,
                "message_id": MI14,
                "msg": "Socketio Event",
                "method": "GET",
                "uri": "/adder/",
                "scheme": "http",
                "remote_addr": "",
                "body": {"event": "command", "data": {"command": "error"}},
            },
            {
                "request_identifier": RI1,
                "message_id": MI14,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder/",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            ANY,
            ANY,
            ANY,
            {
                "request_identifier": RI2,
                "message_id": MI21,
                "msg": "Socketio Event",
                "method": "GET",
                "uri": "/adder/",
                "scheme": "http",
                "remote_addr": "",
                "body": {"event": "command", "data": {"command": "echo", "echo": "echo"}},
            },
            {
                "request_identifier": RI2,
                "message_id": MI21,
                "msg": "Response",
                "method": "GET",
                "uri": "/adder/",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI2,
                "message_id": MI22,
                "msg": "Socketio Event",
                "method": "GET",
                "uri": "/adder/",
                "scheme": "http",
                "remote_addr": "",
                "body": {"event": "command", "data": {"command": "totals"}},
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
                "uri": "/adder/",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI2,
                "message_id": MI23,
                "msg": "Socketio Event",
                "method": "GET",
                "uri": "/adder/",
                "scheme": "http",
                "remote_addr": "",
                "body": {"event": "command", "data": {"command": "add", "add": 10}},
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
                "uri": "/adder/",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            {
                "request_identifier": RI2,
                "message_id": MI24,
                "msg": "Socketio Event",
                "method": "GET",
                "uri": "/adder/",
                "scheme": "http",
                "remote_addr": "",
                "body": {"event": "command", "data": {"command": "totals"}},
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
                "uri": "/adder/",
                "status": 200,
                "remote_addr": "",
                "took_seconds": Between(0, 1),
            },
            ANY,
        ]
