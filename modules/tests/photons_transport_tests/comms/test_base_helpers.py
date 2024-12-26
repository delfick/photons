import asyncio
from unittest import mock

from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_app.errors import TimedOut
from photons_transport.comms.base import timeout_task


class TestTimeoutTask:
    async def test_it_does_nothing_if_the_task_has_a_result(self):
        async def doit():
            return 1

        task = hp.async_as_background(doit())
        await task

        errf = hp.create_future()
        timeout_task(task, errf, 1)

        assert not errf.done()

    async def test_it_does_nothing_if_the_task_has_an_exception(self):
        async def doit():
            raise Exception("NOPE")

        task = hp.async_as_background(doit())

        with assertRaises(Exception, "NOPE"):
            await task

        errf = hp.create_future()
        timeout_task(task, errf, 1)

        assert not errf.done()

    async def test_it_does_nothing_if_the_task_was_cancelled(self):
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

    async def test_it_cancels_the_task_if_its_not_done(self):
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

    async def test_it_does_not_set_exception_on_errf_if_its_already_done(self):
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

    async def test_it_does_not_set_exception_on_errf_already_has_an_exception(self):
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

    async def test_it_does_not_set_exception_on_errf_already_cancelled(self):
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
