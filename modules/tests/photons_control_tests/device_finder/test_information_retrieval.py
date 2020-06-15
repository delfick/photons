# coding: spec

from photons_control.device_finder import Device, Filter, Finder, InfoPoints
from photons_control import test_helpers as chp

from photons_app import helpers as hp

from photons_messages import LightMessages, DeviceMessages
from photons_transport.fake import FakeDevice
from photons_products import Products

from unittest import mock
import asyncio
import pytest

describe "Device":

    @pytest.fixture()
    def device(self):
        return Device.FieldSpec().empty_normalise(serial="d073d5000001")

    @pytest.fixture()
    def fake_device(self):
        return FakeDevice(
            "d073d5000001",
            chp.default_responders(
                Products.LCM2_A19,
                label="kitchen",
                firmware=chp.Firmware(2, 80, 1337),
                group_uuid="aa",
                group_label="g1",
                group_updated_at=42,
                location_uuid="bb",
                location_label="l1",
                location_updated_at=56,
            ),
        )

    @pytest.fixture()
    async def runner(self, memory_devices_runner, fake_device):
        async with memory_devices_runner([fake_device]) as runner:
            yield runner

    @pytest.fixture()
    async def finder(self, runner):
        async with Finder(runner.sender) as finder:
            yield finder

    @pytest.fixture()
    def fake_time(self, FakeTime):
        with FakeTime() as t:
            yield t

    @pytest.fixture()
    def V(self, runner, device, fake_device, finder, fake_time):
        class V:
            def __init__(s):
                s.t = fake_time
                s.device = device
                s.runner = runner
                s.finder = finder
                s.fake_device = fake_device

            async def matches(s, fltr):
                return await s.device.matches(s.runner.sender, fltr, finder.collections)

            def received(s, *pkts, keep_duplicates=False):
                s.fake_device.compare_received(pkts, keep_duplicates=keep_duplicates)
                s.fake_device.reset_received()

            def assertTimes(s, points):
                for p, f in s.device.point_futures.items():
                    if p in points:
                        assert f.done() and f.result() == points[p]
                    else:
                        assert not f.done()

        return V()

    async it "can match against a fltr", V:
        V.t.add(1)

        assert await V.matches(None)
        V.received()

        assert await V.matches(Filter.from_kwargs(label="kitchen"))
        V.received(LightMessages.GetColor())
        V.assertTimes({InfoPoints.LIGHT_STATE: 1})
        V.t.add(5)

        assert not (await V.matches(Filter.from_kwargs(label="den")))
        V.received()
        V.assertTimes({InfoPoints.LIGHT_STATE: 1})
        V.t.add(2)

        assert not (await V.matches(Filter.from_kwargs(label="attic", refresh_info=True)))
        V.received(LightMessages.GetColor())
        V.assertTimes({InfoPoints.LIGHT_STATE: 8})
        V.t.add(1)

        assert not (await V.matches(Filter.from_kwargs(group_name="aa", cap=["matrix"])))
        V.received(DeviceMessages.GetVersion(), DeviceMessages.GetGroup())
        V.assertTimes({InfoPoints.LIGHT_STATE: 8, InfoPoints.GROUP: 9, InfoPoints.VERSION: 9})
        V.t.add(2)

        # It never refreshes version
        assert not (
            await V.matches(Filter.from_kwargs(group_name="aa", cap=["matrix"], refresh_info=True))
        )
        V.received(DeviceMessages.GetGroup())
        V.assertTimes({InfoPoints.LIGHT_STATE: 8, InfoPoints.GROUP: 11, InfoPoints.VERSION: 9})
        V.t.add(3)

        assert await V.matches(Filter.from_kwargs(cap=["not_matrix"], refresh_info=True))
        V.received()
        V.assertTimes({InfoPoints.LIGHT_STATE: 8, InfoPoints.GROUP: 11, InfoPoints.VERSION: 9})

    @pytest.mark.async_timeout(2)
    async it "can start an information loop", V:

        futs = pytest.helpers.FutureDominoes(expected=110)
        futs.start()

        async def tick(every):
            i = -1
            while True:
                i += 1
                await futs[i + 1]
                if i == futs.expected - 1:
                    V.device.final_future.cancel()
                yield
                V.t.set(i)
                await asyncio.sleep(0)

        msgs = [e.value.msg for e in list(InfoPoints)]
        assert msgs == [
            LightMessages.GetColor(),
            DeviceMessages.GetVersion(),
            DeviceMessages.GetHostFirmware(),
            DeviceMessages.GetGroup(),
            DeviceMessages.GetLocation(),
        ]

        message_futs = {}

        class Futs:
            pass

        all_futs = []

        for name, kls in [
            ("color", LightMessages.GetColor),
            ("version", DeviceMessages.GetVersion),
            ("firmware", DeviceMessages.GetHostFirmware),
            ("group", DeviceMessages.GetGroup),
            ("location", DeviceMessages.GetLocation),
        ]:

            class Waiter:
                def __init__(s, name, kls):
                    s.name = name
                    s.kls = kls
                    s.make_fut()

                def make_fut(s, res=None):
                    fut = message_futs[s.name] = V.fake_device.wait_for("memory", s.kls)
                    fut.add_done_callback(s.make_fut)

                def __await__(s):
                    yield from message_futs[s.name]

            waiter = Waiter(name, kls)
            setattr(Futs, name, waiter)
            all_futs.append(waiter)

        async def checker():
            info = {"serial": V.fake_device.serial}

            await futs[1]
            assert V.device.info == info

            await asyncio.wait(all_futs)
            assert V.t.time == len(all_futs) - 1

            V.received(*msgs)

            info.update(
                {
                    "label": "kitchen",
                    "power": "off",
                    "hue": 0.0,
                    "saturation": 1.0,
                    "brightness": 1.0,
                    "kelvin": 3500,
                    "firmware_version": "2.80",
                    "product_id": 27,
                    "product_identifier": "lifx_a19",
                    "cap": [
                        "color",
                        "not_chain",
                        "not_ir",
                        "not_matrix",
                        "not_multizone",
                        "variable_color_temp",
                    ],
                    "group_id": "aa000000000000000000000000000000",
                    "group_name": "g1",
                }
            )
            assert V.device.info == info

            await asyncio.wait([Futs.color])
            V.received(
                LightMessages.GetColor(), keep_duplicates=True,
            )
            if V.t.time == 16:
                V.t.set(15)
            assert V.t.time == len(all_futs) + 10

            await asyncio.wait([Futs.group, Futs.location])
            V.received(
                *([LightMessages.GetColor()] * 3),
                DeviceMessages.GetGroup(),
                DeviceMessages.GetLocation(),
                keep_duplicates=True,
            )
            # First location was at t=4
            # We then wait until at least 64
            # 60 is at 12 rounds, and next location after that is after 5
            assert V.t.time >= 69

            assert V.device.point_futures[InfoPoints.LIGHT_STATE].result() >= 60
            await asyncio.wait([Futs.color])
            V.received(
                LightMessages.GetColor(), keep_duplicates=True,
            )
            assert V.t.time <= 76

            await asyncio.wait([Futs.firmware])
            # First firmware was at t=2
            # So next refresh after 102
            # So needs a full cycle after that
            assert V.t.time >= 107

            V.received(
                LightMessages.GetColor(),
                LightMessages.GetColor(),
                DeviceMessages.GetHostFirmware(),
                keep_duplicates=True,
            )

        checker_task = None
        time_between_queries = {"FIRMWARE": 100}

        with mock.patch.object(hp, "tick", tick):
            async with hp.TaskHolder(V.runner.final_future) as ts:
                checker_task = ts.add(checker())
                ts.add_task(
                    V.device.ensure_refresh_information_loop(
                        V.runner.sender, time_between_queries, V.finder.collections
                    )
                )

        await checker_task
        await futs
