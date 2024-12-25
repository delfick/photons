
import asyncio
import time
import uuid
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError


@pytest.fixture()
def loop():
    return hp.get_event_loop()


class TestCreatingAFuture:
    def test_it_can_create_a_future_from_a_provided_loop(self):
        fut = mock.Mock(name="future")
        loop = mock.Mock(name="loop")
        loop.create_future.return_value = fut
        assert hp.create_future(loop=loop) is fut
        assert fut.name is None
        loop.create_future.assert_called_once_with()

    def test_it_can_create_a_future_from_current_loop(self):
        fut = hp.create_future()
        assert isinstance(fut, asyncio.Future)
        assert fut.name is None

    def test_it_can_give_a_name_to_the_future(self):
        fut = hp.create_future(name="hi")
        assert fut.name == "hi"


class TestFutHasCallback:
    async def test_it_says_no_if_fut_has_no_callbacks(self):

        def func():
            pass

        fut = hp.create_future()
        assert not hp.fut_has_callback(fut, func)

    async def test_it_says_no_if_it_has_other_callbacks(self):

        def func1():
            pass

        def func2():
            pass

        fut = hp.create_future()
        fut.add_done_callback(func1)
        assert not hp.fut_has_callback(fut, func2)

    async def test_it_says_yes_if_we_have_the_callback(self):

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

class TestAsyncWithTimeout:
    async def test_it_returns_the_result_of_waiting_on_the_coroutine(self):
        val = str(uuid.uuid1())

        async def func():
            return val

        res = await hp.async_with_timeout(func(), timeout=10)
        assert res == val

    async def test_it_cancels_the_coroutine_if_it_doesnt_respond(self):

        async def func():
            await asyncio.sleep(2)

        start = time.time()
        with assertRaises(asyncio.CancelledError):
            await hp.async_with_timeout(func(), timeout=0.1)
        assert time.time() - start < 0.5

    async def test_it_cancels_the_coroutine_and_raises_timeout_error(self):
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

class TestAsyncAsBackground:
    async def test_it_runs_the_coroutine_in_the_background(self):

        async def func(one, two, three=None):
            return "{0}.{1}.{2}".format(one, two, three)

        t = hp.async_as_background(func(6, 5, three=9))
        pytest.helpers.assertFutCallbacks(t, hp.reporter)
        assert isinstance(t, asyncio.Task)
        assert await t == "6.5.9"

    async def test_it_uses_silent_reporter_if_silent_is_True(self):

        async def func(one, two, three=None):
            return "{0}.{1}.{2}".format(one, two, three)

        t = hp.async_as_background(func(6, 5, three=9), silent=True)
        pytest.helpers.assertFutCallbacks(t, hp.silent_reporter)
        assert isinstance(t, asyncio.Task)
        assert await t == "6.5.9"

class TestSilentReporter:
    async def test_it_does_nothing_if_the_future_was_cancelled(self):
        fut = hp.create_future()
        fut.cancel()
        assert hp.silent_reporter(fut) is None

    async def test_it_does_nothing_if_the_future_has_an_exception(self):
        fut = hp.create_future()
        fut.set_exception(Exception("wat"))
        assert hp.silent_reporter(fut) is None

    async def test_it_returns_true_if_we_have_a_result(self):
        fut = hp.create_future()
        fut.set_result(mock.Mock(name="result"))
        assert hp.silent_reporter(fut) is True

class TestReporter:
    async def test_it_does_nothing_if_the_future_was_cancelled(self):
        fut = hp.create_future()
        fut.cancel()
        assert hp.reporter(fut) is None

    async def test_it_does_nothing_if_the_future_has_an_exception(self):
        fut = hp.create_future()
        fut.set_exception(Exception("wat"))
        assert hp.reporter(fut) is None

    async def test_it_returns_true_if_we_have_a_result(self):
        fut = hp.create_future()
        fut.set_result(mock.Mock(name="result"))
        assert hp.reporter(fut) is True

