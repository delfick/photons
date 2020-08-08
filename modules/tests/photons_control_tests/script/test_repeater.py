# coding: spec

from photons_control.script import Repeater, Pipeline
from photons_control import test_helpers as chp

from photons_app.special import FoundSerials

from photons_messages import DeviceMessages, LightMessages
from photons_transport.fake import FakeDevice

from collections import defaultdict
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


def assertReceived(received, want):
    rc = []
    received = list(received)

    for lst in want:
        if len(received) == 0:
            rc.append([])
        else:
            buf = []
            for _ in range(len(lst)):
                if received:
                    buf.append(received.pop(0)[:3])
            rc.append(buf)

    for g, w in zip(rc, want):
        assert len(g) == len(set(g))
        assert set(g) == set(w)


describe "Repeater":

    async it "repeats messages", runner, FakeTime, MockedCallLater:
        for use_pipeline in (True, False):
            pipeline = [
                DeviceMessages.SetPower(level=0),
                LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            ]

            if use_pipeline:
                pipeline = Pipeline(*pipeline)

            msg = Repeater(pipeline, min_loop_time=0)

            def no_errors(err):
                assert False, f"Got an error: {err}"

            got = defaultdict(list)
            with FakeTime() as t:
                async with MockedCallLater(t):
                    async with runner.sender(msg, FoundSerials(), error_catcher=no_errors) as pkts:
                        async for pkt in pkts:
                            got[pkt.serial].append(pkt)
                            if all(len(pkts) >= 6 for pkts in got.values()):
                                raise pkts.StopPacketStream()

            assert all(serial in got for serial in runner.serials), got

            for pkts in got.values():
                got_power = False
                got_light = False
                if len(pkts) < 6:
                    assert False, ("Expected at least 6 replies", pkts, runner.serial)

                while pkts:
                    nxt = pkts.pop()
                    if nxt | DeviceMessages.StatePower:
                        if got_power:
                            assert False, "Expected a LightState"
                        got_power = True
                    elif nxt | LightMessages.LightState:
                        if got_light:
                            assert False, "Expected a StatePower"
                        got_light = True
                    else:
                        assert False, f"Got an unexpected packet: {nxt}"

                    if got_power and got_light:
                        got_power = False
                        got_light = False

    async it "can have a min loop time", runner, FakeTime, MockedCallLater:
        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        msg = Repeater(msgs, min_loop_time=2.5)

        def no_errors(err):
            assert False, f"Got an error: {err}"

        responses_at = []
        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with runner.sender(msg, runner.serials, error_catcher=no_errors) as pkts:
                    async for pkt in pkts:
                        responses_at.append(time.time())

                        if len(responses_at) == 8:
                            await m.add(2)

                        elif len(responses_at) == 13:
                            await m.add(4)

                        if len(responses_at) == len(runner.serials) * 10:
                            raise pkts.StopPacketStream()

        assert len(responses_at) == 30
        assert len(runner.sender.received) == 30

        assert responses_at == [
            *[0, 0, 0, 0, 0, 0],
            # we take an extra 2 seconds after the second response here
            *[2.5, 2.5, 4.5, 4.5, 4.5, 4.5],
            # We take an extra 4 seconds after the first response here
            *[5.0, 9.0, 9.0, 9.0, 9.0, 9.0],
            #
            *[9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
            #
            *[12.5, 12.5, 12.5, 12.5, 12.5, 12.5],
        ]

        assertReceived(
            runner.sender.received,
            [
                [
                    (0, "d073d5000001", "SetPowerPayload"),
                    (0, "d073d5000002", "SetPowerPayload"),
                    (0, "d073d5000003", "SetPowerPayload"),
                    (0, "d073d5000001", "SetColorPayload"),
                    (0, "d073d5000002", "SetColorPayload"),
                    (0, "d073d5000003", "SetColorPayload"),
                ],
                #
                [
                    (2.5, "d073d5000001", "SetPowerPayload"),
                    (2.5, "d073d5000002", "SetPowerPayload"),
                    (2.5, "d073d5000003", "SetPowerPayload"),
                    (2.5, "d073d5000001", "SetColorPayload"),
                    (2.5, "d073d5000002", "SetColorPayload"),
                    (2.5, "d073d5000003", "SetColorPayload"),
                ],
                # We've taken 2 seconds here, which means we're less
                # Than the next expected of 5, so we still go from 5
                [
                    (5.0, "d073d5000001", "SetPowerPayload"),
                    (5.0, "d073d5000002", "SetPowerPayload"),
                    (5.0, "d073d5000003", "SetPowerPayload"),
                    (5.0, "d073d5000001", "SetColorPayload"),
                    (5.0, "d073d5000002", "SetColorPayload"),
                    (5.0, "d073d5000003", "SetColorPayload"),
                ],
                # We took 4 seconds in that block, so we don't have to wait
                # any more to be over the next loop of 7.5
                [
                    (9.0, "d073d5000001", "SetPowerPayload"),
                    (9.0, "d073d5000002", "SetPowerPayload"),
                    (9.0, "d073d5000003", "SetPowerPayload"),
                    (9.0, "d073d5000001", "SetColorPayload"),
                    (9.0, "d073d5000002", "SetColorPayload"),
                    (9.0, "d073d5000003", "SetColorPayload"),
                ],
                # The next loop after 7.5 is 10, but that's less than the min
                # so we go to the next expected instead
                [
                    (12.5, "d073d5000001", "SetPowerPayload"),
                    (12.5, "d073d5000002", "SetPowerPayload"),
                    (12.5, "d073d5000003", "SetPowerPayload"),
                    (12.5, "d073d5000001", "SetColorPayload"),
                    (12.5, "d073d5000002", "SetColorPayload"),
                    (12.5, "d073d5000003", "SetColorPayload"),
                ],
            ],
        )

    async it "can have a on_done_loop", runner, FakeTime, MockedCallLater:
        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        done = []

        async def on_done():
            done.append(True)

        msg = Repeater(msgs, on_done_loop=on_done)

        def no_errors(err):
            assert False, f"Got an error: {err}"

        got = []
        with FakeTime() as t:
            async with MockedCallLater(t):
                async with runner.sender(msg, runner.serials, error_catcher=no_errors) as pkts:
                    async for pkt in pkts:
                        got.append(time.time())
                        if len(got) == len(runner.serials) * 2 * 3:
                            raise pkts.StopPacketStream()

        assert got == [0] * 6 + [30] * 6 + [60] * 6
        assert len(done) == 3

    async it "runs on_done if we exit the full message early", runner, FakeTime, MockedCallLater:
        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        done = []

        async def on_done():
            done.append(True)

        msg = Repeater(msgs, on_done_loop=on_done)

        def no_errors(err):
            assert False, f"Got an error: {err}"

        # And make sure it doesn't do on_done for partially completed loops
        got = []
        with FakeTime() as t:
            async with MockedCallLater(t):
                async with runner.sender(msg, runner.serials, error_catcher=no_errors) as pkts:
                    async for pkt in pkts:
                        got.append(time.time())
                        if len(got) == 1 + len(runner.serials) * 2 * 3:
                            raise pkts.StopPacketStream()

        assert got == ([0] * 6) + ([30] * 6) + ([60] * 6) + [90]
        assert len(done) == 4

    async it "can be stopped by a on_done_loop", runner, FakeTime, MockedCallLater:
        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        done = []

        async def on_done():
            done.append(True)
            if len(done) == 3:
                raise Repeater.Stop

        msg = Repeater(msgs, on_done_loop=on_done, min_loop_time=0)

        def no_errors(err):
            assert False, f"Got an error: {err}"

        got = defaultdict(list)
        with FakeTime() as t:
            async with MockedCallLater(t):
                async for pkt in runner.sender(msg, runner.serials, error_catcher=no_errors):
                    got[pkt.serial].append((pkt, time.time()))

        assert all(serial in got for serial in runner.serials), got
        assert all(len(pkts) == 6 for pkts in got.values()), [
            (serial, len(pkts)) for serial, pkts in got.items()
        ]
        assert len(done) == 3

    async it "is not stopped by errors", runner, FakeTime, MockedCallLater:

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetPower:
                return False

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        done = []

        async def on_done():
            done.append(True)
            if len(done) == 2:
                raise Repeater.Stop

        msg = Repeater(msgs, on_done_loop=on_done, min_loop_time=0)

        errors = []

        def got_error(err):
            errors.append(err)

        got = defaultdict(list)
        with FakeTime() as t:
            async with MockedCallLater(t):
                async for pkt in runner.sender(
                    msg, runner.serials, error_catcher=got_error, message_timeout=0.1
                ):
                    got[pkt.serial].append(pkt)

        assert all(serial in got for serial in runner.serials), got
        assert all(len(pkts) == 2 for pkts in got.values()), [
            (serial, len(pkts)) for serial, pkts in got.items()
        ]
        assert all(
            all(pkt | LightMessages.LightState for pkt in pkts) for pkts in got.values()
        ), got
        assert len(done) == 2
