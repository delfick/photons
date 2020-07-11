# coding: spec

from photons_control.device_finder import Finder, Searcher, Collections, Device, Filter

from photons_app import helpers as hp

from unittest import mock
import pytest


describe "Finder":
    it "takes in a sender and uses it's stop_fut if final_future not specified":
        stop_fut = hp.create_future()
        sender = mock.Mock(name="sender", stop_fut=stop_fut)

        finder = Finder(sender)

        assert finder.sender is sender
        assert finder.forget_after == 30

        assert finder.devices == {}
        assert finder.last_seen == {}

        class S:
            def __eq__(s, other):
                return isinstance(other, Searcher) and other.sender is sender

        assert finder.searcher == S()
        assert isinstance(finder.collections, Collections)

        class F:
            def __eq__(s, other):
                return isinstance(other, hp.ChildOfFuture) and other.original_fut is stop_fut

        assert finder.final_future == F()

    it "uses given final_future if one is specified":
        sender = mock.Mock(name="sender", spec=[])
        final_future = hp.create_future()

        finder = Finder(sender, final_future)

        class F:
            def __eq__(s, other):
                return isinstance(other, hp.ChildOfFuture) and other.original_fut is final_future

        assert finder.final_future == F()

    it "allows you to specify forget_after":
        sender = mock.Mock(name="sender", spec=[])
        final_future = hp.create_future()

        finder = Finder(sender, final_future)
        assert finder.forget_after == 30

        finder = Finder(sender, final_future, forget_after=42)
        assert finder.forget_after == 42

    describe "Usage":

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
                sender = mock.NonCallableMock(name="sender", spec=[])

                def __init__(s):
                    s.final_future = final_future

                @hp.memoized_property
                def finder(s):
                    return Finder(s.sender, s.final_future)

            return V()

        async it "can be used as an async generator", V:
            finish = pytest.helpers.AsyncMock(name="finish")

            with mock.patch.object(V.finder, "finish", finish):
                async with V.finder as f:
                    assert f is V.finder
                    finish.assert_not_called()

            finish.assert_called_once_with()

        async it "cleans up it's devices on finish", V:
            serials = {
                s: pytest.helpers.AsyncMock(name=f"{s}_finish") for s in ("s1", "s2", "s3", "s4")
            }
            patches = []

            for serial, finish in serials.items():
                device = Device.FieldSpec().empty_normalise(serial=serial)
                patches.append(mock.patch.object(device, "finish", finish))
                V.finder.devices[serial] = device

            try:
                for p in patches:
                    p.start()

                V.finder.devices["s2"].finish.side_effect = TypeError("NOPE")

                called = []
                s1fut = hp.create_future()

                async def s3finish():
                    called.append("s3finish")
                    s1fut.set_result(True)
                    called.append("s3finish_done")

                async def s1finish():
                    called.append("s1finish")
                    await s1fut
                    called.append("s1finish_done")

                V.finder.devices["s1"].finish.side_effect = s1finish
                V.finder.devices["s3"].finish.side_effect = s3finish

                assert not V.finder.final_future.done()
                await V.finder.finish()
                assert V.finder.final_future.cancelled()

                assert V.finder.devices == {}

                for f in serials.values():
                    f.assert_called_once_with()

                assert called == ["s1finish", "s3finish", "s3finish_done", "s1finish_done"]
            finally:
                for p in patches:
                    p.stop()

        describe "ensure_devices":
            async it "gives the fltr to searcher.discovery", V:
                discover = pytest.helpers.AsyncMock(name="discover", return_value=[])

                with mock.patch.object(V.finder.searcher, "discover", discover):
                    assert (await V.finder._ensure_devices(None)) == ([], [])
                    discover.assert_called_once_with(refresh=False)

                    discover.reset_mock()
                    assert (await V.finder._ensure_devices(Filter.empty())) == ([], [])
                    discover.assert_called_once_with(refresh=False)

                    discover.reset_mock()
                    assert (await V.finder._ensure_devices(Filter.empty(refresh_info=True))) == (
                        [],
                        [],
                    )
                    discover.assert_called_once_with(refresh=False)

                    discover.reset_mock()
                    assert (
                        await V.finder._ensure_devices(Filter.empty(refresh_discovery=True))
                    ) == ([], [])
                    discover.assert_called_once_with(refresh=True)

            async it "can add and remove devices", V, FakeTime:
                m = lambda s: Device.FieldSpec().empty_normalise(serial=s)

                fltr = Filter.empty()
                discover = pytest.helpers.AsyncMock(name="discover")

                devices = {}
                last_seen = {}

                async def assertDevices(added, removed):
                    ad, rd = await V.finder._ensure_devices(fltr)

                    ad = sorted([d.serial for d in ad])
                    rd = sorted([d.serial for d in rd])
                    added = sorted([d.serial for d in added])
                    removed = sorted([d.serial for d in removed])

                    same = ad == added and rd == removed

                    if not same:
                        print("==== ADDED")
                        print(f"Expected: {added}")
                        print(f"Got     : {ad}")
                        print("==== REMOVED")
                        print(f"Expected: {removed}")
                        print(f"Got     : {rd}")

                    assert sorted(V.finder.devices) == sorted(devices)
                    assert sorted(V.finder.devices) == sorted(
                        [d.serial for d in V.finder.devices.values()]
                    )
                    assert sorted(devices) == sorted([d.serial for d in devices.values()])

                    assert V.finder.last_seen == last_seen

                with mock.patch.object(V.finder.searcher, "discover", discover), FakeTime() as t:
                    discover.return_value = []
                    await assertDevices([], [])

                    discover.return_value = ["s1", "s2", "s3"]
                    devices.update({"s1": m("s1"), "s2": m("s2"), "s3": m("s3")})
                    last_seen.update({"s1": t.time, "s2": t.time, "s3": t.time})
                    await assertDevices([m("s1"), m("s2"), m("s3")], [])

                    t.add(10)
                    discover.return_value = ["s2", "s1", "s4"]
                    devices.update({"s4": m("s4")})
                    last_seen.update({"s2": t.time, "s1": t.time, "s4": t.time})
                    await assertDevices([m("s4")], [])

                    t.add(21)
                    discover.return_value = ["s1"]
                    s3 = devices.pop("s3")
                    del last_seen["s3"]
                    last_seen.update({"s1": t.time})
                    await assertDevices([], [s3])

                    t.add(20)
                    discover.return_value = ["s5"]
                    s2 = devices.pop("s2")
                    s4 = devices.pop("s4")
                    del last_seen["s2"]
                    del last_seen["s4"]
                    last_seen.update({"s5": t.time})
                    devices.update({"s5": m("s5")})
                    await assertDevices([m("s5")], [s2, s4])

                    # And no devices added or removed if final future
                    # is done after the search
                    t.add(30)

                    async def dr(refresh):
                        V.finder.final_future.cancel()
                        return ["s7"]

                    discover.reset_mock()
                    discover.side_effect = dr
                    await assertDevices([], [])

        describe "find":

            @pytest.mark.parametrize(
                "fltr,matches_runs",
                [(Filter.empty(), False), (Filter.from_kwargs(label="kitchen"), True)],
            )
            async it "streams devices that match the filter", V, fltr, matches_runs, FakeTime:

                class Patches:
                    def __init__(s, devices):
                        s.patches = []
                        s.devices = devices

                    def __enter__(s):
                        async def match(*args, **kwargs):
                            raise NotImplementedError()

                        async def finish():
                            raise NotImplementedError()

                        for d in s.devices:
                            pmatch = mock.patch.object(
                                d,
                                "matches",
                                pytest.helpers.AsyncMock(
                                    name=f"{d.serial}_matches", side_effect=match
                                ),
                            )

                            pfinish = mock.patch.object(
                                d,
                                "finish",
                                pytest.helpers.AsyncMock(
                                    name=f"{d.serial}_finish", side_effect=finish
                                ),
                            )

                            for p in (pmatch, pfinish):
                                p.start()
                                s.patches.append(p)

                    def __exit__(s, exc_typ, exc, tb):
                        for p in s.patches:
                            p.stop()

                futs = pytest.helpers.FutureDominoes(expected=6)
                called = []

                m = lambda s: Device.FieldSpec().empty_normalise(serial=s)
                s1 = m("s1")
                s2 = m("s2")
                s3 = m("s3")
                s4 = m("s4")
                s5 = m("s5")
                s6 = m("s6")
                s7 = m("s7")

                added = [s2]
                removed = [s4, s5, s6]
                ensure_devices = pytest.helpers.AsyncMock(
                    name="ensure_devices", return_value=[added, removed]
                )

                assert V.finder.devices == {}
                V.finder.devices = {"s1": s1, "s2": s2, "s3": s3, "s7": s7}

                ensure_devices_patch = mock.patch.object(
                    V.finder, "_ensure_devices", ensure_devices
                )

                with Patches([s1, s2, s3, s4, s5, s6, s7]), ensure_devices_patch, FakeTime() as t:

                    async def s4finish():
                        called.append("s4finish_start")
                        await futs[3]
                        if not matches_runs:
                            await futs[4]
                            await futs[5]
                        t.add(1)
                        called.append("s4finish_done")

                    async def s5finish():
                        called.append("s5finish_start")
                        await futs[1]
                        if not matches_runs:
                            await futs[2]
                        t.add(1)
                        called.append("s5finish_done")
                        raise ValueError("NOPE")

                    async def s6finish():
                        called.append("s6finish_start")
                        await futs[6]
                        t.add(1)
                        called.append("s6finish_done")
                        raise ValueError("NOPE")

                    s4.finish.side_effect = s4finish
                    s5.finish.side_effect = s5finish
                    s6.finish.side_effect = s6finish

                    async def s1matches(*args, **kwargs):
                        called.append("s1matches_start")
                        await futs[2]
                        t.add(1)
                        called.append("s1matches_done")
                        return False

                    async def s2matches(*args, **kwargs):
                        called.append("s2matches_start")
                        await futs[5]
                        t.add(1)
                        called.append("s2matches_done")
                        raise TypeError("NUP")

                    async def s3matches(*args, **kwargs):
                        called.append("s3matches_start")
                        await futs[4]
                        t.add(1)
                        called.append("s3matches_done")
                        return True

                    async def s7matches(*args, **kwargs):
                        called.append("s7matches_start")
                        # This finishes at the same time s4 finishes
                        await futs[3]
                        called.append("s7matches_done")
                        return True

                    s1.matches.side_effect = s1matches
                    s2.matches.side_effect = s2matches
                    s3.matches.side_effect = s3matches
                    s7.matches.side_effect = s7matches

                    found = []
                    futs.start()

                    async for device in V.finder.find(fltr):
                        found.append((t.time, device))

                    if not matches_runs:
                        expected = [(0, d) for d in (s1, s2, s3, s7)]
                    else:
                        expected = [(3, s7), (4, s3)]

                    same = found == expected
                    if not same:
                        print("Found")
                        for t, d in found:
                            print("\t", t, d.serial)
                        print("Expected")
                        for t, d in expected:
                            print("\t", t, d.serial)
                    assert same

                    if matches_runs:
                        for d in (s4, s5, s6):
                            d.matches.assert_not_called()
                        for d in (s1, s2, s3, s7):
                            d.matches.assert_called_once_with(
                                V.finder.sender, fltr, V.finder.collections
                            )
                    else:
                        for d in (s1, s2, s3, s4, s5, s6, s7):
                            d.matches.assert_not_called()

                if not matches_runs:
                    expected_called = [
                        "s4finish_start",
                        "s5finish_start",
                        "s6finish_start",
                        "s5finish_done",
                        "s4finish_done",
                        "s6finish_done",
                    ]
                else:
                    expected_called = [
                        "s4finish_start",
                        "s5finish_start",
                        "s5finish_done",
                        "s6finish_start",
                        "s1matches_start",
                        "s2matches_start",
                        "s3matches_start",
                        "s7matches_start",
                        "s1matches_done",
                        "s4finish_done",
                        "s7matches_done",
                        "s3matches_done",
                        "s2matches_done",
                        "s6finish_done",
                    ]

                assert called == expected_called
                await futs

        describe "info":

            @pytest.mark.parametrize(
                "fltr",
                [
                    Filter.from_kwargs(label="kitcehn"),
                    Filter.from_options({"label": "attic", "refresh_info": True}),
                ],
            )
            async it "streams devices after getting all info for that device", V, FakeTime, fltr:

                class Patches:
                    def __init__(s, devices):
                        s.patches = []
                        s.devices = devices

                    def __enter__(s):
                        async def match(*args, **kwargs):
                            raise NotImplementedError()

                        for d in s.devices:
                            pmatch = mock.patch.object(
                                d,
                                "matches",
                                pytest.helpers.AsyncMock(
                                    name=f"{d.serial}_matches", side_effect=match
                                ),
                            )
                            pmatch.start()
                            s.patches.append(pmatch)

                    def __exit__(s, exc_typ, exc, tb):
                        for p in s.patches:
                            p.stop()

                futs = pytest.helpers.FutureDominoes(expected=7)
                called = []

                m = lambda s: Device.FieldSpec().empty_normalise(serial=s)
                s1 = m("s1")
                s2 = m("s2")
                s3 = m("s3")
                s4 = m("s4")

                find_mock = pytest.helpers.MagicAsyncMock(name="find_mock")
                find_patch = mock.patch.object(V.finder, "find", find_mock)

                with Patches([s1, s2, s3, s4]), find_patch, FakeTime() as t:

                    async def find(fr):
                        assert fr is fltr
                        await futs[1]
                        t.add(1)
                        yield s1
                        await futs[3]
                        t.add(1)
                        yield s2
                        await futs[4]
                        t.add(1)
                        yield s3
                        yield s4

                    find_mock.side_effect = find

                    async def s1matches(*args, **kwargs):
                        called.append("s1matches_start")
                        await futs[2]
                        t.add(1)
                        called.append("s1matches_done")
                        raise TypeError("NUP")

                    async def s2matches(*args, **kwargs):
                        called.append("s2matches_start")
                        await futs[5]
                        t.add(1)
                        called.append("s2matches_done")
                        return True

                    async def s3matches(*args, **kwargs):
                        called.append("s3matches_start")
                        await futs[7]
                        t.add(1)
                        called.append("s3matches_done")
                        return True

                    async def s4matches(*args, **kwargs):
                        called.append("s3matches_start")
                        # This finishes at the same time s4 finishes
                        await futs[6]
                        t.add(1)
                        called.append("s7matches_done")
                        return False

                    s1.matches.side_effect = s1matches
                    s2.matches.side_effect = s2matches
                    s3.matches.side_effect = s3matches
                    s4.matches.side_effect = s4matches

                    found = []
                    futs.start()

                    async for device in V.finder.info(fltr):
                        found.append((t.time, device))

                    find_mock.assert_called_once_with(fltr)

                    expected = [(5, s2), (7, s3)]

                    same = found == expected
                    if not same:
                        print("Found")
                        for t, d in found:
                            print("\t", t, d.serial)
                        print("Expected")
                        for t, d in expected:
                            print("\t", t, d.serial)
                    assert same

                    empty_fltr = Filter.empty(refresh_info=fltr.refresh_info)
                    for d in (s1, s2, s3, s4):
                        d.matches.assert_called_once_with(
                            V.finder.sender, empty_fltr, V.finder.collections
                        )

                await futs
