# coding: spec

from photons_control.device_finder import DeviceFinderDaemon, Finder, Filter, DeviceFinder, Device
from photons_control import test_helpers as chp

from photons_app import helpers as hp

from photons_transport.fake import FakeDevice
from photons_products import Products

from unittest import mock
import asyncio
import pytest
import time

describe "DeviceFinderDaemon":
    it "takes in a sender":
        stop_fut = hp.create_future()
        sender = mock.Mock(name="sender", stop_fut=stop_fut)

        daemon = DeviceFinderDaemon(sender)

        assert daemon.sender is sender
        assert isinstance(daemon.final_future, hp.ChildOfFuture)
        assert daemon.final_future.original_fut is sender.stop_fut

        assert daemon.search_interval == 20
        assert daemon.time_between_queries is None

        assert isinstance(daemon.finder, Finder)
        assert daemon.finder.sender is sender
        assert daemon.finder.final_future.original_fut is daemon.final_future
        assert daemon.finder.forget_after == 30

    it "can take in options":
        stop_fut = hp.create_future()
        final_future = hp.create_future()
        sender = mock.Mock(name="sender", stop_fut=stop_fut)

        daemon = DeviceFinderDaemon(
            sender,
            final_future=final_future,
            forget_after=1,
            search_interval=2,
            time_between_queries=3,
        )

        assert daemon.sender is sender
        assert isinstance(daemon.final_future, hp.ChildOfFuture)
        assert daemon.final_future.original_fut is final_future

        assert daemon.search_interval == 2
        assert daemon.time_between_queries == 3

        assert isinstance(daemon.finder, Finder)
        assert daemon.finder.sender is sender
        assert daemon.finder.final_future.original_fut is daemon.final_future
        assert daemon.finder.forget_after == 1

    it "can be given an explicit finder":
        sender = mock.Mock(name="sender")
        finder = mock.Mock(name="finder")
        final_future = mock.Mock(name="final_future")

        daemon = DeviceFinderDaemon(sender, finder=finder, final_future=final_future)
        assert daemon.finder is finder

    describe "usage":

        @pytest.fixture()
        def final_future(self):
            fut = hp.create_future()
            try:
                yield fut
            finally:
                fut.cancel()

        @pytest.fixture()
        def V(self, final_future):
            class V:
                fltr = Filter.empty()
                sender = mock.NonCallableMock(name="sender", spec=[])

                def __init__(s):
                    s.final_future = final_future

                @hp.memoized_property
                def daemon(s):
                    return DeviceFinderDaemon(
                        s.sender,
                        final_future=s.final_future,
                        forget_after=1,
                        search_interval=2,
                        time_between_queries=3,
                    )

            return V()

        it "can make a reference", V:
            ref = V.daemon.reference(V.fltr)
            assert isinstance(ref, DeviceFinder)
            assert ref.fltr is V.fltr
            assert ref.finder is V.daemon.finder

        async it "can be used as an async context manager", V:
            start = pytest.helpers.AsyncMock(name="start", return_value=V.daemon)
            finish = pytest.helpers.AsyncMock(name="finish")

            with mock.patch.multiple(V.daemon, start=start, finish=finish):
                async with V.daemon as d:
                    assert d is V.daemon
                    start.assert_called_once_with()
                    finish.assert_not_called()

            finish.assert_called_once_with(None, None, None)

        async it "can create and close the search loop", V:
            called = []
            started = hp.create_future()

            async def search_loop():
                called.append("search_loop")
                started.set_result(True)
                try:
                    await hp.create_future()
                except asyncio.CancelledError:
                    called.append("cancelled_search_loop")

            with mock.patch.object(V.daemon, "search_loop", search_loop):
                async with V.daemon:
                    assert not V.daemon.final_future.done()
                    await started
                    assert called == ["search_loop"]

                assert V.daemon.final_future.done()
                assert called == ["search_loop", "cancelled_search_loop"]

        async it "will finish the finder if one is made", V:
            assert V.daemon.own_finder
            finish = pytest.helpers.AsyncMock(name="finish")

            with mock.patch.object(V.daemon.finder, "finish", finish):
                await V.daemon.finish()

            finish.assert_called_once_with(None, None, None)

        async it "will not finish the finder if one is provided", V:
            finder = mock.Mock(name="finder")
            daemon = DeviceFinderDaemon(V.sender, final_future=V.final_future, finder=finder)

            assert not daemon.own_finder
            assert daemon.finder is finder
            finish = pytest.helpers.AsyncMock(name="finish")

            with mock.patch.object(finder, "finish", finish):
                await daemon.finish()

            finish.assert_not_called()

        describe "search_loop":

            async it "keeps doing a search", V, FakeTime, MockedCallLater:
                called = []
                finish_fut = hp.create_future()

                with FakeTime() as t:
                    async with MockedCallLater(t):

                        async def find(fltr):
                            assert fltr.matches_all
                            assert fltr.refresh_discovery

                            called.append(("find", time.time()))
                            if len(called) == 4:
                                finish_fut.set_result(True)

                            if False:
                                yield

                        find = pytest.helpers.MagicAsyncMock(name="find", side_effect=find)

                        with mock.patch.object(V.daemon.finder, "find", find):
                            async with V.daemon:
                                await finish_fut

                si = V.daemon.search_interval
                assert called == [
                    ("find", 0),
                    ("find", si),
                    ("find", si * 2),
                    ("find", si * 3),
                ]

            async it "does refresh information loops", V, FakeTime, MockedCallLater:
                called = []
                m = lambda s: Device.FieldSpec().empty_normalise(serial=s)
                d1 = m("d073d5000001")
                d2 = m("d073d5000002")

                d1ril = pytest.helpers.AsyncMock(name="d1_refresh_information_loop")
                d2ril = pytest.helpers.AsyncMock(name="d2_refresh_information_loop")

                p1 = mock.patch.object(d1, "refresh_information_loop", d1ril)
                p2 = mock.patch.object(d2, "refresh_information_loop", d2ril)

                async def find(fltr):
                    assert fltr.matches_all
                    assert fltr.refresh_discovery

                    called.append(1)

                    yield d1
                    yield d2

                    assert len(d1ril.mock_calls) == len(called)
                    assert len(d2ril.mock_calls) == len(called)

                find = pytest.helpers.MagicAsyncMock(name="find", side_effect=find)

                wait = hp.create_future()

                class Tick:
                    def __init__(self, *args, **kwargs):
                        self.args = args
                        self.kwargs = kwargs

                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, exc_typ, exc, tb):
                        pass

                    def __aiter__(self):
                        return self.tick()

                    async def tick(self):
                        async with hp.tick(*self.args, **self.kwargs) as ticks:
                            async for i, nxt_time in ticks:
                                if i == 4:
                                    wait.set_result(True)
                                yield i, nxt_time

                p3 = mock.patch.object(V.daemon.finder, "find", find)
                p4 = mock.patch.object(V.daemon, "hp_tick", Tick)

                with FakeTime() as t:
                    async with MockedCallLater(t):
                        with p1, p2, p3, p4:

                            async def run():
                                async with V.daemon:
                                    await hp.create_future()

                            async with hp.TaskHolder(V.final_future) as ts:
                                t = ts.add(run())
                                await wait
                                t.cancel()

                for eril in (d1ril, d2ril):
                    assert len(eril.mock_calls) >= 3

                    assert eril.mock_calls[0] == mock.call(
                        V.daemon.sender, V.daemon.time_between_queries, V.daemon.finder.collections
                    )

            async it "keeps going if find fails", V:
                called = []
                async with pytest.helpers.FutureDominoes(expected=5) as futs:

                    m = lambda s: Device.FieldSpec().empty_normalise(serial=s)
                    d1 = m("d073d5000001")
                    d2 = m("d073d5000002")

                    d1ril = pytest.helpers.AsyncMock(name="d1_refresh_information_loop")
                    d2ril = pytest.helpers.AsyncMock(name="d2_refresh_information_loop")

                    p1 = mock.patch.object(d1, "refresh_information_loop", d1ril)
                    p2 = mock.patch.object(d2, "refresh_information_loop", d2ril)

                    async def find(fltr):
                        called.append(1)

                        yield d1

                        if len(called) == 2:
                            raise ValueError("NOPE")

                        yield d2

                        if len(called) == 3:
                            await futs[4]

                    find = pytest.helpers.MagicAsyncMock(name="find", side_effect=find)

                    class Tick:
                        def __init__(self, every, final_future=None, name=None, min_wait=0.1):
                            self.every = every

                        async def __aenter__(self):
                            return self

                        async def __aexit__(self, exc_typ, exc, tb):
                            pass

                        def __aiter__(self):
                            return self.tick()

                        async def tick(self):
                            for i in range(3):
                                await futs[i + 1]
                                yield i, self.every

                    p3 = mock.patch.object(V.daemon.finder, "find", find)
                    p4 = mock.patch.object(V.daemon, "hp_tick", Tick)

                    with p1, p2, p3, p4:

                        async def run():
                            async with V.daemon:
                                await hp.create_future()

                        async with hp.TaskHolder(V.final_future) as ts:
                            t = ts.add(run())
                            await futs[5]
                            t.cancel()

                    assert len(called) == 3
                    assert len(d1ril.mock_calls) == 3
                    assert len(d2ril.mock_calls) == 2

                    for eril in (d1ril, d2ril):
                        assert eril.mock_calls[0] == mock.call(
                            V.daemon.sender,
                            V.daemon.time_between_queries,
                            V.daemon.finder.collections,
                        )

        describe "serials":
            async it "yields devices from finder.find", V:
                fltr = Filter.from_kwargs(label="kitchen")

                m = lambda s: Device.FieldSpec().empty_normalise(serial=s)
                d1 = m("d073d5000001")
                d2 = m("d073d5000002")

                async def find(fr):
                    assert fr is fltr
                    yield d1
                    yield d2

                find = pytest.helpers.MagicAsyncMock(name="find", side_effect=find)
                found = []

                with mock.patch.object(V.daemon.finder, "find", find):
                    async for device in V.daemon.serials(fltr):
                        found.append(device)

                assert found == [d1, d2]

        describe "info":
            async it "yields devices from finder.info", V:
                fltr = Filter.from_kwargs(label="kitchen")

                m = lambda s: Device.FieldSpec().empty_normalise(serial=s)
                d1 = m("d073d5000001")
                d2 = m("d073d5000002")

                async def info(fr):
                    assert fr is fltr
                    yield d1
                    yield d2

                info = pytest.helpers.MagicAsyncMock(name="info", side_effect=info)
                found = []

                with mock.patch.object(V.daemon.finder, "info", info):
                    async for device in V.daemon.info(fltr):
                        found.append(device)

                assert found == [d1, d2]

