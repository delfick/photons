from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_app.mimic.attrs import ChangeAttr
from photons_app.mimic.device import Device
from photons_app.mimic.event import Events
from photons_app.mimic.operator import IO, Operator
from photons_app.mimic.operators.listener import Listener, RecordEvents
from photons_app.mimic.packet_filter import Filter
from photons_messages import DeviceMessages, DiscoveryMessages, Services
from photons_products import Products


def make_packet(kls, **kwargs):
    return kls.create(kls.create(**kwargs).pack())


@pytest.fixture()
def device():
    return Device("d073d5001337", Products.LCM2_A19, hp.Firmware(2, 80))


@pytest.fixture()
def wrap_io(device):
    @hp.asynccontextmanager
    async def wrap_io(io):
        try:
            yield io
        finally:
            await io.finish_session()

    return wrap_io


@pytest.fixture()
async def parent_ts(final_future):
    async with hp.TaskHolder(final_future) as ts:
        yield ts


class TestIO:
    def test_it_has_a_packet_filter(self, device):

        class IIO(IO):
            io_source = "iio"

        io = IIO(device)
        assert isinstance(io.packet_filter, Filter)
        assert io.final_future is None
        assert io.last_final_future is None

    class TestSession:
        async def test_it_manages_a_queue_and_consumer_task_for_incoming_messages(
            self, device, wrap_io, final_future, parent_ts
        ):
            process = []
            got = hp.ResettableFuture()

            class TheIO(IO):
                io_source = "theio"

                async def process_incoming(s, bts, give_reply, addr):
                    process.append((bts, give_reply, addr))
                    got.reset()
                    got.set_result(len(process))

            bts1 = mock.Mock(name="bts1")
            give_reply1 = mock.Mock(name="give_reply1")
            addr1 = mock.Mock(name="addr1")

            bts2 = mock.Mock(name="bts2")
            give_reply2 = mock.Mock(name="give_reply2")
            addr2 = mock.Mock(name="addr2")

            async with wrap_io(TheIO(device)) as io:
                await io.start_session(final_future, parent_ts)
                assert isinstance(io.incoming, hp.Queue)
                assert isinstance(io.ts, hp.TaskHolder)
                assert len(list(io.ts)) == 1

                io.incoming.append((bts1, give_reply1, addr1))
                io.incoming.append((bts2, give_reply2, addr2))

                while len(process) != 2:
                    await got
                    got.reset()

                assert process == [(bts1, give_reply1, addr1), (bts2, give_reply2, addr2)]

            assert len(list(io.ts)) == 0
            assert io.ts.final_future.done()
            assert io.incoming.final_future.done()

        async def test_it_can_restart_a_session(self, device, wrap_io, final_future, parent_ts):

            class IIO(IO):
                io_source = "iio"

            async with wrap_io(IIO(device)) as io:
                with assertRaises(
                    PhotonsAppError,
                    "The IO does not have a valid final future to restart the session from",
                ):
                    await io.restart_session()

                await io.start_session(final_future, parent_ts)
                assert not io.incoming.final_future.done()
                assert not io.ts.final_future.done()
                ff = io.final_future
                inc = io.incoming
                fts = io.ts
                assert io.last_final_future is final_future

                await io.restart_session()
                assert not io.incoming.final_future.done()
                assert not io.ts.final_future.done()

                assert io.ts is not fts
                assert io.incoming is not inc
                assert io.final_future is not ff
                assert io.last_final_future is final_future

    class TestReceived:
        async def test_it_adds_to_the_incoming_queue(self, wrap_io, device, final_future):
            bts = mock.Mock(name="bts")
            give_reply = mock.Mock(name="give_reply")
            addr = mock.Mock(name="addr")

            class IIO(IO):
                io_source = "iio"

            async with wrap_io(IIO(device)) as io:
                try:
                    queue = hp.Queue(final_future)
                    io.incoming = queue

                    io.received(bts, give_reply, addr)

                    async for thing in queue:
                        assert thing == (bts, give_reply, addr)
                        break
                finally:
                    await queue.finish()

    class TestProcessInstruction:
        async def test_it_puts_result_from_instruction_through_filter_and_sends_replies(
            self, wrap_io, device, final_future
        ):
            got = []

            class MyIO(IO):
                io_source = "TEST"

                async def _send_reply(s, send, give_reply, addr, *, replying_to):
                    got.append(("sent", send, give_reply, addr, replying_to))

            addr = mock.Mock(name="addr")
            give_reply = mock.Mock(name="give_reply")

            given1 = mock.Mock(name="given1")
            given2 = mock.Mock(name="given2")
            filtered1 = mock.Mock(name="filtered1")
            filtered2 = mock.Mock(name="filtered2")
            filtered3 = mock.Mock(name="filtered3")

            async with wrap_io(MyIO(device)) as io:
                pkt = DeviceMessages.GetPower()
                event = Events.INCOMING(device, io, pkt=pkt, addr=addr)

                class Instruction:
                    def __init__(s):
                        s.event = event

                    async def process(s):
                        got.append(("process", given1))
                        yield given1
                        got.append(("process", given2))
                        yield given2

                instruction = Instruction()

                async def outgoing(r, e):
                    got.append(("outgoing", r, e))
                    if r is given1:
                        yield filtered1
                    elif r is given2:
                        yield filtered2
                        yield filtered3

                with mock.patch.object(io.packet_filter, "outgoing", outgoing):
                    await io.process_instruction(instruction, give_reply)

            assert got == [
                ("process", given1),
                ("outgoing", given1, event),
                ("sent", filtered1, give_reply, addr, pkt),
                ("process", given2),
                ("outgoing", given2, event),
                ("sent", filtered2, give_reply, addr, pkt),
                ("sent", filtered3, give_reply, addr, pkt),
            ]

    class TestProcessIncoming:

        @pytest.fixture()
        def record(self):
            rec = []
            try:
                yield rec
            finally:
                for thing in rec:
                    print(thing)

        @pytest.fixture()
        def sent(self):
            return hp.ResettableFuture()

        @pytest.fixture()
        def got_event(self):
            return hp.ResettableFuture()

        @pytest.fixture()
        def Responder(self):
            class Responder(Operator):
                attrs = [
                    Operator.Attr.Lambda(
                        "power",
                        from_zero=lambda event, options: 0,
                    )
                ]

                async def respond(s, event):
                    if event | DeviceMessages.GetPower:
                        event.set_replies(DeviceMessages.StatePower(level=s.device_attrs.power))
                    if event | DeviceMessages.GetLabel:
                        event.ignore_request()
                    elif event | DeviceMessages.SetPower:
                        event.set_replies(DeviceMessages.StatePower(level=s.device_attrs.power))
                        await s.device_attrs.attrs_apply(
                            s.device_attrs.attrs_path("power").changer_to(event.pkt.level),
                            event=None,
                        )
                    elif event | DiscoveryMessages.GetService:
                        event.set_replies(
                            DiscoveryMessages.StateService(service=Services.UDP, port=56700),
                            DiscoveryMessages.StateService(service=Services.UDP, port=76500),
                        )

            return Responder

        @pytest.fixture()
        def iokls(self, record, sent):
            class MyIO(IO):
                io_source = "TESTIO"

                async def apply(s):
                    s.device.io[s.io_source] = s

                async def _send_reply(s, rr, give_reply, addr, *, replying_to):
                    record.append(
                        (
                            "send",
                            (
                                rr.__class__.__name__,
                                rr.source,
                                rr.sequence,
                                rr.serial,
                                repr(rr.payload),
                            ),
                            give_reply,
                            addr,
                            replying_to.__class__.__name__,
                        )
                    )
                    sent.reset()
                    sent.set_result(True)

            return MyIO

        @pytest.fixture()
        async def device(self, record, Responder, final_future, iokls, got_event):
            device = Device(
                "d073d5001337",
                Products.LCM2_A19,
                hp.Firmware(2, 80),
                lambda d: iokls(d),
                lambda d: Listener(d),
                lambda d: Responder(d),
                lambda d: RecordEvents(
                    d, {"record_events_store": record, "got_event_fut": got_event}
                ),
                search_for_operators=False,
            )
            async with device.session(final_future):
                record.clear()
                yield device

        @pytest.fixture()
        async def switch(self, record, Responder, final_future, iokls, got_event):
            device = Device(
                "d073d5001338",
                Products.LCM3_16_SWITCH,
                hp.Firmware(3, 70),
                lambda d: iokls(d),
                lambda d: Listener(d),
                lambda d: Responder(d),
                lambda d: RecordEvents(
                    d, {"record_events_store": record, "got_event_fut": got_event}
                ),
                search_for_operators=False,
            )
            async with device.session(final_future):
                if record and record[-1] | Events.RESET:
                    record.pop()
                yield device

        async def test_it_does_nothing_if_the_device_is_offline(
            self, device, sent, record, got_event
        ):
            io = device.io["TESTIO"]
            addr = ("memory", device.serial)

            pkt = make_packet(DeviceMessages.GetLabel, source=3, sequence=3, target=device.serial)

            async with device.offline():
                io.received(pkt.pack().tobytes(), True, addr)

            assert record == [
                Events.SHUTTING_DOWN(device),
                Events.POWER_OFF(device),
                Events.POWER_ON(device),
            ]
            record.clear()

            io.received(pkt.pack().tobytes(), True, addr)

            while len(record) != 3:
                await sent
                sent.reset()

            assert record == [
                Events.INCOMING(device, io, pkt=pkt, addr=addr),
                ("send", ("Acknowledgement", 3, 3, device.serial, "{}"), True, addr, "GetLabel"),
                Events.IGNORED(device, io, pkt=pkt, addr=addr),
            ]
            record.clear()

        async def test_it_can_get_and_send_back_messages(self, device, sent, record, got_event):
            io = device.io["TESTIO"]
            addr = ("memory", device.serial)

            pkt = make_packet(
                DiscoveryMessages.GetService, source=3, sequence=3, target=device.serial
            )
            io.received(pkt.pack().tobytes(), True, addr)

            while len(record) != 4:
                await sent
                sent.reset()

            assert record == [
                Events.INCOMING(device, io, pkt=pkt, addr=addr),
                ("send", ("Acknowledgement", 3, 3, device.serial, "{}"), True, addr, "GetService"),
                (
                    "send",
                    (
                        "StateService",
                        3,
                        3,
                        device.serial,
                        '{"port": 56700, "service": "<Services.UDP: 1>"}',
                    ),
                    True,
                    addr,
                    "GetService",
                ),
                (
                    "send",
                    (
                        "StateService",
                        3,
                        3,
                        device.serial,
                        '{"port": 76500, "service": "<Services.UDP: 1>"}',
                    ),
                    True,
                    addr,
                    "GetService",
                ),
            ]

        async def test_it_can_ignore_messages(self, device, sent, record, got_event):
            io = device.io["TESTIO"]
            addr = ("memory", device.serial)

            pkt = make_packet(DeviceMessages.GetLabel, source=3, sequence=3, target=device.serial)
            io.received(pkt.pack().tobytes(), True, addr)

            while len(record) != 3:
                await sent
                sent.reset()

            assert record == [
                Events.INCOMING(device, io, pkt=pkt, addr=addr),
                ("send", ("Acknowledgement", 3, 3, device.serial, "{}"), True, addr, "GetLabel"),
                Events.IGNORED(device, io, pkt=pkt, addr=addr),
            ]
            record.clear()

            @io.packet_filter.intercept_process_request
            async def intercept(event, Cont):
                if event | DeviceMessages.GetPower:
                    record.append(("process", event.pkt.__class__.__name__))
                    return False
                else:
                    raise Cont()

            with intercept:
                pkt = make_packet(
                    DeviceMessages.GetPower, source=3, sequence=3, target=device.serial
                )
                io.received(pkt.pack().tobytes(), True, addr)

                while len(record) != 4:
                    await sent
                    sent.reset()

                assert record == [
                    ("process", "GetPower"),
                    Events.INCOMING(device, io, pkt=pkt, addr=addr),
                    (
                        "send",
                        ("Acknowledgement", 3, 3, device.serial, "{}"),
                        True,
                        addr,
                        "GetPower",
                    ),
                    Events.IGNORED(device, io, pkt=pkt, addr=addr),
                ]
                record.clear()

        async def test_it_can_have_unhandled_messages(
            self, switch, device, sent, record, got_event
        ):
            io = device.io["TESTIO"]
            ioswitch = switch.io["TESTIO"]
            addr = ("memory", device.serial)
            addrswitch = ("memory", switch.serial)

            assert not device.cap.has_unhandled
            assert switch.cap.has_unhandled

            pkt = make_packet(DeviceMessages.GetGroup, source=3, sequence=3, target=device.serial)
            io.received(pkt.pack().tobytes(), True, addr)

            while len(record) != 3:
                await sent
                sent.reset()

            assert record == [
                Events.INCOMING(device, io, pkt=pkt, addr=addr),
                ("send", ("Acknowledgement", 3, 3, device.serial, "{}"), True, addr, "GetGroup"),
                Events.UNHANDLED(device, io, pkt=pkt, addr=addr),
            ]
            record.clear()

            pkt = make_packet(DeviceMessages.GetGroup, source=3, sequence=3, target=switch.serial)
            ioswitch.received(pkt.pack().tobytes(), True, addrswitch)

            while len(record) != 4:
                await sent
                sent.reset()

            assert record == [
                Events.INCOMING(switch, ioswitch, pkt=pkt, addr=addrswitch),
                (
                    "send",
                    ("Acknowledgement", 3, 3, switch.serial, "{}"),
                    True,
                    addrswitch,
                    "GetGroup",
                ),
                Events.UNHANDLED(switch, ioswitch, pkt=pkt, addr=addrswitch),
                (
                    "send",
                    ("StateUnhandled", 3, 3, switch.serial, '{"unhandled_type": 51}'),
                    True,
                    addrswitch,
                    "GetGroup",
                ),
            ]
            record.clear()

        async def test_it_can_not_send_replies_from_res_required_false_unless_is_a_get(
            self, device, sent, record, got_event
        ):
            io = device.io["TESTIO"]
            addr = ("memory", device.serial)

            setter = make_packet(
                DeviceMessages.SetPower,
                source=4,
                sequence=5,
                target=device.serial,
                level=65535,
                res_required=False,
            )
            getter = make_packet(
                DeviceMessages.GetPower,
                source=4,
                sequence=6,
                target=device.serial,
                res_required=False,
                ack_required=False,
            )
            io.received(setter.pack().tobytes(), True, addr)

            await sent
            sent.reset()

            assert record == [
                Events.INCOMING(device, io, pkt=setter, addr=addr),
                Events.ATTRIBUTE_CHANGE(device, [ChangeAttr.test("power", 65535)], True),
                ("send", ("Acknowledgement", 4, 5, device.serial, "{}"), True, addr, "SetPower"),
            ]
            record.clear()

            io.received(getter.pack().tobytes(), True, addr)

            while len(record) != 2:
                await sent
                sent.reset()

            assert record == [
                Events.INCOMING(device, io, pkt=getter, addr=addr),
                (
                    "send",
                    ("StatePower", 4, 6, device.serial, '{"level": 65535}'),
                    True,
                    addr,
                    "GetPower",
                ),
            ]

        async def test_it_can_lose_messages(self, device, sent, record, got_event):
            io = device.io["TESTIO"]
            addr = ("memory", device.serial)

            pkt = make_packet(
                DeviceMessages.SetPower, source=2, sequence=3, target=device.serial, level=65535
            )
            io.received(pkt.pack().tobytes(), True, addr)
            await sent
            sent.reset()

            assert record == [
                Events.INCOMING(device, io, pkt=pkt, addr=addr),
                Events.ATTRIBUTE_CHANGE(device, [ChangeAttr.test("power", 65535)], True),
                ("send", ("Acknowledgement", 2, 3, device.serial, "{}"), True, addr, "SetPower"),
                (
                    "send",
                    ("StatePower", 2, 3, device.serial, '{"level": 0}'),
                    True,
                    addr,
                    "SetPower",
                ),
            ]
            record.clear()

            with io.packet_filter.lost_request(DeviceMessages.SetPower):
                io.received(pkt.pack().tobytes(), True, addr)
                while True:
                    nxt = await got_event
                    got_event.reset()
                    if nxt | Events.LOST:
                        break
                assert record == [Events.LOST(device, io, pkt=pkt, addr=addr)]
                record.clear()

            with io.packet_filter.lost_acks(DeviceMessages.SetPower):
                io.received(pkt.pack().tobytes(), True, addr)
                await sent
                sent.reset()
                assert record == [
                    Events.INCOMING(device, io, pkt=pkt, addr=addr),
                    Events.ATTRIBUTE_CHANGE(device, [ChangeAttr.test("power", 65535)], True),
                    (
                        "send",
                        ("StatePower", 2, 3, device.serial, '{"level": 65535}'),
                        True,
                        addr,
                        "SetPower",
                    ),
                ]
                record.clear()

            pkt = make_packet(
                DeviceMessages.GetPower,
                source=2,
                sequence=3,
                target=device.serial,
                ack_required=False,
            )
            io.received(pkt.pack().tobytes(), True, addr)
            await sent
            sent.reset()
            assert record == [
                Events.INCOMING(device, io, pkt=pkt, addr=addr),
                (
                    "send",
                    ("StatePower", 2, 3, device.serial, '{"level": 65535}'),
                    True,
                    addr,
                    "GetPower",
                ),
            ]
            record.clear()

            pkt = make_packet(
                DeviceMessages.SetPower, source=2, sequence=5, target=device.serial, level=0
            )

            with io.packet_filter.lost_replies(DeviceMessages.SetPower):
                io.received(pkt.pack().tobytes(), True, addr)
                await sent
                sent.reset()
                assert record == [
                    Events.INCOMING(device, io, pkt=pkt, addr=addr),
                    Events.ATTRIBUTE_CHANGE(device, [ChangeAttr.test("power", 0)], True),
                    (
                        "send",
                        ("Acknowledgement", 2, 5, device.serial, "{}"),
                        True,
                        addr,
                        "SetPower",
                    ),
                ]
                record.clear()

            pkt = make_packet(
                DeviceMessages.GetPower,
                source=2,
                sequence=6,
                target=device.serial,
                ack_required=False,
            )
            io.received(pkt.pack().tobytes(), True, addr)
            await sent
            sent.reset()
            assert record == [
                Events.INCOMING(device, io, pkt=pkt, addr=addr),
                (
                    "send",
                    ("StatePower", 2, 6, device.serial, '{"level": 0}'),
                    True,
                    addr,
                    "GetPower",
                ),
            ]
            record.clear()
