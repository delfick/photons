
import time

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_app.errors import TimedOut
from photons_app.special import FoundSerials
from photons_messages import (
    CoreMessages,
    DeviceMessages,
    DiscoveryMessages,
    MultiZoneMessages,
    Services,
)
from photons_products import Products

devices = pytest.helpers.mimic()
devices.add("strip")(
    "d073d5001337", Products.LCM2_Z, hp.Firmware(2, 80), value_store={"zones_count": 22}
)


@pytest.fixture()
async def sender(final_future):
    async with devices.for_test(final_future) as sender:
        await FoundSerials().find(sender, timeout=1)
        sender.received.clear()
        for store in devices.stores.values():
            store.clear()
        yield sender


@pytest.fixture(autouse=True)
async def reset_devices(sender):
    for device in devices:
        await device.reset()
        devices.store(device).clear()


def assertSent(sender, *expected):
    assert len(sender.received) == len(expected)
    for i, (g, e) in enumerate(zip(sender.received, expected)):
        g = list(g)
        e = list(e)

        g[-1] = g[-1].as_dict()
        e[-1] = e[-1].as_dict()

        if g != e:
            print(f"{i}:\n\t{g}\n\t{e}")
        assert g == e


class TestSendingASingleMessages:

    @pytest.fixture()
    def send_single(self, sender):
        async def send_single(original, **kwargs):
            packet = original.clone()
            packet.update(target="d073d5001337", sequence=1, source=2)
            return await sender.send_single(original, packet, **kwargs)

        return send_single

    @pytest.fixture()
    def device(self):
        return devices["strip"]

    class TestHappyPath:

        async def test_it_can_send_and_receive_a_single_message(self, send_single, device):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            result = await send_single(original, timeout=1)

            expected = (DeviceMessages.EchoResponse, {"echoing": b"hi"})
            pytest.helpers.assertSamePackets(result, expected)

            assert devices.store(device) == [
                devices.Events.INCOMING(device, device.io["MEMORY"], pkt=original),
                devices.Events.OUTGOING(
                    device,
                    device.io["MEMORY"],
                    pkt=CoreMessages.Acknowledgement,
                    replying_to=original,
                ),
                devices.Events.OUTGOING(
                    device, device.io["MEMORY"], pkt=expected, replying_to=original
                ),
            ]

        async def test_it_can_get_multiple_replies(self, send_single, device):
            await device.event(
                devices.Events.SET_ZONES, zones=[(i, hp.Color(i, 1, 1, 3500)) for i in range(22)]
            )
            devices.store(device).clear()

            original = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
            expected = [
                (
                    MultiZoneMessages.StateMultiZone,
                    {
                        "zones_count": 22,
                        "zone_index": 0,
                        "colors": [hp.Color(i, 1, 1, 3500) for i in range(8)],
                    },
                ),
                (
                    MultiZoneMessages.StateMultiZone,
                    {
                        "zones_count": 22,
                        "zone_index": 8,
                        "colors": [hp.Color(i, 1, 1, 3500) for i in range(8, 16)],
                    },
                ),
                (
                    MultiZoneMessages.StateMultiZone,
                    {
                        "zones_count": 22,
                        "zone_index": 16,
                        "colors": [hp.Color(i, 1, 1, 3500) for i in range(16, 22)]
                        + [hp.Color(0, 0, 0, 0) for _ in range(22, 24)],
                    },
                ),
            ]

            result = await send_single(original, timeout=1)
            pytest.helpers.assertSamePackets(result, *expected)

            assert devices.store(device) == [
                devices.Events.INCOMING(device, device.io["MEMORY"], pkt=original),
                devices.Events.OUTGOING(
                    device,
                    device.io["MEMORY"],
                    pkt=CoreMessages.Acknowledgement,
                    replying_to=original,
                ),
                *[
                    devices.Events.OUTGOING(
                        device, device.io["MEMORY"], pkt=ex, replying_to=original
                    )
                    for ex in expected
                ],
            ]

        async def test_it_can_get_unlimited_replies(self, send_single, device, FakeTime, MockedCallLater):
            original = DiscoveryMessages.GetService(ack_required=False)
            with FakeTime() as t:
                async with MockedCallLater(t):
                    result = await send_single(original, timeout=1)

            assert t.time == 0.1

            expected = (
                DiscoveryMessages.StateService,
                {"service": Services.UDP, "port": device.io["MEMORY"].options.port},
            )
            pytest.helpers.assertSamePackets(result, expected)
            assert devices.store(device) == [
                devices.Events.INCOMING(device, device.io["MEMORY"], pkt=original),
                devices.Events.OUTGOING(
                    device, device.io["MEMORY"], pkt=expected, replying_to=original
                ),
            ]

    class TestTimeouts:

        async def test_it_can_retry_until_it_gets_a_timeout(self, send_single, sender, device, FakeTime, MockedCallLater):
            original = DeviceMessages.EchoRequest(echoing=b"hi")

            with FakeTime() as t:
                async with MockedCallLater(t):
                    with assertRaises(
                        TimedOut,
                        "Waiting for reply to a packet",
                        sent_pkt_type=58,
                        sequence=1,
                        source=2,
                        serial=device.serial,
                    ):
                        async with device.offline():
                            await send_single(original, timeout=2)

            assert t.time == 2

            assertSent(
                sender,
                *[
                    (round(at * 0.2, 3), device.serial, original.Payload.__name__, original.payload)
                    for at in range(int(2 / 0.2))
                ],
            )

        async def test_it_can_retry_until_it_gets_a_result(self, send_single, sender, device, FakeTime, MockedCallLater):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            io = device.io["MEMORY"]

            with FakeTime() as t:

                @io.packet_filter.intercept_process_request
                async def intercept(event, Cont):
                    if time.time() == 0.6:
                        return True
                    return None

                with intercept:
                    async with MockedCallLater(t):
                        result = await send_single(original, timeout=2)

            assert t.time == 0.6
            expected = (DeviceMessages.EchoResponse, {"echoing": b"hi", "sequence": 3})
            pytest.helpers.assertSamePackets(result, expected)
            assert devices.store(device) == [
                devices.Events.LOST(device, device.io["MEMORY"], pkt=original),
                devices.Events.LOST(device, device.io["MEMORY"], pkt=original),
                devices.Events.LOST(device, device.io["MEMORY"], pkt=original),
                devices.Events.INCOMING(device, device.io["MEMORY"], pkt=original),
                devices.Events.OUTGOING(
                    device,
                    device.io["MEMORY"],
                    pkt=CoreMessages.Acknowledgement,
                    replying_to=original,
                ),
                devices.Events.OUTGOING(
                    device, device.io["MEMORY"], pkt=expected, replying_to=original
                ),
            ]

            assertSent(
                sender,
                *[
                    (at, device.serial, original.Payload.__name__, original.payload)
                    for at in [0, 0.2, 0.4, 0.6]
                ],
            )

        async def test_it_can_give_up_on_getting_multiple_messages_that_have_a_set_length(self, send_single, sender, device, FakeTime, MockedCallLater):
            original = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
            io = device.io["MEMORY"]

            with FakeTime() as t:

                @io.packet_filter.intercept_process_request
                async def process_request(event, Cont):
                    if event | MultiZoneMessages.GetColorZones:
                        event.set_replies(Cont)
                        event.handled = False
                        event._viewers_only = True
                        return True
                    else:
                        raise Cont()

                @io.packet_filter.intercept_process_outgoing
                async def process_outgoing(reply, req_event, Cont):
                    if req_event | MultiZoneMessages.GetColorZones:
                        yield MultiZoneMessages.StateMultiZone.create(
                            zones_count=22,
                            zone_index=0,
                            colors=[hp.Color(i, 1, 1, 3500) for i in range(8)],
                            **reply,
                        )
                        yield MultiZoneMessages.StateMultiZone.create(
                            zones_count=22,
                            zone_index=8,
                            colors=[hp.Color(i, 1, 1, 3500) for i in range(8, 16)],
                        )
                    else:
                        raise Cont()

                with process_request, process_outgoing:
                    async with MockedCallLater(t):
                        with assertRaises(
                            TimedOut,
                            "Waiting for reply to a packet",
                            sent_pkt_type=502,
                            sequence=1,
                            source=2,
                            serial=device.serial,
                        ):
                            await send_single(original, timeout=3)

            assert t.time == 3

            assertSent(
                sender,
                *[
                    (round(at * 0.2, 3), device.serial, original.Payload.__name__, original.payload)
                    for at in range(int(round(3 / 0.2)))
                ],
            )

        async def test_it_can_retry_getting_multiple_replies_till_it_has_all_replies(self, send_single, sender, device, FakeTime, MockedCallLater):
            original = MultiZoneMessages.GetColorZones(
                start_index=0, end_index=255, ack_required=False
            )
            io = device.io["MEMORY"]

            expected = (
                (
                    MultiZoneMessages.StateMultiZone,
                    dict(
                        zones_count=22,
                        zone_index=0,
                        colors=[hp.Color(i, 1, 1, 3500) for i in range(8)],
                    ),
                ),
                (
                    MultiZoneMessages.StateMultiZone,
                    dict(
                        zones_count=22,
                        zone_index=8,
                        colors=[hp.Color(i, 1, 1, 3500) for i in range(8, 16)],
                    ),
                ),
                (
                    MultiZoneMessages.StateMultiZone,
                    dict(
                        zones_count=22,
                        zone_index=16,
                        colors=[hp.Color(i, 1, 1, 3500) for i in range(16, 22)]
                        + [hp.Color(0, 0, 0, 0) for _ in range(22, 24)],
                    ),
                ),
            )

            reply1 = expected[0][0].create(**expected[0][1])
            reply2 = expected[1][0].create(**expected[1][1])
            reply3 = expected[2][0].create(**expected[2][1])

            with FakeTime() as t:

                @io.packet_filter.intercept_process_request
                async def process_request(event, Cont):
                    if event | MultiZoneMessages.GetColorZones:
                        event.set_replies(Cont)
                        event.handled = False
                        event._viewers_only = True
                        return True
                    else:
                        raise Cont()

                @io.packet_filter.intercept_process_outgoing
                async def process_outgoing(reply, req_event, Cont):
                    if req_event | MultiZoneMessages.GetColorZones:
                        yield reply1.clone(overrides=reply)

                        if time.time() != 2.2:
                            return

                        yield reply2.clone(overrides=reply)
                        yield reply3.clone(overrides=reply)
                    else:
                        raise Cont()

                with process_request, process_outgoing:
                    async with MockedCallLater(t):
                        result = await send_single(original, timeout=3)

            assert t.time == 2.2

            pytest.helpers.assertSamePackets(result, *expected)

            assert devices.store(device) == [
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                devices.Events.OUTGOING(device, io, pkt=reply2, replying_to=original),
                devices.Events.OUTGOING(device, io, pkt=reply3, replying_to=original),
            ]

            assertSent(
                sender,
                *[
                    (round(at * 0.2, 3), device.serial, original.Payload.__name__, original.payload)
                    for at in range(1 + int(round(2.2 / 0.2)))
                ],
            )

    class TestWithoutRetries:

        async def test_it_works_if_we_get_a_response_first_time(self, send_single, device):
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            expected = (DeviceMessages.EchoResponse, {"echoing": b"hi"})
            result = await send_single(original, timeout=1, no_retry=True)

            pytest.helpers.assertSamePackets(result, expected)

            io = device.io["MEMORY"]
            assert devices.store(device) == [
                devices.Events.INCOMING(device, io, pkt=original),
                devices.Events.OUTGOING(
                    device, io, pkt=CoreMessages.Acknowledgement(), replying_to=original
                ),
                devices.Events.OUTGOING(
                    device, io, pkt=expected[0].create(**expected[1]), replying_to=original
                ),
            ]

        async def test_it_times_out_if_we_dont_get_a_response(self, send_single, sender, device, FakeTime, MockedCallLater):
            original = DeviceMessages.EchoRequest(echoing=b"hi")

            with FakeTime() as t:
                async with MockedCallLater(t):
                    with assertRaises(
                        TimedOut,
                        "Waiting for reply to a packet",
                        sent_pkt_type=58,
                        sequence=1,
                        source=2,
                        serial=device.serial,
                    ):
                        async with device.offline():
                            await send_single(original, timeout=2, no_retry=True)

            assert t.time == 2

            assertSent(sender, (0, device.serial, original.Payload.__name__, original.payload))

        async def test_it_doesnt_wait_beyond_timeout_for_known_count_multi_reply_messages(self, send_single, sender, device, FakeTime, MockedCallLater):
            original = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
            io = device.io["MEMORY"]

            expected = (
                (
                    MultiZoneMessages.StateMultiZone,
                    dict(
                        zones_count=22,
                        zone_index=0,
                        colors=[hp.Color(i, 1, 1, 3500) for i in range(8)],
                    ),
                ),
                (
                    MultiZoneMessages.StateMultiZone,
                    dict(
                        zones_count=22,
                        zone_index=8,
                        colors=[hp.Color(i, 1, 1, 3500) for i in range(8, 16)],
                    ),
                ),
            )

            reply1 = expected[0][0].create(**expected[0][1])
            reply2 = expected[1][0].create(**expected[1][1])

            with FakeTime() as t:

                @io.packet_filter.intercept_process_request
                async def process_request(event, Cont):
                    if event | MultiZoneMessages.GetColorZones:
                        event.set_replies(Cont)
                        event.handled = False
                        event._viewers_only = True
                        return True
                    else:
                        raise Cont()

                @io.packet_filter.intercept_process_outgoing
                async def process_outgoing(reply, req_event, Cont):
                    if req_event | MultiZoneMessages.GetColorZones:
                        yield reply1
                        yield reply2
                    else:
                        raise Cont()

                with process_request, process_outgoing:
                    async with MockedCallLater(t):
                        with assertRaises(
                            TimedOut,
                            "Waiting for reply to a packet",
                            sent_pkt_type=502,
                            sequence=1,
                            source=2,
                            serial=device.serial,
                        ):
                            await send_single(original, timeout=3, no_retry=True)

            assert t.time == 3

            assertSent(sender, (0, device.serial, original.Payload.__name__, original.payload))

        async def test_it_doesnt_wait_beyond_timeout_for_unlimited_reply_messages_that_get_no_reply(self, send_single, sender, device, FakeTime, MockedCallLater):
            original = DiscoveryMessages.GetService(ack_required=False)
            io = device.io["MEMORY"]

            reply1 = DiscoveryMessages.StateService(service=1, port=56700)
            reply2 = DiscoveryMessages.StateService(service=2, port=56700)

            info = {"m": None}

            @io.packet_filter.intercept_process_request
            async def process_request(event, Cont):
                if event | DiscoveryMessages.GetService:
                    event.set_replies(Cont)
                    event.handled = False
                    event._viewers_only = True
                    return True
                else:
                    raise Cont()

            @io.packet_filter.intercept_process_outgoing
            async def process_outgoing(reply, req_event, Cont):
                if req_event | DiscoveryMessages.GetService:
                    await info["m"].resume_after(2)
                    yield reply1.clone(overrides=reply)
                    yield reply2.clone(overrides=reply)
                else:
                    raise Cont()

            with process_request, process_outgoing, FakeTime() as t:

                async with MockedCallLater(t) as m:

                    info["m"] = m

                    with assertRaises(
                        TimedOut,
                        "Waiting for reply to a packet",
                        sent_pkt_type=2,
                        sequence=1,
                        source=2,
                        serial=device.serial,
                    ):
                        assert await send_single(original, timeout=1, no_retry=True) == []

                    assert t.time == 1
                    assert devices.store(device) == [
                        devices.Events.INCOMING(device, io, pkt=original),
                    ]

                    assertSent(
                        sender, (0, device.serial, original.Payload.__name__, original.payload)
                    )

                    await m.resume_after(1.5)
                    assert devices.store(device) == [
                        devices.Events.INCOMING(device, io, pkt=original),
                        devices.Events.OUTGOING(device, io, pkt=reply1, replying_to=original),
                        devices.Events.OUTGOING(device, io, pkt=reply2, replying_to=original),
                    ]

        async def test_it_does_wait_beyond_timeout_for_unlimited_reply_messages_that_have_any_replies_after_timeout(self, send_single, sender, device, FakeTime, MockedCallLater):
            original = DiscoveryMessages.GetService(ack_required=False)
            sender.transport_target.gaps.gap_between_results = 0.55
            io = device.io["MEMORY"]

            reply1 = DiscoveryMessages.StateService(service=1, port=56700)

            info = {"m": None}

            @io.packet_filter.intercept_process_request
            async def process_request(event, Cont):
                if event | DiscoveryMessages.GetService:
                    event.set_replies(Cont)
                    event.handled = False
                    event._viewers_only = True
                    return True
                else:
                    raise Cont()

            @io.packet_filter.intercept_process_outgoing
            async def process_outgoing(reply, req_event, Cont):
                if req_event | DiscoveryMessages.GetService:
                    await m.resume_after(0.8)
                    yield reply1.clone(overrides=reply)
                else:
                    raise Cont()

            with process_request, process_outgoing, FakeTime() as t:

                async with MockedCallLater(t) as m:

                    info["m"] = m
                    result = await send_single(original, timeout=1, no_retry=True)

                    # Waited 0.8 to get that second reply and finish_multi_gap of 0.6
                    assert t.time == 1.4

                    pytest.helpers.assertSamePackets(
                        result,
                        (
                            DiscoveryMessages.StateService,
                            {
                                "service": Services.UDP,
                                "port": 56700,
                            },
                        ),
                    )

                    assertSent(
                        sender, (0, device.serial, original.Payload.__name__, original.payload)
                    )