describe "Getting devices from the daemon":

    @pytest.fixture()
    def V(self):
        class V:
            serials = ["d073d5000001", "d073d5000002", "d073d5000003"]

            d1 = FakeDevice(serials[0], chp.default_responders(Products.LCM3_TILE))
            d2 = FakeDevice(serials[1], chp.default_responders(Products.LCM2_Z, zones=[]))
            d3 = FakeDevice(
                serials[2],
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

            @hp.memoized_property
            def devices(s):
                return [s.d1, s.d2, s.d3]

        return V()

    async it "can get serials and info", memory_devices_runner, V:
        async with memory_devices_runner(V.devices) as runner:
            async with DeviceFinderDaemon(runner.sender) as daemon:
                found = []
                async for device in daemon.serials(Filter.empty()):
                    found.append(device.serial)
                assert sorted(found) == sorted(V.serials)

                found = []
                async for device in daemon.info(Filter.from_kwargs(label="kitchen")):
                    found.append(device)
                assert [f.serial for f in found] == [V.d3.serial]
                assert found[0].info == {
                    "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
                    "firmware_version": "2.80",
                    "hue": V.d3.attrs.color.hue,
                    "label": "kitchen",
                    "power": "off",
                    "serial": V.d3.serial,
                    "kelvin": V.d3.attrs.color.kelvin,
                    "saturation": V.d3.attrs.color.saturation,
                    "brightness": V.d3.attrs.color.brightness,
                    "group_id": "aa000000000000000000000000000000",
                    "product_id": 27,
                    "group_name": "g1",
                    "location_id": "bb000000000000000000000000000000",
                    "location_name": "l1",
                }
