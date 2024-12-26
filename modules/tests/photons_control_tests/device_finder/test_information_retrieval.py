import asyncio
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_app.errors import FoundNoDevices
from photons_app.mimic.event import Events
from photons_app.special import FoundSerials
from photons_control.device_finder import Device, Filter, Finder, InfoPoints
from photons_messages import DeviceMessages, LightMessages
from photons_products import Products

devices = pytest.helpers.mimic()
devices.add("light")(
    next(devices.serial_seq),
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(
        label="kitchen",
        firmware=hp.Firmware(2, 80),
        group={"identity": "aa", "label": "g1", "updated_at": 42},
        location={"identity": "bb", "label": "l1", "updated_at": 56},
    ),
)
devices.add("switch")(
    next(devices.serial_seq),
    Products.LCM3_32_SWITCH_I,
    hp.Firmware(3, 90),
    value_store=dict(
        label="switcharoo",
        group={"identity": "aa", "label": "g1", "updated_at": 42},
        location={"identity": "bb", "label": "l1", "updated_at": 56},
    ),
)


class VBase:
    def __init__(self, fake_time, sender, finder, final_future):
        self.t = fake_time
        self.sender = sender
        self.finder = finder
        self.final_future = final_future

    async def choose_device(self, name):
        if name == "light":
            await devices["light"].power_on()
            await devices["switch"].power_off()
            self.fake_device = devices["light"]
        else:
            await devices["light"].power_off()
            await devices["switch"].power_on()
            self.fake_device = devices["switch"]
        self.device = Device.FieldSpec().empty_normalise(serial=self.fake_device.serial)

    async def matches(self, fltr):
        return await self.device.matches(self.sender, fltr, self.finder.collections)

    def received(self, *pkts, keep_duplicates=False):
        store = devices.store(self.fake_device)
        total = 0
        for pkt in pkts:
            nxt = store.count(Events.INCOMING(self.fake_device, self.fake_device.io["MEMORY"], pkt=pkt))
            assert nxt > 0, (pkt.__class__.__name__, repr(pkt), nxt)
            total += nxt

        if keep_duplicates or len(pkts) == 0:
            exists = store.count(Events.INCOMING(self.fake_device, self.fake_device.io["MEMORY"], pkt=mock.ANY))
            assert exists == len(pkts)
        store.clear()

    def assertTimes(self, points):
        for p, f in self.device.point_futures.items():
            if p in points:
                assert f.done() and f.result() == points[p]
            else:
                assert not f.done()


