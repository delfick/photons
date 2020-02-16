# coding: spec

from photons_transport import RetryOptions, RetryIterator

from contextlib import contextmanager
from unittest import mock
import asynctest
import pytest
import time

describe "RetryOptions":
    it "can be given a different timeouts":
        timeouts = mock.Mock(name="timeouts")
        options = RetryOptions(timeouts)
        assert options.timeouts is timeouts

    it "has some options":
        options = RetryOptions()
        for attr in (
            "finish_multi_gap",
            "gap_between_results",
            "gap_between_ack_and_res",
            "next_check_after_wait_for_result",
        ):
            assert type(getattr(options, attr)) == float
            assert getattr(options, attr) > 0

        assert type(options.timeouts) == list
        for i, thing in enumerate(options.timeouts):
            assert type(thing) == tuple, f"Item {i} is not a tuple: {thing}"
            assert len(thing) == 2, f"Item {i} is not length two: {thing}"
            assert all(type(t) in (float, int) for t in thing), f"Item {i} has not numbers: {thing}"

        assert options.timeout is None
        assert options.timeout_item is None

    describe "next_time":
        it "returns first time from timeouts if first time":
            assert RetryOptions().next_time == 0.2

            class Options(RetryOptions):
                timeouts = [(0.3, 0.4)]

            assert Options().next_time == 0.3

        it "keeps adding step till we get past end, before going to next timeout item":

            class Options(RetryOptions):
                timeouts = [(0.1, 0.1), (0.2, 0.5), (0.3, 0.9), (1, 5)]

            options = Options()
            expected = [0.1, 0.3, 0.5, 0.8, 1.1, 2.1, 3.1, 4.1, 5.1, 5.1, 5.1]

            for i, want in enumerate(expected):
                nxt = options.next_time
                assert nxt == pytest.approx(want, rel=1e-3)

    describe "iterator":
        it "creates a RetryIterator":
            options = RetryOptions([(0.1, 0.3), (0.5, 2)])
            now = time.time()
            get_now = mock.Mock(name="get_now", return_value=now)
            iterator = options.iterator(end_after=12, min_wait=2, get_now=get_now)
            assert isinstance(iterator, RetryIterator)
            assert iterator.end_at == now + 12
            assert iterator.min_wait == 2

            get_now.assert_called_once_with()
            get_now.reset_mock()
            assert iterator.get_now() == now
            get_now.assert_called_once_with()

            next_times = []
            for _ in range(6):
                next_times.append(iterator.get_next_time())

            # I have no idea why 0.3 is so weird here
            assert next_times == [0.1, 0.2, 0.30000000000000004, 0.8, 1.3, 1.8]

describe "RetryIterator":

    async it "can wait amounts":
        now = time.time()
        iterator = RetryIterator(now + 10, get_now=time.time, get_next_time=None)

        start = time.time()
        await iterator.wait(-1)
        assert time.time() - start < 0.001

        start = time.time()
        await iterator.wait(0.1)
        assert time.time() - start > 0.09
        assert time.time() - start < 0.15

    describe "usage":

        @contextmanager
        def make_iterator(self, end_after, next_times):
            class Now:
                def __init__(s):
                    s.value = 0

                def skip(s, val):
                    if val > 0:
                        s.value += val

                def __call__(s):
                    return s.value

            now = Now()
            calls = []

            def get_now():
                calls.append("get_now")
                return now()

            get_now = mock.Mock(name="get_now", side_effect=get_now)

            def get_next_time():
                calls.append("next_time")
                return next_times.pop(0)

            get_next_time = mock.Mock(name="get_next_time", side_effect=get_next_time)

            async def wait(timeout):
                now.skip(timeout)
                calls.append(("wait", timeout))

            wait = asynctest.mock.CoroutineMock(name="wait", side_effect=wait)

            iterator = RetryIterator(
                now.value + end_after, get_now=get_now, get_next_time=get_next_time
            )

            with mock.patch.object(iterator, "wait", wait):
                yield iterator, now, calls

        async it "works":
            next_times = [1, 1, 1]

            with self.make_iterator(3, next_times) as (iterator, now, calls):
                async for end_in, time_till_next in iterator:
                    now.skip(0.5)
                    calls.append(("loop", end_in, time_till_next, 0.5))

            self.maxDiff = None
            assert calls == [
                "get_now",
                "next_time",
                ("loop", 3.0, 1.0, 0.5),
                "get_now",
                ("wait", 0.5),
                "get_now",
                "next_time",
                ("loop", 2.0, 1, 0.5),
                "get_now",
                ("wait", 0.5),
                "get_now",
                "next_time",
                ("loop", 1.0, 1.0, 0.5),
                "get_now",
            ], calls

            assert next_times == []

        async it "can skip a next time":
            next_times = [0.1, 0.2, 0.1, 0.6, 2]

            with self.make_iterator(3, next_times) as (iterator, now, calls):
                async for end_in, time_till_next in iterator:
                    now.skip(0.5)
                    calls.append(("loop", end_in, time_till_next, 0.5))

            self.maxDiff = None
            assert calls == [
                "get_now",
                "next_time",
                ("loop", 3, 0.1, 0.5),
                "get_now",
                ("wait", -0.4),
                "get_now",
                "next_time",
                "next_time",
                "next_time",
                ("loop", 2.5, 0.5, 0.5),
                "get_now",
                ("wait", 0.0),
                "get_now",
                "next_time",
                ("loop", 2.0, 2.0, 0.5),
                "get_now",
            ], calls

            assert next_times == []

        async it "can skip a wait if we've gone past end_in":
            skips = [0.1, 0.2, 3]
            next_times = [0.1, 0.3, 0.6]

            with self.make_iterator(3, next_times) as (iterator, now, calls):
                async for end_in, time_till_next in iterator:
                    skip = skips.pop(0)
                    now.skip(skip)
                    calls.append(("loop", end_in, time_till_next, skip))

            self.maxDiff = None
            assert calls == [
                "get_now",
                "next_time",
                ("loop", 3, 0.1, 0.1),
                "get_now",
                ("wait", 0.0),
                "get_now",
                "next_time",
                ("loop", 2.9, 0.30000000000000004, 0.2),
                "get_now",
                ("wait", 0.09999999999999998),
                "get_now",
                "next_time",
                ("loop", 2.6, 0.6, 3),
                "get_now",
            ], calls

            assert next_times == []
