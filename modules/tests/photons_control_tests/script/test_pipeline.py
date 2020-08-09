# coding: spec

from photons_control import test_helpers as chp
from photons_control.script import Pipeline

from photons_app.errors import RunErrors, TimedOut
from photons_app.special import FoundSerials
from photons_app import helpers as hp

from photons_messages import DeviceMessages, LightMessages
from photons_transport.fake import FakeDevice

from delfick_project.errors_pytest import assertSameError
from collections import defaultdict
import asyncio
import pytest
import time

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


describe "Pipeline":

    @pytest.mark.parametrize(
        "reference", [lambda runner: runner.serials, lambda runner: FoundSerials()]
    )
    async it "does all messages at once if pipeline isn't used", runner, reference:
        called = []
        wait = hp.create_future()

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetPower:
                called.append(pkt.serial)
                if len(called) == 3 and not wait.done():
                    wait.set_result(True)
                    await asyncio.sleep(0)
                await wait

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        got = defaultdict(list)

        async for pkt in runner.sender(msgs, reference(runner)):
            print(pkt.serial, type(pkt.payload))
            got[pkt.serial].append(pkt)

        assert all(serial in got for serial in runner.serials), got

        for serial, pkts in got.items():
            print(f"GOT: {serial}")
            for p in pkts:
                print("\t", type(p.payload), repr(p.payload))
            print()

            assert len(pkts) == 2
            assert pkts[0] | LightMessages.LightState
            assert pkts[1] | DeviceMessages.StatePower

        assert sorted(called) == sorted(runner.serials)

    @pytest.mark.parametrize(
        "reference", [lambda runner: runner.serials, lambda runner: FoundSerials()]
    )
    async it "waits on replies before sending next if we have a pipeline", runner, reference, FakeTime, MockedCallLater:
        called = []
        wait = hp.create_future()

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetPower:
                called.append(pkt.serial)
                if len(called) == 3 and not wait.done():
                    wait.set_result(True)
                    await asyncio.sleep(0)
                await wait

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msgs = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        got = defaultdict(list)

        async for pkt in runner.sender(msgs, reference(runner)):
            print(pkt.serial, type(pkt.payload))
            got[pkt.serial].append(pkt)

        assert all(serial in got for serial in runner.serials), got

        for serial, pkts in got.items():
            print(f"GOT: {serial}")
            for p in pkts:
                print("\t", type(p.payload), repr(p.payload))
            print()

            assert len(pkts) == 2

            # This is different than the test above where we got the LightState
            # first because it didn't wait for StatePower
            # But in this test, the power is first in the pipeline
            assert pkts[0] | DeviceMessages.StatePower
            assert pkts[1] | LightMessages.LightState

        assert sorted(called) == sorted(runner.serials)

    async it "can wait between messages", runner, FakeTime, MockedCallLater:
        got_times = defaultdict(list)

        async def waiter(pkt, source):
            got_times[pkt.serial].append(time.time())

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            spread=3,
        )

        got = defaultdict(list)

        with FakeTime() as t:
            async with MockedCallLater(t):
                start = time.time()
                async for pkt in runner.sender(msg, runner.serials):
                    got[pkt.serial].append(pkt)
                assert time.time() - start == 9

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 3 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | DeviceMessages.StateLabel, pkts
            assert pkts[2] | LightMessages.LightState, pkts

        assert all(got_times[serial] == [0, 3, 6] for serial in runner.serials)

    async it "devices aren't slowed down by other slow devices", runner:
        light1_power_wait = hp.create_future()

        got = defaultdict(list)

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetPower:
                called.append("got_power")
                if pkt.serial == light1.serial:
                    await light1_power_wait
                    called.append("waited_light1_power")
            else:
                called.append("got_light")

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        called = []
        async for pkt in runner.sender(msg, runner.serials):
            got[pkt.serial].append(pkt)
            called.append(("got_reply", type(pkt.payload).__name__))

            with_two = [
                serial for serial, pkts in got.items() if serial != light1.serial and len(pkts) == 2
            ]
            if len(with_two) == 2 and not light1_power_wait.done():
                assert len(got) == 2, list(got)
                assert all(len(pkts) == 2 for pkts in got.values())
                light1_power_wait.set_result(True)
                called.append("freed_light1_power")

        assert called == [
            "got_power",
            "got_power",
            "got_power",
            ("got_reply", "StatePowerPayload"),
            ("got_reply", "StatePowerPayload"),
            "got_light",
            "got_light",
            ("got_reply", "LightStatePayload"),
            ("got_reply", "LightStatePayload"),
            "freed_light1_power",
            "waited_light1_power",
            ("got_reply", "StatePowerPayload"),
            "got_light",
            ("got_reply", "LightStatePayload"),
        ]

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

    async it "devices are slowed down by other slow devices if synchronized is True", runner, FakeTime, MockedCallLater:
        wait = hp.create_future()
        called = []
        got_times = defaultdict(list)

        async def waiter(pkt, source):
            got_times[pkt.serial].append(time.time())
            if pkt | DeviceMessages.SetPower:
                called.append("got_power")
                if len(got_times) == 3 and not wait.done():
                    wait.set_result(True)

                if pkt.serial == light1.serial:
                    await wait
                    called.append("waited_for_light1_power")
            else:
                called.append("got_light")

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            synchronized=True,
        )

        got = defaultdict(list)
        async for pkt in runner.sender(msg, runner.serials):
            got[pkt.serial].append(pkt)
            called.append(("got_reply", type(pkt.payload).__name__))

        assert called == [
            "got_power",
            "got_power",
            "got_power",
            "waited_for_light1_power",
            ("got_reply", "StatePowerPayload"),
            ("got_reply", "StatePowerPayload"),
            ("got_reply", "StatePowerPayload"),
            "got_light",
            "got_light",
            "got_light",
            ("got_reply", "LightStatePayload"),
            ("got_reply", "LightStatePayload"),
            ("got_reply", "LightStatePayload"),
        ]

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

    async it "doesn't stop on errors", runner, FakeTime, MockedCallLater:

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

        errors = []

        def error(e):
            errors.append((e, time.time()))

        got = defaultdict(list)
        with FakeTime() as t:
            async with MockedCallLater(t):
                async for pkt in runner.sender(
                    msg, runner.serials, error_catcher=error, message_timeout=1
                ):
                    got[pkt.serial].append((pkt, time.time()))

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        assert len(errors) == 1
        assert errors[0][1] >= 1

        assertSameError(
            errors[0][0],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light1.serial, sent_pkt_type=DeviceMessages.SetLabel.Payload.message_type),
            [],
        )

        for serial in (light2.serial, light3.serial):
            assert len(got[serial]) == 3, got[serial]
            assert got[serial][0][0] | DeviceMessages.StatePower
            assert got[serial][1][0] | DeviceMessages.StateLabel
            assert got[serial][2][0] | LightMessages.LightState
            assert [t for _, t in got[serial]] == [0, 0, 0]

        serial = light1.serial
        assert len(got[serial]) == 2, got[serial]
        assert got[serial][0][0] | DeviceMessages.StatePower
        assert got[serial][1][0] | LightMessages.LightState
        # The reply from third message is after the second one times out
        assert [t for _, t in got[serial]] == [0, 1]

    async it "can short cut on errors", runner, FakeTime, MockedCallLater:

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

        errors = []

        def error(e):
            errors.append((e, time.time()))

        got = defaultdict(list)
        with FakeTime() as t:
            async with MockedCallLater(t):
                async for pkt in runner.sender(
                    msg, runner.serials, error_catcher=error, message_timeout=1
                ):
                    got[pkt.serial].append((pkt, time.time()))

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        assert len(errors) == 1
        assert errors[0][1] == 1

        assertSameError(
            errors[0][0],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light1.serial, sent_pkt_type=DeviceMessages.SetLabel.Payload.message_type),
            [],
        )

        for serial in (light2.serial, light3.serial):
            assert len(got[serial]) == 3, got[serial]
            assert got[serial][0][0] | DeviceMessages.StatePower
            assert got[serial][1][0] | DeviceMessages.StateLabel
            assert got[serial][2][0] | LightMessages.LightState
            assert [t for _, t in got[serial]] == [0, 0, 0]

        serial = light1.serial
        assert len(got[serial]) == 1, got[serial]
        assert got[serial][0][0] | DeviceMessages.StatePower
        assert got[serial][0][1] == 0

    async it "can short cut on errors with synchronized", runner, FakeTime, MockedCallLater:

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

        errors = []

        def error(e):
            errors.append((e, time.time()))

        got = defaultdict(list)
        with FakeTime() as t:
            async with MockedCallLater(t):
                async for pkt in runner.sender(
                    msg, runner.serials, error_catcher=error, message_timeout=1
                ):
                    got[pkt.serial].append((pkt, time.time()))

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        assert len(errors) == 1
        assert errors[0][1] == 1
        assertSameError(
            errors[0][0],
            TimedOut,
            "Waiting for reply to a packet",
            dict(serial=light1.serial, sent_pkt_type=DeviceMessages.SetLabel.Payload.message_type),
            [],
        )

        for serial in (light2.serial, light3.serial):
            assert len(got[serial]) == 2, got[serial]
            assert got[serial][0][0] | DeviceMessages.StatePower
            assert got[serial][1][0] | DeviceMessages.StateLabel
            assert [t for _, t in got[serial]] == [0, 0]

        serial = light1.serial
        assert len(got[serial]) == 1, got[serial]
        assert got[serial][0][0] | DeviceMessages.StatePower
        assert got[serial][0][1] == 0

    async it "can raise all errors", runner, FakeTime, MockedCallLater:

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

        with FakeTime() as t:
            async with MockedCallLater(t):
                try:
                    async for pkt in runner.sender(msg, runner.serials, message_timeout=1):
                        got[pkt.serial].append((pkt, time.time()))
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
            assert got[serial][0][0] | DeviceMessages.StatePower
            assert got[serial][1][0] | LightMessages.LightState
            assert [t for _, t in got[serial]] == [0, 1]

        serial = light3.serial
        assert len(got[serial]) == 3, got[serial]
        assert got[serial][0][0] | DeviceMessages.StatePower
        assert got[serial][1][0] | DeviceMessages.StateLabel
        assert got[serial][2][0] | LightMessages.LightState
        assert [t for _, t in got[serial]] == [0, 0, 0]
