# coding: spec

from photons_app.test_helpers import assertFutCallbacks
from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import asyncio
import pytest
import uuid
import time


@pytest.fixture()
def loop():
    return asyncio.get_event_loop()


describe "creating a future":
    it "can create a future from a provided loop":
        fut = mock.Mock(name="future")
        loop = mock.Mock(name="loop")
        loop.create_future.return_value = fut
        assert hp.create_future(loop=loop) is fut
        assert fut.name is None
        loop.create_future.assert_called_once_with()

    it "can create a future from current loop":
        fut = hp.create_future()
        assert isinstance(fut, asyncio.Future)
        assert fut.name is None

    it "can give a name to the future":
        fut = hp.create_future(name="hi")
        assert fut.name == "hi"


describe "fut_has_callback":
    async it "says no if fut has no callbacks":

        def func():
            pass

        fut = hp.create_future()
        assert not hp.fut_has_callback(fut, func)

    async it "says no if it has other callbacks":

        def func1():
            pass

        def func2():
            pass

        fut = hp.create_future()
        fut.add_done_callback(func1)
        assert not hp.fut_has_callback(fut, func2)

    async it "says yes if we have the callback":

        def func1():
            pass

        fut = hp.create_future()
        fut.add_done_callback(func1)
        assert hp.fut_has_callback(fut, func1)

        def func2():
            pass

        assert not hp.fut_has_callback(fut, func2)
        fut.add_done_callback(func2)
        assert hp.fut_has_callback(fut, func2)

describe "async_with_timeout":
    async it "returns the result of waiting on the coroutine":
        val = str(uuid.uuid1())

        async def func():
            return val

        res = await hp.async_with_timeout(func(), timeout=10)
        assert res == val

    async it "cancels the coroutine if it doesn't respond":

        async def func():
            await asyncio.sleep(2)

        start = time.time()
        with assertRaises(asyncio.CancelledError):
            await hp.async_with_timeout(func(), timeout=0.1)
        assert time.time() - start < 0.5

    async it "cancels the coroutine and raises timeout_error":
        error = PhotonsAppError("Blah")

        async def func():
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                assert False, "Expected it to just raise the error rather than cancelling first"

        start = time.time()
        with assertRaises(PhotonsAppError, "Blah"):
            await hp.async_with_timeout(func(), timeout=0.1, timeout_error=error)
        assert time.time() - start < 0.5

describe "async_as_background":
    async it "runs the coroutine in the background":

        async def func(one, two, three=None):
            return "{0}.{1}.{2}".format(one, two, three)

        t = hp.async_as_background(func(6, 5, three=9))
        assertFutCallbacks(t, hp.reporter)
        assert isinstance(t, asyncio.Task)
        assert await t == "6.5.9"

    async it "uses silent_reporter if silent is True":

        async def func(one, two, three=None):
            return "{0}.{1}.{2}".format(one, two, three)

        t = hp.async_as_background(func(6, 5, three=9), silent=True)
        assertFutCallbacks(t, hp.silent_reporter)
        assert isinstance(t, asyncio.Task)
        assert await t == "6.5.9"

describe "silent_reporter":
    async it "does nothing if the future was cancelled":
        fut = hp.create_future()
        fut.cancel()
        assert hp.silent_reporter(fut) is None

    async it "does nothing if the future has an exception":
        fut = hp.create_future()
        fut.set_exception(Exception("wat"))
        assert hp.silent_reporter(fut) is None

    async it "returns true if we have a result":
        fut = hp.create_future()
        fut.set_result(mock.Mock(name="result"))
        assert hp.silent_reporter(fut) is True

describe "reporter":
    async it "does nothing if the future was cancelled":
        fut = hp.create_future()
        fut.cancel()
        assert hp.reporter(fut) is None

    async it "does nothing if the future has an exception":
        fut = hp.create_future()
        fut.set_exception(Exception("wat"))
        assert hp.reporter(fut) is None

    async it "returns true if we have a result":
        fut = hp.create_future()
        fut.set_result(mock.Mock(name="result"))
        assert hp.reporter(fut) is True

