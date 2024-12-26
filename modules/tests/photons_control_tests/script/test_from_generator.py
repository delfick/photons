import asyncio
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from functools import partial

import pytest
from delfick_project.errors_pytest import assertRaises, assertSameError
from photons_app import helpers as hp
from photons_app.errors import BadRun, BadRunWithResults, TimedOut
from photons_app.special import FoundSerials
from photons_control.script import FromGenerator, FromGeneratorPerSerial, Pipeline
from photons_messages import DeviceMessages, DiscoveryMessages
from photons_products import Products
from photons_transport.errors import FailedToFindDevice

devices = pytest.helpers.mimic()


light1 = devices.add("light1")(
    "d073d5000001",
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(power=0, color=hp.Color(0, 1, 0.3, 2500)),
)

light2 = devices.add("light2")(
    "d073d5000002",
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(power=65535, color=hp.Color(100, 1, 0.5, 2500)),
)

light3 = devices.add("light3")(
    "d073d5000003",
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(color=hp.Color(100, 1, 0.5, 2500)),
)


@pytest.fixture(scope="module")
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


@pytest.fixture(scope="module")
async def sender(final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture(autouse=True)
async def reset_devices(sender):
    for device in devices:
        await device.reset()
        devices.store(device).clear()
    sender.gatherer.clear_cache()


class TestFromGenerator:
    async def assertScript(self, sender, gen, *, generator_kwargs=None, expected, **kwargs):
        msg = FromGenerator(gen, **(generator_kwargs or {}))
        await sender(msg, devices.serials, **kwargs)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

    async def test_it_is_able_to_do_a_FromGenerator_per_serial(self, sender):
        async def gen(serial, sender, **kwargs):
            assert serial in (light1.serial, light2.serial)
            yield Pipeline([DeviceMessages.GetPower(), DeviceMessages.SetLabel(label="wat")])

        msg = FromGeneratorPerSerial(gen)

        expected = {
            light1: [DeviceMessages.GetPower(), DeviceMessages.SetLabel(label="wat")],
            light2: [DeviceMessages.GetPower(), DeviceMessages.SetLabel(label="wat")],
            light3: [],
        }

        errors = []

        got = defaultdict(list)
        try:
            async with light3.offline():
                async for pkt in sender(msg, devices.serials, error_catcher=errors):
                    got[pkt.serial].append(pkt)
        finally:
            assert errors == [FailedToFindDevice(serial=light3.serial)]

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

            if expected[device]:
                assert len(got[device.serial]) == 2
                assert got[device.serial][0] | DeviceMessages.StatePower
                assert got[device.serial][1] | DeviceMessages.StateLabel

    async def test_it_is_able_to_do_a_FromGenerator_per_serial_with_per_serial_error_catchers(self, sender):
        per_light_errors = {light1.serial: [], light2.serial: [], light3.serial: []}

        def error_catcher_override(serial, original_error_catcher):
            if not serial:
                return original_error_catcher

            def error(e):
                per_light_errors[serial].append(e)
                hp.add_error(original_error_catcher, e)

            return error

        async def gen(serial, sender, **kwargs):
            yield Pipeline([DeviceMessages.GetPower(), DeviceMessages.SetLabel(label="wat")])

        msg = FromGeneratorPerSerial(gen, error_catcher_override=error_catcher_override)

        expected = {
            light1: [
                DeviceMessages.GetPower(),
                *[DeviceMessages.SetLabel(label="wat") for _ in range(10)],
            ],
            light2: [
                DeviceMessages.GetPower(),
                DeviceMessages.SetLabel(label="wat"),
                *[DeviceMessages.GetPower() for _ in range(9)],
            ],
            light3: [],
        }

        errors = []

        got = defaultdict(list)
        async with light3.offline():
            lost_light1 = light1.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.SetLabel)
            lost_light2 = light2.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetPower)
            with lost_light1, lost_light2:
                async for pkt in sender(msg, devices.serials, error_catcher=errors, message_timeout=2):
                    got[pkt.serial].append(pkt)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

        assert len(errors) == 3
        assertSameError(errors[0], FailedToFindDevice, "", dict(serial=light3.serial), [])
        assertSameError(
            errors[1],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light1.serial, sent_pkt_type=DeviceMessages.SetLabel.Payload.message_type),
            [],
        )
        assertSameError(
            errors[2],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light2.serial, sent_pkt_type=DeviceMessages.GetPower.Payload.message_type),
            [],
        )

        # The FailedToFindDevice happens before the script is run and so doesn't get taken into
        # account by the error_catcher_override
        assert per_light_errors == {
            light1.serial: [errors[1]],
            light3.serial: [],
            light2.serial: [errors[2]],
        }

    async def test_it_Can_get_results(self, sender):
        async def gen(reference, sender, **kwargs):
            yield DeviceMessages.GetPower(target=light1.serial)
            yield DeviceMessages.GetPower(target=light2.serial)
            yield DeviceMessages.GetPower(target=light3.serial)

        expected = {
            light1: [DeviceMessages.GetPower()],
            light2: [DeviceMessages.GetPower()],
            light3: [DeviceMessages.GetPower()],
        }

        got = defaultdict(list)
        async for pkt in sender.transport_target.send(FromGenerator(gen), devices.serials):
            got[pkt.serial].append(pkt)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

            if expected[device]:
                assert len(got[device.serial]) == 1
                assert got[device.serial][0] | DeviceMessages.StatePower

    async def test_it_Sends_all_the_messages_that_are_yielded(self, sender):
        async def gen(reference, sender, **kwargs):
            get_power = DeviceMessages.GetPower()

            async for pkt in sender(get_power, reference, **kwargs):
                if pkt | DeviceMessages.StatePower:
                    if pkt.level == 0:
                        yield DeviceMessages.SetPower(level=65535, target=pkt.serial)
                    else:
                        yield DeviceMessages.SetPower(level=0, target=pkt.serial)

        expected = {
            light1: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=65535)],
            light2: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=0)],
            light3: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=65535)],
        }

        await self.assertScript(sender, gen, expected=expected)

    async def test_it_does_not_ignore_exception_in_generator(self, sender):
        error = Exception("NOPE")

        async def gen(reference, sender, **kwargs):
            raise error
            yield DeviceMessages.GetPower()

        expected = {light1: [], light2: [], light3: []}
        with assertRaises(BadRun, _errors=[error]):
            await self.assertScript(sender, gen, expected=expected)

    async def test_it_adds_exception_from_generator_to_error_catcher(self, sender):
        got = []

        def err(e):
            got.append(e)

        error = Exception("NOPE")

        async def gen(reference, sender, **kwargs):
            raise error
            yield DeviceMessages.GetPower()

        expected = {light1: [], light2: [], light3: []}
        await self.assertScript(sender, gen, expected=expected, error_catcher=err)
        assert got == [error]

    async def test_it_it_can_know_if_the_message_was_sent_successfully(self, sender):
        async def gen(reference, sender, **kwargs):
            t = yield DeviceMessages.GetPower()
            assert await t

        expected = {
            light1: [DeviceMessages.GetPower()],
            light2: [DeviceMessages.GetPower()],
            light3: [DeviceMessages.GetPower()],
        }

        await self.assertScript(sender, gen, generator_kwargs={"reference_override": True}, expected=expected)

    async def test_it_it_can_know_if_the_message_was_not_sent_successfully(self, sender):
        async def gen(reference, sender, **kwargs):
            t = yield DeviceMessages.GetPower()
            assert not (await t)

        expected = {
            light1: [],
            light2: [DeviceMessages.GetPower()],
            light3: [DeviceMessages.GetPower()],
        }

        errors = []

        lost_request_light1 = light1.io["MEMORY"].packet_filter.lost_request(DeviceMessages.GetPower)
        with lost_request_light1:
            await self.assertScript(
                sender,
                gen,
                generator_kwargs={"reference_override": True},
                expected=expected,
                message_timeout=2,
                error_catcher=errors,
            )

        assert len(errors) == 1
        assertSameError(
            errors[0],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light1.serial, sent_pkt_type=DeviceMessages.GetPower.Payload.message_type),
            [],
        )

    async def test_it_it_can_have_a_serial_override(self, sender):
        async def gen(reference, sender, **kwargs):
            async def inner_gen(level, reference, sender2, **kwargs2):
                assert sender is sender2
                del kwargs2["error_catcher"]
                kwargs1 = dict(kwargs)
                del kwargs1["error_catcher"]
                assert kwargs1 == kwargs2
                assert reference in devices.serials
                yield DeviceMessages.SetPower(level=level)

            get_power = DeviceMessages.GetPower()
            async for pkt in sender(get_power, reference, **kwargs):
                if pkt.serial == light1.serial:
                    level = 1
                elif pkt.serial == light2.serial:
                    level = 2
                elif pkt.serial == light3.serial:
                    level = 3
                else:
                    assert False, f"Unknown serial: {pkt.serial}"

                yield FromGenerator(partial(inner_gen, level), reference_override=pkt.serial)

        expected = {
            light1: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=1)],
            light2: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=2)],
            light3: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=3)],
        }

        await self.assertScript(sender, gen, expected=expected)

    async def test_it_it_sends_messages_in_parallel(self, sender):
        got = []

        async def see_request(event):
            if event | DeviceMessages.GetPower:
                got.append(time.time())
            else:
                assert False, "unknown message"

        isr1 = light1.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr2 = light2.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr3 = light3.io["MEMORY"].packet_filter.intercept_see_request(see_request)

        async def gen(reference, sender, **kwargs):
            yield DeviceMessages.GetPower(target=light1.serial)
            yield DeviceMessages.GetPower(target=light2.serial)
            yield DeviceMessages.GetPower(target=light3.serial)

        expected = {
            light1: [DeviceMessages.GetPower()],
            light2: [DeviceMessages.GetPower()],
            light3: [DeviceMessages.GetPower()],
        }

        with isr1, isr2, isr3:
            start = time.time()
            await self.assertScript(sender, gen, expected=expected)
            assert len(got) == 3
            for t in got:
                assert t - start < 0.1

    async def test_it_can_wait_for_other_messages(self, sender):
        got = {}

        async def process_request(event, Cont):
            if event | DeviceMessages.GetPower:
                if event.pkt.serial not in got:
                    got[event.pkt.serial] = time.time()
                if event.pkt.serial == light2.serial:
                    return
                else:
                    raise Cont()
            else:
                assert False, "unknown message"

        psr1 = light1.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr2 = light2.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr3 = light3.io["MEMORY"].packet_filter.intercept_process_request(process_request)

        async def gen(reference, sender, **kwargs):
            assert await (yield DeviceMessages.GetPower(target=light1.serial))
            assert not await (yield DeviceMessages.GetPower(target=light2.serial))
            assert await (yield DeviceMessages.GetPower(target=light3.serial))

        expected = {
            light1: [DeviceMessages.GetPower()],
            light2: [],
            light3: [DeviceMessages.GetPower()],
        }

        with psr1, psr2, psr3:
            start = time.time()
            errors = []
            await self.assertScript(sender, gen, expected=expected, error_catcher=errors, message_timeout=2)

        got = list(got.values())
        assert len(got) == 3
        assert got[0] - start < 0.1
        assert got[1] - start < 0.1
        assert got[2] - got[1] > 0.1

        assert len(errors) == 1
        assertSameError(
            errors[0],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light2.serial, sent_pkt_type=DeviceMessages.GetPower.Payload.message_type),
            [],
        )

    async def test_it_can_provide_errors(self, sender):
        for device in devices:
            devices.store(device).assertIncoming()

        async def gen(reference, sender, **kwargs):
            yield FailedToFindDevice(serial=light1.serial)
            yield DeviceMessages.GetPower(target=light2.serial)
            yield DeviceMessages.GetPower(target=light3.serial)

        expected = {
            light1: [],
            light2: [DeviceMessages.GetPower()],
            light3: [DeviceMessages.GetPower()],
        }

        errors = []
        await self.assertScript(sender, gen, expected=expected, error_catcher=errors)
        assert errors == [FailedToFindDevice(serial=light1.serial)]

        with assertRaises(BadRunWithResults, _errors=[FailedToFindDevice(serial=light1.serial)]):
            await self.assertScript(sender, gen, expected=expected)

    async def test_it_can_be_cancelled(self, sender, m):
        called = []

        @contextmanager
        def alter_called(name):
            called.append(("start", name))
            try:
                yield
            except asyncio.CancelledError:
                called.append(("cancelled", name))
                raise
            except:
                called.append(("error", name, sys.exc_info()))
                raise
            finally:
                called.append(("finally", name))

        def make_secondary_msg(i, m):
            async def gen(reference, sender, **kwargs):
                with alter_called(("secondary", i)):
                    async with hp.tick(0.1) as ticks:
                        async for _ in ticks:
                            called.append(("secondary", i))
                            yield DeviceMessages.SetPower(level=0)

            return FromGenerator(gen, reference_override=True)

        def make_primary_msg(m):
            async def gen(reference, sender, **kwargs):
                with alter_called("primary"):
                    async with hp.tick(0.3) as ticks:
                        async for i, _ in ticks:
                            called.append(("primary", i))
                            yield make_secondary_msg(i, m)

            return FromGenerator(gen, reference_override=True)

        msg = make_primary_msg(m)

        await FoundSerials().find(sender, timeout=1)
        sender.received.clear()

        fut = hp.create_future()
        async with hp.ResultStreamer(fut) as streamer:

            async def pkts():
                with alter_called("pkts"):
                    async for pkt in sender(msg, light1.serial):
                        yield pkt

            t = await streamer.add_generator(pkts(), context="pkt")
            streamer.no_more_work()

            found = []
            async for result in streamer:
                if result.context == "pkt":
                    found.append(result)
                    if len(found) == 18:
                        t.cancel()

            # 3 + 6 + 9
            assert called.count(("secondary", 1)) == 8
            assert called.count(("secondary", 2)) == 5
            assert called.count(("secondary", 3)) == 3
            assert called.count(("secondary", 4)) == 2

            assert called == [
                ("start", "pkts"),
                ("start", "primary"),
                ("primary", 1),
                ("start", ("secondary", 1)),
                ("secondary", 1),
                ("secondary", 1),
                ("secondary", 1),
                ("primary", 2),
                ("start", ("secondary", 2)),
                ("secondary", 2),
                ("secondary", 1),
                ("secondary", 2),
                ("secondary", 1),
                ("primary", 3),
                ("start", ("secondary", 3)),
                ("secondary", 3),
                ("secondary", 2),
                ("secondary", 1),
                ("secondary", 3),
                ("primary", 4),
                ("start", ("secondary", 4)),
                ("secondary", 4),
                ("secondary", 2),
                ("secondary", 1),
                ("secondary", 3),
                ("secondary", 4),
                ("secondary", 2),
                ("secondary", 1),
                ("cancelled", "primary"),
                ("finally", "primary"),
                ("cancelled", ("secondary", 1)),
                ("finally", ("secondary", 1)),
                ("cancelled", ("secondary", 2)),
                ("finally", ("secondary", 2)),
                ("cancelled", ("secondary", 3)),
                ("finally", ("secondary", 3)),
                ("cancelled", ("secondary", 4)),
                ("finally", ("secondary", 4)),
                ("cancelled", "pkts"),
                ("finally", "pkts"),
            ]

        got = [(i, serial, p) for i, serial, p, *_ in sender.received]
        assert len(got) == 18
        assert got == [
            (0.1, "d073d5000001", "SetPowerPayload"),
            (0.2, "d073d5000001", "SetPowerPayload"),
            (0.3, "d073d5000001", "SetPowerPayload"),
            (0.4, "d073d5000001", "SetPowerPayload"),
            (0.4, "d073d5000001", "SetPowerPayload"),
            (0.6, "d073d5000001", "SetPowerPayload"),
            (0.6, "d073d5000001", "SetPowerPayload"),
            (0.7, "d073d5000001", "SetPowerPayload"),
            (0.8, "d073d5000001", "SetPowerPayload"),
            (0.8, "d073d5000001", "SetPowerPayload"),
            (0.9, "d073d5000001", "SetPowerPayload"),
            (1.0, "d073d5000001", "SetPowerPayload"),
            (1.0, "d073d5000001", "SetPowerPayload"),
            (1.0, "d073d5000001", "SetPowerPayload"),
            (1.1, "d073d5000001", "SetPowerPayload"),
            (1.1, "d073d5000001", "SetPowerPayload"),
            (1.2, "d073d5000001", "SetPowerPayload"),
            (1.2, "d073d5000001", "SetPowerPayload"),
        ]
