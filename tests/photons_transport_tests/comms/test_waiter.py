# coding: spec

from photons_transport.comms.waiter import Waiter
from photons_transport.comms.result import Result
from photons_transport import RetryOptions

from photons_app.test_helpers import AsyncTestCase, assertFutCallbacks
from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from unittest import mock
import asynctest
import asyncio
import time

describe AsyncTestCase, "Waiter":
    async it "takes in several things":
        stop_fut = asyncio.Future()
        writer = mock.Mock(name="writer")
        retry_options = mock.Mock(name="retry_options")

        waiter = Waiter(stop_fut, writer, retry_options)

        self.assertIs(waiter.writer, writer)
        self.assertIs(waiter.retry_options, retry_options)

        self.assertIs(waiter.final_future.done(), False)
        stop_fut.cancel()
        self.assertIs(waiter.final_future.cancelled(), True)

        self.assertEqual(waiter.results, [])

    describe "Usage":
        async before_each:
            self.stop_fut = asyncio.Future()
            self.writer = asynctest.mock.CoroutineMock(name="writer")
            self.retry_options = RetryOptions()
            self.waiter = Waiter(self.stop_fut, self.writer, self.retry_options)

        async after_each:
            self.stop_fut.cancel()

        async it "can delete _writings_cb even if it hasn't been created yet":
            del self.waiter._writings_cb

        async it "can delete _writings_cb":
            assert not hasattr(self.waiter, "__writings_cb")
            cb = self.waiter._writings_cb
            assert cb is not None
            self.assertEqual(getattr(self.waiter, "__writings_cb", None), cb)
            self.assertEqual(self.waiter._writings_cb, cb)
            del self.waiter._writings_cb
            assert not hasattr(self.waiter, "__writings_cb")

        async it "is cancelled if the stop fut gets a result":
            self.stop_fut.set_result(None)
            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                await self.waiter

        describe "without so many mocks":
            async it "one writings":
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                result = Result(request, False, self.retry_options)

                async def writer():
                    return result

                self.writer.side_effect = writer

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", 2):
                        res = await self.waiter
                    return res, time.time() - start

                t = self.loop.create_task(doit())
                await asyncio.sleep(0.01)
                results = mock.Mock(name="results")
                result.set_result(results)

                r, took = await self.wait_for(t)
                self.assertLess(took, 0.1)
                self.assertIs(r, results)
                self.writer.assert_called_once_with()

            async it "propagates error from failed writer":
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                result = Result(request, False, self.retry_options)

                async def writer():
                    raise ValueError("Nope")

                self.writer.side_effect = writer

                async def doit():
                    with self.fuzzyAssertRaisesError(ValueError, "Nope"):
                        await self.waiter

                await self.wait_for(doit())

            async it "propagates cancellation from cancelled writer":
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                result = Result(request, False, self.retry_options)

                async def writer():
                    fut = asyncio.Future()
                    fut.cancel()
                    await fut

                self.writer.side_effect = writer

                async def doit():
                    with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                        await self.waiter

                await self.wait_for(doit())

            async it "only one writings if no_retry is True":
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                result1 = Result(request, False, self.retry_options)

                futs = [result1]

                async def writer():
                    return futs.pop(0)

                self.writer.side_effect = writer

                times = [0.05, 2]

                def next_time(s):
                    return times.pop(0)

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", property(next_time)):
                        self.waiter.no_retry = True
                        res = await self.waiter
                    return res, time.time() - start

                t = self.loop.create_task(doit())
                await asyncio.sleep(0.005)
                self.assertEqual(self.writer.mock_calls, [mock.call()])
                await asyncio.sleep(0.06)
                self.assertEqual(self.writer.mock_calls, [mock.call()])

                res = mock.Mock(name="res")
                result1.set_result(res)

                r, took = await self.wait_for(t)
                self.assertLess(took, 0.1)
                self.assertIs(r, res)
                self.assertEqual(self.writer.mock_calls, [mock.call()])

                self.assertEqual(await self.wait_for(result1), res)

            async it "two writings":
                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None

                result1 = Result(request, False, self.retry_options)
                result2 = Result(request, False, self.retry_options)

                futs = [result1, result2]

                async def writer():
                    return futs.pop(0)

                self.writer.side_effect = writer

                times = [0.05, 2]

                def next_time(s):
                    return times.pop(0)

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", property(next_time)):
                        res = await self.waiter
                    return res, time.time() - start

                t = self.loop.create_task(doit())
                await asyncio.sleep(0.005)
                self.assertEqual(self.writer.mock_calls, [mock.call()])
                await asyncio.sleep(0.06)
                self.assertEqual(self.writer.mock_calls, [mock.call(), mock.call()])

                res = mock.Mock(name="res")
                result2.set_result(res)

                r, took = await self.wait_for(t)
                self.assertLess(took, 0.1)
                self.assertIs(r, res)
                self.assertEqual(self.writer.mock_calls, [mock.call(), mock.call()])

                self.assertEqual(await self.wait_for(result1), res)

            async it "one writings with partial write":
                request = mock.Mock(name="request", ack_required=True, res_required=True)
                request.Meta.multi = None

                result = Result(request, False, self.retry_options)
                futs = [result]

                async def writer():
                    return futs.pop(0)

                self.writer.side_effect = writer

                times = [0.05, 2]

                def next_time(s):
                    return times.pop(0)

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", property(next_time)):
                        res = await self.waiter
                    return res, time.time() - start

                t = self.loop.create_task(doit())
                await asyncio.sleep(0.005)
                self.assertEqual(self.writer.mock_calls, [mock.call()])
                result.add_ack()
                await asyncio.sleep(0.08)
                self.assertEqual(self.writer.mock_calls, [mock.call()])

                res = mock.Mock(name="res")
                result.set_result(res)

                r, took = await self.wait_for(t)
                self.assertLess(took, 0.15)
                self.assertIs(r, res)
                self.assertEqual(self.writer.mock_calls, [mock.call()])

            async it "two writings with partial write for first writing":
                request = mock.Mock(name="request", ack_required=True, res_required=True)
                request.Meta.multi = None

                self.retry_options.gap_between_ack_and_res = 0.06
                self.retry_options.next_check_after_wait_for_result = 0.04

                result1 = Result(request, False, self.retry_options)
                result2 = Result(request, False, self.retry_options)

                futs = [result1, result2]

                async def writer():
                    return futs.pop(0)

                self.writer.side_effect = writer

                times = [0.05, 0.05]

                def next_time(s):
                    return times.pop(0)

                async def doit():
                    start = time.time()
                    with mock.patch.object(RetryOptions, "next_time", property(next_time)):
                        res = await self.waiter
                    return res, time.time() - start

                t = self.loop.create_task(doit())
                await asyncio.sleep(0.005)
                self.assertEqual(self.writer.mock_calls, [mock.call()])
                result1.add_ack()
                await asyncio.sleep(0.08)
                self.assertEqual(self.writer.mock_calls, [mock.call()])
                await asyncio.sleep(0.05)
                self.assertEqual(self.writer.mock_calls, [mock.call(), mock.call()])

                res = mock.Mock(name="res")
                result2.set_result(res)

                r, took = await self.wait_for(t)
                self.assertLess(took, 0.2)
                self.assertIs(r, res)
                self.assertEqual(self.writer.mock_calls, [mock.call(), mock.call()])

                self.assertEqual(await self.wait_for(result1), res)

        describe "future":
            async it "cancel the final future on cancel":
                assert not self.waiter.final_future.done()
                assert not self.waiter.final_future.cancelled()
                self.waiter.cancel()
                assert self.waiter.final_future.done()
                assert self.waiter.final_future.cancelled()

                # and sanity check the stop_fut hasn't also been cancelled
                assert not self.stop_fut.cancelled()

            async it "is cancelled when final future is cancelled":
                assert not self.waiter.done()
                assert not self.waiter.cancelled()
                self.waiter.final_future.cancel()
                assert self.waiter.cancelled()
                assert self.waiter.done()

            async it "is cancelled if stop_fut is cancelled":
                assert not self.waiter.done()
                assert not self.waiter.cancelled()
                self.stop_fut.cancel()
                assert self.waiter.cancelled()
                assert self.waiter.done()

            async it "can get result from final future":
                result = mock.Mock(name="result")
                self.waiter.final_future.set_result(result)
                self.assertIs(self.waiter.result(), result)
                assert self.waiter.done()

            async it "can get exception from the final future":
                error = PhotonsAppError("error")
                self.waiter.final_future.set_exception(error)
                self.assertIs(self.waiter.exception(), error)
                assert self.waiter.done()

        describe "await":
            async it "starts a writings":
                called = []

                def w():
                    called.append(1)

                writings = asynctest.mock.CoroutineMock(name="writings", side_effect=w)
                self.waiter.writings = writings

                async def doit():
                    return await self.waiter

                t = self.loop.create_task(doit())
                await asyncio.sleep(0)
                self.assertEqual(called, [1])
                res = mock.Mock(name="res")
                self.waiter.final_future.set_result(res)
                self.assertIs(await t, res)

                self.assertEqual(called, [1])
                self.waiter._writings_cb()
                await asyncio.sleep(0)
                self.assertEqual(called, [1, 1])

                # Awaiting again doesn't call writings
                self.assertIs(await t, res)
                self.assertEqual(called, [1, 1])

        describe "writings":
            async it "does nothing if final_future is done":
                self.waiter.final_future.set_result(True)

                # This will complain if it tries to call_later the writings_cb
                # Cause it doesn't exist yet
                assert await self.wait_for(self.waiter.writings()) is None

            async it "tries to apply a result from the results and quits if successful":
                res = mock.Mock(name="res")
                results = mock.Mock(name="results")

                def faar(ff, fs):
                    assert fs is results
                    ff.set_result(res)

                find_and_apply_result = mock.Mock(name="find_and_apply_result", side_effect=faar)

                self.waiter.results = results
                with mock.patch(
                    "photons_transport.comms.waiter.hp.find_and_apply_result", find_and_apply_result
                ):
                    await self.waiter.writings()

                self.assertIs(self.waiter.result(), res)

            async it "cancels all the results if the final future gets cancelled":
                results = [asyncio.Future(), asyncio.Future(), asyncio.Future()]

                original_find_and_apply_result = hp.find_and_apply_result

                def faar(ff, fs):
                    self.assertEqual(fs, results)
                    for f in results:
                        assert not f.cancelled()
                    ff.cancel()
                    original_find_and_apply_result(ff, fs)

                find_and_apply_result = mock.Mock(name="find_and_apply_result", side_effect=faar)

                self.waiter.results = results
                with mock.patch(
                    "photons_transport.comms.waiter.hp.find_and_apply_result", find_and_apply_result
                ):
                    await self.waiter.writings()

                assert self.waiter.cancelled()
                for f in results:
                    assert f.cancelled()

            async it "calls the writer if no results yet and schedules for self.retry_options.next_time in future":
                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []

                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                self.waiter._writings_cb = writings_cb

                request = mock.Mock(name="request", ack_required=False, res_required=True)
                request.Meta.multi = None
                result = Result(request, False, self.retry_options)

                fut = asyncio.Future()

                async def write():
                    fut.set_result(True)
                    return result

                self.writer.side_effect = write

                with mock.patch.object(RetryOptions, "next_time", 15):
                    with mock.patch.object(self.loop, "call_later", cl):
                        await self.waiter.writings()

                await self.wait_for(fut)
                self.assertEqual(called, [(15, ())])
                self.assertEqual(self.waiter.results, [result])

            async it "does not call writer if we have a partial result":
                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []

                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                result = asyncio.Future()
                result.wait_for_result = lambda: True

                self.waiter._writings_cb = writings_cb
                self.waiter.results = [result]

                do_write = asynctest.mock.CoroutineMock(
                    name="do_write", side_effect=Exception("Expect no write")
                )

                self.waiter.retry_options.next_check_after_wait_for_result = 9001

                with mock.patch.object(RetryOptions, "next_time", 2):
                    with mock.patch.object(self.loop, "call_later", cl):
                        with mock.patch.object(self.waiter, "do_write", do_write):
                            await self.waiter.writings()

                self.assertEqual(called, [(9001, ())])
                self.assertEqual(self.waiter.results, [result])
                self.assertEqual(do_write.mock_calls, [])

            async it "calls writer if we have results that we shouldn't wait for":
                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []

                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                result = asyncio.Future()
                result.wait_for_result = lambda: False

                self.waiter._writings_cb = writings_cb
                self.waiter.results = [result]

                do_write = asynctest.mock.CoroutineMock(name="do_write")

                with mock.patch.object(RetryOptions, "next_time", 9002):
                    with mock.patch.object(self.loop, "call_later", cl):
                        with mock.patch.object(self.waiter, "do_write", do_write):
                            await self.waiter.writings()

                self.assertEqual(called, [(9002, ())])
                self.assertEqual(self.waiter.results, [result])
                do_write.assert_called_with()

            async it "passes on errors from do_write":
                self.waiter.results = []

                do_write = asynctest.mock.CoroutineMock(
                    name="do_write", side_effect=ValueError("Nope")
                )

                with mock.patch.object(self.waiter, "do_write", do_write):
                    await self.waiter.writings()

                with self.fuzzyAssertRaisesError(ValueError, "Nope"):
                    await self.wait_for(self.waiter)

                do_write.assert_called_with()

            async it "passes on cancellation from do_write":
                self.waiter.results = []

                async def do_write():
                    fut = asyncio.Future()
                    fut.cancel()
                    await fut

                do_write = asynctest.mock.CoroutineMock(name="do_write", side_effect=do_write)

                with mock.patch.object(self.waiter, "do_write", do_write):
                    await self.waiter.writings()

                with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                    await self.wait_for(self.waiter)

                do_write.assert_called_with()

        describe "do_write":
            async it "ensures_conn and adds result from writer to results and schedules writings_cb if result already done":
                called = []

                writings_cb = mock.Mock(name="writings_cb")
                original_call_soon = self.loop.call_soon

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

                writer = asynctest.mock.CoroutineMock(name="writer", side_effect=writer)

                self.waiter.writer = writer
                self.waiter._writings_cb = writings_cb

                with mock.patch.object(self.loop, "call_soon", cs):
                    await self.wait_for(self.waiter.do_write())

                self.assertEqual(self.waiter.results, [result])
                self.assertEqual(called, ["writer", ("call_soon", ())])

            async it "calls _writings_cb when result is done if result isn't already done":
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

                writer = asynctest.mock.CoroutineMock(name="writer", side_effect=writer)

                self.waiter.writer = writer
                self.waiter._writings_cb = writings_cb

                await self.wait_for(self.waiter.do_write())

                self.assertEqual(self.waiter.results, [result])
                self.assertEqual(called, ["writer"])
                assertFutCallbacks(result, writings_cb)

                result.set_result([])
                await self.wait_for(fut)
                self.assertEqual(called, ["writer", "writings_cb"])
