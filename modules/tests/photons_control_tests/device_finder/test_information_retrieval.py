# coding: spec

from photons_control.device_finder import Device, Filter, Finder, InfoPoints
from photons_control import test_helpers as chp

from photons_app.errors import FoundNoDevices
from photons_app.special import FoundSerials
from photons_app import helpers as hp

from photons_messages import LightMessages, DeviceMessages
from photons_transport.fake import FakeDevice
from photons_products import Products

from delfick_project.errors_pytest import assertRaises
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
                firmware=hp.Firmware(2, 80),
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

    async it "can start an information loop", V, fake_time, MockedCallLater:
        fake_time.set(1)

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

            def add_done_callback(s, cb):
                message_futs[s.name].add_done_callback(cb)

            def remove_done_callback(s, cb):
                message_futs[s.name].remove_done_callback(cb)

            def done(s):
                return message_futs[s.name].done()

        for name, kls in [
            ("color", LightMessages.GetColor),
            ("version", DeviceMessages.GetVersion),
            ("firmware", DeviceMessages.GetHostFirmware),
            ("group", DeviceMessages.GetGroup),
            ("location", DeviceMessages.GetLocation),
        ]:
            setattr(Futs, name, Waiter(name, kls))

        async def checker(ff):
            info = {"serial": V.fake_device.serial}

            assert V.device.info == info
            await hp.wait_for_all_futures(*[V.device.point_futures[kls] for kls in InfoPoints])

            found = []
            for kls in list(InfoPoints):
                found.append(V.device.point_futures[kls].result())
            assert found == [1, 2, 3, 4, 5]

            assert V.t.time == 5

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
                    "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
                    "group_id": "aa000000000000000000000000000000",
                    "group_name": "g1",
                    "location_id": "bb000000000000000000000000000000",
                    "location_name": "l1",
                }
            )
            assert V.device.info == info

            await hp.wait_for_all_futures(Futs.color)
            V.received(LightMessages.GetColor(), keep_duplicates=True)
            assert V.t.time == 11

            await hp.wait_for_all_futures(Futs.group, Futs.location)
            V.received(
                *([LightMessages.GetColor()] * 5),
                DeviceMessages.GetGroup(),
                DeviceMessages.GetLocation(),
                keep_duplicates=True,
            )
            # First location was at t=5
            # We then wait another 60
            # 60 is at 12 rounds, and next location after that is after 5
            assert V.t.time == 65

            assert V.device.point_futures[InfoPoints.LIGHT_STATE].result() == 61
            await hp.wait_for_all_futures(Futs.color)
            V.received(LightMessages.GetColor(), keep_duplicates=True)
            # 61 + 10 = 71
            assert V.t.time == 71

            await hp.wait_for_all_futures(Futs.firmware)
            # First firmware was at t=3
            # So next refresh after 103 which is 2 after 101 which is where LIGHT_STATE last is
            assert V.device.point_futures[InfoPoints.LIGHT_STATE].result() == 101
            assert V.t.time == 103

            V.received(
                LightMessages.GetColor(),
                LightMessages.GetColor(),
                LightMessages.GetColor(),
                DeviceMessages.GetHostFirmware(),
                keep_duplicates=True,
            )

            ff.cancel()

        checker_task = None
        time_between_queries = {"FIRMWARE": 100}

        await FoundSerials().find(V.runner.sender, timeout=1)

        async with MockedCallLater(fake_time):
            with hp.ChildOfFuture(V.runner.final_future) as ff:
                async with hp.TaskHolder(ff, name="TEST") as ts:
                    checker_task = ts.add(checker(ff))
                    ts.add(
                        V.device.refresh_information_loop(
                            V.runner.sender, time_between_queries, V.finder.collections
                        )
                    )

        await checker_task

    async it "stops the information loop when the device disappears", V, fake_device, fake_time, MockedCallLater:
        fake_time.set(1)

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

            def add_done_callback(s, cb):
                message_futs[s.name].add_done_callback(cb)

            def remove_done_callback(s, cb):
                message_futs[s.name].remove_done_callback(cb)

            def done(s):
                return message_futs[s.name].done()

        for name, kls in [
            ("color", LightMessages.GetColor),
            ("version", DeviceMessages.GetVersion),
            ("firmware", DeviceMessages.GetHostFirmware),
            ("group", DeviceMessages.GetGroup),
            ("location", DeviceMessages.GetLocation),
        ]:
            setattr(Futs, name, Waiter(name, kls))

        async def checker(ff, l):
            info = {"serial": V.fake_device.serial}

            assert V.device.info == info
            await hp.wait_for_all_futures(*[V.device.point_futures[kls] for kls in InfoPoints])

            found = []
            for kls in list(InfoPoints):
                found.append(V.device.point_futures[kls].result())
            assert found == [1, 2, 3, 4, 5]

            assert V.t.time == 5

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
                    "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
                    "group_id": "aa000000000000000000000000000000",
                    "group_name": "g1",
                    "location_id": "bb000000000000000000000000000000",
                    "location_name": "l1",
                }
            )
            assert V.device.info == info

            await hp.wait_for_all_futures(Futs.color)
            V.received(LightMessages.GetColor(), keep_duplicates=True)
            assert V.t.time == 11

            await hp.wait_for_all_futures(Futs.group, Futs.location)
            V.received(
                *([LightMessages.GetColor()] * 5),
                DeviceMessages.GetGroup(),
                DeviceMessages.GetLocation(),
                keep_duplicates=True,
            )
            # First location was at t=5
            # We then wait another 60
            # 60 is at 12 rounds, and next location after that is after 5
            assert V.t.time == 65

            # Now we remove knowledge of the device
            # And expect the information loop to end

            assert V.device.serial in V.runner.sender.found

            with fake_device.offline():
                with assertRaises(FoundNoDevices):
                    await FoundSerials().find(V.runner.sender, timeout=1)

            assert V.device.serial not in V.runner.sender.found

            assert not l.done()

            # This will timeout if it hasn't ended
            await l

            ff.cancel()

        checker_task = None
        time_between_queries = {"FIRMWARE": 100}

        await FoundSerials().find(V.runner.sender, timeout=1)

        async with MockedCallLater(fake_time):
            with hp.ChildOfFuture(V.runner.final_future) as ff:
                async with hp.TaskHolder(ff, name="TEST") as ts:
                    l = ts.add(
                        V.device.refresh_information_loop(
                            V.runner.sender, time_between_queries, V.finder.collections
                        )
                    )
                    checker_task = ts.add(checker(ff, l))

        await checker_task

    async it "doesn't do multiple refresh loops at the same time", V, fake_time, MockedCallLater:

        async def impl(*args, **kwargs):
            await asyncio.sleep(200)

        private_refresh_information_loop = pytest.helpers.AsyncMock(
            name="_refresh_information_loop", side_effect=impl
        )

        with mock.patch.object(
            V.device, "_refresh_information_loop", private_refresh_information_loop
        ):
            async with hp.TaskHolder(V.runner.final_future, name="TEST") as ts:
                assert not V.device.refreshing.done()

                t1 = ts.add(
                    V.device.refresh_information_loop(V.runner.sender, None, V.finder.collections)
                )

                await asyncio.sleep(0)
                assert V.device.refreshing.done()
                private_refresh_information_loop.assert_called_once_with(
                    V.runner.sender, None, V.finder.collections
                )
                assert not t1.done()

                # Next time we add does nothing
                t2 = ts.add(
                    V.device.refresh_information_loop(V.runner.sender, None, V.finder.collections)
                )

                await asyncio.sleep(0)
                assert V.device.refreshing.done()
                private_refresh_information_loop.assert_called_once_with(
                    V.runner.sender, None, V.finder.collections
                )
                assert t2.done()
                assert not t1.done()

                # Now we stop the current one and restart again to actually be called
                t1.cancel()
                await asyncio.sleep(0)
                assert not V.device.refreshing.done()

                t3 = ts.add(
                    V.device.refresh_information_loop(V.runner.sender, None, V.finder.collections)
                )

                await asyncio.sleep(0)
                assert V.device.refreshing.done()
                assert len(private_refresh_information_loop.mock_calls) == 2
                assert not t3.done()

                t3.cancel()
