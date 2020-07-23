# coding: spec

from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
import asyncio
import pytest


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


describe "TaskHolder":
    it "takes in a final future", final_future:
        holder = hp.TaskHolder(final_future)
        assert holder.ts == []
        assert holder.final_future == pytest.helpers.child_future_of(final_future)

    async it "can take in tasks", final_future:
        called = []

        async def wait(amount):
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(0.05))
            ts.add(wait(0.01))

        assert called == [0.01, 0.05]

    async it "exits if we finish all tasks before the manager is left", final_future:
        called = []

        async def wait(amount):
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        async with hp.TaskHolder(final_future) as ts:
            await ts.add(wait(0.05))
            await ts.add(wait(0.01))
            assert called == [0.05, 0.01]

        assert called == [0.05, 0.01]

    async it "can wait for more tasks if they are added when the manager has left", final_future:
        called = []

        async def wait(ts, amount):
            if amount == 0.01:
                ts.add(wait(ts, 0.06))
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 0.05))
            ts.add(wait(ts, 0.01))

        assert called == [0.01, 0.05, 0.06]

    async it "does not fail if a task raises an exception", final_future:
        called = []

        async def wait(ts, amount):
            if amount == 0.01:
                ts.add(wait(ts, 0.06))
            try:
                if amount == 0.06:
                    raise TypeError("WAT")
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 0.05))
            ts.add(wait(ts, 0.01))

        assert called == [0.06, 0.01, 0.05]

    async it "stops waiting tasks if final_future is stopped", final_future:
        called = []

        async def wait(ts, amount):
            try:
                await asyncio.sleep(amount)
                if amount == 0.05:
                    final_future.set_result(True)
            except asyncio.CancelledError:
                called.append(("CANCELLED", amount))
            finally:
                called.append(("FINISHED", amount))

        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 5))
            ts.add(wait(ts, 0.05))

        assert called == [("FINISHED", 0.05), ("CANCELLED", 5), ("FINISHED", 5)]

    async it "can say how many pending tasks it has", final_future:
        called = []

        async def doit():
            await asyncio.sleep(1)

        async with hp.TaskHolder(final_future) as ts:
            assert ts.pending == 0
            t = ts.add(doit())
            assert ts.pending == 1

            def process(res):
                called.append(ts.pending)

            t.add_done_callback(process)
            t.cancel()

        assert called == [0]

    async it "cancels tasks if it gets cancelled", final_future:
        called = []
        waiter = hp.create_future()

        async def a_task(name):
            called.append(f"{name}_start")
            try:
                await hp.create_future()
            except asyncio.CancelledError:
                called.append(f"{name}_cancelled")
            except Exception as error:
                called.append((f"{name}_error", error))
            else:
                called.append(f"{name}_end")

        async def doit():
            async with hp.TaskHolder(final_future) as t:
                t.add(a_task("one"))
                t.add(a_task("two"))
                waiter.set_result(True)
                await hp.create_future()

        t = None
        try:
            t = hp.async_as_background(doit())
            await waiter
            t.cancel()
        finally:
            if t:
                t.cancel()

        with assertRaises(asyncio.CancelledError):
            await t
        assert called == ["one_start", "two_start", "one_cancelled", "two_cancelled"]
