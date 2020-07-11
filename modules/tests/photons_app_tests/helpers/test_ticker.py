# coding: spec

from photons_app import helpers as hp

from unittest import mock
import asyncio
import time


class MockedCallLater:
    def __init__(self, t):
        self.t = t
        self.loop = asyncio.get_event_loop()

        self.task = None
        self.patch = None

        self.cont = hp.create_future()

        self.funcs = []
        self.called_times = []

        self.wait = None
        self.waiter = hp.ResettableFuture()
        self.waiter.set_result(True)

    def for_another(self, amount):
        self.wait = time.time() + amount
        self.waiter.reset()
        return self.waiter

    async def __aenter__(self):
        self.task = hp.async_as_background(self.calls())
        self.patch = mock.patch.object(self.loop, "call_later", self.call_later)
        self.patch.start()
        return self

    def start(self):
        if not self.cont.done():
            self.cont.set_result(True)

    async def __aexit__(self, exc_type, exc, tb):
        if self.patch:
            self.patch.stop()
        if self.task:
            self.task.cancel()
            await asyncio.wait([self.task])

    def call_later(self, when, func, *args):
        def caller():
            self.called_times.append(time.time())
            func(*args)

        self.funcs.append((time.time() + when, caller))

    def run(self, past_only=False):
        remaining = []
        executed = False
        now = time.time()
        for k, f in self.funcs:
            if (past_only and k >= now) or (not past_only and k > now):
                remaining.append((k, f))
            else:
                f()
                executed = True
        self.funcs = remaining
        return executed

    async def calls(self):
        while True:
            await self.cont
            now = time.time()

            if self.wait and now >= self.wait:
                self.waiter.reset()
                self.waiter.set_result(True)
                await asyncio.sleep(0)

            await asyncio.sleep(0)
            if not self.run():
                await asyncio.sleep(0)
                if self.waiter.done() and self.wait:
                    self.wait = None
                else:
                    self.t.add(1)


describe "tick":

    async it "keeps yielding such that yields are 'every' apart", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for i in hp.tick(3):
                    m.start()
                    called.append((i, time.time()))
                    if len(called) == 5:
                        break

        assert called == [(1, 0), (2, 3), (3, 6), (4, 9), (5, 12)]
        assert m.called_times == [3, 6, 9, 12]

    async it "keeps yielding until max_iterations", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for i in hp.tick(3, max_iterations=5):
                    m.start()
                    called.append(i)

        assert called == [1, 2, 3, 4, 5]

    async it "keeps yielding until max_time", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for i in hp.tick(3, max_time=20):
                    m.start()
                    called.append((i, time.time()))

        assert called == [(1, 0), (2, 3), (3, 6), (4, 9), (5, 12), (6, 15), (7, 18), (8, 21)]

    async it "keeps yielding until max_time or max_iterations", FakeTime:

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                called = []

                async for i in hp.tick(3, max_iterations=5, max_time=20):
                    m.start()
                    called.append((i, time.time()))

                assert called == [(1, 0), (2, 3), (3, 6), (4, 9), (5, 12)]

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                called = []

                async for i in hp.tick(3, max_iterations=10, max_time=20):
                    m.start()
                    called.append((i, time.time()))

                assert called == [
                    (1, 0),
                    (2, 3),
                    (3, 6),
                    (4, 9),
                    (5, 12),
                    (6, 15),
                    (7, 18),
                    (8, 21),
                ]

    async it "keeps yielding such that yields are best effort 'every' apart when tasks go over", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for i in hp.tick(3):
                    m.start()
                    called.append((i, time.time()))

                    await m.for_another(2)

                    if len(called) == 3:
                        await m.for_another(3)

                    if len(called) == 5:
                        await m.for_another(7)

                    if len(called) == 7:
                        break

        #                     0       3       6        9       12       15       18
        assert called == [(1, 0), (2, 3), (3, 6), (4, 11), (5, 13), (6, 22), (7, 24)]
        assert m.called_times == [3, 6, 9, 12, 15, 22, 25]

    async it "stops if final_future stops", FakeTime:
        called = []

        final_future = hp.create_future()

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for _ in hp.tick(3, final_future=final_future):
                    m.start()
                    called.append(time.time())
                    if len(called) == 5:
                        final_future.cancel()

        assert called == [0, 3, 6, 9, 12]
        assert m.called_times == [3, 6, 9, 12]

describe "ATicker":
    async it "can change the after permanently", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                ticker = hp.ATicker(3)
                async for _ in ticker:
                    m.start()
                    called.append(time.time())

                    if len(called) == 3:
                        ticker.change_after(5)

                    elif len(called) == 5:
                        await m.for_another(8)

                    elif len(called) == 7:
                        await m.for_another(1)

                    elif len(called) == 10:
                        break

        assert called == [0, 3, 6, 11, 16, 24, 26, 31, 36, 41]
        assert m.called_times == [3, 6, 9, 11, 16, 21, 26, 31, 36, 41]

    async it "can change the after once", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                ticker = hp.ATicker(3)
                async for _ in ticker:
                    m.start()
                    called.append(time.time())

                    if len(called) == 3:
                        ticker.change_after(5, set_new_every=False)

                    elif len(called) == 6:
                        break

        assert called == [0, 3, 6, 9, 12, 15]
        assert m.called_times == [3, 6, 9, 11, 12, 15]
