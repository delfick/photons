# coding: spec

from photons_transport.comms.base import timeout_task, NoLimit

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app.errors import TimedOut
from photons_app import helpers as hp

from unittest import mock
import asyncio

describe AsyncTestCase, "timeout_task":

    @with_timeout
    async it "does nothing if the task has a result":

        async def doit():
            return 1

        task = hp.async_as_background(doit())
        await task

        errf = asyncio.Future()
        timeout_task(task, errf, 1)

        assert not errf.done()

    @with_timeout
    async it "does nothing if the task has an exception":

        async def doit():
            raise Exception("NOPE")

        task = hp.async_as_background(doit())

        with self.fuzzyAssertRaisesError(Exception, "NOPE"):
            await task

        errf = asyncio.Future()
        timeout_task(task, errf, 1)

        assert not errf.done()

    @with_timeout
    async it "does nothing if the task was cancelled":

        async def doit():
            return 1

        task = hp.async_as_background(doit())
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled()

        errf = asyncio.Future()
        timeout_task(task, errf, 1)

        assert not errf.done()

    @with_timeout
    async it "cancels the task if it's not done":
        called = []

        async def doit():
            called.append("sleep")
            await asyncio.sleep(10)
            called.append("slept")

        task = hp.async_as_background(doit())

        errf = asyncio.Future()
        serial = mock.Mock(name="serial")
        timeout_task(task, errf, serial)

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled()
        assert errf.done()

        msg = "Waiting for reply to a packet"
        with self.fuzzyAssertRaisesError(TimedOut, msg, serial=serial):
            await errf

    @with_timeout
    async it "does not set exception on errf if it's already done":
        called = []

        async def doit():
            called.append("sleep")
            await asyncio.sleep(10)
            called.append("slept")

        task = hp.async_as_background(doit())

        errf = asyncio.Future()
        errf.set_result(1)

        serial = mock.Mock(name="serial")
        timeout_task(task, errf, serial)

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled()
        assert errf.done()

        assert await errf == 1

    @with_timeout
    async it "does not set exception on errf already has an exception":
        called = []

        async def doit():
            called.append("sleep")
            await asyncio.sleep(10)
            called.append("slept")

        task = hp.async_as_background(doit())

        errf = asyncio.Future()
        errf.set_exception(ValueError("NOPE"))

        serial = mock.Mock(name="serial")
        timeout_task(task, errf, serial)

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled()
        assert errf.done()

        with self.fuzzyAssertRaisesError(ValueError, "NOPE"):
            await errf

    @with_timeout
    async it "does not set exception on errf already cancelled":
        called = []

        async def doit():
            called.append("sleep")
            await asyncio.sleep(10)
            called.append("slept")

        task = hp.async_as_background(doit())

        errf = asyncio.Future()
        errf.cancel()

        serial = mock.Mock(name="serial")
        timeout_task(task, errf, serial)

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled()
        assert errf.cancelled()

describe AsyncTestCase, "NoLimit":

    @with_timeout
    async it "behaves like a normal semaphore context manager":
        called = []

        lock = NoLimit()

        assert not lock.locked()
        async with lock:
            assert not lock.locked()
            called.append("no limit")
        assert not lock.locked()

        assert called == ["no limit"]

    @with_timeout
    async it "behaves like a normal semaphore not context manager":
        called = []

        lock = NoLimit()
        assert not lock.locked()

        await lock.acquire()
        assert not lock.locked()
        called.append("no limit")
        lock.release()
        assert not lock.locked()

        assert called == ["no limit"]
