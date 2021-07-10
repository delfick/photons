from photons_app.mimic.operator import register, IO
from photons_app.errors import PhotonsAppError
from photons_app.mimic.event import Events
from photons_app.mimic.attrs import Attrs
from photons_app import helpers as hp

import logging


class ExpectedMessages(PhotonsAppError):
    desc = "Expected the fake device to produce one or more messages"


class ExpectedOneMessage(PhotonsAppError):
    desc = "Expected the fake device to produce exactly one message"


class DeviceSession(hp.AsyncCMMixin):
    def __init__(self, final_future, device):
        self.device = device
        self.managed = []
        self.final_future = final_future

    async def start(self):
        await self.device.prepare()

        made = []
        async with hp.TaskHolder(
            self.final_future, name=f"DeviceSession({self.device.serial})::start[ts]"
        ) as ts:
            for _, io in self.device.io.items():
                self.managed.append(io)
                made.append(ts.add(io.start_session(self.final_future), silent=True))

        await self.device.reset()

        # Raise any exceptions
        for t in made:
            await t

    async def finish(self, exc_typ=None, exc=None, tb=None):
        try:
            made = []
            async with hp.TaskHolder(
                self.final_future, name=f"DeviceSession({self.device.serial})::finish[ts]"
            ) as ts:
                for io in self.managed:
                    made.append(ts.add(io.finish_session(), silent=True))
                self.managed = []
        finally:
            await self.device.delete()

        # Raise any exceptions
        for t in made:
            await t


class Device:
    Firmware = hp.Firmware

    def __init__(
        self,
        serial,
        product,
        firmware,
        *options,
        value_store=None,
        protocol_register=None,
        search_for_operators=True,
    ):
        self.has_power = False
        self.original_firmware = firmware.clone()

        self.operators_register = register
        self.search_for_operators = search_for_operators

        if protocol_register is None:
            protocol_register = __import__("photons_messages").protocol_register
        self.protocol_register = protocol_register

        if value_store is None:
            value_store = {}
        self.value_store = value_store

        self.serial = serial
        self.options = options
        self.options = list(options)
        self.firmware = firmware.clone()
        self.applied_options = False

        self._product = product

        self.attrs = Attrs(self)

    def __repr__(self):
        return f"<Device {self.serial}:{self.cap.product.name}:{self.cap.firmware_major},{self.cap.firmware_minor}>"

    def session(self, final_future):
        return DeviceSession(final_future, self)

    async def event(self, eventkls, *args, **kwargs):
        return await self.event_with_options(eventkls, args=args, kwargs=kwargs)

    async def event_with_options(
        self, eventkls, *, is_finished=None, visible=True, execute=True, args, kwargs
    ):
        event = eventkls(self, *args, **kwargs)
        event._exclude_viewers = not visible

        if not execute:
            return event

        return await self.execute_event(event, is_finished)

    async def execute_event(self, event, is_finished):
        if not self.applied_options:
            return event

        if event | Events.RESET:
            for group in (self.viewers, self.io.values(), self.operators):
                for op in group:
                    if hasattr(op, "reset"):
                        await op.reset(event)

        async def response():
            yield
            for group in (self.viewers, self.io.values(), self.operators):
                if getattr(event, "_viewers_only", False) and group is not self.viewers:
                    continue

                if getattr(event, "_exclude_viewers", False) and group is self.viewers:
                    continue

                for op in group:
                    if hasattr(op, "respond"):
                        await op.respond(event)
                        yield

        async for _ in response():
            if is_finished is not None and is_finished(event):
                return event

        return event

    @property
    def product(self):
        return self._product

    @property
    def cap(self):
        return self.product.cap(self.firmware.major, self.firmware.minor)

    async def change_one(self, key, value):
        await self.change((key, value))

    async def change(self, *changes):
        await self.attrs.attrs_apply(
            *[
                self.attrs.attrs_path(*((key,) if isinstance(key, str) else key)).changer_to(value)
                for key, value in changes
            ]
        )

    async def power_on(self):
        self.has_power = True
        return await self.event(Events.POWER_ON)

    async def power_off(self):
        await self.event(Events.SHUTTING_DOWN)
        self.has_power = False
        return await self.event(Events.POWER_OFF)

    @hp.asynccontextmanager
    async def offline(self):
        try:
            yield await self.power_off()
        finally:
            await self.power_on()

    async def prepare(self):
        if self.applied_options:
            return

        self.io = {}
        self.viewers = []
        self.operators = []

        options = list(self.options)
        if self.search_for_operators:
            options.extend(self.operators_register)

        for option in options:
            if isinstance(option, type):
                option = option.select(self)
            elif callable(option):
                option = option(self)

            if option is not None:
                if isinstance(option, IO) and self.value_store.get("has_io", True) is False:
                    continue
                await option.apply()

        self.applied_options = True

    async def reset(self, zerod=False):
        self.has_power = False
        self.firmware = self.original_firmware.clone()

        self.attrs.attrs_reset()
        await self.event(Events.RESET, zerod=zerod)
        self.attrs.attrs_start()

        self.has_power = True

    async def delete(self):
        await self.event(Events.DELETE)
        if hasattr(self, "io"):
            del self.io
        if hasattr(self, "viewers"):
            del self.viewers
        if hasattr(self, "operators"):
            del self.operators
        self.applied_options = False

    async def annotate(self, level, message, **details):
        if isinstance(level, str):
            level = getattr(logging, level)
        return await self.event(Events.ANNOTATION, level, message, **details)

    async def discoverable(self, service, broadcast_address):
        if not self.has_power:
            return False

        try:
            await self.event(Events.DISCOVERABLE, address=broadcast_address, service=service)
        except Events.Stop:
            return False
        else:
            return True

    def state_for(self, kls, expect_one=True, expect_any=True):
        result = []

        for _, operator in sorted(self.io.items()):
            operator.make_state_for(kls, result)

        for operator in self.operators:
            operator.make_state_for(kls, result)

        if expect_one:
            if len(result) != 1:
                raise ExpectedOneMessage(kls=kls, got=len(result), device=self)
            return result[0]

        if expect_any and not result:
            raise ExpectedMessages(kls=kls, device=self)

        return result
