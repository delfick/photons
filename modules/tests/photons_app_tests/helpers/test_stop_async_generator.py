# coding: spec

from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import asyncio
import sys


describe "stop_async_generator":
    async it "can cancel a generator":
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

    async it "can throw an arbitrary exception into the generator":
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

    async it "works if generator is already complete":

        async def d():
            yield True

        gen = d()
        async for _ in gen:
            pass

        await hp.stop_async_generator(gen)

    async it "works if generator is already complete by cancellation":

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

    async it "works if generator is already complete by exception":

        async def d():
            raise ValueError("NOPE")
            yield True

        gen = d()
        with assertRaises(ValueError, "NOPE"):
            async for _ in gen:
                pass

        await hp.stop_async_generator(gen)

    async it "works if generator is half complete":

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

    async it "works if generator is cancelled inside":
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

    async it "works if generator is cancelled outside":
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
