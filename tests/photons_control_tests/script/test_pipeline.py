# coding: spec

from photons_control.test_helpers import Device, ModuleLevelRunner
from photons_control.script import Pipeline

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut
from photons_app.test_helpers import AsyncTestCase
from photons_app.special import FoundSerials

from photons_messages import DeviceMessages, LightMessages

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from collections import defaultdict
from itertools import chain
import asyncio

light1 = Device("d073d5000001", use_sockets=False)
light2 = Device("d073d5000002", use_sockets=False)
light3 = Device("d073d5000003", use_sockets=False)

mlr = ModuleLevelRunner([light1, light2, light3], use_sockets=False)

setUp = mlr.setUp
tearDown = mlr.tearDown

def loop_time():
    return asyncio.get_event_loop().time()

describe AsyncTestCase, "Pipeline":
    use_default_loop = True

    @mlr.test
    async it "does all messages at once if pipeline isn't used", runner:
        got_times = defaultdict(list)

        async def waiter(pkt):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.1)

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msgs = [
              DeviceMessages.SetPower(level=0)
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            ]

        got = defaultdict(list)
        async with runner.target.session() as afr:
            await afr.find_specific_serials(runner.serials)
            start = loop_time()
            async for pkt, _, _ in runner.target.script(msgs).run_with(runner.serials):
                got[pkt.serial].append(pkt)
        self.assertLess(loop_time() - start, 0.2)

        assert all(serial in got for serial in runner.serials), got

        for serial, pkts in got.items():
            self.assertEqual(len(pkts), 2, pkts)
            assert pkts[0] | LightMessages.LightState, pkts
            assert pkts[1] | DeviceMessages.StatePower, pkts

        assert all(serial in got_times for serial in runner.serials), got_times
        diffs = list(chain.from_iterable([t - start for t in ts] for serial, ts in got_times.items()))
        assert all(diff < 0.1 for diff in diffs), diffs

    @mlr.test
    async it "waits on replies before sending next if we have a pipeline", runner:
        got_times = defaultdict(list)

        async def waiter(pkt):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.05)

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            )

        got = defaultdict(list)
        async with runner.target.session() as afr:
            await afr.find_specific_serials(runner.serials)
            start = loop_time()
            async for pkt, _, _ in runner.target.script(msg).run_with(runner.serials):
                got[pkt.serial].append(pkt)
        self.assertLess(loop_time() - start, 0.4)

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

        assert all(serial in got_times for serial in runner.serials), got_times

        for serial, times in got_times.items():
            self.assertEqual(len(times), 2, times)
            self.assertLess(times[0] - start, 0.07)
            self.assertGreater(times[1] - times[0], 0.07)

    @mlr.test
    async it "can wait between messages", runner:
        got_times = defaultdict(list)

        async def waiter(pkt):
            got_times[pkt.serial].append(loop_time())

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , DeviceMessages.SetLabel(label="wat")
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            , spread = 0.2
            )

        got = defaultdict(list)
        async with runner.target.session() as afr:
            await afr.find_specific_serials(runner.serials)
            start = loop_time()
            async for pkt, _, _ in runner.target.script(msg).run_with(runner.serials):
                got[pkt.serial].append(pkt)
        self.assertLess(loop_time() - start, 1)

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 3 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | DeviceMessages.StateLabel, pkts
            assert pkts[2] | LightMessages.LightState, pkts

        assert all(serial in got_times for serial in runner.serials), got_times

        for serial, times in got_times.items():
            self.assertEqual(len(times), 3, times)
            self.assertLess(times[0] - start, 0.07)
            self.assertGreater(times[1] - start, 0.2)

    @mlr.test
    async it "understands SpecialReference objects", runner:
        got_times = defaultdict(list)

        async def waiter(pkt):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.1)

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            )

        got = defaultdict(list)
        async with runner.target.session() as afr:
            reference = FoundSerials()
            await reference.find(afr, timeout=1)
            start = loop_time()
            async for pkt, _, _ in runner.target.script(msg).run_with(reference, afr):
                got[pkt.serial].append(pkt)
        self.assertLess(loop_time() - start, 0.4)

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

        assert all(serial in got_times for serial in runner.serials), got_times

        for serial, times in got_times.items():
            self.assertEqual(len(times), 2, times)
            self.assertLess(times[0] - start, 0.06)
            self.assertGreater(times[1] - start, 0.1)

    @mlr.test
    async it "devices aren't slowed down by other slow devices", runner:
        got_times = defaultdict(list)

        async def waiter(pkt):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.01)
                if pkt.serial == light1.serial:
                    await asyncio.sleep(0.1)

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            )

        got = defaultdict(list)
        async with runner.target.session() as afr:
            await afr.find_specific_serials(runner.serials)
            start = loop_time()
            async for pkt, _, _ in runner.target.script(msg).run_with(runner.serials):
                got[pkt.serial].append(pkt)
        self.assertLess(loop_time() - start, 0.4)

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
            self.assertEqual(len(times), 2, times)
            self.assertLess(times[0] - start, 0.07, serial)
            self.assertLess(times[1] - times[0], 0.07, serial)

        l1ts = got_times[light1.serial]
        self.assertEqual(len(l1ts), 2)
        self.assertLess(l1ts[0] - start, 0.07)
        self.assertGreater(l1ts[1] - l1ts[0], 0.09)

    @mlr.test
    async it "devices are slowed down by other slow devices if synchronized is True", runner:
        got_times = defaultdict(list)

        async def waiter(pkt):
            got_times[pkt.serial].append(loop_time())
            if pkt | DeviceMessages.SetPower:
                await asyncio.sleep(0.05)
                if pkt.serial == light1.serial:
                    await asyncio.sleep(0.1)

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            , synchronized = True
            )

        got = defaultdict(list)
        async with runner.target.session() as afr:
            await afr.find_specific_serials(runner.serials)
            start = loop_time()
            async for pkt, _, _ in runner.target.script(msg).run_with(runner.serials, afr):
                got[pkt.serial].append(pkt)
        self.assertLess(loop_time() - start, 0.4)

        assert all(serial in got for serial in runner.serials), got
        assert all(len(got[serial]) == 2 for serial in runner.serials), got

        for serial, pkts in got.items():
            assert pkts[0] | DeviceMessages.StatePower, pkts
            assert pkts[1] | LightMessages.LightState, pkts

        assert all(serial in got_times for serial in runner.serials), got_times

        for serial, times in got_times.items():
            self.assertEqual(len(times), 2, times)
            self.assertLess(times[0] - start, 0.07)
            self.assertGreater(times[1] - times[0], 0.1)

    @mlr.test
    async it "doesn't stop on errors", runner:
        async def waiter(pkt):
            if pkt | DeviceMessages.SetLabel:
                if pkt.serial == light1.serial:
                    return False

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , DeviceMessages.SetLabel(label="wat")
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            )

        got = defaultdict(list)
        errors = []
        async with runner.target.session() as afr:
            await afr.find_specific_serials(runner.serials)
            start = loop_time()
            async for pkt, _, _ in runner.target.script(msg).run_with(runner.serials, error_catcher=errors, message_timeout=0.2):
                got[pkt.serial].append((pkt, loop_time()))

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], TimedOut("Waiting for reply to a packet", serial=light1.serial))

        last_time_light1 = sorted(t for _, t in got[light1.serial])[-1]

        for serial in (light2.serial, light3.serial):
            self.assertEqual(len(got[serial]), 3, got[serial])
            assert got[serial][0][0] | DeviceMessages.StatePower
            assert got[serial][1][0] | DeviceMessages.StateLabel
            assert got[serial][2][0] | LightMessages.LightState
            last_time = sorted(t for _, t in got[serial])
            self.assertGreater(last_time_light1 - last_time[-1], 0.1)

        serial = light1.serial
        self.assertEqual(len(got[serial]), 2, got[serial])
        assert got[serial][0][0] | DeviceMessages.StatePower
        assert got[serial][1][0] | LightMessages.LightState

    @mlr.test
    async it "can short cut on errors", runner:
        async def waiter(pkt):
            if pkt | DeviceMessages.SetLabel:
                if pkt.serial == light1.serial:
                    return False

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , DeviceMessages.SetLabel(label="wat")
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            , short_circuit_on_error = True
            )

        got = defaultdict(list)
        errors = []
        async for pkt, _, _ in runner.target.script(msg).run_with(runner.serials, error_catcher=errors, message_timeout=0.2):
            got[pkt.serial].append(pkt)

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], TimedOut("Waiting for reply to a packet", serial=light1.serial))

        for serial in (light2.serial, light3.serial):
            self.assertEqual(len(got[serial]), 3, got[serial])
            assert got[serial][0] | DeviceMessages.StatePower
            assert got[serial][1] | DeviceMessages.StateLabel
            assert got[serial][2] | LightMessages.LightState

        serial = light1.serial
        self.assertEqual(len(got[serial]), 1, got[serial])
        assert got[serial][0] | DeviceMessages.StatePower

    @mlr.test
    async it "can short cut on errors with synchronized", runner:
        async def waiter(pkt):
            if pkt | DeviceMessages.SetLabel:
                if pkt.serial == light1.serial:
                    return False

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , DeviceMessages.SetLabel(label="wat")
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            , synchronized = True
            , short_circuit_on_error = True
            )

        got = defaultdict(list)
        errors = []
        async for pkt, _, _ in runner.target.script(msg).run_with(runner.serials, error_catcher=errors, message_timeout=0.1):
            got[pkt.serial].append(pkt)

        assert all(serial in got for serial in runner.serials), (list(got), errors)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], TimedOut("Waiting for reply to a packet", serial=light1.serial))

        for serial in (light2.serial, light3.serial):
            self.assertEqual(len(got[serial]), 2, got[serial])
            assert got[serial][0] | DeviceMessages.StatePower
            assert got[serial][1] | DeviceMessages.StateLabel

        serial = light1.serial
        self.assertEqual(len(got[serial]), 1, got[serial])
        assert got[serial][0] | DeviceMessages.StatePower

    @mlr.test
    async it "can raise all errors", runner:
        async def waiter(pkt):
            if pkt | DeviceMessages.SetLabel:
                if pkt.serial in (light1.serial, light2.serial):
                    return False

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        msg = Pipeline(
              DeviceMessages.SetPower(level=0)
            , DeviceMessages.SetLabel(label="wat")
            , LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500)
            )

        got = defaultdict(list)
        try:
            async for pkt, _, _ in runner.target.script(msg).run_with(runner.serials, message_timeout=0.1):
                got[pkt.serial].append(pkt)
        except RunErrors as errors:
            self.assertEqual(len(errors.errors), 2)
            serials = {light1.serial: True, light2.serial: True}
            for error in errors.errors:
                self.assertIsInstance(error, TimedOut)
                serials.pop(error.kwargs["serial"])
            self.assertEqual(serials, {})

        for serial in (light1.serial, light2.serial):
            self.assertEqual(len(got[serial]), 2, got[serial])
            assert got[serial][0] | DeviceMessages.StatePower
            assert got[serial][1] | LightMessages.LightState

        serial = light3.serial
        self.assertEqual(len(got[serial]), 3, got[serial])
        assert got[serial][0] | DeviceMessages.StatePower
        assert got[serial][1] | DeviceMessages.StateLabel
        assert got[serial][2] | LightMessages.LightState
