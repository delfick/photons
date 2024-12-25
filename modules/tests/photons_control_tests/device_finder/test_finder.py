from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_control.device_finder import Collections, Device, Filter, Finder


class TestFinder:
    def test_it_takes_in_a_sender_and_uses_its_stop_fut_if_final_future_not_specified(self):
        stop_fut = hp.create_future()
        sender = mock.Mock(name="sender", stop_fut=stop_fut)

        finder = Finder(sender)

        assert finder.sender is sender
        assert finder.forget_after == 30

        assert finder.devices == {}
        assert finder.last_seen == {}

        assert isinstance(finder.collections, Collections)

        class F:
            def __eq__(s, other):
                return isinstance(other, hp.ChildOfFuture) and other.original_fut is stop_fut

        assert finder.final_future == F()

    def test_it_uses_given_final_future_if_one_is_specified(self):
        sender = mock.Mock(name="sender", spec=[])
        final_future = hp.create_future()

        finder = Finder(sender, final_future)

        class F:
            def __eq__(s, other):
                return isinstance(other, hp.ChildOfFuture) and other.original_fut is final_future

        assert finder.final_future == F()

    def test_it_allows_you_to_specify_forget_after(self):
        sender = mock.Mock(name="sender", spec=[])
        final_future = hp.create_future()

        finder = Finder(sender, final_future)
        assert finder.forget_after == 30

        finder = Finder(sender, final_future, forget_after=42)
        assert finder.forget_after == 42

    class TestUsage:

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

        async def test_it_can_be_used_as_an_async_generator(self, V):
            finish = pytest.helpers.AsyncMock(name="finish")

            with mock.patch.object(V.finder, "finish", finish):
                async with V.finder as f:
                    assert f is V.finder
                    finish.assert_not_called()

            finish.assert_called_once_with(None, None, None)

        async def test_it_cleans_up_its_devices_on_finish(self, V):
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

                async def s3finish(exc_typ=None, exc=None, tb=None):
                    called.append("s3finish")
                    s1fut.set_result(True)
                    called.append("s3finish_done")

                async def s1finish(exc_typ=None, exc=None, tb=None):
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
                    f.assert_called_once_with(None, None, None)

                assert called == ["s1finish", "s3finish", "s3finish_done", "s1finish_done"]
            finally:
                for p in patches:
                    p.stop()

        class TestEnsureDevices:
            async def test_it_can_add_and_remove_devices(self, V, fake_time):
                t = fake_time

                async def assertDevices(serials, added, removed):
                    existing = {d.serial: id(d) for d in V.finder.devices.values()}
                    existing_last_seen = dict(V.finder.last_seen)

                    rd = V.finder._ensure_devices(serials)
                    rd = sorted([d.serial for d in rd])

                    now = list(V.finder.devices)

                    got = sorted(set(now) - set(existing))
                    want = sorted(added)
                    removed = sorted(removed)

                    same = got == want and rd == removed

                    if not same:
                        print("==== ADDED")
                        print(f"Expected: {added}")
                        print(f"Got     : {got}")
                        print("==== REMOVED")
                        print(f"Expected: {removed}")
                        print(f"Got     : {rd}")

                    assert got == want
                    assert rd == removed
                    assert all(serial not in V.finder.devices for serial in removed)

                    assert {
                        d.serial: id(d)
                        for d in V.finder.devices.values()
                        if d.serial in existing and d.serial not in removed
                    } == {serial: d for serial, d in existing.items() if serial not in removed}

                    for serial in V.finder.devices:
                        assert serial not in removed
                        if serial not in added and serial in serials:
                            assert V.finder.last_seen[serial] > existing_last_seen[serial]

                await assertDevices([], [], [])

                await assertDevices(["s1", "s2", "s3"], ["s1", "s2", "s3"], [])

                t.add(10)
                await assertDevices(["s2", "s1", "s4"], ["s4"], [])

                t.add(21)
                await assertDevices(["s1"], [], ["s3"])

                t.add(20)
                await assertDevices(["s5"], ["s5"], ["s2", "s4"])

                t.add(10)
                await assertDevices(["s1", "s5"], [], [])

        class TestFind:

            @pytest.mark.parametrize(
                "fltr,matches_runs",
                [(Filter.empty(), False), (Filter.from_kwargs(label="kitchen"), True)],
            )
            async def test_it_streams_devices_that_match_the_filter(
                self, V, fltr, matches_runs, fake_time
            ):
                t = fake_time

                class Patches:
                    def __init__(s, devices):
                        s.patches = []
                        s.devices = devices

                    def __enter__(s):
                        async def match(*args, **kwargs):
                            raise NotImplementedError()

                        async def finish(exc_typ=None, exc=None, tb=None):
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

                called = []
                async with pytest.helpers.FutureDominoes(expected=6) as futs:
                    m = lambda s: Device.FieldSpec().empty_normalise(serial=s)
                    s1 = m("s1")
                    s2 = m("s2")
                    s3 = m("s3")
                    s4 = m("s4")
                    s5 = m("s5")
                    s6 = m("s6")
                    s7 = m("s7")

                    all_serials = [s1, s2, s3, s4, s5, s6, s7]
                    private_find_all_serials = pytest.helpers.AsyncMock(
                        name="_find_all_serials", return_value=all_serials
                    )

                    removed = [s4, s5, s6]
                    private_ensure_devices = mock.Mock(name="_ensure_devices", return_value=removed)

                    assert V.finder.devices == {}
                    V.finder.devices = {"s1": s1, "s2": s2, "s3": s3, "s7": s7}

                    ensure_devices_patch = mock.patch.object(
                        V.finder, "_ensure_devices", private_ensure_devices
                    )
                    find_all_serials_patch = mock.patch.object(
                        V.finder, "_find_all_serials", private_find_all_serials
                    )

                    with Patches(
                        [s1, s2, s3, s4, s5, s6, s7]
                    ), ensure_devices_patch, find_all_serials_patch:

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

                private_ensure_devices.assert_called_once_with(all_serials)

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

        class TestInfo:

            @pytest.mark.parametrize(
                "fltr",
                [
                    Filter.from_kwargs(label="kitcehn"),
                    Filter.from_options({"label": "attic", "refresh_info": True}),
                ],
            )
            async def test_it_streams_devices_after_getting_all_info_for_that_device(
                self, V, fltr, fake_time
            ):
                t = fake_time

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

                async with pytest.helpers.FutureDominoes(expected=7) as futs:
                    called = []

                    m = lambda s: Device.FieldSpec().empty_normalise(serial=s)
                    s1 = m("s1")
                    s2 = m("s2")
                    s3 = m("s3")
                    s4 = m("s4")

                    find_mock = pytest.helpers.MagicAsyncMock(name="find_mock")
                    find_patch = mock.patch.object(V.finder, "find", find_mock)

                    with Patches([s1, s2, s3, s4]), find_patch:

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