describe "transfer_result":
    async it "works as a done_callback", loop:
        fut = hp.create_future()

        async def doit():
            return [1, 2]

        t = loop.create_task(doit())
        t.add_done_callback(hp.transfer_result(fut))
        await t

        assert fut.result() == [1, 2]

    async it "can run a process function", loop:
        fut = hp.create_future()
        res = mock.Mock(name="res")

        async def doit():
            return res

        def process(r, f):
            assert r.result() is res
            assert f is fut
            assert f.result() is res

        t = loop.create_task(doit())
        t.add_done_callback(hp.transfer_result(fut, process=process))
        await t

        assert fut.result() is res

    describe "errors_only":
        async it "cancels fut if res is cancelled":
            fut = hp.create_future()
            res = hp.create_future()
            res.cancel()

            hp.transfer_result(fut, errors_only=True)(res)
            assert res.cancelled()

        async it "sets exception on fut if res has an exception":
            fut = hp.create_future()
            res = hp.create_future()

            error = ValueError("NOPE")
            res.set_exception(error)

            hp.transfer_result(fut, errors_only=True)(res)
            assert fut.exception() == error

        async it "does not transfer result":
            fut = hp.create_future()
            res = hp.create_future()
            res.set_result([1, 2])

            hp.transfer_result(fut, errors_only=True)(res)
            assert not fut.done()

    describe "not errors_only":
        async it "cancels fut if res is cancelled":
            fut = hp.create_future()
            res = hp.create_future()
            res.cancel()

            hp.transfer_result(fut, errors_only=False)(res)
            assert res.cancelled()

        async it "sets exception on fut if res has an exception":
            fut = hp.create_future()
            res = hp.create_future()

            error = ValueError("NOPE")
            res.set_exception(error)

            hp.transfer_result(fut, errors_only=False)(res)
            assert fut.exception() == error

        async it "transfers result":
            fut = hp.create_future()
            res = hp.create_future()
            res.set_result([1, 2])

            hp.transfer_result(fut, errors_only=False)(res)
            assert fut.result() == [1, 2]

describe "noncancelled_results_from_futs":
    async it "returns results from done futures that aren't cancelled":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()
        fut4 = hp.create_future()

        result1 = mock.Mock(name="result1")
        result2 = mock.Mock(name="result2")

        fut2.set_result(result1)
        fut3.cancel()
        fut4.set_result(result2)

        assert hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4]) == (
            None,
            [result1, result2],
        )

    async it "returns found errors as well":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()
        fut4 = hp.create_future()

        error1 = Exception("wat")
        result2 = mock.Mock(name="result2")

        fut2.set_exception(error1)
        fut3.cancel()
        fut4.set_result(result2)

        assert hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4]) == (error1, [result2])

    async it "squashes the same error into one error":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()
        fut4 = hp.create_future()

        error1 = PhotonsAppError("wat", one=1)
        error2 = PhotonsAppError("wat", one=1)

        fut2.set_exception(error1)
        fut3.cancel()
        fut4.set_exception(error2)

        assert hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4]) == (error1, [])

    async it "can return error with multiple errors":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()
        fut4 = hp.create_future()
        fut5 = hp.create_future()

        error1 = PhotonsAppError("wat")
        error2 = PhotonsAppError("wat2")
        result2 = mock.Mock(name="result2")

        fut2.set_exception(error1)
        fut3.cancel()
        fut4.set_result(result2)
        fut5.set_exception(error2)

        assert hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4, fut5]) == (
            PhotonsAppError(_errors=[error1, error2]),
            [result2],
        )

describe "find_and_apply_result":

    @pytest.fixture()
    def V(self):
        class V:
            fut1 = hp.create_future()
            fut2 = hp.create_future()
            fut3 = hp.create_future()
            fut4 = hp.create_future()
            final_fut = hp.create_future()

            @hp.memoized_property
            def available_futs(s):
                return [s.fut1, s.fut2, s.fut3, s.fut4]

        return V()

    async it "cancels futures if final_future is cancelled", V:
        V.final_fut.cancel()
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False

        assert V.fut1.cancelled()
        assert V.fut2.cancelled()
        assert V.fut3.cancelled()
        assert V.fut4.cancelled()

        assert V.final_fut.cancelled()

    async it "sets exceptions on futures if final_future has an exception", V:
        error = ValueError("NOPE")
        V.final_fut.set_exception(error)
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False

        for f in V.available_futs:
            assert f.exception() is error

    async it "ignores futures already done when final_future has an exception", V:
        err1 = Exception("LOLZ")
        V.available_futs[0].set_exception(err1)
        V.available_futs[1].cancel()
        V.available_futs[2].set_result([1, 2])

        err2 = ValueError("NOPE")
        V.final_fut.set_exception(err2)
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False

        assert V.available_futs[0].exception() is err1
        assert V.available_futs[1].cancelled()
        assert V.available_futs[2].result() == [1, 2]
        assert V.available_futs[3].exception() is err2

    async it "spreads error if any is found", V:
        error1 = Exception("wat")
        V.fut2.set_exception(error1)

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True

        assert V.fut1.exception() is error1
        assert V.fut2.exception() is error1
        assert V.fut3.exception() is error1
        assert V.fut4.exception() is error1

        assert V.final_fut.exception() is error1

    async it "doesn't spread error to those already cancelled or with error", V:
        error1 = PhotonsAppError("wat")
        V.fut2.set_exception(error1)

        error2 = PhotonsAppError("wat2")
        V.fut1.set_exception(error2)

        V.fut4.cancel()

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True

        assert V.fut1.exception() is error2
        assert V.fut2.exception() is error1
        assert V.fut3.exception() == PhotonsAppError(_errors=[error2, error1])
        assert V.fut4.cancelled()

        assert V.final_fut.exception() == PhotonsAppError(_errors=[error2, error1])

    async it "sets results if one has a result", V:
        result = mock.Mock(name="result")
        V.fut1.set_result(result)

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True

        assert V.fut1.result() is result
        assert V.fut2.result() is result
        assert V.fut3.result() is result
        assert V.fut4.result() is result

        assert V.final_fut.result() is result

    async it "sets results if one has a result except for cancelled ones", V:
        result = mock.Mock(name="result")
        V.fut1.set_result(result)
        V.fut2.cancel()

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True

        assert V.fut1.result() is result
        assert V.fut2.cancelled()
        assert V.fut3.result() is result
        assert V.fut4.result() is result

        assert V.final_fut.result() is result

    async it "sets result on final_fut unless it's already cancelled", V:
        result = mock.Mock(name="result")
        V.fut1.set_result(result)
        V.final_fut.cancel()

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False
        assert V.final_fut.cancelled()

    async it "cancels final_fut if any of our futs are cancelled", V:
        V.fut1.cancel()
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True
        assert V.final_fut.cancelled()

    async it "does nothing if none of the futures are done", V:
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False
        for f in V.available_futs:
            assert not f.done()
        assert not V.final_fut.done()

