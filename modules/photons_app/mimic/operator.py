from photons_app.mimic.packet_filter import Filter, SendReplies, SendUnhandled, SendAck
from photons_app.errors import PhotonsAppError
from photons_app.mimic.event import Events
from photons_app import helpers as hp

from photons_protocol.messages import Messages

from delfick_project.norms import dictobj, Meta


register = []


def operator(kls):
    register.append(kls)
    return kls


class LambdaSetter:
    def __init__(self, key, *, from_zero, from_options=None):
        self.key = key
        self.from_zero = from_zero
        self.from_options = from_options

    async def __call__(self, event, options):
        if event.zerod:
            yield event.device.attrs.attrs_path(self.key).changer_to(self.from_zero(event, options))
        else:
            fn = self.from_options
            if fn is None:
                fn = self.from_zero
            yield event.device.attrs.attrs_path(self.key).changer_to(fn(event, options))


def StaticSetter(key, value):
    return LambdaSetter(key, from_zero=lambda event, options: value)


class Operator:
    """
    This class represents a slice of functionality.

    It has:

    attrs
        A list of DefaultSetter objects that have change() async iterator
        for yielding attribute change objects for updating the attrs on the device

        The change async iterator gets the event object and the options on the operator.
        These are used when we start or reset the device.

    options
        An object that represents options this operator is started with. The
        operator may use this object to know what values to set on the device
        when a normal reset happens.

    respond
        A function that takes in an event object and does something. There
        are multiple events that are possible as found in
        photons_app.mimc.event
    """

    class Attr:
        Lambda = LambdaSetter
        Static = StaticSetter

    attrs = []

    class Options(dictobj.Spec):
        pass

    @classmethod
    def only_io_and_viewer_operators(kls, value_store):
        return bool(value_store.get("only_io_and_viewer_operators"))

    def __init__(self, device, options=None, *args, **kwargs):
        self.device = device
        self.device_attrs = device.attrs
        self.options = self.Options.FieldSpec().normalise(
            Meta.empty(), {} if options is None else options
        )
        self.setup(*args, **kwargs)

    def setup(self):
        pass

    async def apply(self):
        self.device.operators.append(self)

    async def reset(self, event):
        changes = []
        for ch in self.attrs:
            async for change in ch(event, self.options):
                changes.append(change)

        if changes:
            await event.device.attrs.attrs_apply(*changes)

    async def respond(self, event):
        pass

    def state_for(self, kls, expect_one=True, expect_any=True):
        return self.device.state_for(kls, expect_one=expect_one, expect_any=expect_any)

    def make_state_for(self, kls, result):
        pass

    async def change_one(self, key, value):
        return await self.device.change_one(key, value)

    async def change(self, *changes):
        return await self.device.change(*changes)


class Viewer(Operator):
    async def apply(self):
        self.device.viewers.append(self)


class IO(Operator):
    def setup(self):
        self.packet_filter = Filter()

        self.final_future = None
        self.last_final_future = None

    async def _start_session(self):
        pass

    async def _finish_session(self):
        pass

    async def apply(self):
        raise NotImplementedError()

    async def _send_reply(self, reply, addr, replying_to):
        raise NotImplementedError()

    async def start_session(self, final_future):
        await self.finish_session()

        self.last_final_future = final_future
        self.final_future = hp.ChildOfFuture(
            final_future,
            name=f"{self.__class__.__name__}({self.device.serial}::start_session[final_future]",
        )

        self.ts = hp.TaskHolder(
            self.final_future,
            name=f"{self.__class__.__name__}({self.device.serial}::start_session[ts]",
        )

        self.incoming = hp.Queue(
            self.final_future,
            name=f"{self.__class__.__name__}({self.device.serial}::start_session[incoming]",
        )

        await self.ts.start()
        self.ts.add(self.incoming_loop())
        return await self._start_session()

    async def restart_session(self):
        if self.last_final_future is None or self.last_final_future.done():
            raise PhotonsAppError(
                "The IO does not have a valid final future to restart the session from"
            )
        return await self.start_session(self.last_final_future)

    async def finish_session(self):
        if getattr(self, "final_future", None) is None:
            return

        ff = self.final_future

        try:
            await self._finish_session()
            self.final_future.cancel()
            await self.ts.finish()
            await self.incoming.finish()
        finally:
            if ff:
                ff.cancel()
            self.final_future = None

    def received(self, bts, give_reply, addr):
        self.incoming.append((bts, give_reply, addr))

    async def incoming_loop(self):
        async for bts, give_reply, addr in self.incoming:
            self.ts.add(self.process_incoming(bts, give_reply, addr))

    async def process_incoming(self, bts, give_reply, addr):
        if not self.device.has_power:
            return

        pkt = Messages.create(bts, protocol_register=self.device.protocol_register)

        event = await self.device.event_with_options(
            Events.INCOMING,
            execute=False,
            args=(self,),
            kwargs=dict(pkt=pkt, addr=addr),
        )

        processed = await self.packet_filter.process_request(event)
        if processed is None:
            event = await self.device.event(Events.LOST, self, pkt=pkt, addr=addr)
            return

        await self.device.execute_event(event, lambda e: e.handled)

        await self.process_instruction(SendAck(event), give_reply)

        if processed is False:
            await self.device.event(
                Events.IGNORED, self, pkt=event.pkt, bts=event.bts, addr=event.addr
            )
            return

        if event.ignored:
            await self.device.event(
                Events.IGNORED, self, pkt=event.pkt, bts=event.bts, addr=event.addr
            )
        elif not event.handled and not event.replies:
            await self.device.event(
                Events.UNHANDLED, self, pkt=event.pkt, bts=event.bts, addr=event.addr
            )
            await self.process_instruction(SendUnhandled(event), give_reply)
        else:
            await self.process_instruction(SendReplies(event), give_reply)

    async def process_instruction(self, instruction, give_reply):
        async for reply in instruction.process():
            async for rr in self.packet_filter.outgoing(reply, instruction.event):
                await self._send_reply(
                    rr, give_reply, instruction.event.addr, replying_to=instruction.event.pkt
                )

    async def respond(self, event):
        pass
