# coding: spec

from photons_transport import RetryOptions, RetryIterator

from photons_app.test_helpers import TestCase, AsyncTestCase, with_timeout

from contextlib import contextmanager
from unittest import mock
import asynctest
import time

describe TestCase, "RetryOptions":
    it "can be given a different timeouts":
        timeouts = mock.Mock(name="timeouts")
        options = RetryOptions(timeouts)
        self.assertIs(options.timeouts, timeouts)

    it "has some options":
        options = RetryOptions()
        for attr in (
            "finish_multi_gap",
            "gap_between_results",
            "gap_between_ack_and_res",
            "next_check_after_wait_for_result",
        ):
            self.assertEqual(type(getattr(options, attr)), float)
            self.assertGreater(getattr(options, attr), 0)

        self.assertEqual(type(options.timeouts), list)
        for i, thing in enumerate(options.timeouts):
            self.assertEqual(type(thing), tuple, f"Item {i} is not a tuple: {thing}")
            self.assertEqual(len(thing), 2, f"Item {i} is not length two: {thing}")
            assert all(type(t) in (float, int) for t in thing), f"Item {i} has not numbers: {thing}"

        self.assertIs(options.timeout, None)
        self.assertIs(options.timeout_item, None)

    describe "next_time":
        it "returns first time from timeouts if first time":
            self.assertEqual(RetryOptions().next_time, 0.2)

            class Options(RetryOptions):
                timeouts = [(0.3, 0.4)]

            self.assertEqual(Options().next_time, 0.3)

        it "keeps adding step till we get past end, before going to next timeout item":

            class Options(RetryOptions):
                timeouts = [(0.1, 0.1), (0.2, 0.5), (0.3, 0.9), (1, 5)]

            options = Options()
            expected = [0.1, 0.3, 0.5, 0.8, 1.1, 2.1, 3.1, 4.1, 5.1, 5.1, 5.1]

            for i, want in enumerate(expected):
                nxt = options.next_time
                self.assertAlmostEqual(nxt, want, 3, f"Expected item {i} to be {want}, got {nxt}")

    describe "iterator":
        it "creates a RetryIterator":
            options = RetryOptions([(0.1, 0.3), (0.5, 2)])
            now = time.time()
            get_now = mock.Mock(name="get_now", return_value=now)
            iterator = options.iterator(end_after=12, min_wait=2, get_now=get_now)
            self.assertIsInstance(iterator, RetryIterator)
            self.assertEqual(iterator.end_at, now + 12)
            self.assertEqual(iterator.min_wait, 2)

            get_now.assert_called_once_with()
            get_now.reset_mock()
            self.assertEqual(iterator.get_now(), now)
            get_now.assert_called_once_with()

            next_times = []
            for _ in range(6):
                next_times.append(iterator.get_next_time())

            # I have no idea why 0.3 is so weird here
            self.assertEqual(next_times, [0.1, 0.2, 0.30000000000000004, 0.8, 1.3, 1.8])

describe AsyncTestCase, "RetryIterator":

    @with_timeout
    async it "can wait amounts":
        now = time.time()
        iterator = RetryIterator(now + 10, get_now=time.time, get_next_time=None)

        start = time.time()
        await iterator.wait(-1)
        self.assertLess(time.time() - start, 0.001)

        start = time.time()
        await iterator.wait(0.1)
        self.assertGreater(time.time() - start, 0.09)
        self.assertLess(time.time() - start, 0.15)

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

        @with_timeout
        async it "works":
            next_times = [1, 1, 1]

            with self.make_iterator(3, next_times) as (iterator, now, calls):
                async for end_in, time_till_next in iterator:
                    now.skip(0.5)
                    calls.append(("loop", end_in, time_till_next, 0.5))

            self.maxDiff = None
            self.assertEqual(
                calls,
                [
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
                ],
                calls,
            )

            self.assertEqual(next_times, [])

        @with_timeout
        async it "can skip a next time":
            next_times = [0.1, 0.2, 0.1, 0.6, 2]

            with self.make_iterator(3, next_times) as (iterator, now, calls):
                async for end_in, time_till_next in iterator:
                    now.skip(0.5)
                    calls.append(("loop", end_in, time_till_next, 0.5))

            self.maxDiff = None
            self.assertEqual(
                calls,
                [
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
                ],
                calls,
            )

            self.assertEqual(next_times, [])

        @with_timeout
        async it "can skip a wait if we've gone past end_in":
            skips = [0.1, 0.2, 3]
            next_times = [0.1, 0.3, 0.6]

            with self.make_iterator(3, next_times) as (iterator, now, calls):
                async for end_in, time_till_next in iterator:
                    skip = skips.pop(0)
                    now.skip(skip)
                    calls.append(("loop", end_in, time_till_next, skip))

            self.maxDiff = None
            self.assertEqual(
                calls,
                [
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
                ],
                calls,
            )

            self.assertEqual(next_times, [])