describe "waiting for all futures":
    async it "does nothing if there are no futures":
        await hp.wait_for_all_futures()

    async it "waits for all the futures to be complete regardless of status":
        """Deliberately don't wait on futures to ensure we don't get warnings if they aren't awaited"""
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()
        fut4 = hp.create_future()

        w = hp.async_as_background(hp.wait_for_all_futures(fut1, fut2, fut3, fut3, fut4))
        await asyncio.sleep(0.01)
        assert not w.done()

        fut1.set_result(True)
        await asyncio.sleep(0.01)
        assert not w.done()

        fut2.set_exception(Exception("yo"))
        await asyncio.sleep(0.01)
        assert not w.done()

        fut3.cancel()
        await asyncio.sleep(0.01)
        assert not w.done()

        fut4.set_result(False)

        await asyncio.sleep(0.01)
        assert w.done()
        await w

        assert not any(f._callbacks for f in (fut1, fut2, fut3, fut4))

describe "waiting for first future":
    async it "does nothing if there are no futures":
        await hp.wait_for_first_future()

    async it "returns if any of the futures are already done":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()

        fut2.set_result(True)
        await hp.wait_for_first_future(fut1, fut2, fut3)
        assert not fut2._callbacks
        assert all(len(f._callbacks) == 1 for f in (fut1, fut3))

    async it "returns on the first future to have a result":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()

        w = hp.async_as_background(hp.wait_for_first_future(fut1, fut2, fut3))
        await asyncio.sleep(0.01)
        assert not w.done()

        fut2.set_result(True)
        await fut2
        await asyncio.sleep(0.01)
        assert w.done()

        await w
        assert not fut2._callbacks
        assert all(len(f._callbacks) == 1 for f in (fut1, fut3))

    async it "returns on the first future to have an exception":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()

        w = hp.async_as_background(hp.wait_for_first_future(fut1, fut2, fut3))
        await asyncio.sleep(0.01)
        assert not w.done()

        fut3.set_exception(ValueError("NOPE"))
        with assertRaises(ValueError, "NOPE"):
            await fut3
        await asyncio.sleep(0.01)
        assert w.done()

        await w
        assert not fut3._callbacks
        assert all(len(f._callbacks) == 1 for f in (fut1, fut2))

    async it "returns on the first future to be cancelled":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()

        w = hp.async_as_background(hp.wait_for_first_future(fut1, fut2, fut3))
        await asyncio.sleep(0.01)
        assert not w.done()

        fut1.cancel()
        with assertRaises(asyncio.CancelledError):
            await fut1
        await asyncio.sleep(0.01)
        assert w.done()

        await w
        assert not fut1._callbacks
        assert all(len(f._callbacks) == 1 for f in (fut2, fut3))

describe "cancel futures and wait":
    async it "does nothing if there are no futures":
        await hp.cancel_futures_and_wait()

    async it "does nothing if all the futures are already done":
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()

        fut1.set_result(True)
        fut2.set_exception(ValueError("YEAP"))
        fut3.cancel()

        await hp.cancel_futures_and_wait(fut1, fut2, fut3)

    async it "cancels running tasks":
        called = []

        async def run1():
            print("DAFUQ")
            try:
                await asyncio.sleep(100)
                print(" DSfsdf ")
            except asyncio.CancelledError:
                print("?")
                called.append("run1")

        async def run2():
            called.append("run2")
            await asyncio.sleep(50)

        async def run3():
            raise ValueError("HELLO")

        fut1 = hp.async_as_background(run1())
        fut2 = hp.async_as_background(run2())
        fut3 = hp.async_as_background(run3())

        await asyncio.sleep(0.01)
        await hp.cancel_futures_and_wait(fut1, fut2, fut3)
        assert sorted(called) == ["run1", "run2"]
