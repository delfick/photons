
import asyncio

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp

class TestResettableFuture:
    async def test_it_ensure_future_returns_the_ResettableFuture_as_is(self):
        fut = hp.ResettableFuture()
        assert asyncio.ensure_future(fut) is fut

    async def test_it_creates_a_future(self):
        fut = hp.ResettableFuture()
        assert isinstance(fut.fut, asyncio.Future)
        assert fut.name is None
        assert fut.fut.name == "ResettableFuture(None)::__init__[fut]"

        fut = hp.ResettableFuture(name="blah")
        assert fut.name == "blah"
        assert isinstance(fut.fut, asyncio.Future)
        assert fut.fut.name == "ResettableFuture(blah)::__init__[fut]"

    async def test_it_gets_callbacks_from_the_current_future(self):
        fut = hp.ResettableFuture()
        assert len(fut._callbacks) == 1
        pytest.helpers.assertFutCallbacks(fut, hp.silent_reporter)
        assert fut._callbacks == fut.fut._callbacks

    async def test_it_knows_if_the_future_is_done(self):
        fut = hp.ResettableFuture()
        assert not fut.done()
        fut.set_result(True)
        assert fut.done()
        fut.reset()
        assert not fut.done()

        fut.set_exception(TypeError("NOPE"))
        assert fut.done()
        fut.reset()
        assert not fut.done()

        fut.cancel()
        assert fut.done()
        fut.reset()
        assert not fut.done()

    async def test_it_can_get_and_set_a_result(self):
        fut = hp.ResettableFuture()
        fut.set_result(True)
        assert fut.result() is True

        with assertRaises(hp.InvalidStateError):
            fut.set_result(False)

        assert await fut is True

        fut.reset()
        assert not fut.done()
        fut.set_result(False)
        assert fut.result() is False

        assert await fut is False

    async def test_it_can_get_and_set_an_exception(self):
        fut = hp.ResettableFuture()
        error = ValueError("NOPE")
        fut.set_exception(error)
        assert fut.exception() is error

        with assertRaises(hp.InvalidStateError):
            fut.set_exception(TypeError("HI"))

        with assertRaises(ValueError, "NOPE"):
            await fut

        fut.reset()
        assert not fut.done()
        error2 = TypeError("HI")
        fut.set_exception(error2)
        assert fut.exception() is error2

        with assertRaises(TypeError, "HI"):
            await fut

    async def test_it_can_be_cancelled_and_be_asked_if_cancelled(self):
        fut = hp.ResettableFuture()
        fut.cancel()
        assert fut.cancelled()

        fut.cancel()
        assert fut.cancelled()

        with assertRaises(asyncio.CancelledError):
            await fut

        fut.reset()
        assert not fut.done()

        fut.cancel()
        with assertRaises(asyncio.CancelledError):
            await fut

    async def test_it_can_have_done_callbacks(self):
        fut = hp.ResettableFuture()

        called = []

        def one(res):
            called.append("ONE")

        def two(res):
            called.append("TWO")

        def three(res):
            called.append("THREE")

        fut.add_done_callback(one)
        fut.add_done_callback(two)
        fut.add_done_callback(three)

        fut.set_result(True)
        await asyncio.sleep(0)
        assert not fut._callbacks
        assert called == ["ONE", "TWO", "THREE"]

        fut.reset()
        called.clear()
        fut.add_done_callback(one)
        fut.add_done_callback(two)
        fut.add_done_callback(three)

        assert fut._callbacks and len(fut._callbacks) == 4
        fut.remove_done_callback(two)
        assert fut._callbacks and len(fut._callbacks) == 3

        fut.cancel()
        await asyncio.sleep(0)
        assert not fut._callbacks
        assert called == ["ONE", "THREE"]

        fut.reset()
        called.clear()
        fut.set_exception(TypeError("NOPE"))
        await asyncio.sleep(0)
        fut.add_done_callback(one)
        fut.add_done_callback(two)
        await asyncio.sleep(0)

        assert called == ["ONE", "TWO"]

    async def test_it_has_a_repr(self):
        fut = hp.ResettableFuture()
        assert repr(fut) == "<ResettableFuture#None((pending))>"

        fut = hp.ResettableFuture(name="hello")
        assert repr(fut) == "<ResettableFuture#hello((pending))>"

    class TestReset:
        async def test_it_does_nothing_if_the_future_hasnt_been_resolved_yet(self):
            fut = hp.ResettableFuture()
            f = fut.fut

            fut.reset()
            assert fut.fut is f

            called = []

            cb = lambda res: called.append("DONE1")
            fut.add_done_callback(cb)
            pytest.helpers.assertFutCallbacks(f, cb, hp.silent_reporter)
            pytest.helpers.assertFutCallbacks(fut, cb, hp.silent_reporter)

            fut.reset()
            pytest.helpers.assertFutCallbacks(f, cb, hp.silent_reporter)
            pytest.helpers.assertFutCallbacks(fut, cb, hp.silent_reporter)

            await asyncio.sleep(0)
            assert called == []
            pytest.helpers.assertFutCallbacks(f, cb, hp.silent_reporter)
            pytest.helpers.assertFutCallbacks(fut, cb, hp.silent_reporter)

            fut.set_result(True)
            await asyncio.sleep(0)
            assert called == ["DONE1"]
            pytest.helpers.assertFutCallbacks(f)
            pytest.helpers.assertFutCallbacks(fut)

        async def test_it_can_force_the_future_to_be_closed(self):
            fut = hp.ResettableFuture()
            f = fut.fut

            called = []
            cb = lambda res: called.append("DONE1")
            fut.add_done_callback(cb)
            pytest.helpers.assertFutCallbacks(f, cb, hp.silent_reporter)
            pytest.helpers.assertFutCallbacks(fut, cb, hp.silent_reporter)

            fut.reset(force=True)
            await asyncio.sleep(0)
            assert fut.fut is not f
            assert called == ["DONE1"]
            pytest.helpers.assertFutCallbacks(fut.fut, hp.silent_reporter)
            pytest.helpers.assertFutCallbacks(fut, hp.silent_reporter)
