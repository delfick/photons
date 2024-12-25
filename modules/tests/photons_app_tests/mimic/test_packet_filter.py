
import pytest
from photons_app import helpers as hp
from photons_app.mimic.device import Device
from photons_app.mimic.event import Events
from photons_app.mimic.operator import Operator
from photons_app.mimic.packet_filter import Filter, SendAck, SendReplies, SendUnhandled
from photons_messages import CoreMessages, DeviceMessages
from photons_products import Products


@pytest.fixture()
def device():
    return Device("d073d5001337", Products.LCM2_A19, hp.Firmware(2, 80))


@pytest.fixture()
def io(device):
    io = Operator(device)
    io.io_source = "TEST_IO"
    return io


@pytest.fixture()
def incoming_event(device, io):
    return Events.INCOMING(
        device, io, pkt=DeviceMessages.GetPower(source=20, sequence=34, target=device.serial)
    )


class TestSendAck:
    def test_it_takes_in_an_event(self, incoming_event):
        assert SendAck(incoming_event).event is incoming_event

    async def test_it_does_not_produce_if_ack_required_is_False(self, incoming_event, device):
        incoming_event.pkt.ack_required = False
        sa = SendAck(incoming_event)

        replies = []
        async for msg in sa.process():
            replies.append(msg)
        assert replies == []

    async def test_it_produces_an_ack(self, incoming_event, device):
        sa = SendAck(incoming_event)

        replies = []
        async for msg in sa.process():
            replies.append(msg)
        assert len(replies) == 1, replies
        reply = replies[0]
        assert reply | CoreMessages.Acknowledgement
        assert reply.source == 20
        assert reply.sequence == 34
        assert reply.serial == device.serial

class TestSendReplies:
    def test_it_takes_in_an_event(self, incoming_event):
        assert SendReplies(incoming_event).event is incoming_event

    async def test_it_fills_out_each_reply_on_the_event_with_source_sequence_target_if_missing(self, incoming_event, device):
        sr = SendReplies(incoming_event)

        replies = []
        async for msg in sr.process():
            replies.append(msg)
        assert replies == []

        sending = [
            DeviceMessages.StatePower(),
            DeviceMessages.StatePower(source=45),
            DeviceMessages.StatePower(sequence=76),
            DeviceMessages.StatePower(sequence=78, target="d073d5999999"),
            DeviceMessages.StatePower(target=None),
        ]
        incoming_event.add_replies(*sending)

        for msg in sending:
            assert msg.source != 20
            assert msg.sequence != 34
            assert msg.serial != device.serial

        replies = []
        async for msg in sr.process():
            replies.append(msg)

        assert len(replies) == len(sending)
        assert all(m is n for m, n in zip(sending, replies))

        expected = [
            (20, 34, device.serial),
            (45, 34, device.serial),
            (20, 76, device.serial),
            (20, 78, "d073d5999999"),
            (20, 34, device.serial),
        ]
        for m, (src, seq, ser) in zip(replies, expected):
            assert m.source == src
            assert m.sequence == seq
            assert m.serial == ser

class TestSendUnhandled:
    def test_it_takes_in_an_event(self, incoming_event):
        assert SendUnhandled(incoming_event).event is incoming_event

    async def test_it_does_not_send_a_StateUnhandled_if_firmware_doesnt_support_it(self, device, incoming_event):
        assert not device.cap.has_unhandled

        su = SendUnhandled(incoming_event)

        replies = []
        async for msg in su.process():
            replies.append(msg)
        assert replies == []

    async def test_it_sends_a_StateUnhandled_if_firmware_does_support_it(self, incoming_event):
        device = Device(
            "d073d5001338",
            Products.LCM3_16_SWITCH,
            hp.Firmware(3, 80),
        )
        incoming_event.device = device

        assert device.cap.has_unhandled

        su = SendUnhandled(incoming_event)

        replies = []
        async for msg in su.process():
            replies.append(msg)
        assert len(replies) == 1
        reply = replies[0]
        assert reply | CoreMessages.StateUnhandled
        assert reply.unhandled_type == DeviceMessages.GetPower.Payload.message_type
        assert reply.source == 20
        assert reply.sequence == 34
        assert reply.serial == device.serial

