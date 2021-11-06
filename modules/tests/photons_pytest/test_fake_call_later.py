# coding: spec

from photons_app import helpers as hp

import time


def call_later(*args):
    return hp.get_event_loop().call_later(*args)


describe "MockedCalledLater":

    async it "works", FakeTime, MockedCallLater:
        with FakeTime() as t:
            async with MockedCallLater(t):
                waiter = hp.create_future()
                call_later(5, waiter.set_result, True)
                assert await waiter is True
                assert time.time() == 5

    async it "does the calls in order", FakeTime, MockedCallLater:
        with FakeTime() as t:
            async with MockedCallLater(t):
                assert time.time() == 0

                called = []
                waiter = hp.create_future()

                def c(v):
                    called.append((time.time(), v))
                    if len(called) == 4:
                        waiter.set_result(True)

                call_later(2, c, "2")
                call_later(1, c, "1")
                call_later(5, c, "5")
                call_later(0.3, c, "0.3")

                assert await waiter is True

                assert called == [(0.3, "0.3"), (1, "1"), (2, "2"), (5, "5")]

    async it "can cancel handles", FakeTime, MockedCallLater:
        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                info = {"handle": None}

                def nxt(*args):
                    if info["handle"]:
                        info["handle"].cancel()

                    info["handle"] = call_later(*args)

                waiter = hp.ResettableFuture()
                nxt(1, waiter.set_result, True)
                nxt(0.3, waiter.set_result, True)

                assert await waiter is True
                waiter.reset()
                assert time.time() == 0.3

                await m.add(1)
                assert time.time() == 1.3
                assert waiter.done()
                waiter.reset()

                nxt(2, waiter.set_result, True)
                await m.add(1.5)
                assert time.time() == 2.8

                nxt(1.5, waiter.set_result, True)
                await m.add(0.6)
                assert time.time() == 3.4
                assert not waiter.done()

                assert await waiter is True
                assert time.time() == 2.8 + 1.5
                assert time.time() == 0.3 + 1 + 1.5 + 1.5

                waiter.reset()
                nxt(0.3, waiter.set_result, True)
                await m.add(0.4)
                assert waiter.done()
                assert await waiter is True

                assert time.time() == 0.3 + 1 + 1.5 + 1.5 + 0.4
