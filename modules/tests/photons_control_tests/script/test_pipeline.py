# coding: spec

from photons_control import test_helpers as chp
from photons_control.script import Pipeline

from photons_app.errors import RunErrors, TimedOut
from photons_app.special import FoundSerials

from photons_messages import DeviceMessages, LightMessages
from photons_transport.fake import FakeDevice

from delfick_project.errors_pytest import assertSameError
from collections import defaultdict
from itertools import chain
import asyncio
import pytest

light1 = FakeDevice("d073d5000001", chp.default_responders())
light2 = FakeDevice("d073d5000002", chp.default_responders())
light3 = FakeDevice("d073d5000003", chp.default_responders())


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner([light1, light2, light3]) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


def loop_time():
    return asyncio.get_event_loop().time()


describe "Pipeline":

    async it "does all messages at once if pipeline isn't used", runner:
        got_times = defaultdict(list)

        async def waiter(pkt, source):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.1)

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        got = defaultdict(list)
        await runner.sender.find_specific_serials(runner.serials)
        start = loop_time()
        async for pkt in runner.sender(msgs, runner.serials):
            print(pkt.serial, repr(pkt.payload))
            got[pkt.serial].append(pkt)
        assert loop_time() - start < 0.3

        assert all(serial in got for serial in runner.serials), got

        for serial, pkts in got.items():
            assert len(pkts) == 2, pkts
            assert pkts[0] | LightMessages.LightState, pkts
            assert pkts[1] | DeviceMessages.StatePower, pkts

        assert all(serial in got_times for serial in runner.serials), got_times
        diffs = list(
            chain.from_iterable([t - start for t in ts] for serial, ts in got_times.items())
        )
        assert all(diff < 0.2 for diff in diffs), diffs

    async it "waits on replies before sending next if we have a pipeline", runner:
        got_times = defaultdict(list)

        async def waiter(pkt, source):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.05)

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        got = defaultdict(list)
        await runner.sender.find_specific_serials(runner.serials)
        start = loop_time()
        async for pkt in runner.sender(msg, runner.serials):
            got[pkt.serial].append(pkt)
        assert loop_time() - start < 0.4

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

        assert all(serial in got_times for serial in runner.serials), got_times

        for serial, times in got_times.items():
            assert len(times) == 2, times
            assert times[0] - start < 0.07
            assert times[1] - times[0] > 0.06

    async it "can wait between messages", runner:
        got_times = defaultdict(list)

        async def waiter(pkt, source):
            got_times[pkt.serial].append(loop_time())

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            spread=0.2,
        )

        got = defaultdict(list)
        await runner.sender.find_specific_serials(runner.serials)
        start = loop_time()
        async for pkt in runner.sender(msg, runner.serials):
            got[pkt.serial].append(pkt)
        assert loop_time() - start < 1

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 3 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | DeviceMessages.StateLabel, pkts
            assert pkts[2] | LightMessages.LightState, pkts

        assert all(serial in got_times for serial in runner.serials), got_times

        for serial, times in got_times.items():
            assert len(times) == 3, times
            assert times[0] - start < 0.15
            assert times[1] - start > 0.2

    async it "understands SpecialReference objects", runner:
        got_times = defaultdict(list)

        async def waiter(pkt, source):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.1)

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        got = defaultdict(list)
        reference = FoundSerials()
        await reference.find(runner.sender, timeout=1)
        start = loop_time()
        async for pkt in runner.sender(msg, reference):
            got[pkt.serial].append(pkt)
        assert loop_time() - start < 0.4

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

        assert all(serial in got_times for serial in runner.serials), got_times

        for serial, times in got_times.items():
            assert len(times) == 2, times
            assert times[0] - start < 0.06
            assert times[1] - start > 0.1

    async it "devices aren't slowed down by other slow devices", runner:
        got_times = defaultdict(list)

        async def waiter(pkt, source):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.01)
                if pkt.serial == light1.serial:
                    await asyncio.sleep(0.1)

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        got = defaultdict(list)
        await runner.sender.find_specific_serials(runner.serials)
        start = loop_time()
        async for pkt in runner.sender(msg, runner.serials):
            got[pkt.serial].append(pkt)
        assert loop_time() - start < 0.4

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

        assert light1.serial in got_times, got_times
        assert light2.serial in got_times, got_times
        assert light3.serial in got_times, got_times

        for serial in (light2.serial, light3.serial):
            times = got_times[serial]
            assert len(times) == 2, times
            assert times[0] - start < 0.07, serial
            assert times[1] - times[0] < 0.07, serial

        l1ts = got_times[light1.serial]
        assert len(l1ts) == 2
        assert l1ts[0] - start < 0.07
        assert l1ts[1] - l1ts[0] > 0.09

    async it "devices are slowed down by other slow devices if synchronized is True", runner:
        got_times = defaultdict(list)

        async def waiter(pkt, source):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.05)
                if pkt.serial == light1.serial:
                    await asyncio.sleep(0.1)

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            synchronized=True,
        )

        got = defaultdict(list)
        await runner.sender.find_specific_serials(runner.serials)
        start = loop_time()
        async for pkt in runner.sender(msg, runner.serials):
            got[pkt.serial].append(pkt)
        assert loop_time() - start < 0.4

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

        assert all(serial in got_times for serial in runner.serials), got_times

        for serial, times in got_times.items():
            assert len(times) == 2, times
            assert times[0] - start < 0.07
            assert times[1] - times[0] > 0.1

    async it "doesn't stop on errors", runner:

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetLabel:
                if pkt.serial == light1.serial:
                    return False

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        got = defaultdict(list)
        errors = []
        await runner.sender.find_specific_serials(runner.serials)
        async for pkt in runner.sender(
            msg, runner.serials, error_catcher=errors, message_timeout=0.2
        ):
            got[pkt.serial].append((pkt, loop_time()))

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        assert len(errors) == 1

        assertSameError(
            errors[0],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light1.serial, sent_pkt_type=DeviceMessages.SetLabel.Payload.message_type),
            [],
        )

        last_time_light1 = sorted(t for _, t in got[light1.serial])[-1]

        for serial in (light2.serial, light3.serial):
            assert len(got[serial]) == 3, got[serial]
            assert got[serial][0][0] | DeviceMessages.StatePower
            assert got[serial][1][0] | DeviceMessages.StateLabel
            assert got[serial][2][0] | LightMessages.LightState
            last_time = sorted(t for _, t in got[serial])
            assert last_time_light1 - last_time[-1] > 0.1

        serial = light1.serial
        assert len(got[serial]) == 2, got[serial]
        assert got[serial][0][0] | DeviceMessages.StatePower
        assert got[serial][1][0] | LightMessages.LightState

    async it "can short cut on errors", runner:

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetLabel:
                if pkt.serial == light1.serial:
                    return False

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            short_circuit_on_error=True,
        )

        got = defaultdict(list)
        errors = []
        async for pkt in runner.sender(
            msg, runner.serials, error_catcher=errors, message_timeout=0.2
        ):
            got[pkt.serial].append(pkt)

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        assert len(errors) == 1

        assertSameError(
            errors[0],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light1.serial, sent_pkt_type=DeviceMessages.SetLabel.Payload.message_type),
            [],
        )

        for serial in (light2.serial, light3.serial):
            assert len(got[serial]) == 3, got[serial]
            assert got[serial][0] | DeviceMessages.StatePower
            assert got[serial][1] | DeviceMessages.StateLabel
            assert got[serial][2] | LightMessages.LightState

        serial = light1.serial
        assert len(got[serial]) == 1, got[serial]
        assert got[serial][0] | DeviceMessages.StatePower

    async it "can short cut on errors with synchronized", runner:

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetLabel:
                if pkt.serial == light1.serial:
                    return False

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            synchronized=True,
            short_circuit_on_error=True,
        )

        got = defaultdict(list)
        errors = []
        async for pkt in runner.sender(
            msg, runner.serials, error_catcher=errors, message_timeout=0.1
        ):
            got[pkt.serial].append(pkt)

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        assert len(errors) == 1
        assertSameError(
            errors[0],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light1.serial, sent_pkt_type=DeviceMessages.SetLabel.Payload.message_type),
            [],
        )

        for serial in (light2.serial, light3.serial):
            assert len(got[serial]) == 2, got[serial]
            assert got[serial][0] | DeviceMessages.StatePower
            assert got[serial][1] | DeviceMessages.StateLabel

        serial = light1.serial
        assert len(got[serial]) == 1, got[serial]
        assert got[serial][0] | DeviceMessages.StatePower

    async it "can raise all errors", runner:

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetLabel:
                if pkt.serial in (light1.serial, light2.serial):
                    return False

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        got = defaultdict(list)
        try:
            async for pkt in runner.sender(msg, runner.serials, message_timeout=0.1):
                got[pkt.serial].append(pkt)
        except RunErrors as errors:
            assert len(errors.errors) == 2
            serials = {light1.serial: True, light2.serial: True}
            for error in errors.errors:
                if not isinstance(error, TimedOut):
                    raise error
                serials.pop(error.kwargs["serial"])
            assert serials == {}

        for serial in (light1.serial, light2.serial):
            assert len(got[serial]) == 2, got[serial]
            assert got[serial][0] | DeviceMessages.StatePower
            assert got[serial][1] | LightMessages.LightState

        serial = light3.serial
        assert len(got[serial]) == 3, got[serial]
        assert got[serial][0] | DeviceMessages.StatePower
        assert got[serial][1] | DeviceMessages.StateLabel
        assert got[serial][2] | LightMessages.LightState
