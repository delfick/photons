# coding: spec

from photons_control.script import FromGenerator, FromGeneratorPerSerial, Pipeline
from photons_control import test_helpers as chp

from photons_app.errors import BadRun, TimedOut, BadRunWithResults
from photons_app import helpers as hp

from photons_transport.errors import FailedToFindDevice
from photons_transport.fake import FakeDevice
from photons_messages import DeviceMessages

from delfick_project.errors_pytest import assertRaises, assertSameError
from contextlib import contextmanager
from collections import defaultdict
from functools import partial
import asyncio
import pytest
import sys


light1 = FakeDevice(
    "d073d5000001", chp.default_responders(power=0, color=chp.Color(0, 1, 0.3, 2500))
)

light2 = FakeDevice(
    "d073d5000002", chp.default_responders(power=65535, color=chp.Color(100, 1, 0.5, 2500))
)

light3 = FakeDevice("d073d5000003", chp.default_responders(color=chp.Color(100, 1, 0.5, 2500)))


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner([light1, light2, light3]) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


def loop_time():
    return asyncio.get_event_loop().time()


describe "FromGenerator":

    async def assertScript(self, runner, gen, *, generator_kwargs=None, expected, **kwargs):
        msg = FromGenerator(gen, **(generator_kwargs or {}))
        await runner.sender(msg, runner.serials, **kwargs)

        assert len(runner.devices) > 0

        for device in runner.devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

            device.compare_received(expected[device])

    async it "is able to do a FromGenerator per serial", runner:

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
            with light3.offline():
                async for pkt in runner.sender(msg, runner.serials, error_catcher=errors):
                    got[pkt.serial].append(pkt)
        finally:
            assert errors == [FailedToFindDevice(serial=light3.serial)]

        assert len(runner.devices) > 0

        for device in runner.devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

            device.compare_received(expected[device])

            if expected[device]:
                assert len(got[device.serial]) == 2
                assert got[device.serial][0] | DeviceMessages.StatePower
                assert got[device.serial][1] | DeviceMessages.StateLabel

    async it "is able to do a FromGenerator per serial with per serial error_catchers", runner:

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
            light1: [DeviceMessages.GetPower(), DeviceMessages.SetLabel(label="wat")],
            light2: [DeviceMessages.GetPower(), DeviceMessages.SetLabel(label="wat")],
            light3: [],
        }

        errors = []

        got = defaultdict(list)
        with light3.offline():
            with light1.no_replies_for(DeviceMessages.SetLabel):
                with light2.no_replies_for(DeviceMessages.GetPower):
                    async for pkt in runner.sender(
                        msg, runner.serials, error_catcher=errors, message_timeout=0.05
                    ):
                        got[pkt.serial].append(pkt)

        assert len(runner.devices) > 0

        for device in runner.devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

            device.compare_received(expected[device])

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

    async it "Can get results", runner:

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
        async for pkt in runner.target.send(FromGenerator(gen), runner.serials):
            got[pkt.serial].append(pkt)

        assert len(runner.devices) > 0

        for device in runner.devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

            device.compare_received(expected[device])

            assert len(got[device.serial]) == 1
            assert got[device.serial][0] | DeviceMessages.StatePower

    async it "Sends all the messages that are yielded", runner:

        async def gen(reference, sender, **kwargs):
            get_power = DeviceMessages.GetPower()

            async for pkt in runner.sender(get_power, reference, **kwargs):
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

        await self.assertScript(runner, gen, expected=expected)

    async it "does not ignore exception in generator", runner:
        error = Exception("NOPE")

        async def gen(reference, sender, **kwargs):
            raise error
            yield DeviceMessages.GetPower()

        expected = {light1: [], light2: [], light3: []}
        with assertRaises(BadRun, _errors=[error]):
            await self.assertScript(runner, gen, expected=expected)

    async it "adds exception from generator to error_catcher", runner:
        got = []

        def err(e):
            got.append(e)

        error = Exception("NOPE")

        async def gen(reference, sender, **kwargs):
            raise error
            yield DeviceMessages.GetPower()

        expected = {light1: [], light2: [], light3: []}
        await self.assertScript(runner, gen, expected=expected, error_catcher=err)
        assert got == [error]

    async it "it can know if the message was sent successfully", runner:

        async def gen(reference, sender, **kwargs):
            t = yield DeviceMessages.GetPower()
            assert await t

        expected = {
            light1: [DeviceMessages.GetPower()],
            light2: [DeviceMessages.GetPower()],
            light3: [DeviceMessages.GetPower()],
        }

        await self.assertScript(
            runner, gen, generator_kwargs={"reference_override": True}, expected=expected
        )

    async it "it can know if the message was not sent successfully", runner:

        async def waiter(pkt, source):
            if pkt | DeviceMessages.GetPower:
                return False

        light1.set_intercept_got_message(waiter)

        async def gen(reference, sender, **kwargs):
            t = yield DeviceMessages.GetPower()
            assert not (await t)

        expected = {
            light1: [],
            light2: [DeviceMessages.GetPower()],
            light3: [DeviceMessages.GetPower()],
        }

        errors = []

        await self.assertScript(
            runner,
            gen,
            generator_kwargs={"reference_override": True},
            expected=expected,
            message_timeout=0.2,
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

    async it "it can have a serial override", runner:

        async def gen(reference, sender, **kwargs):
            async def inner_gen(level, reference, sender2, **kwargs2):
                assert sender is sender2
                del kwargs2["error_catcher"]
                kwargs1 = dict(kwargs)
                del kwargs1["error_catcher"]
                assert kwargs1 == kwargs2
                assert reference in runner.serials
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

        await self.assertScript(runner, gen, expected=expected)

    async it "it sends messages in parallel", runner:
        got = []

        async def waiter(pkt, source):
            if pkt | DeviceMessages.GetPower:
                got.append(loop_time())
            else:
                assert False, "unknown message"

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        async def gen(reference, sender, **kwargs):
            yield DeviceMessages.GetPower(target=light1.serial)
            yield DeviceMessages.GetPower(target=light2.serial)
            yield DeviceMessages.GetPower(target=light3.serial)

        expected = {
            light1: [DeviceMessages.GetPower()],
            light2: [DeviceMessages.GetPower()],
            light3: [DeviceMessages.GetPower()],
        }

        start = loop_time()
        await self.assertScript(runner, gen, expected=expected)
        assert len(got) == 3
        for t in got:
            assert t - start < 0.1

    async it "can wait for other messages", runner:
        got = {}

        async def waiter(pkt, source):
            if pkt | DeviceMessages.GetPower:
                if pkt.serial not in got:
                    got[pkt.serial] = loop_time()
                if pkt.serial == light2.serial:
                    return False
            else:
                assert False, "unknown message"

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        async def gen(reference, sender, **kwargs):
            assert await (yield DeviceMessages.GetPower(target=light1.serial))
            assert not await (yield DeviceMessages.GetPower(target=light2.serial))
            assert await (yield DeviceMessages.GetPower(target=light3.serial))

        expected = {
            light1: [DeviceMessages.GetPower()],
            light2: [],
            light3: [DeviceMessages.GetPower()],
        }

        start = loop_time()
        errors = []
        await self.assertScript(
            runner, gen, expected=expected, error_catcher=errors, message_timeout=0.2
        )
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

    async it "can provide errors", runner:
        for device in runner.devices:
            device.compare_received([])

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
        await self.assertScript(runner, gen, expected=expected, error_catcher=errors)
        assert errors == [FailedToFindDevice(serial=light1.serial)]

        with assertRaises(BadRunWithResults, _errors=[FailedToFindDevice(serial=light1.serial)]):
            await self.assertScript(runner, gen, expected=expected)

    async it "can be cancelled", runner, FakeTime, MockedCallLater:
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

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                msg = make_primary_msg(m)

                fut = hp.create_future()
                async with hp.ResultStreamer(fut) as streamer:

                    async def pkts():
                        with alter_called("pkts"):
                            async for pkt in runner.sender(msg, light1.serial):
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
                ("secondary", 2),
                ("secondary", 1),
                ("primary", 4),
                ("start", ("secondary", 4)),
                ("secondary", 4),
                ("secondary", 3),
                ("secondary", 2),
                ("secondary", 1),
                ("secondary", 4),
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

        got = [(i, serial, p) for i, serial, p, *_ in runner.sender.received]
        assert len(got) == 18
        assert got == [
            (0, "d073d5000001", "SetPowerPayload"),
            (0.1, "d073d5000001", "SetPowerPayload"),
            (0.2, "d073d5000001", "SetPowerPayload"),
            (0.3, "d073d5000001", "SetPowerPayload"),
            (0.3, "d073d5000001", "SetPowerPayload"),
            (0.4, "d073d5000001", "SetPowerPayload"),
            (0.4, "d073d5000001", "SetPowerPayload"),
            (0.6, "d073d5000001", "SetPowerPayload"),
            (0.6, "d073d5000001", "SetPowerPayload"),
            (0.6, "d073d5000001", "SetPowerPayload"),
            (0.8, "d073d5000001", "SetPowerPayload"),
            (0.8, "d073d5000001", "SetPowerPayload"),
            (0.8, "d073d5000001", "SetPowerPayload"),
            (0.9, "d073d5000001", "SetPowerPayload"),
            (1.0, "d073d5000001", "SetPowerPayload"),
            (1.0, "d073d5000001", "SetPowerPayload"),
            (1.0, "d073d5000001", "SetPowerPayload"),
            (1.1, "d073d5000001", "SetPowerPayload"),
        ]