class TestDevice:
    @pytest.fixture()
    async def sender(self, final_future):
        async with devices.for_test(final_future) as sender:
            await devices["light"].power_off()
            await devices["switch"].power_off()
            with mock.patch.object(type(sender.transport_target.gaps), "finish_multi_gap", 0):
                yield sender

    @pytest.fixture()
    async def finder(self, sender):
        async with Finder(sender) as finder:
            yield finder

    async def test_it_can_match_against_a_fltr(self, sender, finder, fake_time, final_future):
        V = VBase(fake_time, sender, finder, final_future)
        await V.choose_device("light")
        V.t.add(1)

        assert await V.matches(None)
        V.received()

        assert await V.matches(Filter.from_kwargs(label="kitchen"))
        V.received(LightMessages.GetColor())
        V.assertTimes({InfoPoints.LIGHT_STATE: 1, InfoPoints.VERSION: 1})
        V.t.add(5)

        assert not (await V.matches(Filter.from_kwargs(label="den")))
        V.received()
        V.assertTimes({InfoPoints.LIGHT_STATE: 1, InfoPoints.VERSION: 1})
        V.t.add(2)

        assert not (await V.matches(Filter.from_kwargs(label="attic", refresh_info=True)))
        V.received(LightMessages.GetColor())
        V.assertTimes({InfoPoints.LIGHT_STATE: 8, InfoPoints.VERSION: 1})
        V.t.add(1)

        assert not (await V.matches(Filter.from_kwargs(group_name="aa", cap=["matrix"])))
        V.received(DeviceMessages.GetGroup())
        V.assertTimes({InfoPoints.LIGHT_STATE: 8, InfoPoints.GROUP: 9, InfoPoints.VERSION: 1})
        V.t.add(2)

        # It never refreshes version
        assert not (await V.matches(Filter.from_kwargs(group_name="aa", cap=["matrix"], refresh_info=True)))
        V.received(DeviceMessages.GetGroup())
        V.assertTimes({InfoPoints.LIGHT_STATE: 8, InfoPoints.GROUP: 11, InfoPoints.VERSION: 1})
        V.t.add(3)

        assert await V.matches(Filter.from_kwargs(cap=["not_matrix"], refresh_info=True))
        V.received()
        V.assertTimes({InfoPoints.LIGHT_STATE: 8, InfoPoints.GROUP: 11, InfoPoints.VERSION: 1})

    async def test_it_can_match_against_a_fltr_for_a_non_light(self, sender, finder, fake_time, final_future):
        V = VBase(fake_time, sender, finder, final_future)
        await V.choose_device("switch")
        V.t.add(1)

        assert await V.matches(None)
        V.received()

        assert await V.matches(Filter.from_kwargs(label="switcharoo"))
        V.received(LightMessages.GetColor(), DeviceMessages.GetLabel())
        V.assertTimes({InfoPoints.LABEL: 1, InfoPoints.VERSION: 1})
        V.t.add(5)

        assert not (await V.matches(Filter.from_kwargs(label="den")))
        V.received()
        V.assertTimes({InfoPoints.LABEL: 1, InfoPoints.VERSION: 1})
        V.t.add(2)

        assert not (await V.matches(Filter.from_kwargs(label="attic", refresh_info=True)))
        V.received(DeviceMessages.GetLabel())
        V.assertTimes({InfoPoints.LABEL: 8, InfoPoints.VERSION: 1})
        V.t.add(1)

        assert not (await V.matches(Filter.from_kwargs(group_name="aa", cap=["matrix"])))
        V.received(DeviceMessages.GetGroup())
        V.assertTimes({InfoPoints.LABEL: 8, InfoPoints.GROUP: 9, InfoPoints.VERSION: 1})
        V.t.add(2)

        # It never refreshes version
        assert not (await V.matches(Filter.from_kwargs(group_name="aa", cap=["matrix"], refresh_info=True)))
        V.received(DeviceMessages.GetGroup())
        V.assertTimes({InfoPoints.LABEL: 8, InfoPoints.GROUP: 11, InfoPoints.VERSION: 1})
        V.t.add(3)

        assert await V.matches(Filter.from_kwargs(cap=["not_matrix"], refresh_info=True))
        V.received()
        V.assertTimes({InfoPoints.LABEL: 8, InfoPoints.GROUP: 11, InfoPoints.VERSION: 1})

    async def test_it_can_start_an_information_loop(self, fake_time, sender, finder, final_future):
        V = VBase(fake_time, sender, finder, final_future)
        await V.choose_device("light")
        fake_time.set(1)

        msgs = [e.value.msg for e in list(InfoPoints) if e is not InfoPoints.LABEL]
        assert msgs == [
            DeviceMessages.GetVersion(),
            LightMessages.GetColor(),
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
                fut = message_futs[s.name] = V.fake_device.attrs.event_waiter.wait_for_incoming(V.fake_device.io["MEMORY"], s.kls)
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
            ("version", DeviceMessages.GetVersion),
            ("color", LightMessages.GetColor),
            ("firmware", DeviceMessages.GetHostFirmware),
            ("group", DeviceMessages.GetGroup),
            ("location", DeviceMessages.GetLocation),
        ]:
            setattr(Futs, name, Waiter(name, kls))

        async def checker(ff):
            info = {"serial": V.fake_device.serial, "product_type": "unknown"}

            assert V.device.info == info
            await hp.wait_for_all_futures(*[V.device.point_futures[kls] for kls in InfoPoints if kls is not InfoPoints.LABEL])

            found = []
            for kls in list(InfoPoints):
                if kls is not InfoPoints.LABEL:
                    found.append(V.device.point_futures[kls].result())
            assert found == [1, 2, 3, 4, 5]

            assert V.t.time == 5

            V.received(*msgs)

            info.update(
                {
                    "label": "kitchen",
                    "power": "off",
                    "hue": 0.0,
                    "saturation": 0.0,
                    "brightness": 1.0,
                    "kelvin": 3500,
                    "firmware_version": "2.80",
                    "product_id": 27,
                    "product_name": "LIFX A19",
                    "product_type": "light",
                    "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
                    "group_id": "aa000000000000000000000000000000",
                    "group_name": "g1",
                    "location_id": "bb000000000000000000000000000000",
                    "location_name": "l1",
                }
            )
            assert V.device.info == info

            await hp.wait_for_all_futures(Futs.color)
            V.received(LightMessages.GetColor(), keep_duplicates=False)
            assert V.t.time == 12

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

            assert V.device.point_futures[InfoPoints.LIGHT_STATE].result() == 62
            await hp.wait_for_all_futures(Futs.color)
            V.received(LightMessages.GetColor(), keep_duplicates=True)
            # 62 + 10 = 72
            assert V.t.time == 72

            await hp.wait_for_all_futures(Futs.firmware)
            assert V.device.point_futures[InfoPoints.LIGHT_STATE].result() == 102
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

        await FoundSerials().find(V.sender, timeout=1)

        with hp.ChildOfFuture(V.final_future) as ff:
            async with hp.TaskHolder(ff, name="TEST") as ts:
                checker_task = ts.add(checker(ff))
                ts.add(V.device.refresh_information_loop(V.sender, time_between_queries, V.finder.collections))

        await checker_task

    async def test_it_can_start_an_information_loop_for_a_switch(self, fake_time, sender, finder, final_future):
        V = VBase(fake_time, sender, finder, final_future)
        await V.choose_device("switch")
        fake_time.set(1)

        msgs = [e.value.msg for e in list(InfoPoints) if e is not InfoPoints.LIGHT_STATE]
        assert msgs == [
            DeviceMessages.GetVersion(),
            DeviceMessages.GetLabel(),
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
                fut = message_futs[s.name] = V.fake_device.attrs.event_waiter.wait_for_incoming(V.fake_device.io["MEMORY"], s.kls)
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
            ("label", DeviceMessages.GetLabel),
            ("version", DeviceMessages.GetVersion),
            ("firmware", DeviceMessages.GetHostFirmware),
            ("group", DeviceMessages.GetGroup),
            ("location", DeviceMessages.GetLocation),
        ]:
            setattr(Futs, name, Waiter(name, kls))

        async def checker(ff):
            info = {"serial": V.fake_device.serial, "product_type": "unknown"}

            assert V.device.info == info
            await hp.wait_for_all_futures(*[V.device.point_futures[kls] for kls in InfoPoints if kls is not InfoPoints.LIGHT_STATE])

            found = []
            for kls in list(InfoPoints):
                if kls is not InfoPoints.LIGHT_STATE:
                    found.append(V.device.point_futures[kls].result())
            assert found == [1, 2, 3, 4, 5]

            assert V.t.time == 5

            V.received(*msgs)

            info.update(
                {
                    "label": "switcharoo",
                    "firmware_version": "3.90",
                    "product_id": 89,
                    "product_name": "LIFX Switch",
                    "product_type": "non_light",
                    "cap": pytest.helpers.has_caps_list("buttons", "unhandled", "relays"),
                    "group_id": "aa000000000000000000000000000000",
                    "group_name": "g1",
                    "location_id": "bb000000000000000000000000000000",
                    "location_name": "l1",
                }
            )
            assert V.device.info == info

            await hp.wait_for_all_futures(Futs.label)
            V.received(DeviceMessages.GetLabel(), keep_duplicates=True)
            assert V.t.time == 12

            await hp.wait_for_all_futures(Futs.group, Futs.location)
            V.received(
                *([DeviceMessages.GetLabel()] * 5),
                DeviceMessages.GetGroup(),
                DeviceMessages.GetLocation(),
                keep_duplicates=True,
            )
            # First location was at t=5
            # We then wait another 60
            # 60 is at 12 rounds, and next location after that is after 5
            assert V.t.time == 65

            assert V.device.point_futures[InfoPoints.LABEL].result() == 62
            await hp.wait_for_all_futures(Futs.label)
            V.received(DeviceMessages.GetLabel(), keep_duplicates=True)
            # 62 + 10 = 72
            assert V.t.time == 72

            await hp.wait_for_all_futures(Futs.firmware)
            assert V.device.point_futures[InfoPoints.LABEL].result() == 102
            assert V.t.time == 103

            V.received(
                DeviceMessages.GetLabel(),
                DeviceMessages.GetLabel(),
                DeviceMessages.GetLabel(),
                DeviceMessages.GetHostFirmware(),
                keep_duplicates=True,
            )

            ff.cancel()

        checker_task = None
        time_between_queries = {"FIRMWARE": 100}

        await FoundSerials().find(V.sender, timeout=1)

        with hp.ChildOfFuture(V.final_future) as ff:
            async with hp.TaskHolder(ff, name="TEST") as ts:
                checker_task = ts.add(checker(ff))
                ts.add(V.device.refresh_information_loop(V.sender, time_between_queries, V.finder.collections))

        await checker_task

    async def test_it_stops_the_information_loop_when_the_device_disappears(self, fake_time, sender, finder, final_future):
        V = VBase(fake_time, sender, finder, final_future)
        await V.choose_device("light")
        fake_time.set(1)

        msgs = [e.value.msg for e in list(InfoPoints) if e is not InfoPoints.LABEL]
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
                fut = message_futs[s.name] = V.fake_device.attrs.event_waiter.wait_for_incoming(V.fake_device.io["MEMORY"], s.kls)
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

        async def checker(ff, item):
            info = {"serial": V.fake_device.serial, "product_type": "unknown"}

            assert V.device.info == info
            await hp.wait_for_all_futures(*[V.device.point_futures[kls] for kls in InfoPoints if kls is not InfoPoints.LABEL])

            found = []
            for kls in list(InfoPoints):
                if kls is not InfoPoints.LABEL:
                    found.append(V.device.point_futures[kls].result())
            assert found == [1, 2, 3, 4, 5]

            assert V.t.time == 5

            V.received(*msgs)

            info.update(
                {
                    "label": "kitchen",
                    "power": "off",
                    "hue": 0.0,
                    "saturation": 0.0,
                    "brightness": 1.0,
                    "kelvin": 3500,
                    "firmware_version": "2.80",
                    "product_id": 27,
                    "product_name": "LIFX A19",
                    "product_type": "light",
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
            assert V.t.time == 12

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

            assert V.device.serial in V.sender.found

            async with V.fake_device.offline():
                with assertRaises(FoundNoDevices):
                    await FoundSerials().find(V.sender, timeout=1)

            assert V.device.serial not in V.sender.found

            assert not item.done()

            # This will timeout if it hasn't ended
            await item

            ff.cancel()

        checker_task = None
        time_between_queries = {"FIRMWARE": 100}

        await FoundSerials().find(V.sender, timeout=1)

        with hp.ChildOfFuture(V.final_future) as ff:
            async with hp.TaskHolder(ff, name="TEST") as ts:
                item = ts.add(V.device.refresh_information_loop(V.sender, time_between_queries, V.finder.collections))
                checker_task = ts.add(checker(ff, item))

        await checker_task

    async def test_it_doesnt_do_multiple_refresh_loops_at_the_same_time(self, fake_time, sender, finder, final_future):
        V = VBase(fake_time, sender, finder, final_future)
        await V.choose_device("light")

        async def impl(*args, **kwargs):
            await asyncio.sleep(200)

        private_refresh_information_loop = pytest.helpers.AsyncMock(name="_refresh_information_loop", side_effect=impl)

        with mock.patch.object(V.device, "_refresh_information_loop", private_refresh_information_loop):
            async with hp.TaskHolder(V.final_future, name="TEST") as ts:
                assert not V.device.refreshing.done()

                t1 = ts.add(V.device.refresh_information_loop(V.sender, None, V.finder.collections))

                await asyncio.sleep(0)
                assert V.device.refreshing.done()
                private_refresh_information_loop.assert_called_once_with(V.sender, None, V.finder.collections)
                assert not t1.done()

                # Next time we add does nothing
                t2 = ts.add(V.device.refresh_information_loop(V.sender, None, V.finder.collections))

                await asyncio.sleep(0)
                assert V.device.refreshing.done()
                private_refresh_information_loop.assert_called_once_with(V.sender, None, V.finder.collections)
                assert t2.done()
                assert not t1.done()

                # Now we stop the current one and restart again to actually be called
                t1.cancel()
                await asyncio.sleep(0)
                assert not V.device.refreshing.done()

                t3 = ts.add(V.device.refresh_information_loop(V.sender, None, V.finder.collections))

                await asyncio.sleep(0)
                assert V.device.refreshing.done()
                assert len(private_refresh_information_loop.mock_calls) == 2
                assert not t3.done()

                t3.cancel()
