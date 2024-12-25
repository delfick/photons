
import asyncio
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp


@pytest.fixture()
def final_future():
    fut = hp.create_future(name="final")
    try:
        yield fut
    finally:
        fut.cancel()


class TestChildOfFuture:
    async def test_it_takes_in_an_original_future(self, final_future):
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

    async def test_it_ensure_future_returns_the_ResettableFuture_as_is(self, final_future):
        with hp.ChildOfFuture(final_future) as fut:
            assert asyncio.ensure_future(fut) is fut

    class TestContextManager:
        async def test_it_is_cancelled_if_not_resolved_after_block(self, final_future):
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

        async def test_it_is_resolved_if_given_result_in_block(self, final_future):
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

        async def test_it_is_resolved_if_given_exception_in_block(self, final_future):
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

        async def test_it_is_resolved_if_cancelled_in_block(self, final_future):
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

    class TestOriginalResolving:
        async def test_it_cancels_the_fut_if_the_final_future_cancels(self, final_future):
            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                final_future.cancel()
                await asyncio.sleep(0)
                assert fut.cancelled()

            assert not fut._callbacks
            assert not final_future._callbacks

        async def test_it_passes_on_exception_if_the_final_future_has_exception(self, final_future):
            error = ValueError("HI")

            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                final_future.set_exception(error)
                await asyncio.sleep(0)
                assert fut.exception() is error

            assert not fut._callbacks
            assert not final_future._callbacks

        async def test_it_cancels_the_fut_if_the_final_future_gets_a_result(self, final_future):
            with hp.ChildOfFuture(final_future) as fut:
                assert len(fut._callbacks) == 2
                assert len(final_future._callbacks) == 2

                final_future.set_result(True)
                await asyncio.sleep(0)
                assert fut.cancelled()

            assert not fut._callbacks
            assert not final_future._callbacks

    class TestDoneCallbacks:
        async def test_it_fires_done_callbacks_on_cancel(self, final_future):
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

        async def test_it_fires_done_callbacks_on_exception(self, final_future):
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

        async def test_it_fires_done_callbacks_on_result(self, final_future):
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

    class TestResolvingTheFuture:
        async def test_it_can_have_a_result(self, final_future):
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

        async def test_it_can_have_an_exception(self, final_future):
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

        async def test_it_can_be_cancelled(self, final_future):
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
