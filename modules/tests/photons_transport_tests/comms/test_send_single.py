# coding: spec

from photons_transport.targets import MemoryTarget
from photons_transport.fake import FakeDevice

from photons_app.special import FoundSerials
from photons_app.errors import TimedOut
from photons_app import helpers as hp

from photons_messages import (
    DeviceMessages,
    MultiZoneMessages,
    DiscoveryMessages,
    Services,
    protocol_register,
)
from photons_control import test_helpers as chp
from photons_products import Products

from delfick_project.errors_pytest import assertRaises
import pytest
import time


def assertSamePackets(got, *want):
    assert isinstance(got, list)
    assert len(got) == len(want)
    for g, w in zip(got, want):
        if isinstance(w, tuple):
            kls, options = w
            options = {"sequence": 1, "source": 2, "target": "d073d5001337", **options}
            w = kls.create(kls.create(**options).pack())
            if g.pack() != w.pack():
                print(f"GOT: {repr(g)}")
                print(f"WANT: {repr(w)}")
                print()
            assert g.pack() == w.pack()
        else:
            assert g | w


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


@pytest.fixture()
async def _setup():
    device = FakeDevice(
        "d073d5001337",
        chp.default_responders(Products.LCM2_Z, zones=[hp.Color(i, 1, 1, 3500) for i in range(22)]),
    )
    async with device:
        options = {"final_future": hp.create_future(), "protocol_register": protocol_register}
        target = MemoryTarget.create(options, {"devices": [device]})
        yield target, device


