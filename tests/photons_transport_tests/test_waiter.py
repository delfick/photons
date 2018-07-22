# coding: spec

from photons_transport.target.waiter import Waiter

from photons_app.test_helpers import AsyncTestCase
from photons_app.errors import PhotonsAppError

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
import asynctest
import asyncio
import mock
import time

describe AsyncTestCase, "Waiter":
    async it "takes in several things":
        stop_fut = asyncio.Future()
        writer = mock.Mock(name="writer")
        first_resend = mock.Mock(name="first_resend")
        first_wait = mock.Mock(name="first_wait")

        waiter = Waiter(stop_fut, writer
            , first_resend=first_resend, first_wait=first_wait
            )

        self.assertIs(waiter.writer, writer)
        self.assertEqual(waiter.timeouts, [first_wait, first_resend])

        self.assertIs(waiter.final_future.done(), False)
        stop_fut.cancel()
        self.assertIs(waiter.final_future.cancelled(), True)

        self.assertEqual(waiter.futs, [])
        self.assertEqual(waiter.next_time, None)

    describe "Usage":
        async before_each:
            self.stop_fut = asyncio.Future()
            self.writer = asynctest.mock.CoroutineMock(name="writer")
            self.waiter = Waiter(self.stop_fut, self.writer)

            self.ensure_conn = asynctest.mock.CoroutineMock(name="ensure_conn")
            self.writer.ensure_conn = self.ensure_conn

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
                ack_fut = asyncio.Future()
                res_fut = asyncio.Future()

                def writer():
                    self.ensure_conn.assert_called_once_with()
                    return ack_fut, res_fut
                self.writer.side_effect = writer

                dnt = mock.Mock(name="determine_next_time", return_value=time.time() + 2)

                async def doit():
                    start = time.time()
                    with mock.patch.object(self.waiter, "determine_next_time", dnt):
                        res = await self.waiter
                    return res, time.time() - start

                t = self.loop.create_task(doit())
                await asyncio.sleep(0.01)
                self.writer.assert_called_once_with()

                res = mock.Mock(name="res")
                ack_fut.set_result(True)
                res_fut.set_result(res)

                r, took = await self.wait_for(t)
                self.assertLess(took, 0.1)
                self.assertIs(r, res)
                self.writer.assert_called_once_with()

            async it "two writings":
                ack_fut1 = asyncio.Future()
                res_fut1 = asyncio.Future()

                ack_fut2 = asyncio.Future()
                res_fut2 = asyncio.Future()

                futs = [(ack_fut1, res_fut1), (ack_fut2, res_fut2)]

                def writer():
                    self.assertEqual(len(self.ensure_conn.mock_calls), 2 - (len(futs) - 1))
                    return futs.pop(0)
                self.writer.side_effect = writer

                times = [time.time() + 0.05, time.time() + 2]

                def determine_next_time():
                    return times.pop(0)
                dnt = mock.Mock(name="determine_next_time", side_effect=determine_next_time)

                async def doit():
                    start = time.time()
                    with mock.patch.object(self.waiter, "determine_next_time", dnt):
                        res = await self.waiter
                    return res, time.time() - start

                t = self.loop.create_task(doit())
                await asyncio.sleep(0.005)
                self.assertEqual(self.writer.mock_calls, [mock.call()])
                await asyncio.sleep(0.05)
                self.assertEqual(self.writer.mock_calls, [mock.call(), mock.call()])

                res = mock.Mock(name="res")
                ack_fut2.set_result(True)
                res_fut2.set_result(res)

                r, took = await self.wait_for(t)
                self.assertLess(took, 0.1)
                self.assertIs(r, res)
                self.assertEqual(self.writer.mock_calls, [mock.call(), mock.call()])

                assert ack_fut1.done()
                self.assertIs(res_fut2.result(), res)

            async it "one writings with partial write":
                ack_fut1 = asyncio.Future()
                res_fut1 = asyncio.Future()

                futs = [(ack_fut1, res_fut1)]

                def writer():
                    self.ensure_conn.assert_called_once_with()
                    return futs.pop(0)
                self.writer.side_effect = writer

                times = [time.time() + 0.05, time.time() + 2]

                def determine_next_time():
                    return times.pop(0)
                dnt = mock.Mock(name="determine_next_time", side_effect=determine_next_time)

                async def doit():
                    start = time.time()
                    with mock.patch.object(self.waiter, "determine_next_time", dnt):
                        res = await self.waiter
                    return res, time.time() - start

                t = self.loop.create_task(doit())
                await asyncio.sleep(0.005)
                self.assertEqual(self.writer.mock_calls, [mock.call()])
                ack_fut1.set_result(True)
                await asyncio.sleep(0.08)
                self.assertEqual(self.writer.mock_calls, [mock.call()])

                res = mock.Mock(name="res")
                res_fut1.set_result(res)

                r, took = await self.wait_for(t)
                self.assertLess(took, 0.1)
                self.assertIs(r, res)
                self.assertEqual(self.writer.mock_calls, [mock.call()])

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

        describe "determine_next_time":
            async before_each:
                self.current_time = mock.Mock(name="current_time")
                class MagicTime(object):
                    def __add__(s, other):
                        return (self.current_time, other)
                self.time = mock.Mock(name='time', return_value=MagicTime())

            async it "adds first item from timeout to current time if there are more than one in there":
                t1 = mock.Mock(name="t1")
                t2 = mock.Mock(name="t2")
                self.waiter.timeouts = [t1, t2]
                with mock.patch("time.time", self.time):
                    self.assertEqual(self.waiter.determine_next_time(), (self.current_time, t1))
                self.assertEqual(self.waiter.timeouts, [t2])

            async it "progressively adds to the timeout with each call":
                self.waiter.timeouts = [0.05]

                def assertSameNumber(l, wanted):
                    assert len(l) == 1
                    n = "{0:.2f}".format(l[0])
                    w = "{0:.2f}".format(wanted)
                    self.assertEqual(n, w)

                for progression in (0.1, 0.2, 0.3, 0.8, 1.3, 1.8, 2.3, 2.8, 3.3, 3.8, 4.3, 4.8, 5.3, 10.3, 15.3):
                    with mock.patch("time.time", self.time):
                        c, p = self.waiter.determine_next_time()
                        self.assertIs(c, self.current_time)
                        assertSameNumber([p], progression)
                    assertSameNumber(self.waiter.timeouts, progression)

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

            async it "tries to apply a result from the futs and quits if successful":
                res = mock.Mock(name="res")
                futs = mock.Mock(name="futs")
                def faar(ff, fs):
                    assert fs is futs
                    ff.set_result(res)
                find_and_apply_result = mock.Mock(name="find_and_apply_result", side_effect=faar)

                self.waiter.futs = futs
                with mock.patch("photons_transport.target.waiter.hp.find_and_apply_result", find_and_apply_result):
                    await self.waiter.writings()

                self.assertIs(self.waiter.result(), res)

            async it "cancels all the futs if the final future gets cancelled":
                futs = [asyncio.Future(), asyncio.Future(), asyncio.Future()]
                def faar(ff, fs):
                    self.assertEqual(fs, futs)
                    for f in futs:
                        assert not f.cancelled()
                    ff.cancel()
                find_and_apply_result = mock.Mock(name="find_and_apply_result", side_effect=faar)

                self.waiter.futs = futs
                with mock.patch("photons_transport.target.waiter.hp.find_and_apply_result", find_and_apply_result):
                    await self.waiter.writings()

                assert self.waiter.cancelled()
                for f in futs:
                    assert f.cancelled()

            async it "calls again in the future without writing if we're not up to next time yet":
                now = time.time()
                self.waiter.next_time = now + 10

                te = mock.Mock(name="time", return_value=now)

                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []
                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                self.waiter._writings_cb = writings_cb
                self.waiter.futs = []
                with mock.patch("time.time", te):
                    with mock.patch.object(self.loop, "call_later", cl):
                        await self.waiter.writings()

                self.assertEqual(called, [(10, ())])

            async it "calls the writer if no next time and uses determine_next_time":
                now = time.time()
                te = mock.Mock(name="time", return_value=now)

                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []
                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                self.waiter._writings_cb = writings_cb
                self.waiter.futs = []

                nt = now + 15
                determine_next_time = mock.Mock(name="determine_next_time", return_value=nt)

                dwf = mock.Mock(name="do_write_future")
                do_write = mock.Mock(name="do_write", return_value=dwf)

                with mock.patch("time.time", te):
                    with mock.patch.object(self.loop, "call_later", cl):
                        with mock.patch.multiple(self.waiter, determine_next_time=determine_next_time, do_write=do_write):
                            assert self.waiter.next_time is None
                            await self.waiter.writings()

                self.assertEqual(called, [(15, ())])
                self.assertEqual(self.waiter.futs, [dwf])
                self.assertEqual(self.waiter.next_time, nt)
                do_write.assert_called_once_with()

            async it "calls the writer if next time is in the past":
                now = time.time()
                te = mock.Mock(name="time", return_value=now)

                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []
                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                self.waiter._writings_cb = writings_cb
                self.waiter.futs = []

                nt = now + 2
                determine_next_time = mock.Mock(name="determine_next_time", return_value=nt)

                dwf = mock.Mock(name="do_write_future")
                do_write = mock.Mock(name="do_write", return_value=dwf)

                with mock.patch("time.time", te):
                    with mock.patch.object(self.loop, "call_later", cl):
                        with mock.patch.multiple(self.waiter, determine_next_time=determine_next_time, do_write=do_write):
                            self.waiter.next_time = now - 10
                            await self.waiter.writings()

                self.assertEqual(called, [(2, ())])
                self.assertEqual(self.waiter.futs, [dwf])
                self.assertEqual(self.waiter.next_time, nt)
                do_write.assert_called_once_with()

            async it "does not call writer if we have a partial result":
                now = time.time()
                te = mock.Mock(name="time", return_value=now)

                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []
                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                self.waiter._writings_cb = writings_cb
                self.waiter.futs = []

                nt = now + 2
                determine_next_time = mock.Mock(name="determine_next_time", return_value=nt)

                dwf = mock.Mock(name="do_write_future")
                do_write = mock.Mock(name="do_write", return_value=dwf)

                futs = [asyncio.Future(), asyncio.Future()]
                futs[0].partial = mock.Mock(name="partial", return_value=0)
                futs[1].partial = mock.Mock(name="partial", return_value=now-1)
                self.waiter.futs = futs

                with mock.patch("time.time", te):
                    with mock.patch.object(self.loop, "call_later", cl):
                        with mock.patch.multiple(self.waiter, determine_next_time=determine_next_time, do_write=do_write):
                            self.waiter.next_time = now - 10
                            await self.waiter.writings()

                self.assertEqual(called, [(2, ())])
                self.assertEqual(len(self.waiter.futs), 2)
                self.assertEqual(self.waiter.next_time, nt)
                self.assertEqual(do_write.mock_calls, [])

            async it "does call writer if we have no partial result":
                now = time.time()
                te = mock.Mock(name="time", return_value=now)

                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []
                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                self.waiter._writings_cb = writings_cb
                self.waiter.futs = []

                nt = now + 2
                determine_next_time = mock.Mock(name="determine_next_time", return_value=nt)

                dwf = mock.Mock(name="do_write_future")
                do_write = mock.Mock(name="do_write", return_value=dwf)

                futs = [asyncio.Future(), asyncio.Future()]
                futs[0].partial = mock.Mock(name="partial", return_value=0)
                futs[1].partial = mock.Mock(name="partial", return_value=0)
                self.waiter.futs = futs

                with mock.patch("time.time", te):
                    with mock.patch.object(self.loop, "call_later", cl):
                        with mock.patch.multiple(self.waiter, determine_next_time=determine_next_time, do_write=do_write):
                            self.waiter.next_time = now - 10
                            await self.waiter.writings()

                self.assertEqual(called, [(2, ())])
                self.assertEqual(len(self.waiter.futs), 3)
                self.assertEqual(self.waiter.next_time, nt)
                do_write.assert_called_once_with()

            async it "does call writer if we have only old partial results":
                now = time.time()
                te = mock.Mock(name="time", return_value=now)

                writings_cb = mock.Mock(name="writings_cb")
                original_call_later = self.loop.call_later

                called = []
                def cl(t, cb, *args):
                    if cb is writings_cb:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)

                self.waiter._writings_cb = writings_cb
                self.waiter.futs = []

                nt = now + 2
                determine_next_time = mock.Mock(name="determine_next_time", return_value=nt)

                dwf = mock.Mock(name="do_write_future")
                do_write = mock.Mock(name="do_write", return_value=dwf)

                futs = [asyncio.Future(), asyncio.Future()]
                futs[0].partial = mock.Mock(name="partial", return_value=0)
                futs[1].partial = mock.Mock(name="partial", return_value=now - 6)
                self.waiter.futs = futs

                with mock.patch("time.time", te):
                    with mock.patch.object(self.loop, "call_later", cl):
                        with mock.patch.multiple(self.waiter, determine_next_time=determine_next_time, do_write=do_write):
                            self.waiter.next_time = now - 10
                            await self.waiter.writings()

                self.assertEqual(called, [(2, ())])
                self.assertEqual(len(self.waiter.futs), 3)
                self.assertEqual(self.waiter.next_time, nt)
                do_write.assert_called_once_with()

        describe "do_write":
            async it "create a FutPair from our writer":
                w = mock.Mock(name="w")
                self.waiter.writer = mock.Mock(name="writer", return_value=w)

                fut = mock.Mock(name="fut")
                ensure_future = mock.Mock(name="ensure_future", return_value=fut)

                fp = mock.Mock(name="futpair")
                FakeFutPair = mock.Mock(name="FutPair", return_value=fp)

                writings_cb = mock.Mock(name="writings_cb")
                self.waiter._writings_cb = writings_cb

                with mock.patch("photons_transport.target.waiter.FutPair", FakeFutPair):
                    with mock.patch("asyncio.ensure_future", ensure_future):
                        self.assertIs(self.waiter.do_write(), fp)

                fp.add_done_callback.assert_called_once_with(writings_cb)
                FakeFutPair.assert_called_once_with(fut)
                ensure_future.assert_called_once_with(w)
