# coding: spec

import asyncio
import time

from photons_app import helpers as hp

describe "tick":

    async it "keeps yielding such that yields are 'every' apart", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.tick(3) as ticks:
                    async for i, nxt in ticks:
                        called.append((i, nxt, time.time()))
                        if len(called) == 5:
                            break

        assert called == [(1, 3, 0), (2, 3, 3), (3, 3, 6), (4, 3, 9), (5, 3, 12)]
        assert m.called_times == [3, 6, 9, 12]

    async it "works with 0 every", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.tick(0, min_wait=0) as ticks:
                    async for i, nxt in ticks:
                        called.append((i, nxt, time.time()))
                        if i == 3:
                            await m.add(2)
                        elif i == 6:
                            break

        assert called == [(1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 2.0), (5, 0, 2.0), (6, 0, 2.0)]

    async it "works with 0 every and nonzero min_wait", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.tick(0, min_wait=0.1) as ticks:
                    async for i, nxt in ticks:
                        called.append((i, nxt, time.time()))
                        if i == 3:
                            await m.add(2)
                        elif i == 6:
                            break

        assert called == [
            (1, 0.1, 0),
            (2, 0.1, 0.1),
            (3, 0.1, 0.2),
            (4, 0.1, 2.2),
            (5, 0.1, 2.3),
            (6, 0.1, 2.4),
        ]

    async it "keeps yielding until max_iterations", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t):
                async with hp.tick(3, max_iterations=5) as ticks:
                    async for i, _ in ticks:
                        called.append(i)

        assert called == [1, 2, 3, 4, 5]

    async it "keeps yielding until max_time", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t):
                async with hp.tick(3, max_time=20) as ticks:
                    async for i, _ in ticks:
                        called.append((i, time.time()))

        assert called == [(1, 0), (2, 3), (3, 6), (4, 9), (5, 12), (6, 15), (7, 18)]

    async it "keeps yielding until max_time or max_iterations", FakeTime, MockedCallLater:

        with FakeTime() as t:
            async with MockedCallLater(t):
                called = []

                async with hp.tick(3, max_iterations=5, max_time=20) as ticks:
                    async for i, _ in ticks:
                        called.append((i, time.time()))

                assert called == [(1, 0), (2, 3), (3, 6), (4, 9), (5, 12)]

        with FakeTime() as t:
            async with MockedCallLater(t):
                called = []

                async with hp.tick(3, max_iterations=10, max_time=20) as ticks:
                    async for i, _ in ticks:
                        called.append((i, time.time()))

                assert called == [
                    (1, 0),
                    (2, 3),
                    (3, 6),
                    (4, 9),
                    (5, 12),
                    (6, 15),
                    (7, 18),
                ]

    async it "keeps yielding such that yields are best effort 'every' apart when tasks go over", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.tick(3) as ticks:
                    async for i, _ in ticks:
                        called.append((i, time.time()))

                        await m.add(2)

                        if len(called) == 3:
                            await m.add(3)

                        if len(called) == 5:
                            await m.add(7)

                        if len(called) == 7:
                            break

        #                     0       3       6        9       12       15       18
        assert called == [(1, 0), (2, 3), (3, 6), (4, 11), (5, 13), (6, 22), (7, 24)]
        assert m.called_times == [3, 6, 9, 12, 15, 24]

    async it "stops if final_future stops", FakeTime, MockedCallLater:
        called = []

        final_future = hp.create_future()

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.tick(3, final_future=final_future) as ticks:
                    async for _ in ticks:
                        called.append(time.time())
                        if len(called) == 5:
                            final_future.cancel()

        assert called == [0, 3, 6, 9, 12]
        assert m.called_times == [3, 6, 9, 12]

describe "ATicker":

    async it "can change the after permanently", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.ATicker(3) as ticks:
                    async for i, nxt in ticks:
                        called.append((i, nxt, time.time()))

                        if len(called) == 3:
                            ticks.change_after(5)

                        elif len(called) == 5:
                            await m.add(8)

                        elif len(called) == 7:
                            await m.add(1)

                        elif len(called) == 10:
                            break

        assert called == [
            (1, 3, 0),
            (2, 3, 3),
            (3, 3, 6),
            (4, 5, 11),
            (5, 5, 16),
            (6, 2, 24),
            (7, 5, 26),
            (8, 5, 31),
            (9, 5, 36),
            (10, 5, 41),
        ]
        assert m.called_times == [3, 6, 11, 16, 21, 26, 31, 36, 41]

    async it "can change the after once", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.ATicker(3) as ticks:
                    async for i, nxt in ticks:
                        called.append((i, nxt, time.time()))

                        if len(called) == 3:
                            ticks.change_after(5, set_new_every=False)

                        elif len(called) == 6:
                            break

        assert called == [(1, 3, 0), (2, 3, 3), (3, 3, 6), (4, 1, 11), (5, 3, 12), (6, 3, 15)]
        assert m.called_times == [3, 6, 11, 12, 15]

    async it "can have a minimum wait", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.ATicker(5, min_wait=2) as ticks:
                    async for i, nxt in ticks:
                        called.append((i, nxt, time.time()))

                        if len(called) == 2:
                            await m.add(9)

                        elif len(called) == 4:
                            break

        assert called == [(1, 5, 0), (2, 5, 5), (3, 6, 14), (4, 5, 20)]
        assert m.called_times == [5, 10, 20]

    async it "can be told to follow the schedule", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with hp.ATicker(5, min_wait=False) as ticks:
                    async for i, nxt in ticks:
                        called.append((i, nxt, time.time()))

                        if len(called) == 2:
                            await m.add(9)

                        elif len(called) == 4:
                            await m.add(12)

                        elif len(called) == 6:
                            break

        assert called == [
            (1, 5, 0),
            (2, 5.0, 5.0),
            (3, 1.0, 14.0),
            (4, 5.0, 15.0),
            (5, 3.0, 27.0),
            (6, 5.0, 30.0),
        ]
        assert m.called_times == [5, 10, 14, 15, 20, 27, 30]

    describe "with a pauser":
        async it "can be paused", FakeTime, MockedCallLater:
            called = []

            pauser = asyncio.Semaphore()

            with FakeTime() as t:
                async with MockedCallLater(t) as m:
                    async with hp.ATicker(5, min_wait=False, pauser=pauser) as ticks:
                        async for i, nxt in ticks:
                            called.append((i, nxt, time.time()))

                            if len(called) == 2:
                                await pauser.acquire()
                                hp.get_event_loop().call_later(28, pauser.release)

                            elif len(called) == 6:
                                break

            assert called == [
                (1, 5, 0),
                (2, 5.0, 5.0),
                (3, 2.0, 33.0),
                (4, 5.0, 35.0),
                (5, 5.0, 40.0),
                (6, 5.0, 45.0),
            ]
            assert m.called_times == [5.0, 10.0, 33.0, 33.0, 35.0, 40.0, 45.0]

        async it "cancelled final_future not stopped by pauser", FakeTime, MockedCallLater:
            called = []

            pauser = asyncio.Semaphore()

            with FakeTime() as t:
                async with MockedCallLater(t) as m:
                    async with hp.ATicker(5, min_wait=False, pauser=pauser) as ticks:
                        async for i, nxt in ticks:
                            called.append((i, nxt, time.time()))

                            if len(called) == 2:
                                await pauser.acquire()
                                hp.get_event_loop().call_later(14, ticks.final_future.cancel)

                assert time.time() == 19

            assert pauser.locked()
            assert called == [
                (1, 5, 0),
                (2, 5.0, 5.0),
            ]
            assert m.called_times == [5.0, 10.0, 19.0]
