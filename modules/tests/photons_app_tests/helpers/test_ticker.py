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
        self.trigger = hp.ResettableFuture()

        self.whens = []

        self.called = []
        self.called_times = []

    async def __aenter__(self):
        self.task = hp.async_as_background(self.calls())
        self.patch = mock.patch.object(self.loop, "call_later", self.call_later)
        self.patch.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.patch:
            self.patch.stop()
        if self.task:
            self.task.cancel()
            await asyncio.wait([self.task])

    def call_later(self, when, func):
        self.trigger.reset()
        self.trigger.set_result(True)
        self.whens.append((time.time() + when, when, func))
        self.called.append((when, func))
        self.called_times.append(when)

    async def calls(self):
        while True:
            await self.trigger
            self.trigger.reset()

            whens = list(self.whens)
            self.whens.clear()

            finals = [(final, i) for i, (final, _, _) in enumerate(whens)]

            for final, i, in sorted(finals):
                if time.time() < final:
                    self.t.set(final)
                whens[i][2]()
                await asyncio.sleep(0)


describe "tick":
    async it "keeps yielding such that yields are 'every' apart", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for _ in hp.tick(3):
                    called.append(time.time())
                    if len(called) == 5:
                        break

        assert called == [0, 3, 6, 9, 12]
        assert m.called_times == [3, 3, 3, 3]

    async it "keeps yielding such that yields are best effort 'every' apart when tasks go over", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for _ in hp.tick(3):
                    called.append(time.time())
                    t.add(2)
                    if len(called) == 3:
                        t.add(3)

                    if len(called) == 5:
                        t.add(7)

                    if len(called) == 7:
                        break

        assert called == [0, 3, 6, 11, 14, 23, 26]
        assert m.called_times == [1, 1, -2, 1, -6, 1]

    async it "stops if final_future stops", FakeTime:
        called = []

        final_future = asyncio.Future()

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async for _ in hp.tick(3, final_future=final_future):
                    called.append(time.time())
                    if len(called) == 5:
                        final_future.cancel()

        assert called == [0, 3, 6, 9, 12]
        assert m.called_times == [3, 3, 3, 3]

describe "ATicker":
    async it "can change the after permanently", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                ticker = hp.ATicker(3)
                async for _ in ticker:
                    called.append(time.time())

                    if len(called) == 3:
                        ticker.change_after(5)

                    elif len(called) == 5:
                        t.add(8)

                    elif len(called) == 7:
                        t.add(1)

                    elif len(called) == 10:
                        break

        assert called == [0, 3, 6, 11, 16, 24, 29, 34, 39, 44]
        assert m.called_times == [3, 3, 5, 5, 5, -3, 5, 4, 5, 5]

    async it "can change the after once", FakeTime:
        called = []

        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                ticker = hp.ATicker(3)
                async for _ in ticker:
                    called.append(time.time())

                    if len(called) == 3:
                        ticker.change_after(5, set_new_every=False)

                    elif len(called) == 6:
                        break

        assert called == [0, 3, 6, 11, 14, 17]
        assert m.called_times == [3, 3, 5, 3, 3, 3]