describe "Sending a single messages":

    @pytest.fixture
    async def sending(self, _setup):
        target, device = _setup

        async with target.session() as sender:
            await FoundSerials().find(sender, timeout=1)
            yield sender, device

    @pytest.fixture()
    def send_single(self, sending):
        async def send_single(original, **kwargs):
            packet = original.clone()
            packet.update(target="d073d5001337", sequence=1, source=2)
            return await sending[0].send_single(original, packet, **kwargs)

        return send_single

    @pytest.fixture()
    def sender(self, sending):
        return sending[0]

    @pytest.fixture()
    def device(self, sending):
        return sending[1]

    describe "happy path":
        async it "it can send and receive a single message", send_single, device:
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            result = await send_single(original, timeout=1)
            assertSamePackets(result, (DeviceMessages.EchoResponse, {"echoing": b"hi"}))
            device.compare_received(
                [DeviceMessages.EchoRequest(echoing=b"hi")], keep_duplicates=True
            )

        async it "can get multiple replies", send_single, device:
            original = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
            result = await send_single(original, timeout=1)
            assertSamePackets(
                result,
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
            )
            device.compare_received(
                [MultiZoneMessages.GetColorZones(start_index=0, end_index=255)],
                keep_duplicates=True,
            )

        async it "can get unlimited replies", send_single, device, FakeTime, MockedCallLater:
            original = DiscoveryMessages.GetService()
            with FakeTime() as t:
                async with MockedCallLater(t):
                    result = await send_single(original, timeout=1)

            assert t.time == 0.1
            assertSamePackets(
                result,
                (
                    DiscoveryMessages.StateService,
                    {"service": Services.UDP, "port": device.services[0].state_service.port},
                ),
            )
            device.compare_received([DiscoveryMessages.GetService()], keep_duplicates=True)

    describe "timeouts":
        async it "can retry until it gets a timeout", send_single, sender, device, FakeTime, MockedCallLater:
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
                        with device.offline():
                            await send_single(original, timeout=2)

            assert t.time == 2

            assertSent(
                sender,
                *[
                    (round(at * 0.2, 3), device.serial, original.Payload.__name__, original.payload)
                    for at in range(int(2 / 0.2))
                ],
            )

        async it "can retry until it gets a result", send_single, sender, device, FakeTime, MockedCallLater:
            original = DeviceMessages.EchoRequest(echoing=b"hi")

            with FakeTime() as t:

                async def intercept(pkt, source):
                    if time.time() == 0.6:
                        return
                    return False

                device.set_intercept_got_message(intercept)

                async with MockedCallLater(t):
                    result = await send_single(original, timeout=2)

            assert t.time == 0.6
            assertSamePackets(
                result, (DeviceMessages.EchoResponse, {"echoing": b"hi", "sequence": 3})
            )
            device.compare_received([DeviceMessages.EchoRequest(echoing=b"hi")])

            assertSent(
                sender,
                *[
                    (at, device.serial, original.Payload.__name__, original.payload)
                    for at in [0, 0.2, 0.4, 0.6]
                ],
            )

        async it "can give up on getting multiple messages that have a set length", send_single, sender, device, FakeTime, MockedCallLater:
            original = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)

            with FakeTime() as t:

                async def set_reply(pkt, source):
                    return (
                        True,
                        [
                            MultiZoneMessages.StateMultiZone.create(
                                zones_count=22,
                                zone_index=0,
                                colors=[hp.Color(i, 1, 1, 3500) for i in range(8)],
                            ),
                            MultiZoneMessages.StateMultiZone.create(
                                zones_count=22,
                                zone_index=8,
                                colors=[hp.Color(i, 1, 1, 3500) for i in range(8, 16)],
                            ),
                        ],
                    )

                device.set_reply(MultiZoneMessages.GetColorZones, set_reply)

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

        async it "can retry getting multiple replies till it has all replies", send_single, sender, device, FakeTime, MockedCallLater:
            original = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)

            with FakeTime() as t:

                async def set_reply(pkt, source):
                    if time.time() == 2.2:
                        return

                    return (
                        True,
                        [
                            MultiZoneMessages.StateMultiZone.create(
                                zones_count=22,
                                zone_index=0,
                                colors=[hp.Color(i, 1, 1, 3500) for i in range(8)],
                            ),
                            MultiZoneMessages.StateMultiZone.create(
                                zones_count=22,
                                zone_index=8,
                                colors=[hp.Color(i, 1, 1, 3500) for i in range(8, 16)],
                            ),
                        ],
                    )

                device.set_reply(MultiZoneMessages.GetColorZones, set_reply)

                async with MockedCallLater(t):
                    result = await send_single(original, timeout=3)

            assert t.time == 2.2

            assertSamePackets(
                result,
                (
                    MultiZoneMessages.StateMultiZone,
                    {
                        "zones_count": 22,
                        "zone_index": 0,
                        "colors": [hp.Color(i, 1, 1, 3500) for i in range(8)],
                        "sequence": 11,
                    },
                ),
                (
                    MultiZoneMessages.StateMultiZone,
                    {
                        "zones_count": 22,
                        "zone_index": 8,
                        "colors": [hp.Color(i, 1, 1, 3500) for i in range(8, 16)],
                        "sequence": 11,
                    },
                ),
                (
                    MultiZoneMessages.StateMultiZone,
                    {
                        "zones_count": 22,
                        "zone_index": 16,
                        "colors": [hp.Color(i, 1, 1, 3500) for i in range(16, 22)]
                        + [hp.Color(0, 0, 0, 0) for _ in range(22, 24)],
                        "sequence": 11,
                    },
                ),
            )
            device.compare_received(
                [MultiZoneMessages.GetColorZones(start_index=0, end_index=255, sequence=11)]
            )

            assertSent(
                sender,
                *[
                    (round(at * 0.2, 3), device.serial, original.Payload.__name__, original.payload)
                    for at in range(1 + int(round(2.2 / 0.2)))
                ],
            )

    describe "without retries":
        async it "works if we get a response first time", send_single, device:
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            result = await send_single(original, timeout=1, no_retry=True)
            assertSamePackets(result, (DeviceMessages.EchoResponse, {"echoing": b"hi"}))
            device.compare_received(
                [DeviceMessages.EchoRequest(echoing=b"hi")], keep_duplicates=True
            )

        async it "times out if we don't get a response", send_single, sender, device, FakeTime, MockedCallLater:
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
                        with device.offline():
                            await send_single(original, timeout=2, no_retry=True)

            assert t.time == 2

            assertSent(sender, (0, device.serial, original.Payload.__name__, original.payload))

        async it "doesn't wait beyond timeout for known count multi reply messages", send_single, sender, device, FakeTime, MockedCallLater:
            original = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)

            with FakeTime() as t:

                async def set_reply(pkt, source):
                    return (
                        True,
                        [
                            MultiZoneMessages.StateMultiZone.create(
                                zones_count=22,
                                zone_index=0,
                                colors=[hp.Color(i, 1, 1, 3500) for i in range(8)],
                            ),
                            MultiZoneMessages.StateMultiZone.create(
                                zones_count=22,
                                zone_index=8,
                                colors=[hp.Color(i, 1, 1, 3500) for i in range(8, 16)],
                            ),
                        ],
                    )

                device.set_reply(MultiZoneMessages.GetColorZones, set_reply)

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

        async it "doesn't wait beyond timeout for unlimited reply messages that get no reply", send_single, sender, device, FakeTime, MockedCallLater:
            original = DiscoveryMessages.GetService()

            with FakeTime() as t:

                async with MockedCallLater(t) as m:

                    async def set_reply(pkt, source):
                        await m.resume_after(2)
                        return [s.state_service for s in device.services]

                    device.set_reply(DiscoveryMessages.GetService, set_reply)

                    with assertRaises(
                        TimedOut,
                        "Waiting for reply to a packet",
                        sent_pkt_type=2,
                        sequence=1,
                        source=2,
                        serial=device.serial,
                    ):
                        await send_single(original, timeout=1, no_retry=True)

            assert t.time == 1

            assertSent(sender, (0, device.serial, original.Payload.__name__, original.payload))

        async it "does wait beyond timeout for unlimited reply messages that have any replies after timeout", send_single, sender, device, FakeTime, MockedCallLater:
            original = DiscoveryMessages.GetService()
            sender.transport_target.gaps.gap_between_results = 0.55

            with FakeTime() as t:

                async with MockedCallLater(t) as m:

                    async def set_reply(pkt, source):
                        await m.resume_after(0.8)
                        return [s.state_service for s in device.services]

                    device.set_reply(DiscoveryMessages.GetService, set_reply)

                    result = await send_single(original, timeout=1, no_retry=True)

            # Waited 0.8 to get that second reply and finish_multi_gap of 0.6
            assert t.time == 1.4

            assertSamePackets(
                result,
                (
                    DiscoveryMessages.StateService,
                    {"service": Services.UDP, "port": device.services[0].state_service.port},
                ),
            )

            assertSent(sender, (0, device.serial, original.Payload.__name__, original.payload))
