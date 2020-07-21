# coding: spec

from photons_app import helpers as hp

import time


describe "tick":

    async it "keeps yielding such that yields are 'every' apart", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for i, nxt in hp.tick(3):
                    called.append((i, nxt, time.time()))
                    if len(called) == 5:
                        break

        assert called == [(1, 3, 0), (2, 3, 3), (3, 3, 6), (4, 3, 9), (5, 3, 12)]
        assert m.called_times == [3, 6, 9, 12]

    async it "keeps yielding until max_iterations", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t):
                async for i, _ in hp.tick(3, max_iterations=5):
                    called.append(i)

        assert called == [1, 2, 3, 4, 5]

    async it "keeps yielding until max_time", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t):
                async for i, _ in hp.tick(3, max_time=20):
                    called.append((i, time.time()))

        assert called == [(1, 0), (2, 3), (3, 6), (4, 9), (5, 12), (6, 15), (7, 18)]

    async it "keeps yielding until max_time or max_iterations", FakeTime, MockedCallLater:

        with FakeTime() as t:
            async with MockedCallLater(t):
                called = []

                async for i, _ in hp.tick(3, max_iterations=5, max_time=20):
                    called.append((i, time.time()))

                assert called == [(1, 0), (2, 3), (3, 6), (4, 9), (5, 12)]

        with FakeTime() as t:
            async with MockedCallLater(t):
                called = []

                async for i, _ in hp.tick(3, max_iterations=10, max_time=20):
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
                async for i, _ in hp.tick(3):
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
                async for _ in hp.tick(3, final_future=final_future):
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
                ticker = hp.ATicker(3)
                async for i, nxt in ticker:
                    called.append((i, nxt, time.time()))

                    if len(called) == 3:
                        ticker.change_after(5)

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
                ticker = hp.ATicker(3)
                async for i, nxt in ticker:
                    called.append((i, nxt, time.time()))

                    if len(called) == 3:
                        ticker.change_after(5, set_new_every=False)

                    elif len(called) == 6:
                        break

        assert called == [(1, 3, 0), (2, 3, 3), (3, 3, 6), (4, 1, 11), (5, 3, 12), (6, 3, 15)]
        assert m.called_times == [3, 6, 11, 12, 15]

    async it "can have a minimum wait", FakeTime, MockedCallLater:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                ticker = hp.ATicker(5, min_wait=2)
                async for i, nxt in ticker:
                    called.append((i, nxt, time.time()))

                    if len(called) == 2:
                        await m.add(9)

                    elif len(called) == 4:
                        break

        assert called == [(1, 5, 0), (2, 5, 5), (3, 6, 14), (4, 5, 20)]
        assert m.called_times == [5, 10, 20]
