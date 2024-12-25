
import time
from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_transport import RetryTicker


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


class TestRetryTicker:
    def test_it_Must_be_given_timeouts(self):
        timeouts = mock.Mock(name="timeouts")
        options = RetryTicker(timeouts=timeouts)
        assert options.timeouts is timeouts

    class TestTick:
        async def test_it_yields_till_the_timeout(self, final_future, FakeTime, MockedCallLater):
            options = RetryTicker(timeouts=[[0.6, 1.8], [0.8, 5], [1.2, 15]])

            found = []
            with FakeTime() as t:
                async with MockedCallLater(t):
                    async for info in options.tick(final_future, 10):
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

        async def test_it_takes_into_account_how_long_the_block_takes(self, final_future, FakeTime, MockedCallLater):
            options = RetryTicker(timeouts=[[0.6, 1.8], [0.8, 5], [1.2, 15]])

            found = []
            with FakeTime() as t:
                async with MockedCallLater(t) as m:
                    count = -1
                    async for info in options.tick(final_future, 11):
                        count += 1
                        found.append((time.time(), info))
                        if count == 2:
                            await m.add(1)
                        elif count == 5:
                            await m.add(2)
                        elif count == 8:
                            await m.add(0.7)
                        elif count == 9:
                            await m.add(3)

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
