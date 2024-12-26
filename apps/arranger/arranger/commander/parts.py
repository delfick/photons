import asyncio
from typing import Annotated, Protocol, TypeVar

import attrs
import strcs
from photons_app import helpers as hp
from photons_web_server import commander

from arranger.arranger import Arranger

from .selector import Serial

T = TypeVar("T")


class Creator(Protocol):
    def __call__(
        self,
        typ: type[T] | strcs.Type[T],
        value: object = strcs.NotSpecified,
        meta: strcs.Meta | None = None,
        once_only_creator: strcs.ConvertFunction[T] | None = None,
    ) -> T: ...


@attrs.define(kw_only=True)
class InvalidCommand(Exception):
    error: str = "Invalid command"


@attrs.define(kw_only=True)
class NoSuchPath(Exception):
    error: str = "Specified path is invalid"
    wanted: str
    available: list[str]


@attrs.define(kw_only=True)
class NoSuchCommand(Exception):
    error: str = "Specified command is unknown"
    wanted: str
    available: list[str]


@attrs.define(kw_only=True)
class HighlightBody:
    serial: Serial
    part_number: int
    arranger: Annotated[Arranger, strcs.FromMeta("arranger")]


@attrs.define(kw_only=True)
class ChangePositionBody:
    serial: Serial
    part_number: int
    user_x: int
    user_y: int
    arranger: Annotated[Arranger, strcs.FromMeta("arranger")]


class PartRouter:
    def __init__(self) -> None:
        self.registered: dict[str, commander.Responder] = {}

    async def start(self, message_id: str, respond: commander.Responder) -> None:
        await respond.progress({"instruction": "started"}, do_log=False)

        self.registered[message_id] = respond
        try:
            await hp.create_future(name="PartRouter::start")
        except asyncio.CancelledError:
            if message_id in self.registered:
                del self.registered[message_id]

    async def command(
        self,
        respond: commander.Responder,
        message: commander.Message,
        create: Creator,
        parent_message_id: str,
    ) -> None:
        command = message.body["body"].get("command")
        available_commands = ["highlight", "change_position"]
        if command not in available_commands:
            await respond(NoSuchCommand(wanted=command, available=sorted(available_commands)))

        parent_respond = self.registered.get(parent_message_id)
        if parent_respond is None:
            return

        if command == "highlight":
            try:
                body = create(HighlightBody, message.body["body"].get("args"))
            except Exception as e:
                await respond(e)
            else:
                await self.highlight(body=body, respond=parent_respond)
        elif command == "change_position":
            try:
                body = create(ChangePositionBody, message.body["body"].get("args"))
            except Exception as e:
                await respond(e)
            else:
                await self.change_position(body=body, respond=parent_respond)

    async def highlight(self, respond: commander.Responder, body: HighlightBody) -> None:
        await body.arranger.add_highlight((body.serial.serial, body.part_number))

    async def change_position(self, respond: commander.Responder, body: ChangePositionBody) -> None:
        await body.arranger.change_position(body.serial.serial, body.part_number, body.user_x, body.user_y)


class PartsCommand(commander.Command):
    @classmethod
    def add_routes(kls, routes: commander.RouteTransformer) -> None:
        routes.ws(kls.parts, "/v1/ws", name="parts")

    async def parts(
        self,
        respond: commander.Responder,
        message: commander.Message,
    ) -> bool | None:
        path = message.body.get("path")
        if path == "__tick__":
            return

        if path != "/v1/lifx/command":
            await respond(NoSuchPath(wanted=path, available=["/v1/lifx/command"]))

        part_router = self.meta.retrieve_one(PartRouter, type_cache=self.store.strcs_register.type_cache)
        tasks = self.meta.retrieve_one(hp.TaskHolder, type_cache=self.store.strcs_register.type_cache)
        arranger = self.meta.retrieve_one(Arranger, type_cache=self.store.strcs_register.type_cache)

        message_id = message.body.get("message_id") or None
        if isinstance(message_id, str):
            available_commands = ["parts/store"]
            if (command := message.body["body"].get("command")) not in available_commands:
                await respond(NoSuchCommand(wanted=command, available=sorted(available_commands)))

            def progress_cb(info: object, do_log: bool = True) -> None:
                tasks.add(respond.progress(info, do_log=do_log))

            async with arranger.add_stream(progress_cb):
                # Ensure arranger is running
                tasks.add(arranger.run())

                await part_router.start(message_id or None, respond)
        elif isinstance(message_id, list):
            await part_router.command(respond, message, self.create, message_id[0])
        else:
            await respond(InvalidCommand)
