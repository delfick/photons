# coding: spec

from photons_transport.comms.waiter import Waiter
from photons_transport.comms.result import Result
from photons_transport import RetryOptions

from photons_app.test_helpers import assertFutCallbacks
from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import asyncio
import pytest
import time

describe "Waiter":
    async it "takes in several things":
        stop_fut = asyncio.Future()
        writer = mock.Mock(name="writer")
        retry_options = mock.Mock(name="retry_options")

        waiter = Waiter(stop_fut, writer, retry_options)

        assert waiter.writer is writer
        assert waiter.retry_options is retry_options

        assert waiter.final_future.done() is False
        stop_fut.cancel()
        assert waiter.final_future.cancelled() is True

        assert waiter.results == []
        await waiter.finish()

    describe "Usage":

        @pytest.fixture()
        async def V(self):
            class V:
                stop_fut = asyncio.Future()
                writer = pytest.helpers.AsyncMock(name="writer")
                retry_options = RetryOptions()

                async def __aenter__(s):
                    s.waiter = Waiter(s.stop_fut, s.writer, s.retry_options)
                    return s

                async def __aexit__(s, exc_type, exc, tb):
                    if hasattr(s, "waiter"):
                        await s.waiter.finish()

                @hp.memoized_property
                def loop(s):
                    return asyncio.get_event_loop()

            async with V() as v:
                yield v

        @pytest.fixture(autouse=True)
        async def cleanup(self, V):
            try:
                yield
            finally:
                V.stop_fut.cancel()
                await V.waiter.finish()

        async it "can delete _writings_cb even if it hasn't been created yet", V:
            del V.waiter._writings_cb

        async it "can delete _writings_cb", V:
            assert not hasattr(V.waiter, "__writings_cb")
            cb = V.waiter._writings_cb
            assert cb is not None
            assert getattr(V.waiter, "__writings_cb", None) == cb
            assert V.waiter._writings_cb == cb
            del V.waiter._writings_cb
            assert not hasattr(V.waiter, "__writings_cb")

        async it "is cancelled if the stop fut gets a result", V:
            V.stop_fut.set_result(None)
            with assertRaises(asyncio.CancelledError):
                await V.waiter

        describe "without so many mocks":
            async it "one writings", V:
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                result = Result(request, False, V.retry_options)

                async def writer():
                    return result

                V.writer.side_effect = writer

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", 2):
                        res = await V.waiter
                    return res, time.time() - start

                t = V.loop.create_task(doit())
                await asyncio.sleep(0.01)
                results = mock.Mock(name="results")
                result.set_result(results)

                r, took = await t
                assert took < 0.1
                assert r is results
                V.writer.assert_called_once_with()

            async it "propagates error from failed writer", V:
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                async def writer():
                    raise ValueError("Nope")

                V.writer.side_effect = writer

                with assertRaises(ValueError, "Nope"):
                    await V.waiter

            async it "propagates cancellation from cancelled writer", V:
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                async def writer():
                    fut = asyncio.Future()
                    fut.cancel()
                    await fut

                V.writer.side_effect = writer

                with assertRaises(asyncio.CancelledError):
                    await V.waiter

            async it "only one writings if no_retry is True", V:
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                result1 = Result(request, False, V.retry_options)

                futs = [result1]

                async def writer():
                    return futs.pop(0)

                V.writer.side_effect = writer

                times = [0.05, 2]

                def next_time(s):
                    return times.pop(0)

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", property(next_time)):
                        V.waiter.no_retry = True
                        res = await V.waiter
                    return res, time.time() - start

                t = V.loop.create_task(doit())
                await asyncio.sleep(0.005)
                assert V.writer.mock_calls == [mock.call()]
                await asyncio.sleep(0.06)
                assert V.writer.mock_calls == [mock.call()]

                res = mock.Mock(name="res")
                result1.set_result(res)

                r, took = await t
                assert took < 0.1
                assert r is res
                assert V.writer.mock_calls == [mock.call()]

                assert (await result1) == res

            async it "two writings", V:
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                result1 = Result(request, False, V.retry_options)
                result2 = Result(request, False, V.retry_options)

                futs = [result1, result2]

                async def writer():
                    return futs.pop(0)

                V.writer.side_effect = writer

                times = [0.05, 2]

                def next_time(s):
                    return times.pop(0)

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", property(next_time)):
                        res = await V.waiter
                    return res, time.time() - start

                t = V.loop.create_task(doit())
                await asyncio.sleep(0.005)
                assert V.writer.mock_calls == [mock.call()]
                await asyncio.sleep(0.06)
                assert V.writer.mock_calls == [mock.call(), mock.call()]

                res = mock.Mock(name="res")
                result2.set_result(res)

                r, took = await t
                assert took < 0.1
                assert r is res
                assert V.writer.mock_calls == [mock.call(), mock.call()]

                assert (await result1) == res

            async it "one writings with partial write", V:
                request = mock.Mock(name="request", ack_required=True, res_required=True)
                request.Meta.multi = None

                result = Result(request, False, V.retry_options)
                futs = [result]

                async def writer():
                    return futs.pop(0)

                V.writer.side_effect = writer

                times = [0.05, 2]

                def next_time(s):
                    return times.pop(0)

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", property(next_time)):
                        res = await V.waiter
                    return res, time.time() - start

                t = V.loop.create_task(doit())
                await asyncio.sleep(0.005)
                assert V.writer.mock_calls == [mock.call()]
                result.add_ack()
                await asyncio.sleep(0.08)
                assert V.writer.mock_calls == [mock.call()]

                res = mock.Mock(name="res")
                result.set_result(res)

                r, took = await t
                assert took < 0.15
                assert r is res
                assert V.writer.mock_calls == [mock.call()]

            async it "two writings with partial write for first writing", V:
                request = mock.Mock(name="request", ack_required=True, res_required=True)
                request.Meta.multi = None

                V.retry_options.gap_between_ack_and_res = 0.06
                V.retry_options.next_check_after_wait_for_result = 0.04

                result1 = Result(request, False, V.retry_options)
                result2 = Result(request, False, V.retry_options)

                futs = [result1, result2]

                async def writer():
                    return futs.pop(0)

                V.writer.side_effect = writer

                times = [0.05, 0.05]

                def next_time(s):
                    return times.pop(0)

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", property(next_time)):
                        res = await V.waiter
                    return res, time.time() - start

                t = V.loop.create_task(doit())
                await asyncio.sleep(0.005)
                assert V.writer.mock_calls == [mock.call()]
                result1.add_ack()
                await asyncio.sleep(0.08)
                assert V.writer.mock_calls == [mock.call()]
                await asyncio.sleep(0.05)
                assert V.writer.mock_calls == [mock.call(), mock.call()]

                res = mock.Mock(name="res")
                result2.set_result(res)

                r, took = await t
                assert took < 0.2
                assert r is res
                assert V.writer.mock_calls == [mock.call(), mock.call()]

                assert (await result1) == res

        describe "future":
            async it "cancel the final future on cancel", V:
                assert not V.waiter.final_future.done()
                assert not V.waiter.final_future.cancelled()
                V.waiter.cancel()
                assert V.waiter.final_future.done()
                assert V.waiter.final_future.cancelled()

                # and sanity check the stop_fut hasn't also been cancelled
                assert not V.stop_fut.cancelled()

            async it "is cancelled when final future is cancelled", V:
                assert not V.waiter.done()
                assert not V.waiter.cancelled()
                V.waiter.final_future.cancel()
                assert V.waiter.cancelled()
                assert V.waiter.done()

            async it "is cancelled if stop_fut is cancelled", V:
                assert not V.waiter.done()
                assert not V.waiter.cancelled()
                V.stop_fut.cancel()
                assert V.waiter.cancelled()
                assert V.waiter.done()

            async it "can get result from final future", V:
                result = mock.Mock(name="result")
                V.waiter.final_future.set_result(result)
                assert V.waiter.result() is result
                assert V.waiter.done()

            async it "can get exception from the final future", V:
                error = PhotonsAppError("error")
                V.waiter.final_future.set_exception(error)
                assert V.waiter.exception() is error
                assert V.waiter.done()

        describe "await":
            async it "starts a writings", V:
                called = []

                called_fut = hp.ResettableFuture()

                def w():
                    called.append(1)
                    called_fut.set_result(True)

                writings = pytest.helpers.AsyncMock(name="writings", side_effect=w)
                V.waiter.writings = writings

                async def doit():
                    return await V.waiter

                t = V.loop.create_task(doit())
                await called_fut
                called_fut.reset()
                assert called == [1]
                res = mock.Mock(name="res")
                V.waiter.final_future.set_result(res)
                assert await t is res

                assert called == [1]
                V.waiter._writings_cb()
                await called_fut
                assert called == [1, 1]

                # Awaiting again doesn't call writings
                assert await t is res
                assert called == [1, 1]

        describe "writings":
            async it "does nothing if final_future is done", V:
                V.waiter.final_future.set_result(True)

                # This will complain if it tries to call_later the writings_cb
                # Cause it doesn't exist yet
                assert (await V.waiter.writings()) is None

            async it "tries to apply a result from the results and quits if successful", V:
                res = mock.Mock(name="res")
                results = mock.Mock(name="results")

                def faar(ff, fs):
                    assert fs is results
                    ff.set_result(res)

                find_and_apply_result = mock.Mock(name="find_and_apply_result", side_effect=faar)

                V.waiter.results = results
                with mock.patch(
                    "photons_transport.comms.waiter.hp.find_and_apply_result", find_and_apply_result
                ):
                    await V.waiter.writings()

                assert V.waiter.result() is res

            async it "cancels all the results if the final future gets cancelled", V:
                results = [asyncio.Future(), asyncio.Future(), asyncio.Future()]

                original_find_and_apply_result = hp.find_and_apply_result

                def faar(ff, fs):
                    assert fs == results
                    for f in results:
                        assert not f.cancelled()
                    ff.cancel()
                    original_find_and_apply_result(ff, fs)

                find_and_apply_result = mock.Mock(name="find_and_apply_result", side_effect=faar)

                V.waiter.results = results
                with mock.patch(
                    "photons_transport.comms.waiter.hp.find_and_apply_result", find_and_apply_result
                ):
                    await V.waiter.writings()

                assert V.waiter.cancelled()
                for f in results:
                    assert f.cancelled()

            async it "calls the writer if no results yet and schedules for V.retry_options.next_time in future", V:
                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = V.loop.call_later

                called = []

                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                V.waiter._writings_cb = writings_cb

                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None
                result = Result(request, False, V.retry_options)

                fut = asyncio.Future()

                async def write():
                    fut.set_result(True)
                    return result

                V.writer.side_effect = write

                with mock.patch.object(RetryOptions, "next_time", 15):
                    with mock.patch.object(V.loop, "call_later", cl):
                        await V.waiter.writings()

                await fut
                assert called == [(15, ())]
                assert V.waiter.results == [result]

            async it "does not call writer if we have a partial result", V:
                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = V.loop.call_later

                called = []

                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                result = asyncio.Future()
                result.wait_for_result = lambda: True

                V.waiter._writings_cb = writings_cb
                V.waiter.results = [result]

                do_write = pytest.helpers.AsyncMock(
                    name="do_write", side_effect=Exception("Expect no write")
                )

                V.waiter.retry_options.next_check_after_wait_for_result = 9001

                with mock.patch.object(RetryOptions, "next_time", 2):
                    with mock.patch.object(V.loop, "call_later", cl):
                        with mock.patch.object(V.waiter, "do_write", do_write):
                            await V.waiter.writings()

                assert called == [(9001, ())]
                assert V.waiter.results == [result]
                assert do_write.mock_calls == []

            async it "calls writer if we have results that we shouldn't wait for", V:
                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = V.loop.call_later

                called = []

                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                result = asyncio.Future()
                result.wait_for_result = lambda: False

                V.waiter._writings_cb = writings_cb
                V.waiter.results = [result]

                do_write = pytest.helpers.AsyncMock(name="do_write")

                with mock.patch.object(RetryOptions, "next_time", 9002):
                    with mock.patch.object(V.loop, "call_later", cl):
                        with mock.patch.object(V.waiter, "do_write", do_write):
                            await V.waiter.writings()

                assert called == [(9002, ())]
                assert V.waiter.results == [result]
                do_write.assert_called_with()

            async it "passes on errors from do_write", V:
                V.waiter.results = []

                do_write = pytest.helpers.AsyncMock(name="do_write", side_effect=ValueError("Nope"))

                with mock.patch.object(V.waiter, "do_write", do_write):
                    await V.waiter.writings()

                with assertRaises(ValueError, "Nope"):
                    await V.waiter

                do_write.assert_called_with()

            async it "passes on cancellation from do_write", V:
                V.waiter.results = []

                async def do_write():
                    fut = asyncio.Future()
                    fut.cancel()
                    await fut

                do_write = pytest.helpers.AsyncMock(name="do_write", side_effect=do_write)

                with mock.patch.object(V.waiter, "do_write", do_write):
                    await V.waiter.writings()

                with assertRaises(asyncio.CancelledError):
                    await V.waiter

                do_write.assert_called_with()

        describe "do_write":
            async it "ensures_conn and adds result from writer to results and schedules writings_cb if result already done", V:
                called = []

                writings_cb = mock.Mock(name="writings_cb")
                original_call_soon = V.loop.call_soon

                def cs(cb, *args, **kwargs):
                    if cb is writings_cb:
                        called.append(("call_soon", args))
                    else:
                        original_call_soon(cb, *args, **kwargs)

                result = asyncio.Future()
                result.set_result([])

                async def writer():
                    called.append("writer")
                    return result

                writer = pytest.helpers.AsyncMock(name="writer", side_effect=writer)

                V.waiter.writer = writer
                V.waiter._writings_cb = writings_cb

                with mock.patch.object(V.loop, "call_soon", cs):
                    await V.waiter.do_write()

                assert V.waiter.results == [result]
                assert called == ["writer", ("call_soon", ())]

            async it "calls _writings_cb when result is done if result isn't already done", V:
                called = []

                fut = asyncio.Future()

                def writings_cb(*args):
                    called.append("writings_cb")
                    fut.set_result(True)

                writings_cb = mock.Mock(name="writings_cb", side_effect=writings_cb)

                result = asyncio.Future()

                async def writer():
                    called.append("writer")
                    return result

                writer = pytest.helpers.AsyncMock(name="writer", side_effect=writer)

                V.waiter.writer = writer
                V.waiter._writings_cb = writings_cb

                await V.waiter.do_write()

                assert V.waiter.results == [result]
                assert called == ["writer"]
                assertFutCallbacks(result, writings_cb)

                result.set_result([])
                await fut
                assert called == ["writer", "writings_cb"]
