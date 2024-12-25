
import asyncio
import sys
from collections import defaultdict
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertSameError
from photons_app import helpers as hp
from photons_app.errors import RunErrors, TimedOut
from photons_app.mimic.attrs import ChangeAttr
from photons_app.mimic.event import Events
from photons_control.script import FromGenerator
from photons_messages import CoreMessages, DeviceMessages
from photons_products import Products

devices = pytest.helpers.mimic(has_udp=True, has_memory=False)

devices.add("one")("d073d5001337", Products.LCM2_A19, hp.Firmware(2, 77))
devices.add("two")("d073d5001338", Products.LCM2_A19, hp.Firmware(2, 77))


@pytest.fixture()
async def sender(final_future):
    async with devices.for_test(final_future, udp=True) as sender:
        yield sender


class TestSendingMessages:

    @pytest.fixture
    def V(self, sender):
        class V:
            target = sender.transport_target
            device = devices["one"]
            device2 = devices["two"]
            device_port = devices["one"].io["UDP"].options.port

        return V()

    class TestSendApi:

        async def test_it_works_with_the_sender_as_sender_api(self, V, sender):
            original = DeviceMessages.EchoRequest(echoing=b"hi")

            got = defaultdict(list)
            async for pkt in sender(original, V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async def test_it_works_with_targetsend_api(self, V):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            V.target.default_broadcast = ("127.0.0.1", V.device_port)

            got = defaultdict(list)
            async for pkt in V.target.send(original, V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async def test_it_sender_also_works_as_a_synchronous_api(self, V, sender):
            original = DeviceMessages.EchoRequest(echoing=b"hi")

            got = defaultdict(list)
            for pkt in await sender(original, V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async def test_it_targetsend_also_works_as_a_synchronous_api(self, V):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            V.target.default_broadcast = ("127.0.0.1", V.device_port)

            got = defaultdict(list)
            for pkt in await V.target.send(original, V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        class TestBreakingAStream:

            async def test_it_is_possible_to_cleanly_stop_when_sending_just_a_packet(self, V, sender):
                got = []
                msg = DeviceMessages.SetPower(level=0)
                async with sender(msg, [V.device.serial, V.device2.serial]) as pkts:
                    async for pkt in pkts:
                        got.append(pkt)
                        raise pkts.StopPacketStream()

                assert len(got) == 1
                expected = (DeviceMessages.StatePower, {"level": 0})
                reply = expected[0].create(**expected[1])
                pytest.helpers.assertSamePackets(got, expected)

                device = V.device
                io = device.io["UDP"]
                assert devices.store(device) == [
                    Events.INCOMING(device, io, pkt=msg),
                    Events.ATTRIBUTE_CHANGE(device, [ChangeAttr.test("power", 0)], True),
                    Events.OUTGOING(
                        device, io, pkt=CoreMessages.Acknowledgement(), replying_to=msg
                    ),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=msg),
                ]

                device2 = V.device2
                io2 = device2.io["UDP"]
                assert devices.store(device2) == [
                    Events.INCOMING(device2, io2, pkt=msg),
                    Events.ATTRIBUTE_CHANGE(device2, [ChangeAttr.test("power", 0)], True),
                    Events.OUTGOING(
                        device2, io2, pkt=CoreMessages.Acknowledgement(), replying_to=msg
                    ),
                    Events.OUTGOING(device2, io2, pkt=reply, replying_to=msg),
                ]

            async def test_it_is_possible_to_cleanly_stop(self, V, sender, FakeTime, MockedCallLater):
                original = DeviceMessages.EchoRequest(echoing=b"hi", ack_required=False)

                async def gen(sd, reference, **kwargs):
                    async with hp.tick(0, min_wait=0) as ticks:
                        async for _ in ticks:
                            await (yield original)

                msg = FromGenerator(gen, reference_override=True)

                got = []
                with FakeTime() as t:
                    async with MockedCallLater(t, precision=0.01):
                        async with sender(msg, V.device.serial) as pkts:
                            async for pkt in pkts:
                                got.append(pkt)
                                if len(got) == 5:
                                    raise pkts.StopPacketStream()

                assert len(got) == 5
                expected = (DeviceMessages.EchoResponse, {"echoing": b"hi"})
                reply = expected[0].create(**expected[1])
                pytest.helpers.assertSamePackets(got, *[expected] * 5)

                device = V.device
                io = device.io["UDP"]
                assert devices.store(device) == [
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                ]

            async def test_it_is_possible_to_perform_finally_blocks_in_deep_layers(self, V, sender):
                original = DeviceMessages.EchoRequest(echoing=b"hi", ack_required=False)
                called = []

                async def gen(sd, reference, **kwargs):
                    async with hp.tick(0, min_wait=0, name="test") as ticks:
                        async for i, _ in ticks:
                            try:
                                called.append(("start", i))
                                await (yield original)
                            except:
                                called.append(("except", i, sys.exc_info()))
                                raise
                            finally:
                                called.append(("finally", i))

                msg = FromGenerator(gen, reference_override=True)

                got = []
                async with sender(msg, V.device.serial) as pkts:
                    async for pkt in pkts:
                        got.append(pkt)
                        if len(got) == 5:
                            raise pkts.StopPacketStream()

                assert len(got) == 5
                expected = (DeviceMessages.EchoResponse, {"echoing": b"hi"})
                reply = expected[0].create(**expected[1])
                pytest.helpers.assertSamePackets(got, *[expected] * 5)

                device = V.device
                io = device.io["UDP"]
                assert devices.store(device) == [
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                ]

                assert called == [
                    ("start", 1),
                    ("finally", 1),
                    ("start", 2),
                    ("finally", 2),
                    ("start", 3),
                    ("finally", 3),
                    ("start", 4),
                    ("finally", 4),
                    ("start", 5),
                    ("except", 5, (asyncio.CancelledError, mock.ANY, mock.ANY)),
                    ("finally", 5),
                ]

            async def test_it_is_possible_to_perform_finally_blocks_in_deeper_layers(self, V, sender):
                original2 = DeviceMessages.EchoRequest(echoing=b"bye", ack_required=False)
                called = []

                async def gen(sd, reference, **kwargs):
                    async with hp.tick(0, max_iterations=3, name="test_m1", min_wait=0) as ticks:
                        async for i, _ in ticks:
                            try:
                                called.append(("m1_start", i))
                                await (yield original2)
                            except:
                                called.append(("m1_except", i, type(sys.exc_info()[1]).__name__))
                                raise
                            finally:
                                called.append(("m1_finally", i))

                msg = FromGenerator(gen, reference_override=True)

                original1 = DeviceMessages.EchoRequest(echoing=b"hi", ack_required=False)

                async def gen(sd, reference, **kwargs):
                    async with hp.tick(0, min_wait=0, name="test_m2") as ticks:
                        async for i, _ in ticks:
                            try:
                                called.append(("m2_start", i))
                                await (yield [original1, msg])
                            except:
                                called.append(("m2_except", i, type(sys.exc_info()[1]).__name__))
                                raise
                            finally:
                                called.append(("m2_finally", i))

                msg2 = FromGenerator(gen, reference_override=True)

                got = []
                async with sender(msg2, V.device.serial) as pkts:
                    async for pkt in pkts:
                        got.append(pkt)
                        if len(got) == 10:
                            raise pkts.StopPacketStream()

                assert len(got) == 10
                expected = [
                    (DeviceMessages.EchoResponse, {"echoing": b"hi"}),
                    (DeviceMessages.EchoResponse, {"echoing": b"bye"}),
                ]
                reply1 = expected[0][0].create(**expected[0][1])
                reply2 = expected[1][0].create(**expected[1][1])
                pytest.helpers.assertSamePackets(
                    got, *[expected[0], *[expected[1]] * 3] * 2, expected[0], expected[1]
                )

                assert len(got) == 10
                device = V.device
                io = device.io["UDP"]
                assert devices.store(device) == [
                    Events.INCOMING(device, io, pkt=original1),
                    Events.OUTGOING(device, io, pkt=reply1, replying_to=original1),
                    Events.INCOMING(device, io, pkt=original2),
                    Events.OUTGOING(device, io, pkt=reply2, replying_to=original2),
                    Events.INCOMING(device, io, pkt=original2),
                    Events.OUTGOING(device, io, pkt=reply2, replying_to=original2),
                    Events.INCOMING(device, io, pkt=original2),
                    Events.OUTGOING(device, io, pkt=reply2, replying_to=original2),
                    #
                    Events.INCOMING(device, io, pkt=original1),
                    Events.OUTGOING(device, io, pkt=reply1, replying_to=original1),
                    Events.INCOMING(device, io, pkt=original2),
                    Events.OUTGOING(device, io, pkt=reply2, replying_to=original2),
                    Events.INCOMING(device, io, pkt=original2),
                    Events.OUTGOING(device, io, pkt=reply2, replying_to=original2),
                    Events.INCOMING(device, io, pkt=original2),
                    Events.OUTGOING(device, io, pkt=reply2, replying_to=original2),
                    #
                    Events.INCOMING(device, io, pkt=original1),
                    Events.OUTGOING(device, io, pkt=reply1, replying_to=original1),
                    Events.INCOMING(device, io, pkt=original2),
                    Events.OUTGOING(device, io, pkt=reply2, replying_to=original2),
                ]

                assert called == [
                    ("m2_start", 1),
                    ("m1_start", 1),
                    ("m1_finally", 1),
                    ("m1_start", 2),
                    ("m1_finally", 2),
                    ("m1_start", 3),
                    ("m1_finally", 3),
                    ("m2_finally", 1),
                    ("m2_start", 2),
                    ("m1_start", 1),
                    ("m1_finally", 1),
                    ("m1_start", 2),
                    ("m1_finally", 2),
                    ("m1_start", 3),
                    ("m1_finally", 3),
                    ("m2_finally", 2),
                    ("m2_start", 3),
                    ("m1_start", 1),
                    ("m2_except", 3, "CancelledError"),
                    ("m2_finally", 3),
                    ("m1_except", 1, "CancelledError"),
                    ("m1_finally", 1),
                ]

            async def test_it_stop_doesnt_add_to_error_catcher(self, V, sender):
                original = DeviceMessages.EchoRequest(echoing=b"hi")

                async def gen(sd, reference, **kwargs):
                    async with hp.tick(0, min_wait=0) as ticks:
                        async for _ in ticks:
                            await (yield original)

                msg = FromGenerator(gen, reference_override=True)

                got = []
                errors = []
                async with sender(msg, V.device.serial, error_catcher=errors) as pkts:
                    async for pkt in pkts:
                        got.append(1)
                        if len(got) == 5:
                            raise pkts.StopPacketStream()

                assert not errors
                assert len(got) == 5

            async def test_it_allows_errors_to_go_to_an_error_catcher(self, V, FakeTime, MockedCallLater, sender):
                ack = CoreMessages.Acknowledgement()
                original = DeviceMessages.EchoRequest(echoing=b"hi")
                reply = DeviceMessages.EchoResponse(echoing=b"hi")

                async def gen(sd, reference, **kwargs):
                    assert await (
                        yield DeviceMessages.EchoRequest(echoing=b"hi", target=V.device.serial)
                    )
                    assert not await (
                        yield DeviceMessages.EchoRequest(echoing=b"hi", target=V.device2.serial)
                    )
                    for i in range(5):
                        assert await (
                            yield DeviceMessages.EchoRequest(echoing=b"hi", target=V.device.serial)
                        )

                msg = FromGenerator(gen)

                got = []
                errors = []
                io2 = V.device2.io["UDP"]
                with FakeTime() as t:
                    async with MockedCallLater(t, precision=0.01):
                        with io2.packet_filter.lost_replies(DeviceMessages.EchoResponse):
                            async with sender(
                                msg,
                                [V.device.serial, V.device2.serial],
                                message_timeout=2,
                                error_catcher=errors,
                            ) as pkts:
                                async for pkt in pkts:
                                    got.append(1)
                                    if len(got) == 3:
                                        raise pkts.StopPacketStream()

                assert len(errors) == 1
                assertSameError(
                    errors[0],
                    TimedOut,
                    "Waiting for reply to a packet",
                    {"serial": V.device2.serial, "sent_pkt_type": 58},
                    [],
                )

                assert len(got) == 3
                device = V.device
                io = device.io["UDP"]
                records = devices.store(device)
                assert 9 <= len(records.record) <= 15
                assert len(records.record) % 3 == 0
                assert records == [
                    Events.INCOMING(device, io, pkt=original),
                    Events.OUTGOING(device, io, pkt=ack, replying_to=original),
                    Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                ] * (len(records.record) // 3)

                device2 = V.device2
                io2 = device2.io["UDP"]
                records = devices.store(device2)
                assert 14 <= len(records.record) <= 16
                assert len(records.record) % 2 == 0
                assert records == [
                    Events.INCOMING(device2, io2, pkt=original),
                    Events.OUTGOING(device2, io2, pkt=ack, replying_to=original),
                ] * (len(records.record) // 2)

            async def test_it_doesnt_stop_errors(self, V, FakeTime, MockedCallLater, sender):
                ack = CoreMessages.Acknowledgement()
                original = DeviceMessages.EchoRequest(echoing=b"hi")
                reply = DeviceMessages.EchoResponse(echoing=b"hi")

                async def gen(sd, reference, **kwargs):
                    assert await (
                        yield DeviceMessages.EchoRequest(echoing=b"hi", target=V.device.serial)
                    )
                    assert not await (
                        yield DeviceMessages.EchoRequest(echoing=b"hi", target=V.device2.serial)
                    )
                    assert not await (
                        yield DeviceMessages.EchoRequest(echoing=b"hi", target=V.device2.serial)
                    )
                    for i in range(5):
                        assert await (
                            yield DeviceMessages.EchoRequest(echoing=b"hi", target=V.device.serial)
                        )

                msg = FromGenerator(gen)

                got = []
                error = None
                io2 = V.device2.io["UDP"]
                with FakeTime() as t:
                    async with MockedCallLater(t, precision=0.01):
                        try:
                            with io2.packet_filter.lost_replies(DeviceMessages.EchoResponse):
                                async with sender(
                                    msg, [V.device.serial, V.device2.serial], message_timeout=2
                                ) as pkts:
                                    async for pkt in pkts:
                                        got.append(1)
                                        if len(got) == 4:
                                            raise pkts.StopPacketStream()
                        except RunErrors as e:
                            error = e

                        assert isinstance(error, RunErrors)
                        assert len(error.errors) == 2
                        for e in error.errors:
                            assertSameError(
                                e,
                                TimedOut,
                                "Waiting for reply to a packet",
                                {"serial": V.device2.serial, "sent_pkt_type": 58},
                                [],
                            )

                        assert len(got) == 4
                        device = V.device
                        io = device.io["UDP"]
                        records = devices.store(device)
                        assert 12 <= len(records.record) <= 18
                        assert len(records.record) % 3 == 0
                        assert records == [
                            Events.INCOMING(device, io, pkt=original),
                            Events.OUTGOING(device, io, pkt=ack, replying_to=original),
                            Events.OUTGOING(device, io, pkt=reply, replying_to=original),
                        ] * (len(records.record) // 3)

                        device2 = V.device2
                        io2 = device2.io["UDP"]
                        records = devices.store(device2)
                        assert 30 <= len(records.record) <= 40
                        assert len(records.record) % 2 == 0
                        assert records == [
                            Events.INCOMING(device2, io2, pkt=original),
                            Events.OUTGOING(device2, io2, pkt=ack, replying_to=original),
                        ] * (len(records.record) // 2)

    class TestRunWithApi:

        async def test_it_works_with_the_run_with_api_with_sender(self, V, sender):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            script = V.target.script(original)

            got = defaultdict(list)
            async for pkt in script.run_with(V.device.serial, sender):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

            original = DeviceMessages.EchoRequest(echoing=b"hi")
            script = V.target.script(original)

            got = defaultdict(list)
            async for pkt, remote_addr, sender_message in script.run_with(V.device.serial, sender):
                assert pkt.Information.remote_addr == remote_addr
                assert pkt.Information.sender_message is sender_message
                assert sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async def test_it_works_with_run_with_api_without_sender(self, V, sender):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            script = V.target.script(original)
            V.target.default_broadcast = ("127.0.0.1", V.device_port)

            got = defaultdict(list)
            async for pkt in script.run_with(V.device.serial, sender=sender):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

            got = defaultdict(list)
            async for pkt, remote_addr, sender_message in script.run_with(
                V.device.serial, sender=sender
            ):
                assert pkt.Information.remote_addr == remote_addr
                assert pkt.Information.sender_message is sender_message
                assert sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async def test_it_works_with_the_run_with_all_api_with_sender(self, V, sender):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            script = V.target.script(original)

            got = defaultdict(list)
            for pkt in await script.run_with_all(V.device.serial, sender):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

            original = DeviceMessages.EchoRequest(echoing=b"hi")
            script = V.target.script(original)

            got = defaultdict(list)
            for pkt, remote_addr, sender_message in await script.run_with_all(
                V.device.serial, sender
            ):
                assert pkt.Information.remote_addr == remote_addr
                assert pkt.Information.sender_message is sender_message
                assert sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async def test_it_works_with_run_with_all_api_without_sender(self, V):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            script = V.target.script(original)
            V.target.default_broadcast = ("127.0.0.1", V.device_port)

            got = defaultdict(list)
            for pkt in await script.run_with_all(V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

            got = defaultdict(list)
            for pkt, remote_addr, sender_message in await script.run_with_all(V.device.serial):
                assert pkt.Information.remote_addr == remote_addr
                assert pkt.Information.sender_message is sender_message
                assert sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}