class TestTransferResult:
    async def test_it_works_as_a_done_callback(self, loop):
        fut = hp.create_future()

        async def doit():
            return [1, 2]

        t = loop.create_task(doit())
        t.add_done_callback(hp.transfer_result(fut))
        await t

        assert fut.result() == [1, 2]

    async def test_it_can_run_a_process_function(self, loop):
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

    class TestErrorsOnly:
        async def test_it_cancels_fut_if_res_is_cancelled(self):
            fut = hp.create_future()
            res = hp.create_future()
            res.cancel()

            hp.transfer_result(fut, errors_only=True)(res)
            assert res.cancelled()

        async def test_it_sets_exception_on_fut_if_res_has_an_exception(self):
            fut = hp.create_future()
            res = hp.create_future()

            error = ValueError("NOPE")
            res.set_exception(error)

            hp.transfer_result(fut, errors_only=True)(res)
            assert fut.exception() == error

        async def test_it_does_not_transfer_result(self):
            fut = hp.create_future()
            res = hp.create_future()
            res.set_result([1, 2])

            hp.transfer_result(fut, errors_only=True)(res)
            assert not fut.done()

    class TestNotErrorsOnly:
        async def test_it_cancels_fut_if_res_is_cancelled(self):
            fut = hp.create_future()
            res = hp.create_future()
            res.cancel()

            hp.transfer_result(fut, errors_only=False)(res)
            assert res.cancelled()

        async def test_it_sets_exception_on_fut_if_res_has_an_exception(self):
            fut = hp.create_future()
            res = hp.create_future()

            error = ValueError("NOPE")
            res.set_exception(error)

            hp.transfer_result(fut, errors_only=False)(res)
            assert fut.exception() == error

        async def test_it_transfers_result(self):
            fut = hp.create_future()
            res = hp.create_future()
            res.set_result([1, 2])

            hp.transfer_result(fut, errors_only=False)(res)
            assert fut.result() == [1, 2]

class TestNoncancelledResultsFromFuts:
    async def test_it_returns_results_from_done_futures_that_arent_cancelled(self):
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

    async def test_it_returns_found_errors_as_well(self):
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

    async def test_it_squashes_the_same_error_into_one_error(self):
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

    async def test_it_can_return_error_with_multiple_errors(self):
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

class TestFindAndApplyResult:

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

    async def test_it_cancels_futures_if_final_future_is_cancelled(self, V):
        V.final_fut.cancel()
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False

        assert V.fut1.cancelled()
        assert V.fut2.cancelled()
        assert V.fut3.cancelled()
        assert V.fut4.cancelled()

        assert V.final_fut.cancelled()

    async def test_it_sets_exceptions_on_futures_if_final_future_has_an_exception(self, V):
        error = ValueError("NOPE")
        V.final_fut.set_exception(error)
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False

        for f in V.available_futs:
            assert f.exception() is error

    async def test_it_ignores_futures_already_done_when_final_future_has_an_exception(self, V):
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

    async def test_it_spreads_error_if_any_is_found(self, V):
        error1 = Exception("wat")
        V.fut2.set_exception(error1)

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True

        assert V.fut1.exception() is error1
        assert V.fut2.exception() is error1
        assert V.fut3.exception() is error1
        assert V.fut4.exception() is error1

        assert V.final_fut.exception() is error1

    async def test_it_doesnt_spread_error_to_those_already_cancelled_or_with_error(self, V):
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

    async def test_it_sets_results_if_one_has_a_result(self, V):
        result = mock.Mock(name="result")
        V.fut1.set_result(result)

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True

        assert V.fut1.result() is result
        assert V.fut2.result() is result
        assert V.fut3.result() is result
        assert V.fut4.result() is result

        assert V.final_fut.result() is result

    async def test_it_sets_results_if_one_has_a_result_except_for_cancelled_ones(self, V):
        result = mock.Mock(name="result")
        V.fut1.set_result(result)
        V.fut2.cancel()

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True

        assert V.fut1.result() is result
        assert V.fut2.cancelled()
        assert V.fut3.result() is result
        assert V.fut4.result() is result

        assert V.final_fut.result() is result

    async def test_it_sets_result_on_final_fut_unless_its_already_cancelled(self, V):
        result = mock.Mock(name="result")
        V.fut1.set_result(result)
        V.final_fut.cancel()

        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False
        assert V.final_fut.cancelled()

    async def test_it_cancels_final_fut_if_any_of_our_futs_are_cancelled(self, V):
        V.fut1.cancel()
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is True
        assert V.final_fut.cancelled()

    async def test_it_does_nothing_if_none_of_the_futures_are_done(self, V):
        assert hp.find_and_apply_result(V.final_fut, V.available_futs) is False
        for f in V.available_futs:
            assert not f.done()
        assert not V.final_fut.done()

