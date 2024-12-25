import asyncio
import time
from collections import defaultdict

import pytest
from delfick_project.errors_pytest import assertSameError
from photons_app import helpers as hp
from photons_app.errors import RunErrors, TimedOut
from photons_app.special import FoundSerials
from photons_control.script import Pipeline
from photons_messages import DeviceMessages, LightMessages
from photons_products import Products

devices = pytest.helpers.mimic()

light1 = devices.add("light1")("d073d5000001", Products.LCM2_A19, hp.Firmware(2, 80))
light2 = devices.add("light2")("d073d5000002", Products.LCM2_A19, hp.Firmware(2, 80))
light3 = devices.add("light3")("d073d5000003", Products.LCM2_A19, hp.Firmware(2, 80))


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


class TestPipeline:

    @pytest.mark.parametrize("reference", [devices.serials, FoundSerials()])
    async def test_it_does_all_messages_at_once_if_pipeline_isnt_used(self, sender, reference):
        called = []
        wait = hp.create_future()

        async def see_request(event):
            if event | DeviceMessages.SetPower:
                called.append(event.pkt.serial)
                if len(called) == 3 and not wait.done():
                    wait.set_result(True)
                    await asyncio.sleep(0)
                await wait

        isr1 = light1.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr2 = light2.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr3 = light3.io["MEMORY"].packet_filter.intercept_see_request(see_request)

        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        got = defaultdict(list)

        with isr1, isr2, isr3:
            async for pkt in sender(msgs, reference):
                print(pkt.serial, type(pkt.payload))
                got[pkt.serial].append(pkt)

        assert all(serial in got for serial in devices.serials), got

        for serial, pkts in got.items():
            print(f"GOT: {serial}")
            for p in pkts:
                print("\t", type(p.payload), repr(p.payload))
            print()

            assert len(pkts) == 2
            assert any(p | DeviceMessages.StatePower for p in pkts)
            assert any(p | LightMessages.LightState for p in pkts)

        assert sorted(called) == sorted(devices.serials)

    @pytest.mark.parametrize("reference", [devices.serials, FoundSerials()])
    async def test_it_waits_on_replies_before_sending_next_if_we_have_a_pipeline(
        self, sender, reference
    ):
        called = []
        wait = hp.create_future()

        async def see_request(event):
            if event | DeviceMessages.SetPower:
                called.append(event.pkt.serial)
                if len(called) == 3 and not wait.done():
                    wait.set_result(True)
                    await asyncio.sleep(0)
                await wait

        isr1 = light1.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr2 = light2.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr3 = light3.io["MEMORY"].packet_filter.intercept_see_request(see_request)

        msgs = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        got = defaultdict(list)

        with isr1, isr2, isr3:
            async for pkt in sender(msgs, reference):
                print(pkt.serial, type(pkt.payload))
                got[pkt.serial].append(pkt)

        assert all(serial in got for serial in devices.serials), got

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

        assert sorted(called) == sorted(devices.serials)

    async def test_it_can_wait_between_messages(self, sender):
        got_times = defaultdict(list)

        async def see_request(event):
            got_times[event.pkt.serial].append(time.time())

        isr1 = light1.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr2 = light2.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr3 = light3.io["MEMORY"].packet_filter.intercept_see_request(see_request)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            spread=3,
        )

        got = defaultdict(list)

        with isr1, isr2, isr3:
            start = time.time()
            async for pkt in sender(msg, devices.serials):
                got[pkt.serial].append(pkt)
            assert time.time() - start == 9

        assert all(serial in got for serial in devices.serials), got
        assert all(len(got[serial]) == 3 for serial in devices.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | DeviceMessages.StateLabel, pkts
            assert pkts[2] | LightMessages.LightState, pkts

        assert all(got_times[serial] == [0, 3, 6] for serial in devices.serials)

    async def test_it_devices_arent_slowed_down_by_other_slow_devices(self, sender):
        light1_power_wait = hp.create_future()

        got = defaultdict(list)

        async def see_request(event):
            if event | DeviceMessages.SetPower:
                called.append("got_power")
                if event.pkt.serial == light1.serial:
                    await light1_power_wait
                    called.append("waited_light1_power")
            else:
                called.append("got_light")

        isr1 = light1.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr2 = light2.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr3 = light3.io["MEMORY"].packet_filter.intercept_see_request(see_request)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        called = []
        with isr1, isr2, isr3:
            async for pkt in sender(msg, devices.serials):
                got[pkt.serial].append(pkt)
                called.append(("got_reply", type(pkt.payload).__name__))

                with_two = [
                    serial
                    for serial, pkts in got.items()
                    if serial != light1.serial and len(pkts) == 2
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

        assert all(serial in got for serial in devices.serials), got
        assert all(len(got[serial]) == 2 for serial in devices.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

    async def test_it_devices_are_slowed_down_by_other_slow_devices_if_synchronized_is_True(
        self, sender
    ):
        wait = hp.create_future()
        called = []
        got_times = defaultdict(list)

        async def see_request(event):
            got_times[event.pkt.serial].append(time.time())
            if event | DeviceMessages.SetPower:
                called.append("got_power")
                if len(got_times) == 3 and not wait.done():
                    wait.set_result(True)

                if event.pkt.serial == light1.serial:
                    await wait
                    called.append("waited_for_light1_power")
            else:
                called.append("got_light")

        isr1 = light1.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr2 = light2.io["MEMORY"].packet_filter.intercept_see_request(see_request)
        isr3 = light3.io["MEMORY"].packet_filter.intercept_see_request(see_request)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            synchronized=True,
        )

        got = defaultdict(list)
        with isr1, isr2, isr3:
            async for pkt in sender(msg, devices.serials):
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

        assert all(serial in got for serial in devices.serials), got
        assert all(len(got[serial]) == 2 for serial in devices.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

    async def test_it_doesnt_stop_on_errors(self, sender):

        async def process_request(event, Cont):
            if event | DeviceMessages.SetLabel:
                if event.pkt.serial == light1.serial:
                    return
            raise Cont()

        psr1 = light1.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr2 = light2.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr3 = light3.io["MEMORY"].packet_filter.intercept_process_request(process_request)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        errors = []

        def error(e):
            errors.append((e, time.time()))

        got = defaultdict(list)
        with psr1, psr2, psr3:
            async for pkt in sender(msg, devices.serials, error_catcher=error, message_timeout=1):
                got[pkt.serial].append((pkt, time.time()))

        assert all(serial in got for serial in devices.serials), (list(got), errors)
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

    async def test_it_can_short_cut_on_errors(self, sender):

        async def process_request(event, Cont):
            if event | DeviceMessages.SetLabel:
                if event.pkt.serial == light1.serial:
                    return
            raise Cont()

        psr1 = light1.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr2 = light2.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr3 = light3.io["MEMORY"].packet_filter.intercept_process_request(process_request)

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
        with psr1, psr2, psr3:
            async for pkt in sender(msg, devices.serials, error_catcher=error, message_timeout=1):
                got[pkt.serial].append((pkt, time.time()))

        assert all(serial in got for serial in devices.serials), (list(got), errors)
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

    async def test_it_can_short_cut_on_errors_with_synchronized(self, sender):

        async def process_request(event, Cont):
            if event | DeviceMessages.SetLabel:
                if event.pkt.serial == light1.serial:
                    return False
            raise Cont()

        psr1 = light1.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr2 = light2.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr3 = light3.io["MEMORY"].packet_filter.intercept_process_request(process_request)

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
        with psr1, psr2, psr3:
            async for pkt in sender(msg, devices.serials, error_catcher=error, message_timeout=1):
                got[pkt.serial].append((pkt, time.time()))

        assert all(serial in got for serial in devices.serials), (list(got), errors)
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

    async def test_it_can_raise_all_errors(self, sender):

        async def process_request(event, Cont):
            if event | DeviceMessages.SetLabel:
                if event.pkt.serial in (light1.serial, light2.serial):
                    return False
            raise Cont()

        psr1 = light1.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr2 = light2.io["MEMORY"].packet_filter.intercept_process_request(process_request)
        psr3 = light3.io["MEMORY"].packet_filter.intercept_process_request(process_request)

        msg = Pipeline(
            DeviceMessages.SetPower(level=0),
            DeviceMessages.SetLabel(label="wat"),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        )

        got = defaultdict(list)

        with psr1, psr2, psr3:
            try:
                async for pkt in sender(msg, devices.serials, message_timeout=1):
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
