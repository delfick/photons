# coding: spec

from photons_transport import RetryOptions

from unittest import mock
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

    describe "tick":
        async it "yields till the timeout", FakeTime, MockedCallLater:
            options = RetryOptions(timeouts=[[0.6, 1.8], [0.8, 5], [1.2, 15]])

            found = []
            with FakeTime() as t:
                async with MockedCallLater(t):
                    async for info in options.tick(10):
                        found.append((time.time(), info))

            assert found == [
                (0, (10, 0.6)),
                (0.6, (9.4, 0.6)),
                (1.2, (8.8, 0.6)),
                (1.8, (8.2, 0.6)),
                (2.4, (7.6, 0.6)),
                # We change to 0.8 at this point, so that undoes the next 0.6
                (3.2, (6.8, 0.8)),
                (4.0, (6.0, 0.8)),
                (4.8, (5.2, 0.8)),
                (5.6, (4.4, 0.8)),
                # Same as before but to 1.2 now
                (6.8, (3.2, 1.2)),
                (8.0, (2.0, 1.2)),
                (9.2, (0.8, 1.2)),
            ]

        async it "takes into account how long the block takes", FakeTime, MockedCallLater:
            options = RetryOptions(timeouts=[[0.6, 1.8], [0.8, 5], [1.2, 15]])

            found = []
            with FakeTime() as t:
                async with MockedCallLater(t) as m:
                    count = -1
                    async for info in options.tick(11):
                        count += 1
                        found.append((time.time(), info))
                        if count == 2:
                            await m.for_another(1)
                        elif count == 5:
                            await m.for_another(2)
                        elif count == 8:
                            await m.for_another(0.7)
                        elif count == 9:
                            await m.for_another(3)

            assert found == [
                (0, (11, 0.6)),
                # 0
                (0.6, (10.4, 0.6)),
                # 1
                (1.2, (9.8, 0.6)),
                # 2 - takes 1 seconds makes it 0.4 after it would have otherwise been
                (2.2, (8.8, 0.2)),
                # 3 - We changed to 0.8, so 1.8 was where we were. The 0.2 happens before we change
                # So we end up going to 2.6 instead
                (2.6, (8.4, 0.8)),
                # 4
                (3.4, (7.6, 0.8)),
                # 5 - takes 2 which is more than the 0.8
                # So instead of 4.2 or 5, we get out at 5.4 and still have 0.4 left
                (5.4, (5.6, 0.4)),
                # 6
                (6.2, (4.8, 1.2)),
                # 7
                (7.4, (3.6, 1.2)),
                # 8 - takes 0.7 means still only after 1.2
                (8.6, (2.4, 1.2)),
                # 9 - takes 3 bringing us over 11 so no other tick
            ]
