# coding: spec

from photons_transport.target.waiter import FutPair

from photons_app.test_helpers import AsyncTestCase, assertFutCallbacks
from photons_app.errors import PhotonsAppError

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import asyncio
import mock

describe AsyncTestCase, "FutPair":
    async it "takes in parentfut and sets set_final as a done callback":
        parentfut = mock.Mock(name="parentfut")

        set_final_cb = mock.Mock(name="set_final_cb")
        with mock.patch.object(FutPair, "set_final_cb", set_final_cb):
            futpair = FutPair(parentfut)

        set_final_cb.assert_called_once_with()

        self.assertIs(futpair.parentfut, parentfut)

        self.assertEqual(futpair.loop, self.loop)
        self.assertEqual(futpair.ack_time, 0)
        self.assertEqual(futpair.done_callbacks, [])
        self.assertEqual(type(futpair.final), asyncio.Future)
        self.assertEqual(futpair.final.done(), False)

    describe "functionality":
        async before_each:
            self.parentfut = asyncio.Future()

            set_final_cb = mock.Mock(name="set_final_cb")
            with mock.patch.object(FutPair, "set_final_cb", set_final_cb):
                self.futpair = FutPair(self.parentfut)
            set_final_cb.assert_called_once_with()

        describe "adding final cb":
            async it "calls _parent_done_cb if parentfut is already complete":
                self.futpair.parentfut.set_result((asyncio.Future(), asyncio.Future()))

                _parent_done_cb = mock.Mock(name="_parent_done_cb", spec=[])
                with mock.patch.object(self.futpair, "_parent_done_cb", _parent_done_cb):
                    self.futpair.set_final_cb()
                _parent_done_cb.assert_called_once_with(self.futpair.parentfut)
                self.assertEqual(self.futpair.done_callbacks, [self.futpair.set_final])

            async it "adds set_final as a done_callback if parentfut is not complete":
                self.futpair.set_final_cb()
                self.assertEqual(self.futpair.done_callbacks, [self.futpair.set_final])
                assertFutCallbacks(self.futpair.parentfut, self.futpair._parent_done_cb)

        describe "add_done_callback":
            async it "adds _done_cb to parentfut and func to done_callbacks if it's not done yet":
                func = mock.Mock(name="func")
                self.futpair.add_done_callback(func)
                assertFutCallbacks(self.parentfut, self.futpair._parent_done_cb)
                self.assertEqual(self.futpair.done_callbacks, [func])

                # And we only add _done_cb once
                func2 = mock.Mock(name="func2")
                self.futpair.add_done_callback(func2)
                assertFutCallbacks(self.parentfut, self.futpair._parent_done_cb)
                self.assertEqual(self.futpair.done_callbacks, [func, func2])

            async it "calls each cbs only once no matter when they are given":
                called = []

                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()
                self.parentfut.set_result((ack_fut, res_fut))
                def f(fut):
                    called.append((fut.result(), 1))
                func = mock.Mock(name="func", side_effect=f, spec=[])

                self.futpair.add_done_callback(func)
                await asyncio.sleep(0)
                self.assertEqual(called, [])

                # And if res_fut is not done yet
                def f2(fut):
                    called.append((fut.result(), 2))
                func2 = mock.Mock(name="func2", side_effect=f2, spec=[])

                ack_fut.set_result(True)
                self.futpair.add_done_callback(func2)
                await asyncio.sleep(0)
                self.assertEqual(called, [])

                result = mock.Mock(name="result")
                res_fut.set_result(result)

                def f3(fut):
                    called.append((fut.result(), 3))
                func3 = mock.Mock(name="func3", side_effect=f3, spec=[])
                self.futpair.add_done_callback(func3)

                await asyncio.sleep(0)
                self.assertEqual(sorted(called), [(result, 1), (result, 2), (result, 3)])

                def f4(fut):
                    called.append((fut.result(), 4))
                func4 = mock.Mock(name="func4", side_effect=f4, spec=[])
                self.futpair.add_done_callback(func4)

                await asyncio.sleep(0)
                self.assertEqual(sorted(called), [(result, 1), (result, 2), (result, 3), (result, 4)])

        describe "set_final":
            async it "transfers a cancellation to the final future":
                res = asyncio.Future()
                res.cancel()

                self.assertEqual(self.futpair.cancelled(), False)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.cancelled(), True)

            async it "transfers an exception to the final future":
                error = PhotonsAppError("error")
                res = asyncio.Future()
                res.set_exception(error)

                self.assertEqual(self.futpair.done(), False)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.done(), True)
                self.assertIs(self.futpair.exception(), error)

            async it "transefers result to the final future":
                result = mock.Mock(name="result")
                res = asyncio.Future()
                res.set_result(result)

                self.assertEqual(self.futpair.done(), False)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.done(), True)
                self.assertIs(self.futpair.result(), result)

            async it "does nothing if the future is already cancelled":
                self.futpair.final.cancel()

                res = asyncio.Future()
                res.cancel()
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.cancelled(), True)

                error = PhotonsAppError("error")
                res = asyncio.Future()
                res.set_exception(error)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.cancelled(), True)

                result = mock.Mock(name="result")
                res = asyncio.Future()
                res.set_result(result)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.cancelled(), True)

            async it "does nothing if the future already has a result":
                result = mock.Mock(name="result")
                self.futpair.final.set_result(result)

                res = asyncio.Future()
                res.cancel()
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.result(), result)

                error = PhotonsAppError("error")
                res = asyncio.Future()
                res.set_exception(error)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.result(), result)

                result2 = mock.Mock(name="result2")
                res = asyncio.Future()
                res.set_result(result2)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.result(), result)

            async it "does nothing if the future already has an exception":
                error = PhotonsAppError("error")
                self.futpair.final.set_exception(error)

                res = asyncio.Future()
                res.cancel()
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.exception(), error)

                error2 = PhotonsAppError("error2")
                res = asyncio.Future()
                res.set_exception(error2)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.exception(), error)

                result = mock.Mock(name="result")
                res = asyncio.Future()
                res.set_result(result)
                self.futpair.set_final(res)
                self.assertEqual(self.futpair.exception(), error)

        describe "remove_done_callback":
            async it "removes from done_callbacks":
                func = mock.Mock(name="func", spec=[])
                func2 = mock.Mock(name="func2", spec=[])
                self.futpair.done_callbacks.append(func)
                self.futpair.done_callbacks.append(func2)

                self.futpair.remove_done_callback(func)
                self.assertEqual(self.futpair.done_callbacks, [func2])

            async it "doesn't complain when it tries to remove from res_fut if it doesn't have it set":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                func = mock.Mock(name="func", spec=[])

                self.futpair.parentfut.set_result((ack_fut, res_fut))
                self.futpair.remove_done_callback(func)
                assert True, "it didn't complain!"

            async it "removes callback from the res_fut":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                func = mock.Mock(name="func", spec=[])
                res_fut.add_done_callback(func)
                assertFutCallbacks(res_fut, func)

                self.futpair.parentfut.set_result((ack_fut, res_fut))
                self.futpair.remove_done_callback(func)
                assertFutCallbacks(res_fut)

        describe "_parent_done_cb":
            async it "adds _done_ack to the ack_fut":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()
                res = asyncio.Future()
                res.set_result((ack_fut, res_fut))

                assertFutCallbacks(ack_fut)
                self.futpair._parent_done_cb(res)
                assertFutCallbacks(ack_fut, self.futpair._done_ack)

                # And doesn't duplicate itself
                self.futpair._parent_done_cb(res)
                assertFutCallbacks(ack_fut, self.futpair._done_ack)

            async it "cancels the futpair if parentfut was cancelled":
                res = asyncio.Future()
                res.cancel()
                self.futpair._parent_done_cb(res)
                self.assertEqual(self.futpair.cancelled(), True)

            async it "gives the exception to the futpair if it had an exception":
                error = PhotonsAppError("error")
                res = asyncio.Future()
                res.set_exception(error)

                self.futpair._parent_done_cb(res)
                self.assertEqual(self.futpair.exception(), error)

            async it "does not pass on the exception if futpair is already done":
                error = PhotonsAppError("error")
                res = asyncio.Future()
                res.set_exception(error)

                data = mock.Mock(name="data")
                self.futpair.set_result(data)
                self.futpair._parent_done_cb(res)
                self.assertEqual(self.futpair.result(), data)

        describe "_done_ack":
            async it "cancels the future if the ack was cancelled":
                ack_fut = asyncio.Future()
                ack_fut.cancel()
                self.futpair._done_ack(ack_fut)
                self.assertEqual(self.futpair.cancelled(), True)

            async it "passes on the exception if there was one":
                error = PhotonsAppError("error")
                ack_fut = asyncio.Future()
                ack_fut.set_exception(error)
                self.futpair._done_ack(ack_fut)
                self.assertEqual(self.futpair.exception(), error)

            async it "sets ack_time if the result is not False":
                ack_fut = asyncio.Future()
                ack_fut.set_result(True)
                self.assertEqual(self.futpair.ack_time, 0)

                t = mock.Mock(name="time")
                time = mock.Mock(name="time", return_value=t)

                with mock.patch("time.time", time):
                    self.futpair._done_ack(ack_fut)

                self.assertIs(self.futpair.ack_time, t)

            async it "doesn't set ack_time if the result is False":
                ack_fut = asyncio.Future()
                ack_fut.set_result(False)
                self.assertEqual(self.futpair.ack_time, 0)
                self.futpair._done_ack(ack_fut)
                self.assertIs(self.futpair.ack_time, 0)

            async it "adds callbacks to the res_fut and empties done_callbacks in the process":
                ack_fut = asyncio.Future()
                ack_fut.set_result(False)

                res_fut = asyncio.Future()

                f1 = mock.Mock(name="f1")
                f2 = mock.Mock(name="f2")

                self.futpair.parentfut.set_result((ack_fut, res_fut))
                self.futpair.done_callbacks.extend([f1, f2])

                self.futpair._done_ack(ack_fut)
                assertFutCallbacks(res_fut, f1, f2)
                self.assertEqual(self.futpair.done_callbacks, [])

        describe "cancel":
            async it "cancels parentfut and final":
                self.futpair.cancel()
                self.assertEqual(self.futpair.parentfut.cancelled(), True)
                self.assertEqual(self.futpair.final.cancelled(), True)

        describe "cancelled":
            async it "says yes if parentfut is cancelled":
                self.assertIs(self.futpair.cancelled(), False)
                self.futpair.parentfut.cancel()
                self.assertIs(self.futpair.cancelled(), True)

            async it "says no if parentfut is cancelled but final is done and not cancelled":
                self.futpair.final.set_result(True)
                self.futpair.parentfut.cancel()
                self.assertIs(self.futpair.cancelled(), False)

            async it "says yes if ack_fut is cancelled":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                ack_fut.cancel()
                self.futpair.parentfut.set_result((ack_fut, res_fut))
                self.assertIs(self.futpair.cancelled(), True)

            async it "says yes if res_fut is cancelled":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                res_fut.cancel()
                self.futpair.parentfut.set_result((ack_fut, res_fut))
                self.assertIs(self.futpair.cancelled(), True)

            async it "says yes if ack_fut and res_fut are cancelled":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                ack_fut.cancel()
                res_fut.cancel()
                self.futpair.parentfut.set_result((ack_fut, res_fut))
                self.assertIs(self.futpair.cancelled(), True)

            async it "says yes if final is cancelled":
                self.futpair.final.cancel()
                self.assertIs(self.futpair.cancelled(), True)

        describe "done":
            async it "says yes if final is cancelled":
                self.futpair.final.cancel()
                self.assertIs(self.futpair.done(), True)

            async it "says yes if final is done":
                self.futpair.final.set_result(True)
                self.assertIs(self.futpair.done(), True)

        describe "partial":
            async it "returns ack_time":
                ack_time = mock.Mock(name="ack_time")
                self.futpair.ack_time = ack_time
                self.assertIs(self.futpair.partial(), ack_time)

        describe "exception":
            async it "returns the exception on final":
                error = PhotonsAppError("error")
                self.futpair.final.set_exception(error)
                self.assertIs(self.futpair.exception(), error)

        describe "set_exception":
            async it "sets it on parentfut and final":
                error = PhotonsAppError("error")
                self.futpair.set_exception(error)
                self.assertEqual(self.futpair.parentfut.exception(), error)
                self.assertEqual(self.futpair.final.exception(), error)

            async it "sets it on ack_fut and res_fut":
                error = PhotonsAppError("error")
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()
                self.futpair.parentfut.set_result((ack_fut, res_fut))
                self.futpair.set_exception(error)

                self.assertEqual(ack_fut.exception(), error)
                self.assertEqual(res_fut.exception(), error)
                self.assertEqual(self.futpair.final.exception(), error)

        describe "set_result":
            async it "cancels parentfut and sets result on final":
                data = mock.Mock(name="data")
                self.futpair.set_result(data)
                self.assertIs(self.futpair.parentfut.cancelled(), True)
                self.assertIs(self.futpair.final.result(), data)

                # Make sure the futpair isn't considered cancelled
                self.assertIs(self.futpair.cancelled(), False)

            async it "cancels ack_fut and res_fut":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()
                self.futpair.parentfut.set_result((ack_fut, res_fut))

                data = mock.Mock(name="data")
                self.futpair.set_result(data)

                self.assertIs(ack_fut.cancelled(), True)
                self.assertIs(res_fut.cancelled(), True)
                self.assertIs(self.futpair.final.result(), data)

                # Make sure the futpair isn't considered cancelled
                self.assertIs(self.futpair.cancelled(), False)

        describe "result":
            async it "returns result from final":
                data = mock.Mock(name="data")
                self.futpair.set_result(data)
                self.assertIs(self.futpair.result(), data)

        describe "repr":
            async it "uses the parentfut if it's not done":
                r = repr(self.futpair)
                self.assertEqual(r, "<FutPair <Future pending>>")

            async it "uses the parentfut if it's cancelled":
                self.futpair.parentfut.cancel()
                r = repr(self.futpair)
                self.assertEqual(r, "<FutPair <Future cancelled>>")

            async it "uses the ack_fut and res_fut if parentfut is done":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()
                self.futpair.parentfut.set_result((ack_fut, res_fut))
                r = repr(self.futpair)
                self.assertEqual(r, "<FutPair <Future pending> |:| <Future pending>>")

        describe "await":
            async before_each:
                # The original before_each means this isn't called
                self.futpair.set_final_cb()

                self.final_called = []
                def cb(f):
                    self.final_called.append(f)
                self.cb = cb

            async it "is complete when the res_fut is set":
                self.futpair.add_done_callback(self.cb)

                order = []
                async def doer():
                    order.append(1)
                    d = await self.futpair
                    order.append("final")
                    return d

                task = self.loop.create_task(doer())
                await asyncio.sleep(0)

                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()
                self.futpair.parentfut.set_result((ack_fut, res_fut))
                await asyncio.sleep(0)
                order.append(2)

                ack_fut.set_result(False)
                await asyncio.sleep(0)
                order.append(3)

                data = mock.Mock(name="data")
                res_fut.set_result(data)
                order.append(4)
                await asyncio.sleep(0)
                order.append(5)

                self.assertIs(await self.wait_for(task), data)
                self.assertEqual(order, [1, 2, 3, 4, 5, "final"])
                self.assertEqual(self.final_called, [res_fut])

            async it "is cancelled if parentfut is cancelled":
                self.futpair.add_done_callback(self.cb)

                order = []
                async def doer():
                    order.append(1)
                    await self.futpair

                task = self.loop.create_task(doer())
                await asyncio.sleep(0)

                self.futpair.parentfut.cancel()
                await asyncio.sleep(0)
                order.append(2)

                with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                    await task

                self.assertEqual(order, [1, 2])
                self.assertEqual(self.final_called, [self.futpair.parentfut])

            async it "is cancelled if parentfut is already cancelled":
                parentfut = asyncio.Future()
                parentfut.cancel()
                futpair = FutPair(parentfut)
                futpair.add_done_callback(self.cb)

                with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                    await self.wait_for(futpair)
                self.assertEqual(self.final_called, [parentfut])

            async it "is cancelled if ack_fut is cancelled":
                self.futpair.add_done_callback(self.cb)

                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                async def doer():
                    await self.futpair

                task = asyncio.ensure_future(self.loop.create_task(doer()))
                await asyncio.sleep(0)

                self.futpair.parentfut.set_result((ack_fut, res_fut))
                await asyncio.sleep(0)
                assert not task.done()

                ack_fut.cancel()
                await asyncio.sleep(0)

                with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                    await self.wait_for(task)
                self.assertEqual(self.final_called, [res_fut])

            async it "is cancelled if res_fut is cancelled if ack_fut is done":
                self.futpair.add_done_callback(self.cb)

                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                async def doer():
                    await self.futpair

                task = asyncio.ensure_future(self.loop.create_task(doer()))
                await asyncio.sleep(0)

                self.futpair.parentfut.set_result((ack_fut, res_fut))
                await asyncio.sleep(0)
                assert not task.done()

                res_fut.cancel()
                await asyncio.sleep(0)
                assert not task.done()

                ack_fut.set_result(True)
                await asyncio.sleep(0)

                with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                    await self.wait_for(task)
                self.assertEqual(self.final_called, [res_fut])

            async it "is cancelled if res_fut is already cancelled":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                ack_fut.set_result(True)
                res_fut.cancel()

                parentfut = asyncio.Future()
                parentfut.set_result((ack_fut, res_fut))

                futpair = FutPair(parentfut)
                futpair.add_done_callback(self.cb)
                with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                    await self.wait_for(futpair)
                self.assertEqual(self.final_called, [res_fut])

            async it "gets exception if parentfut gets an exception":
                self.futpair.add_done_callback(self.cb)

                error = PhotonsAppError("error")

                async def doer():
                    await self.futpair

                task = asyncio.ensure_future(self.loop.create_task(doer()))
                await asyncio.sleep(0)

                self.futpair.parentfut.set_exception(error)
                with self.fuzzyAssertRaisesError(PhotonsAppError, "error"):
                    await self.wait_for(task)
                self.assertEqual(self.final_called, [self.futpair.parentfut])

            async it "gets exception if parentfut already has exception":
                parentfut = asyncio.Future()
                error = PhotonsAppError("error")
                parentfut.set_exception(error)

                futpair = FutPair(parentfut)
                futpair.add_done_callback(self.cb)
                with self.fuzzyAssertRaisesError(PhotonsAppError, "error"):
                    await self.wait_for(futpair)
                self.assertEqual(self.final_called, [parentfut])

            async it "gets exception if ack_fut gets an exception":
                self.futpair.add_done_callback(self.cb)

                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                error = PhotonsAppError("error")

                async def doer():
                    await self.futpair

                task = asyncio.ensure_future(self.loop.create_task(doer()))
                await asyncio.sleep(0)

                self.futpair.parentfut.set_result((ack_fut, res_fut))
                await asyncio.sleep(0)
                assert not task.done()

                ack_fut.set_exception(error)
                with self.fuzzyAssertRaisesError(PhotonsAppError, "error"):
                    await self.wait_for(task)
                self.assertEqual(self.final_called, [res_fut])

            async it "gets exception if ack_fut already has an exception":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                error = PhotonsAppError("error")
                ack_fut.set_exception(error)

                parentfut = asyncio.Future()
                parentfut.set_result((ack_fut, res_fut))

                futpair = FutPair(parentfut)
                futpair.add_done_callback(self.cb)
                with self.fuzzyAssertRaisesError(PhotonsAppError, "error"):
                    await self.wait_for(futpair)
                self.assertEqual(self.final_called, [res_fut])

            async it "gets exception if res_fut gets an exception":
                self.futpair.add_done_callback(self.cb)

                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                error = PhotonsAppError("error")

                async def doer():
                    await self.futpair

                task = asyncio.ensure_future(self.loop.create_task(doer()))
                await asyncio.sleep(0)

                self.futpair.parentfut.set_result((ack_fut, res_fut))
                await asyncio.sleep(0)
                assert not task.done()

                ack_fut.set_result(False)
                await asyncio.sleep(0)
                assert not task.done()

                res_fut.set_exception(error)
                with self.fuzzyAssertRaisesError(PhotonsAppError, "error"):
                    await self.wait_for(task)
                self.assertEqual(self.final_called, [res_fut])

            async it "gets exception if res_fut already has an exception":
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                error = PhotonsAppError("error")
                ack_fut.set_result(True)
                res_fut.set_exception(error)

                parentfut = asyncio.Future()
                parentfut.set_result((ack_fut, res_fut))

                futpair = FutPair(parentfut)
                futpair.add_done_callback(self.cb)
                with self.fuzzyAssertRaisesError(PhotonsAppError, "error"):
                    await self.wait_for(futpair)
                self.assertEqual(self.final_called, [res_fut])
