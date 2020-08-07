# coding: spec

from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import asyncio
import pytest


@pytest.fixture()
def final_future():
    fut = hp.create_future(name="final")
    try:
        yield fut
    finally:
        fut.cancel()


describe "ChildOfFuture":
    async it "takes in an original future", final_future:
        with hp.ChildOfFuture(final_future) as fut:
            assert fut.original_fut is final_future
            assert fut.name is None
            assert isinstance(fut.fut, asyncio.Future)

            assert fut.fut.name == "ChildOfFuture(None)::__init__[fut]"
            assert repr(fut) == "<ChildOfFuture#None((pending))<Future#final(pending)>>"

        with hp.ChildOfFuture(final_future, name="FUTZ") as fut:
            assert fut.original_fut is final_future
            assert fut.name == "FUTZ"
            assert isinstance(fut.fut, asyncio.Future)

            assert fut.fut.name == "ChildOfFuture(FUTZ)::__init__[fut]"
            assert repr(fut) == "<ChildOfFuture#FUTZ((pending))<Future#final(pending)>>"

    async it "ensure_future returns the ResettableFuture as is", final_future:
        with hp.ChildOfFuture(final_future) as fut:
            assert asyncio.ensure_future(fut) is fut

    describe "context manager":
        async it "is cancelled if not resolved after block", final_future:
            assert len(final_future._callbacks) == 1

            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                assert not fut.done()
                assert not final_future.done()

            assert not fut._callbacks

            assert len(final_future._callbacks) == 2
            await asyncio.sleep(0)
            assert len(final_future._callbacks) == 1

            assert fut.cancelled()
            assert not final_future.done()

        async it "is resolved if given result in block", final_future:
            assert len(final_future._callbacks) == 1

            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                assert not fut.done()
                assert not final_future.done()

                fut.set_result(True)

            assert not fut._callbacks

            assert len(final_future._callbacks) == 2
            await asyncio.sleep(0)
            assert len(final_future._callbacks) == 1

            assert fut.result() is True
            assert not final_future.done()

        async it "is resolved if given exception in block", final_future:
            assert len(final_future._callbacks) == 1

            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                assert not fut.done()
                assert not final_future.done()

                fut.set_exception(ValueError("HI"))

            assert not fut._callbacks

            assert len(final_future._callbacks) == 2
            await asyncio.sleep(0)
            assert len(final_future._callbacks) == 1

            with assertRaises(ValueError, "HI"):
                await fut

            assert not final_future.done()

        async it "is resolved if cancelled in block", final_future:
            assert len(final_future._callbacks) == 1

            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                assert not fut.done()
                assert not final_future.done()

                fut.cancel()

            assert not fut._callbacks

            assert len(final_future._callbacks) == 2
            await asyncio.sleep(0)
            assert len(final_future._callbacks) == 1

            assert fut.cancelled()
            assert not final_future.done()

    describe "original resolving":
        async it "cancels the fut if the final future cancels", final_future:
            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                final_future.cancel()
                await asyncio.sleep(0)
                assert fut.cancelled()

            assert not fut._callbacks
            assert not final_future._callbacks

        async it "passes on exception if the final future has exception", final_future:
            error = ValueError("HI")

            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                final_future.set_exception(error)
                await asyncio.sleep(0)
                assert fut.exception() is error

            assert not fut._callbacks
            assert not final_future._callbacks

        async it "cancels the fut if the final_future gets a result", final_future:
            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                final_future.set_result(True)
                await asyncio.sleep(0)
                assert fut.cancelled()

            assert not fut._callbacks
            assert not final_future._callbacks

    describe "done callbacks":
        async it "fires done callbacks on cancel", final_future:
            called = []

            def one(res):
                assert res.cancelled()
                called.append("ONE")

            def two(res):
                assert res.cancelled()
                called.append("TWO")

            with hp.ChildOfFuture(final_future) as fut:
                fut.add_done_callback(one)
                fut.add_done_callback(two)
                assert hp.fut_has_callback(fut, one)
                assert hp.fut_has_callback(fut, two)
                fut.cancel()

                await asyncio.sleep(0)
                assert called == ["ONE", "TWO"]
                assert not fut._callbacks

            called.clear()

            with hp.ChildOfFuture(final_future) as fut:
                fut.cancel()

                await asyncio.sleep(0)
                assert not fut._callbacks

                fut.add_done_callback(one)
                fut.add_done_callback(two)
                await asyncio.sleep(0)

                assert called == ["ONE", "TWO"]
                assert not fut._callbacks

            called.clear()

            with hp.ChildOfFuture(final_future) as fut:
                fut.add_done_callback(one)
                fut.add_done_callback(two)
                final_future.cancel()

                await asyncio.sleep(0)
                assert not fut._callbacks
                await asyncio.sleep(0)
                assert called == ["ONE", "TWO"]
                assert not fut._callbacks

        async it "fires done callbacks on exception", final_future:
            called = []
            error = ValueError("NOPE")

            def one(res):
                assert res.exception() is error
                called.append("ONE")

            def two(res):
                assert res.exception() is error
                called.append("TWO")

            with hp.ChildOfFuture(final_future) as fut:
                fut.add_done_callback(one)
                fut.add_done_callback(two)
                assert hp.fut_has_callback(fut, one)
                assert hp.fut_has_callback(fut, two)
                fut.set_exception(error)

                await asyncio.sleep(0)
                assert called == ["ONE", "TWO"]
                assert not fut._callbacks

            called.clear()

            with hp.ChildOfFuture(final_future) as fut:
                fut.set_exception(error)

                await asyncio.sleep(0)
                assert not fut._callbacks

                fut.add_done_callback(one)
                fut.add_done_callback(two)
                await asyncio.sleep(0)

                assert called == ["ONE", "TWO"]
                assert not fut._callbacks

            called.clear()

            with hp.ChildOfFuture(final_future) as fut:
                fut.add_done_callback(one)
                fut.add_done_callback(two)
                final_future.set_exception(error)

                await asyncio.sleep(0)
                assert not fut._callbacks
                await asyncio.sleep(0)
                assert called == ["ONE", "TWO"]
                assert not fut._callbacks

        async it "fires done callbacks on result", final_future:
            called = []
            result = mock.Mock(name="result")

            def result_one(res):
                assert res.result() is result
                called.append("RESULT_ONE")

            def result_two(res):
                assert res.result() is result
                called.append("RESULT_TWO")

            def cancelled_one(res):
                assert res.cancelled()
                called.append("CANCELLED_ONE")

            def cancelled_two(res):
                assert res.cancelled()
                called.append("CANCELLED_TWO")

            with hp.ChildOfFuture(final_future) as fut:
                fut.add_done_callback(result_one)
                fut.add_done_callback(result_two)
                assert hp.fut_has_callback(fut, result_one)
                assert hp.fut_has_callback(fut, result_two)
                fut.set_result(result)

                await asyncio.sleep(0)
                assert called == ["RESULT_ONE", "RESULT_TWO"]
                assert not fut._callbacks

            called.clear()

            with hp.ChildOfFuture(final_future) as fut:
                fut.set_result(result)

                await asyncio.sleep(0)
                assert not fut._callbacks

                fut.add_done_callback(result_one)
                fut.add_done_callback(result_two)
                await asyncio.sleep(0)

                assert called == ["RESULT_ONE", "RESULT_TWO"]
                assert not fut._callbacks

            called.clear()

            with hp.ChildOfFuture(final_future) as fut:
                fut.add_done_callback(cancelled_one)
                fut.add_done_callback(cancelled_two)
                final_future.set_result(result)

                await asyncio.sleep(0)
                assert not fut._callbacks
                await asyncio.sleep(0)
                assert called == ["CANCELLED_ONE", "CANCELLED_TWO"]
                assert not fut._callbacks

    describe "resolving the future":
        async it "can have a result", final_future:
            with hp.ChildOfFuture(final_future) as fut:
                fut.set_result(True)
                assert fut.done()
                await asyncio.sleep(0)
                assert await fut is True

            with hp.ChildOfFuture(final_future) as fut:
                final_future.set_result(True)

                with assertRaises(hp.InvalidStateError):
                    fut.set_result(True)

                assert fut.done()
                assert fut.cancelled()

        async it "can have an exception", final_future:
            error = ValueError("NOPE")

            with hp.ChildOfFuture(final_future) as fut:
                fut.set_exception(error)
                assert fut.done()

                await asyncio.sleep(0)

                with assertRaises(ValueError, "NOPE"):
                    await fut

                assert fut.exception() is error

            with hp.ChildOfFuture(final_future) as fut:
                final_future.set_exception(error)

                with assertRaises(hp.InvalidStateError):
                    fut.set_exception(error)

                assert fut.exception() is error
                assert fut.done()

        async it "can be cancelled", final_future:
            with hp.ChildOfFuture(final_future) as fut:
                fut.cancel()
                assert fut.done()
                assert fut.cancelled()

                await asyncio.sleep(0)

                with assertRaises(asyncio.CancelledError):
                    await fut

            with hp.ChildOfFuture(final_future) as fut:
                final_future.cancel()
                assert fut.cancelled()

                fut.cancel()
                assert fut.cancelled()

                with assertRaises(asyncio.CancelledError):
                    await fut

                assert fut.done()