class TestFilter:

    @pytest.fixture()
    def fltr(self):
        return Filter()

    class TestProcessRequest:

        @pytest.fixture()
        def make_incoming(self, device, io):
            def make_incoming(serial, kls=DeviceMessages.GetPower):
                return Events.INCOMING(device, io, pkt=kls(source=200, sequence=300, target=serial))

            return make_incoming

        class TestDefaults:
            async def test_it_says_yes_to_an_incoming_event_only_if_the_target_is_this_device_or_broadcast(self, make_incoming, fltr, device):
                assert await fltr.process_request(make_incoming("d073d5000000")) is False
                assert await fltr.process_request(make_incoming("d073d5000001")) is False

                assert await fltr.process_request(make_incoming(device.serial)) is True
                assert await fltr.process_request(make_incoming("0" * 12)) is True

        class TestSeeRequest:
            async def test_it_looks_at_request_but_does_not_affect_outcome(self, make_incoming, fltr, device):
                got = []

                async def intercept1(event):
                    assert event | Events.INCOMING
                    got.append(1)
                    return 500

                async def intercept2(event):
                    assert event | Events.INCOMING
                    got.append(2)
                    return 600

                with fltr.intercept_see_request(intercept1):
                    assert await fltr.process_request(make_incoming("d073d5000000")) is False

                    with fltr.intercept_see_request(intercept2):
                        assert await fltr.process_request(make_incoming("d073d5000001")) is False

                    assert await fltr.process_request(make_incoming(device.serial)) is True
                    assert await fltr.process_request(make_incoming("0" * 12)) is True

                assert got == [1, 2, 1, 1]

        class TestInterceptRequest:
            async def test_it_looks_at_request_after_see_request_and_affects_outcome(self, make_incoming, fltr, device):
                got = []

                async def see1(event):
                    assert event | Events.INCOMING
                    got.append("s1")
                    return 800

                async def intercept1(event, Cont):
                    assert event | Events.INCOMING
                    got.append("i1")
                    return 500

                async def see2(event):
                    assert event | Events.INCOMING
                    got.append("s2")
                    return 900

                async def intercept2(event, Cont):
                    assert event | Events.INCOMING
                    got.append("i2")
                    return 600

                with fltr.intercept_process_request(intercept1):
                    with fltr.intercept_see_request(see1):
                        assert await fltr.process_request(make_incoming("d073d5000000")) == 500

                        with fltr.intercept_process_request(intercept2):
                            assert await fltr.process_request(make_incoming("d073d5000001")) == 600

                        with fltr.intercept_see_request(see2):
                            assert await fltr.process_request(make_incoming(device.serial)) == 500

                    assert await fltr.process_request(make_incoming("0" * 12)) == 500

                assert got == ["s1", "i1", "s1", "i2", "s2", "i1", "i1"]

            async def test_it_can_continue_as_normal_if_Cont_is_raised(self, make_incoming, fltr, device):
                got = []

                async def intercept(event, Cont):
                    assert event | Events.INCOMING
                    got.append("i1")
                    raise Cont()

                with fltr.intercept_process_request(intercept):
                    assert await fltr.process_request(make_incoming(device.serial)) is True
                    assert got == ["i1"]
                    assert await fltr.process_request(make_incoming("d073d5000000")) is False

                assert got == ["i1", "i1"]

        class TestLostRequest:
            async def test_it_causes_a_message_to_return_None(self, fltr, device, make_incoming):
                await fltr.process_request(
                    make_incoming(device.serial, DeviceMessages.GetPower)
                ) is True

                with fltr.lost_request(DeviceMessages.GetPower, DeviceMessages.SetPower):
                    await fltr.process_request(
                        make_incoming(device.serial, DeviceMessages.GetPower)
                    ) is None
                    await fltr.process_request(
                        make_incoming("d073d5656565", DeviceMessages.GetPower)
                    ) is None

                    await fltr.process_request(
                        make_incoming(device.serial, DeviceMessages.SetPower)
                    ) is None

                    await fltr.process_request(
                        make_incoming(device.serial, DeviceMessages.GetLabel)
                    ) is True

                    with fltr.lost_request(DeviceMessages.SetGroup):
                        await fltr.process_request(
                            make_incoming(device.serial, DeviceMessages.GetPower)
                        ) is None
                        await fltr.process_request(
                            make_incoming(device.serial, DeviceMessages.GetGroup)
                        ) is None

                    await fltr.process_request(
                        make_incoming(device.serial, DeviceMessages.GetGroup)
                    ) is True

                await fltr.process_request(
                    make_incoming(device.serial, DeviceMessages.GetPower)
                ) is True

    class TestOutgoing:

        @pytest.fixture()
        def make_incoming(self, device, io):
            def make_incoming(kls):
                return Events.INCOMING(
                    device, io, pkt=kls(source=200, sequence=300, target=device.serial)
                )

            return make_incoming

        @pytest.fixture()
        async def outgoing(self, fltr):
            async def outgoing(reply, request_event):
                replies = []
                async for msg in fltr.outgoing(reply, request_event):
                    replies.append(msg)
                return replies

            return outgoing

        class TestDefaults:
            async def test_it_yields_the_reply(self, make_incoming, outgoing):
                request_event = make_incoming(DeviceMessages.GetPower)
                reply = DeviceMessages.StatePower()
                assert await outgoing(reply, request_event) == [reply]

            async def test_it_doesnt_give_replies_if_no_res_required(self, make_incoming, outgoing):
                request_event = make_incoming(DeviceMessages.SetPower)
                request_event.pkt.res_required = False
                reply = DeviceMessages.StatePower()
                assert await outgoing(reply, request_event) == []

            async def test_it_doesnt_give_replies_if_no_res_required_unless_is_a_Get(self, make_incoming, outgoing):
                request_event = make_incoming(DeviceMessages.GetPower)
                request_event.pkt.res_required = False
                reply = DeviceMessages.StatePower()
                assert await outgoing(reply, request_event) == [reply]

        class TestLostAcks:
            async def test_it_can_ignore_acks_if_request_is_from_a_certain_class(self, make_incoming, outgoing, fltr):
                request_event = make_incoming(DeviceMessages.GetPower)
                ack = CoreMessages.Acknowledgement()

                assert await outgoing(ack, request_event) == [ack]

                with fltr.lost_acks(DeviceMessages.GetPower):
                    assert await outgoing(ack, request_event) == []

                    with fltr.lost_acks(DeviceMessages.SetPower):
                        assert await outgoing(ack, request_event) == []
                        assert await outgoing(ack, make_incoming(DeviceMessages.SetPower)) == []

                    assert await outgoing(ack, request_event) == []
                    assert await outgoing(ack, make_incoming(DeviceMessages.SetPower)) == [ack]

                assert await outgoing(ack, request_event) == [ack]

        class TestLostReplies:

            async def test_it_can_ignore_replies_if_request_is_from_a_certain_class(self, make_incoming, outgoing, fltr):
                request_event = make_incoming(DeviceMessages.GetPower)
                ack = CoreMessages.Acknowledgement()
                reply = DeviceMessages.StatePower()

                assert await outgoing(ack, request_event) == [ack]
                assert await outgoing(reply, request_event) == [reply]

                with fltr.lost_replies(DeviceMessages.GetPower):
                    assert await outgoing(ack, request_event) == [ack]
                    assert await outgoing(reply, request_event) == []

                    with fltr.lost_replies(DeviceMessages.SetPower):
                        assert await outgoing(ack, request_event) == [ack]
                        assert await outgoing(reply, request_event) == []

                        assert await outgoing(ack, make_incoming(DeviceMessages.SetPower)) == [ack]
                        assert await outgoing(reply, make_incoming(DeviceMessages.SetPower)) == []

                    assert await outgoing(ack, request_event) == [ack]
                    assert await outgoing(reply, request_event) == []

                    assert await outgoing(ack, make_incoming(DeviceMessages.SetPower)) == [ack]
                    assert await outgoing(reply, make_incoming(DeviceMessages.SetPower)) == [reply]

                assert await outgoing(ack, request_event) == [ack]
                assert await outgoing(reply, request_event) == [reply]

            async def test_it_can_ignore_replies_that_themselves_are_a_particular_class(self, make_incoming, outgoing, fltr):
                request_event = make_incoming(DeviceMessages.GetPower)
                ack = CoreMessages.Acknowledgement()
                reply1 = DeviceMessages.StatePower()
                reply2 = DeviceMessages.StateLabel()

                assert await outgoing(ack, request_event) == [ack]
                assert await outgoing(reply1, request_event) == [reply1]
                assert await outgoing(reply2, request_event) == [reply2]

                with fltr.lost_replies(DeviceMessages.StatePower):
                    assert await outgoing(ack, request_event) == [ack]
                    assert await outgoing(reply1, request_event) == []
                    assert await outgoing(reply2, request_event) == [reply2]

                    with fltr.lost_replies(DeviceMessages.StateLabel):
                        assert await outgoing(ack, request_event) == [ack]
                        assert await outgoing(reply1, request_event) == []
                        assert await outgoing(reply2, request_event) == []

                        assert await outgoing(ack, make_incoming(DeviceMessages.SetPower)) == [ack]
                        assert await outgoing(reply1, make_incoming(DeviceMessages.SetPower)) == []
                        assert await outgoing(reply2, make_incoming(DeviceMessages.SetPower)) == []

                    assert await outgoing(ack, request_event) == [ack]
                    assert await outgoing(reply1, request_event) == []
                    assert await outgoing(reply2, request_event) == [reply2]

                    assert await outgoing(ack, make_incoming(DeviceMessages.SetPower)) == [ack]
                    assert await outgoing(reply1, make_incoming(DeviceMessages.SetPower)) == []
                    assert await outgoing(reply2, make_incoming(DeviceMessages.SetPower)) == [
                        reply2
                    ]

                assert await outgoing(ack, request_event) == [ack]
                assert await outgoing(reply1, request_event) == [reply1]
                assert await outgoing(reply2, request_event) == [reply2]

        class TestSeeOutgoing:
            async def test_it_looks_at_event_but_does_not_affect_outcome(self, outgoing, make_incoming, fltr, device):
                request_event = make_incoming(DeviceMessages.GetPower)
                ack = CoreMessages.Acknowledgement()
                reply = DeviceMessages.StatePower()
                got = []

                async def intercept1(rep, req_event):
                    assert rep in (ack, reply)
                    assert req_event | Events.INCOMING
                    got.append(1)
                    return 500

                async def intercept2(rep, req_event):
                    assert rep in (ack, reply)
                    assert req_event | Events.INCOMING
                    got.append(2)
                    return 600

                with fltr.intercept_see_outgoing(intercept1):
                    assert await outgoing(reply, request_event) == [reply]

                    with fltr.intercept_see_outgoing(intercept2):
                        assert await outgoing(reply, request_event) == [reply]

                    assert await outgoing(ack, request_event) == [ack]
                    assert await outgoing(reply, request_event) == [reply]

                assert await outgoing(ack, request_event) == [ack]
                assert got == [1, 2, 1, 1]

        class TestInterceptOutgoing:
            async def test_it_looks_at_outgoing_after_see_outgoing_and_affects_outcome(self, outgoing, make_incoming, fltr, device):
                request_event = make_incoming(DeviceMessages.GetPower)
                reply1 = DeviceMessages.StatePower()
                reply2 = DeviceMessages.StateLabel()
                reply3 = DeviceMessages.StateGroup()
                reply4 = DeviceMessages.StateLocation()

                got = []

                async def see1(rep, req_event):
                    assert rep in (reply1, reply2, reply3, reply4)
                    assert req_event | Events.INCOMING
                    got.append("s1")
                    return 800

                async def intercept1(rep, req_event, Cont):
                    assert rep in (reply1, reply2, reply3, reply4)
                    assert req_event | Events.INCOMING
                    got.append("i1")
                    yield reply2

                async def see2(rep, req_event):
                    assert rep in (reply1, reply2, reply3, reply4)
                    assert req_event | Events.INCOMING
                    got.append("s2")
                    return 900

                async def intercept2(rep, req_event, Cont):
                    assert rep in (reply1, reply2, reply3, reply4)
                    assert req_event | Events.INCOMING
                    got.append("i2")
                    yield reply1
                    yield reply3

                with fltr.intercept_process_outgoing(intercept1):
                    with fltr.intercept_see_outgoing(see1):
                        assert await outgoing(reply4, request_event) == [reply2]

                        with fltr.intercept_process_outgoing(intercept2):
                            assert await outgoing(reply4, request_event) == [reply1, reply3]

                        with fltr.intercept_see_outgoing(see2):
                            assert await outgoing(reply4, request_event) == [reply2]

                    assert await outgoing(reply4, request_event) == [reply2]

                assert got == ["s1", "i1", "s1", "i2", "s2", "i1", "i1"]
                assert await outgoing(reply4, request_event) == [reply4]

            async def test_it_can_continue_as_normal_if_Cont_is_raised(self, make_incoming, outgoing, fltr, device):
                got = []

                request_event = make_incoming(DeviceMessages.GetPower)
                reply = DeviceMessages.StatePower()

                async def intercept(rep, req_event, Cont):
                    assert req_event | Events.INCOMING
                    got.append("i1")
                    raise Cont()
                    if False:
                        yield

                with fltr.intercept_process_outgoing(intercept):
                    assert await outgoing(reply, request_event) == [reply]

                assert got == ["i1"]