class TestWaitingForAllFutures:
    async def test_it_does_nothing_if_there_are_no_futures(self):
        await hp.wait_for_all_futures()

    async def test_it_waits_for_all_the_futures_to_be_complete_regardless_of_status(self):
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

class TestWaitingForFirstFuture:
    async def test_it_does_nothing_if_there_are_no_futures(self):
        await hp.wait_for_first_future()

    async def test_it_returns_if_any_of_the_futures_are_already_done(self):
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()

        fut2.set_result(True)
        await hp.wait_for_first_future(fut1, fut2, fut3)
        assert not fut2._callbacks
        assert all(len(f._callbacks) == 1 for f in (fut1, fut3))

    async def test_it_returns_on_the_first_future_to_have_a_result(self):
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

    async def test_it_returns_on_the_first_future_to_have_an_exception(self):
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

    async def test_it_returns_on_the_first_future_to_be_cancelled(self):
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

class TestCancelFuturesAndWait:
    async def test_it_does_nothing_if_there_are_no_futures(self):
        await hp.cancel_futures_and_wait()

    async def test_it_does_nothing_if_all_the_futures_are_already_done(self):
        fut1 = hp.create_future()
        fut2 = hp.create_future()
        fut3 = hp.create_future()

        fut1.set_result(True)
        fut2.set_exception(ValueError("YEAP"))
        fut3.cancel()

        await hp.cancel_futures_and_wait(fut1, fut2, fut3)

    async def test_it_cancels_running_tasks(self):
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

class TestEnsuringAexit:
    async def test_it_ensures_aexit_is_called_on_exception(self):
        error = Exception("NOPE")
        called = []

        class Thing:
            async def __aenter__(s):
                called.append("aenter")
                await s.start()

            async def start(s):
                raise error

            async def __aexit__(s, exc_typ, exc, tb):
                called.append("aexit")
                assert exc is error

        with assertRaises(Exception, "NOPE"):
            async with Thing():
                called.append("inside")

        assert called == ["aenter"]
        called.clear()

        # But with our special context manager

        error = Exception("NOPE")
        called = []

        class Thing:
            async def __aenter__(s):
                called.append("aenter")
                async with hp.ensure_aexit(s):
                    await s.start()

            async def start(self):
                raise error

            async def __aexit__(s, exc_typ, exc, tb):
                called.append("aexit")
                assert exc is error

        with assertRaises(Exception, "NOPE"):
            async with Thing():
                called.append("inside")

        assert called == ["aenter", "aexit"]

    async def test_it_doesnt_call_exit_twice_on_success(self):
        called = []

        class Thing:
            async def __aenter__(s):
                called.append("aenter")
                async with hp.ensure_aexit(s):
                    await s.start()

            async def start(self):
                called.append("start")

            async def __aexit__(s, exc_typ, exc, tb):
                called.append("aexit")
                assert exc is None

        async with Thing():
            called.append("inside")

        assert called == ["aenter", "start", "inside", "aexit"]
