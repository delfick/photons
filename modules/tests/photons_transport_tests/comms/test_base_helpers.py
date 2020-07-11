# coding: spec

from photons_transport.comms.base import timeout_task, NoLimit

from photons_app.errors import TimedOut
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import asyncio

describe "timeout_task":

    async it "does nothing if the task has a result":

        async def doit():
            return 1

        task = hp.async_as_background(doit())
        await task

        errf = hp.create_future()
        timeout_task(task, errf, 1)

        assert not errf.done()

    async it "does nothing if the task has an exception":

        async def doit():
            raise Exception("NOPE")

        task = hp.async_as_background(doit())

        with assertRaises(Exception, "NOPE"):
            await task

        errf = hp.create_future()
        timeout_task(task, errf, 1)

        assert not errf.done()

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

        errf = hp.create_future()
        timeout_task(task, errf, 1)

        assert not errf.done()

    async it "cancels the task if it's not done":
        called = []

        async def doit():
            called.append("sleep")
            await asyncio.sleep(10)
            called.append("slept")

        task = hp.async_as_background(doit())

        errf = hp.create_future()
        serial = mock.Mock(name="serial")
        timeout_task(task, errf, serial)

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled()
        assert errf.done()

        msg = "Waiting for reply to a packet"
        with assertRaises(TimedOut, msg, serial=serial):
            await errf

    async it "does not set exception on errf if it's already done":
        called = []

        async def doit():
            called.append("sleep")
            await asyncio.sleep(10)
            called.append("slept")

        task = hp.async_as_background(doit())

        errf = hp.create_future()
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

    async it "does not set exception on errf already has an exception":
        called = []

        async def doit():
            called.append("sleep")
            await asyncio.sleep(10)
            called.append("slept")

        task = hp.async_as_background(doit())

        errf = hp.create_future()
        errf.set_exception(ValueError("NOPE"))

        serial = mock.Mock(name="serial")
        timeout_task(task, errf, serial)

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled()
        assert errf.done()

        with assertRaises(ValueError, "NOPE"):
            await errf

    async it "does not set exception on errf already cancelled":
        called = []

        async def doit():
            called.append("sleep")
            await asyncio.sleep(10)
            called.append("slept")

        task = hp.async_as_background(doit())

        errf = hp.create_future()
        errf.cancel()

        serial = mock.Mock(name="serial")
        timeout_task(task, errf, serial)

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert task.cancelled()
        assert errf.cancelled()

describe "NoLimit":

    async it "behaves like a normal semaphore context manager":
        called = []

        lock = NoLimit()

        assert not lock.locked()
        async with lock:
            assert not lock.locked()
            called.append("no limit")
        assert not lock.locked()

        assert called == ["no limit"]

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
