import asyncio
import sys
from unittest import mock

from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp


class TestStopAsyncGenerator:
    async def test_it_can_cancel_a_generator(self):
        called = []
        ready = hp.create_future()

        async def d():
            try:
                called.append("wait")
                ready.set_result(True)
                yield 1
            except:
                called.append(sys.exc_info())
                raise
            finally:
                called.append("finally")

        gen = d()
        assert await gen.asend(None) == 1

        assert called == ["wait"]

        with assertRaises(asyncio.CancelledError):
            await hp.stop_async_generator(gen)

        assert called == [
            "wait",
            (asyncio.CancelledError, mock.ANY, mock.ANY),
            "finally",
        ]

    async def test_it_can_throw_an_arbitrary_exception_into_the_generator(self):
        called = []
        ready = hp.create_future()

        async def d():
            try:
                called.append("wait")
                ready.set_result(True)
                yield 1
            except:
                called.append(sys.exc_info())
                raise
            finally:
                called.append("finally")

        gen = d()
        assert await gen.asend(None) == 1

        assert called == ["wait"]

        error = ValueError("NOPE")
        with assertRaises(ValueError, "NOPE"):
            await hp.stop_async_generator(gen, exc=error)

        assert called == [
            "wait",
            (ValueError, error, mock.ANY),
            "finally",
        ]

    async def test_it_works_if_generator_is_already_complete(self):
        async def d():
            yield True

        gen = d()
        async for _ in gen:
            pass

        await hp.stop_async_generator(gen)

    async def test_it_works_if_generator_is_already_complete_by_cancellation(self):
        async def d():
            fut = hp.create_future()
            fut.cancel()
            await fut
            yield True

        gen = d()
        with assertRaises(asyncio.CancelledError):
            async for _ in gen:
                pass

        await hp.stop_async_generator(gen)

    async def test_it_works_if_generator_is_already_complete_by_exception(self):
        async def d():
            raise ValueError("NOPE")
            yield True

        gen = d()
        with assertRaises(ValueError, "NOPE"):
            async for _ in gen:
                pass

        await hp.stop_async_generator(gen)

    async def test_it_works_if_generator_is_half_complete(self):
        called = []

        async def d():
            called.append("start")
            try:
                for i in range(10):
                    called.append(i)
                    yield i
            except asyncio.CancelledError:
                called.append("cancel")
                raise
            except:
                called.append(("except", sys.exc_info()))
                raise
            finally:
                called.append("finally")

        gen = d()
        async for i in gen:
            if i == 5:
                break

        assert called == ["start", 0, 1, 2, 3, 4, 5]

        with assertRaises(asyncio.CancelledError):
            await hp.stop_async_generator(gen)
        assert called == ["start", 0, 1, 2, 3, 4, 5, "cancel", "finally"]

    async def test_it_works_if_generator_is_cancelled_inside(self):
        waiter = hp.create_future()

        called = []

        async def d():
            called.append("start")
            try:
                for i in range(10):
                    if waiter.done():
                        await waiter
                    called.append(i)
                    yield i
            except asyncio.CancelledError:
                called.append("cancel")
                raise
            except:
                called.append(("except", sys.exc_info()))
                raise
            finally:
                called.append("finally")

        gen = d()

        with assertRaises(asyncio.CancelledError):
            async for i in gen:
                if i == 5:
                    waiter.cancel()

        assert called == ["start", 0, 1, 2, 3, 4, 5, "cancel", "finally"]
        await hp.stop_async_generator(gen)

    async def test_it_works_if_generator_is_cancelled_outside(self):
        waiter = hp.create_future()

        called = []

        async def d():
            called.append("start")
            try:
                for i in range(10):
                    if waiter.done():
                        await waiter
                    called.append(i)
                    yield i
            except asyncio.CancelledError:
                called.append("cancel")
                raise
            except:
                called.append(("except", sys.exc_info()))
                raise
            finally:
                called.append("finally")

        gen = d()

        async def consume():
            async for i in gen:
                if i == 5:
                    waiter.set_result(True)
                    await hp.create_future()

        with assertRaises(asyncio.CancelledError):
            task = hp.async_as_background(consume())
            await waiter
            task.cancel()
            await task

        assert called == ["start", 0, 1, 2, 3, 4, 5]
        with assertRaises(asyncio.CancelledError):
            await hp.stop_async_generator(gen)
        assert called == ["start", 0, 1, 2, 3, 4, 5, "cancel", "finally"]
