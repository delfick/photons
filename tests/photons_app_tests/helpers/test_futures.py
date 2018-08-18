# coding: spec

from photons_app.test_helpers import AsyncTestCase, assertFutCallbacks
from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import asyncio
import uuid
import time
import mock

describe AsyncTestCase, "ResettableFuture":
    async it "ensure_future returns the ResettableFuture as is":
        fut = hp.ResettableFuture()
        self.assertIs(asyncio.ensure_future(fut), fut)

    describe "Reset":
        async it "can be reset":
            res = mock.Mock(name="res")
            res2 = mock.Mock(name="res2")
            fut = hp.ResettableFuture()

            fut.set_result(res)
            self.assertIs(await fut, res)

            assert fut.done()
            fut.reset()

            assert not fut.done()
            fut.set_result(res2)
            self.assertIs(await fut, res2)

        async it "passes on the done callbacks to the new future":
            called = []

            def done1(fut):
                called.append(1)

            def done2(fut):
                called.append(2)

            fut = hp.ResettableFuture()
            fut.add_done_callback(done1)
            fut.add_done_callback(done2)

            self.assertEqual(called, [])
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            self.assertEqual(called, [1, 2])

            fut.reset()
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            self.assertEqual(called, [1, 2, 1, 2])

        async it "doesn't pass on removed callbacks to new fut":
            called = []

            def done1(fut):
                called.append(1)

            def done2(fut):
                called.append(2)

            class Thing:
                def done3(s, fut):
                    called.append(3)
            thing = Thing()

            fut = hp.ResettableFuture()
            fut.add_done_callback(done1)
            fut.add_done_callback(done2)
            fut.add_done_callback(thing.done3)

            self.assertEqual(called, [])
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            self.assertEqual(called, [1, 2, 3])

            fut.remove_done_callback(done1)
            fut.remove_done_callback(thing.done3)

            fut.reset()
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            self.assertEqual(called, [1, 2, 3, 2])

        async it "respects remove_done_callback":
            called = []

            def done1(fut):
                called.append(1)

            def done2(fut):
                called.append(2)

            fut = hp.ResettableFuture()
            fut.add_done_callback(done1)
            fut.add_done_callback(done2)

            # Remove the first done_callback
            fut.remove_done_callback(done1)

            self.assertEqual(called, [])
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            self.assertEqual(called, [2])

            fut.reset()
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            self.assertEqual(called, [2, 2])

    describe "set_result":
        async it "sets result on the current fut and calls all the on_creation functions":
            called = []

            def cb1(data):
                called.append((1, data))

            def cb2(data):
                called.append((2, data))

            res = mock.Mock(name="res")
            fut = hp.ResettableFuture()
            fut.on_creation(cb1)
            fut.on_creation(cb2)

            self.assertEqual(called, [])
            fut.set_result(res)

            await asyncio.sleep(0)
            self.assertEqual(called, [(1, res), (2, res)])

            self.assertEqual(fut.info["fut"].result(), res)

    describe "future interface":
        async it "fulfills the future interface":
            fut = hp.ResettableFuture()
            assert not fut.done()
            fut.set_result(True)
            assert fut.done()
            self.assertEqual(fut.result(), True)
            assert not fut.cancelled()
            self.assertEqual(fut.exception(), None)
            self.assertEqual(await fut, True)

            fut2 = hp.ResettableFuture()
            error = PhotonsAppError("lol")
            assert not fut2.done()
            fut2.set_exception(error)
            assert fut2.done()
            self.assertEqual(fut2.exception(), error)
            assert not fut2.cancelled()
            with self.fuzzyAssertRaisesError(PhotonsAppError, "lol"):
                await fut2

            fut3 = hp.ResettableFuture()
            assert not fut3.done()
            assert not fut3.cancelled()
            fut3.cancel()
            assert fut3.cancelled()

            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                await fut3

    describe "extra future interface":
        async it "is ready done but not cancelled":
            fut = hp.ResettableFuture()
            assert not fut.ready()

            fut.set_result(True)
            assert fut.ready()

            fut2 = hp.ResettableFuture()
            fut2.cancel()
            assert not fut2.ready()

        async it "is settable if not done and not cancelled":
            fut = hp.ResettableFuture()
            assert fut.settable()

            fut.set_result(True)
            assert not fut.settable()

            fut2 = hp.ResettableFuture()
            fut2.cancel()
            assert not fut2.settable()

        async it "is is finished if done or cancelled":
            fut = hp.ResettableFuture()
            assert not fut.finished()

            fut.set_result(True)
            assert fut.finished()

            fut2 = hp.ResettableFuture()
            fut2.cancel()
            assert fut2.finished()

    describe "freeze":
        async it "returns a resettable future with the current fut and callbacks":
            called = []

            def on_creation(data):
                called.append(("on_creation", data))

            def on_done(fut):
                called.append("on_done")

            def on_creation2(data):
                called.append(("on_creation2", data))

            def on_done2(fut):
                called.append("on_done2")

            fut = hp.ResettableFuture()
            fut.on_creation(on_creation)
            fut.add_done_callback(on_done)

            frozen = fut.freeze()
            fut.reset()

            fut.on_creation(on_creation2)
            fut.add_done_callback(on_done2)

            self.assertEqual(called, [])
            res = mock.Mock(name='res')
            frozen.set_result(res)
            await asyncio.sleep(0)

            self.assertEqual(called, [("on_creation", res), "on_done"])
            self.assertEqual(await frozen, res)

            assert not fut.done()

    describe "__repr__":
        async it "reprs the fut it has":
            class Fut:
                def __repr__(self):
                    return "REPRED_YO"

            fut = hp.ResettableFuture()
            fut.info["fut"] = Fut()

            self.assertEqual(repr(fut), "<ResettableFuture: REPRED_YO>")

    describe "await":
        async it "yield from the fut if it's done":
            res = mock.Mock(name="res")
            fut = hp.ResettableFuture()
            fut.set_result(res)
            self.assertIs(await fut, res)

        async it "works across resets":
            called = []
            fut = hp.ResettableFuture()

            async def waiter():
                called.append(await fut)

            try:
                task = asyncio.ensure_future(self.loop.create_task(waiter()))

                res = mock.Mock(name="res")
                fut.reset()
                await asyncio.sleep(0)
                assert not task.done()

                fut.reset()
                await asyncio.sleep(0)
                assert not task.done()

                fut.set_result(res)
                await asyncio.sleep(0)
                assert task.done()
            finally:
                task.cancel()

            self.assertEqual(called, [res])

describe AsyncTestCase, "ChildOfFuture":
    async before_each:
        self.orig_fut = asyncio.Future()
        self.cof = hp.ChildOfFuture(self.orig_fut)

    async it "ensure_future returns the ChildOfFuture as is":
        fut = asyncio.Future()
        fut = hp.ChildOfFuture(fut)
        self.assertIs(asyncio.ensure_future(fut), fut)

    describe "set_result":
        async it "complains if the original fut is already cancelled":
            self.orig_fut.cancel()
            with self.fuzzyAssertRaisesError(asyncio.futures.InvalidStateError, "CANCELLED: .+"):
                self.cof.set_result(True)

        async it "Otherwise sets a result on the fut":
            assert not self.cof.done()
            self.cof.set_result(True)
            assert self.cof.done()
            assert not self.orig_fut.done()
            self.assertEqual(await self.cof, True)

    describe "Getting  result":
        async it "cancels the future if original is done":
            res = mock.Mock(name="res")
            self.orig_fut.set_result(res)
            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                self.cof.result()

        async it "gets result from original if that is cancelled":
            self.orig_fut.cancel()
            self.cof.this_fut.set_result(True)
            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                self.cof.result()

        async it "gets result from this fut if it has a result":
            res = mock.Mock(name="res")
            assert not self.orig_fut.done() and not self.orig_fut.cancelled()
            self.cof.this_fut.set_result(res)
            self.assertIs(self.cof.result(), res)

        async it "gets result from this fut if it is cancelled":
            assert not self.orig_fut.done() and not self.orig_fut.cancelled()
            self.cof.this_fut.cancel()
            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                self.cof.result()

        async it "calls result on original_fut if neither are finished":
            with self.fuzzyAssertRaisesError(asyncio.futures.InvalidStateError, "Result is not (ready|set)"):
                self.cof.result()

    describe "done":
        async it "is done if either this or original fut are done":
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            assert not cof.done()
            o.set_result(True)
            assert cof.done()

            o2 = asyncio.Future()
            cof2 = hp.ChildOfFuture(o2)
            cof2.set_result(True)
            assert not o2.done()
            assert cof2.done()

            o3 = asyncio.Future()
            cof3 = hp.ChildOfFuture(o3)
            o3.cancel()
            assert cof3.done()

            o4 = asyncio.Future()
            cof4 = hp.ChildOfFuture(o4)
            cof4.cancel()
            assert not o4.done()
            assert cof4.done()

    describe "cancelled":
        async it "is cancelled if either this or original fut are cancelled":
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            assert not cof.cancelled()

            o2 = asyncio.Future()
            cof2 = hp.ChildOfFuture(o2)
            cof2.cancel()
            assert not o2.cancelled()
            assert cof2.cancelled()

            o3 = asyncio.Future()
            cof3 = hp.ChildOfFuture(o3)
            o3.cancel()
            assert cof3.cancelled()

        async it "is cancelled if the original fut is done without errors":
            o = asyncio.Future()
            o.set_result(None)
            cof = hp.ChildOfFuture(o)
            assert cof.cancelled()

            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            o.set_result(None)
            assert cof.cancelled()

    describe "exception":
        async it "it complains no exception is set if neither fut cancelled or have exception":
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            with self.fuzzyAssertRaisesError(asyncio.futures.InvalidStateError):
                cof.exception()

        async it "complains future is cancelled when either fut is cancelled":
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            o.cancel()
            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                cof.exception()

            o2 = asyncio.Future()
            cof2 = hp.ChildOfFuture(o2)
            cof2.cancel()
            assert not o2.cancelled()
            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                cof.exception()

        async it "returns the exception if original fut has an exception":
            error = PhotonsAppError("lol")
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            o.set_exception(error)
            self.assertIs(cof.exception(), error)

        async it "returns the exception if this_fut has an exception":
            error = PhotonsAppError("lol")
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            cof.set_exception(error)
            assert not o.done()
            self.assertIs(cof.exception(), error)

    describe "cancelling the parent":
        async it "cancels original_fut parent if that has cancel_parent":
            grandparent = asyncio.Future()
            parent = hp.ChildOfFuture(grandparent)
            cof = hp.ChildOfFuture(parent)
            cof.cancel_parent()
            assert parent.cancelled()
            assert grandparent.cancelled()
            assert not cof.this_fut.cancelled()
            assert cof.cancelled()

        async it "cancels original fut if has no cancel_parent on it":
            parent = asyncio.Future()
            cof = hp.ChildOfFuture(parent)
            cof.cancel_parent()
            assert parent.cancelled()
            assert not cof.this_fut.cancelled()
            assert cof.cancelled()

    describe "cancel":
        async it "only cancels this_fut":
            self.cof.cancel()
            assert not self.orig_fut.cancelled()
            assert self.cof.cancelled()

    describe "extra future interface":
        async it "is ready if done and not cancelled":
            yes = lambda: True
            no = lambda: False

            with mock.patch.object(self.cof, "done", yes):
                with mock.patch.object(self.cof, "cancelled", no):
                    assert self.cof.ready()

            with mock.patch.object(self.cof, "done", no):
                with mock.patch.object(self.cof, "cancelled", no):
                    assert not self.cof.ready()

            with mock.patch.object(self.cof, "done", no):
                with mock.patch.object(self.cof, "cancelled", yes):
                    assert not self.cof.ready()

            with mock.patch.object(self.cof, "done", yes):
                with mock.patch.object(self.cof, "cancelled", yes):
                    assert not self.cof.ready()

        async it "is settable if not done and not cancelled":
            yes = lambda: True
            no = lambda: False

            with mock.patch.object(self.cof, "done", yes):
                with mock.patch.object(self.cof, "cancelled", no):
                    assert not self.cof.settable()

            with mock.patch.object(self.cof, "done", no):
                with mock.patch.object(self.cof, "cancelled", no):
                    assert self.cof.settable()

            with mock.patch.object(self.cof, "done", no):
                with mock.patch.object(self.cof, "cancelled", yes):
                    assert not self.cof.settable()

            with mock.patch.object(self.cof, "done", yes):
                with mock.patch.object(self.cof, "cancelled", yes):
                    assert not self.cof.settable()

        async it "is finished if done or cancelled":
            yes = lambda: True
            no = lambda: False

            with mock.patch.object(self.cof, "done", yes):
                with mock.patch.object(self.cof, "cancelled", no):
                    assert self.cof.finished()

            with mock.patch.object(self.cof, "done", no):
                with mock.patch.object(self.cof, "cancelled", no):
                    assert not self.cof.finished()

            with mock.patch.object(self.cof, "done", no):
                with mock.patch.object(self.cof, "cancelled", yes):
                    assert self.cof.finished()

            with mock.patch.object(self.cof, "done", yes):
                with mock.patch.object(self.cof, "cancelled", yes):
                    assert self.cof.finished()

    describe "set_exception":
        async it "sets exception on this_fut":
            error = PhotonsAppError("error")
            self.cof.set_exception(error)
            assert not self.orig_fut.done()
            self.assertIs(self.cof.exception(), error)

    describe "done_callbacks":
        async it "callbacks are called if original future is done first":
            called = []

            def done(res):
                called.append(res)

            self.cof.add_done_callback(done)
            assertFutCallbacks(self.orig_fut, self.cof._parent_done_cb)
            assertFutCallbacks(self.cof.this_fut, self.cof._done_cb)

            self.orig_fut.set_result(True)
            await asyncio.sleep(0)
            self.assertEqual(called, [self.orig_fut])

        async it "calls callbacks only once if both this_fut and orig_fut are called":
            called = []

            def done(res):
                called.append(res)

            self.cof.add_done_callback(done)
            assertFutCallbacks(self.orig_fut, self.cof._parent_done_cb)
            assertFutCallbacks(self.cof.this_fut, self.cof._done_cb)

            self.cof.set_result(True)
            await asyncio.sleep(0)
            self.assertEqual(called, [self.cof.this_fut])

            self.orig_fut.set_result(True)
            await asyncio.sleep(0)
            self.assertEqual(called, [self.cof.this_fut])

        async it "does only calls callback once if this_fut is cancelled first":
            called = []

            def done(res):
                called.append(res)

            self.cof.add_done_callback(done)
            assertFutCallbacks(self.orig_fut, self.cof._parent_done_cb)
            assertFutCallbacks(self.cof.this_fut, self.cof._done_cb)

            self.cof.cancel()
            await asyncio.sleep(0)
            self.assertEqual(called, [self.cof.this_fut])

            self.orig_fut.cancel()
            await asyncio.sleep(0)
            self.assertEqual(called, [self.cof.this_fut])

        async it "works with multiple callbacks":
            called = []

            def done(res):
                called.append(res)

            def done2(res):
                called.append((2, res))

            self.cof.add_done_callback(done)
            self.cof.add_done_callback(done2)

            assertFutCallbacks(self.orig_fut, self.cof._parent_done_cb)
            assertFutCallbacks(self.cof.this_fut, self.cof._done_cb)

            self.cof.set_result(True)
            await asyncio.sleep(0)
            self.assertEqual(called, [self.cof.this_fut, (2, self.cof.this_fut)])

        async it "calls callback if parent is killed first":
            called = []

            def done(res):
                called.append(res)

            self.cof.add_done_callback(done)
            assertFutCallbacks(self.orig_fut, self.cof._parent_done_cb)
            assertFutCallbacks(self.cof.this_fut, self.cof._done_cb)

            self.orig_fut.cancel()
            await asyncio.sleep(0)
            self.assertEqual(called, [self.orig_fut])

    describe "removing a done callback":
        async it "removes from cof.done_callbacks":
            cb = mock.Mock(name='cb')
            cb2 = mock.Mock(name='cb2')

            self.assertEqual(self.cof.done_callbacks, [])

            self.cof.add_done_callback(cb)
            self.assertEqual(self.cof.done_callbacks, [cb])

            self.cof.add_done_callback(cb2)
            self.assertEqual(self.cof.done_callbacks, [cb, cb2])

            self.cof.remove_done_callback(cb)
            self.assertEqual(self.cof.done_callbacks, [cb2])

            self.cof.remove_done_callback(cb2)
            self.assertEqual(self.cof.done_callbacks, [])

            self.cof.add_done_callback(self.cof._parent_done_cb)
            self.assertEqual(self.cof.done_callbacks, [self.cof._parent_done_cb])

            other = lambda: 1
            self.cof.add_done_callback(other)
            self.assertEqual(self.cof.done_callbacks, [self.cof._parent_done_cb, other])

            self.cof.remove_done_callback(self.cof._parent_done_cb)
            self.assertEqual(self.cof.done_callbacks, [other])

            self.cof.remove_done_callback(other)
            self.assertEqual(self.cof.done_callbacks, [])

        async it "removes callback from the futures if no more callbacks":
            assertFutCallbacks(self.orig_fut)
            assertFutCallbacks(self.cof.this_fut)

            cb = mock.Mock(name='cb')
            cb2 = mock.Mock(name='c2')

            self.assertEqual(self.cof.done_callbacks, [])

            self.cof.add_done_callback(cb)
            self.assertEqual(self.cof.done_callbacks, [cb])
            assertFutCallbacks(self.orig_fut, self.cof._parent_done_cb)
            assertFutCallbacks(self.cof.this_fut, self.cof._done_cb)

            self.cof.add_done_callback(cb2)
            self.assertEqual(self.cof.done_callbacks, [cb, cb2])
            assertFutCallbacks(self.orig_fut, self.cof._parent_done_cb)
            assertFutCallbacks(self.cof.this_fut, self.cof._done_cb)

            self.cof.remove_done_callback(cb)
            self.assertEqual(self.cof.done_callbacks, [cb2])
            assertFutCallbacks(self.orig_fut, self.cof._parent_done_cb)
            assertFutCallbacks(self.cof.this_fut, self.cof._done_cb)

            self.cof.remove_done_callback(cb2)
            self.assertEqual(self.cof.done_callbacks, [])
            assertFutCallbacks(self.orig_fut)
            assertFutCallbacks(self.cof.this_fut)

    describe "repr":
        async it "gives repr for both futures":
            class OFut:
                def __repr__(self):
                    return "OFUT"
            class Fut:
                def __repr__(self):
                    return "TFUT"

            fut = hp.ChildOfFuture(OFut())
            fut.this_fut = Fut()
            self.assertEqual(repr(fut), "<ChildOfFuture: OFUT |:| TFUT>")

    describe "awaiting":
        def waiting_for(self, res):
            async def waiter():
                return await self.cof

            class Waiter:
                async def __aenter__(s):
                    self.task = self.loop.create_task(waiter())
                    return

                async def __aexit__(s, exc_type, exc, tb):
                    if exc:
                        return False

                    if res is asyncio.CancelledError:
                        with self.fuzzyAssertRaisesError(res):
                            await self.wait_for(self.task)
                    elif type(res) is PhotonsAppError:
                        with self.fuzzyAssertRaisesError(PhotonsAppError, res.message):
                            await self.wait_for(self.task)
                    else:
                        self.assertEqual(await self.wait_for(self.task), res)

            return Waiter()

        async it "returns result from this_fut if that goes first":
            res = mock.Mock(name="res")
            async with self.waiting_for(res):
                self.cof.set_result(res)

        async it "cancels this_fut if original fut gets a result":
            res = mock.Mock(name="res")
            async with self.waiting_for(asyncio.CancelledError):
                self.orig_fut.set_result(res)

        async it "returns result from this_fut if that cancels first":
            async with self.waiting_for(asyncio.CancelledError):
                self.cof.cancel()

        async it "returns result from orig_fut if that goes first":
            async with self.waiting_for(asyncio.CancelledError):
                self.orig_fut.cancel()

        async it "returns result from this_fut if that exceptions first":
            error = PhotonsAppError("fail")
            async with self.waiting_for(error):
                self.cof.set_exception(error)

        async it "returns result from orig_fut if that goes first":
            error = PhotonsAppError("yeap")
            async with self.waiting_for(error):
                self.orig_fut.set_exception(error)

describe AsyncTestCase, "fut_has_callback":
    async it "says no if fut has no callbacks":
        def func():
            pass

        fut = asyncio.Future()
        assert not hp.fut_has_callback(fut, func)

    async it "says no if it has other callbacks":
        def func1():
            pass

        def func2():
            pass

        fut = asyncio.Future()
        fut.add_done_callback(func1)
        assert not hp.fut_has_callback(fut, func2)

    async it "says yes if we have the callback":
        def func1():
            pass

        fut = asyncio.Future()
        fut.add_done_callback(func1)
        assert hp.fut_has_callback(fut, func1)

        def func2():
            pass
        assert not hp.fut_has_callback(fut, func2)
        fut.add_done_callback(func2)
        assert hp.fut_has_callback(fut, func2)

describe AsyncTestCase, "async_as_normal":
    async it "returns a function that spawns the coroutine as a task":
        async def func(one, two, three=None):
            return "{0}.{1}.{2}".format(one, two, three)

        normal = hp.async_as_normal(func)
        t = normal(1, 2, three=4)
        assert isinstance(t, asyncio.Task)
        self.assertEqual(await t, "1.2.4")

describe AsyncTestCase, "async_with_timeout":
    async it "returns the result of waiting on the coroutine":
        val = str(uuid.uuid1())

        async def func():
            return val

        res = await self.wait_for(hp.async_with_timeout(func(), timeout=10))
        self.assertEqual(res, val)

    async it "cancels the coroutine if it doesn't respond":
        async def func():
            await asyncio.sleep(2)
            return val

        start = time.time()
        with self.fuzzyAssertRaisesError(asyncio.CancelledError):
            await hp.async_with_timeout(func(), timeout=0.1)
        self.assertLess(time.time() - start, 0.5)

    async it "cancels the coroutine and raises timeout_error":
        error = PhotonsAppError("Blah")

        async def func():
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError as error:
                assert False, "Expected it to just raise the error rather than cancelling first"
            return val

        start = time.time()
        with self.fuzzyAssertRaisesError(PhotonsAppError, "Blah"):
            await hp.async_with_timeout(func(), timeout=0.1, timeout_error=error)
        self.assertLess(time.time() - start, 0.5)

describe AsyncTestCase, "async_as_background":
    async it "runs the coroutine in the background":
        async def func(one, two, three=None):
            return "{0}.{1}.{2}".format(one, two, three)

        t = hp.async_as_background(func(6, 5, three=9))
        assertFutCallbacks(t, hp.reporter)
        assert isinstance(t, asyncio.Task)
        self.assertEqual(await t, "6.5.9")

    async it "uses silent_reporter if silent is True":
        async def func(one, two, three=None):
            return "{0}.{1}.{2}".format(one, two, three)

        t = hp.async_as_background(func(6, 5, three=9), silent=True)
        assertFutCallbacks(t, hp.silent_reporter)
        assert isinstance(t, asyncio.Task)
        self.assertEqual(await t, "6.5.9")

describe AsyncTestCase, "silent_reporter":
    async it "does nothing if the future was cancelled":
        fut = asyncio.Future()
        fut.cancel()
        self.assertEqual(hp.silent_reporter(fut), None)

    async it "does nothing if the future has an exception":
        fut = asyncio.Future()
        fut.set_exception(Exception("wat"))
        self.assertEqual(hp.silent_reporter(fut), None)

    async it "returns true if we have a result":
        fut = asyncio.Future()
        fut.set_result(mock.Mock(name="result"))
        self.assertEqual(hp.silent_reporter(fut), True)

describe AsyncTestCase, "reporter":
    async it "does nothing if the future was cancelled":
        fut = asyncio.Future()
        fut.cancel()
        self.assertEqual(hp.reporter(fut), None)

    async it "does nothing if the future has an exception":
        fut = asyncio.Future()
        fut.set_exception(Exception("wat"))
        self.assertEqual(hp.reporter(fut), None)

    async it "returns true if we have a result":
        fut = asyncio.Future()
        fut.set_result(mock.Mock(name="result"))
        self.assertEqual(hp.reporter(fut), True)

describe AsyncTestCase, "transfer_result":
    async it "works as a done_callback":
        fut = asyncio.Future()

        async def doit():
            return [1, 2]

        t = self.loop.create_task(doit())
        t.add_done_callback(hp.transfer_result(fut))
        await self.wait_for(t)

        self.assertEqual(fut.result(), [1, 2])

    describe "errors_only":
        async it "cancels fut if res is cancelled":
            fut = asyncio.Future()
            res = asyncio.Future()
            res.cancel()

            hp.transfer_result(fut, errors_only=True)(res)
            assert res.cancelled()

        async it "sets exception on fut if res has an exception":
            fut = asyncio.Future()
            res = asyncio.Future()

            error = ValueError("NOPE")
            res.set_exception(error)

            hp.transfer_result(fut, errors_only=True)(res)
            self.assertEqual(fut.exception(), error)

        async it "does not transfer result":
            fut = asyncio.Future()
            res = asyncio.Future()
            res.set_result([1, 2])

            hp.transfer_result(fut, errors_only=True)(res)
            assert not fut.done()

    describe "not errors_only":
        async it "cancels fut if res is cancelled":
            fut = asyncio.Future()
            res = asyncio.Future()
            res.cancel()

            hp.transfer_result(fut, errors_only=False)(res)
            assert res.cancelled()

        async it "sets exception on fut if res has an exception":
            fut = asyncio.Future()
            res = asyncio.Future()

            error = ValueError("NOPE")
            res.set_exception(error)

            hp.transfer_result(fut, errors_only=False)(res)
            self.assertEqual(fut.exception(), error)

        async it "transfers result":
            fut = asyncio.Future()
            res = asyncio.Future()
            res.set_result([1, 2])

            hp.transfer_result(fut, errors_only=False)(res)
            self.assertEqual(fut.result(), [1, 2])

describe AsyncTestCase, "noncancelled_results_from_futs":
    async it "returns results from done futures that aren't cancelled":
        fut1 = asyncio.Future()
        fut2 = asyncio.Future()
        fut3 = asyncio.Future()
        fut4 = asyncio.Future()

        result1 = mock.Mock(name="result1")
        result2 = mock.Mock(name="result2")

        fut2.set_result(result1)
        fut3.cancel()
        fut4.set_result(result2)

        self.assertEqual(
              hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4])
            , (None, [result1, result2])
            )

    async it "returns found errors as well":
        fut1 = asyncio.Future()
        fut2 = asyncio.Future()
        fut3 = asyncio.Future()
        fut4 = asyncio.Future()

        error1 = Exception("wat")
        result2 = mock.Mock(name="result2")

        fut2.set_exception(error1)
        fut3.cancel()
        fut4.set_result(result2)

        self.assertEqual(
              hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4])
            , (error1, [result2])
            )

    async it "squashes the same error into one error":
        fut1 = asyncio.Future()
        fut2 = asyncio.Future()
        fut3 = asyncio.Future()
        fut4 = asyncio.Future()

        error1 = PhotonsAppError("wat", one=1)
        error2 = PhotonsAppError("wat", one=1)
        result2 = mock.Mock(name="result2")

        fut2.set_exception(error1)
        fut3.cancel()
        fut4.set_exception(error2)

        self.assertEqual(
              hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4])
            , (error1, [])
            )

    async it "can return error with multiple errors":
        fut1 = asyncio.Future()
        fut2 = asyncio.Future()
        fut3 = asyncio.Future()
        fut4 = asyncio.Future()
        fut5 = asyncio.Future()

        error1 = PhotonsAppError("wat")
        error2 = PhotonsAppError("wat2")
        result2 = mock.Mock(name="result2")

        fut2.set_exception(error1)
        fut3.cancel()
        fut4.set_result(result2)
        fut5.set_exception(error2)

        self.assertEqual(
              hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4, fut5])
            , (PhotonsAppError(_errors=[error1, error2]), [result2])
            )

describe AsyncTestCase, "find_and_apply_result":
    async before_each:
        self.fut1 = asyncio.Future()
        self.fut2 = asyncio.Future()
        self.fut3 = asyncio.Future()
        self.fut4 = asyncio.Future()
        self.available_futs = [self.fut1, self.fut2, self.fut3, self.fut4]
        self.final_fut = asyncio.Future()

    async it "cancels futures if final_future is cancelled":
        self.final_fut.cancel()
        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), False)

        assert self.fut1.cancelled()
        assert self.fut2.cancelled()
        assert self.fut3.cancelled()
        assert self.fut4.cancelled()

        assert self.final_fut.cancelled()

    async it "sets exceptions on futures if final_future has an exception":
        error = ValueError("NOPE")
        self.final_fut.set_exception(error)
        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), False)

        for f in self.available_futs:
            self.assertIs(f.exception(), error)

    async it "ignores futures already done when final_future has an exception":
        err1 = Exception("LOLZ")
        self.available_futs[0].set_exception(err1)
        self.available_futs[1].cancel()
        self.available_futs[2].set_result([1, 2])

        err2 = ValueError("NOPE")
        self.final_fut.set_exception(err2)
        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), False)

        self.assertIs(self.available_futs[0].exception(), err1)
        assert self.available_futs[1].cancelled()
        self.assertEqual(self.available_futs[2].result(), [1, 2])
        self.assertIs(self.available_futs[3].exception(), err2)

    async it "spreads error if any is found":
        error1 = Exception("wat")
        self.fut2.set_exception(error1)

        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), True)

        self.assertIs(self.fut1.exception(), error1)
        self.assertIs(self.fut2.exception(), error1)
        self.assertIs(self.fut3.exception(), error1)
        self.assertIs(self.fut4.exception(), error1)

        self.assertIs(self.final_fut.exception(), error1)

    async it "doesn't spread error to those already cancelled or with error":
        error1 = PhotonsAppError("wat")
        self.fut2.set_exception(error1)

        error2 = PhotonsAppError("wat2")
        self.fut1.set_exception(error2)

        self.fut4.cancel()

        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), True)

        self.assertIs(self.fut1.exception(), error2)
        self.assertIs(self.fut2.exception(), error1)
        self.assertEqual(self.fut3.exception(), PhotonsAppError(_errors=[error2, error1]))
        assert self.fut4.cancelled()

        self.assertEqual(self.final_fut.exception(), PhotonsAppError(_errors=[error2, error1]))

    async it "sets results if one has a result":
        result = mock.Mock(name="result")
        self.fut1.set_result(result)

        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), True)

        self.assertIs(self.fut1.result(), result)
        self.assertIs(self.fut2.result(), result)
        self.assertIs(self.fut3.result(), result)
        self.assertIs(self.fut4.result(), result)

        self.assertIs(self.final_fut.result(), result)

    async it "sets results if one has a result except for cancelled ones":
        result = mock.Mock(name="result")
        self.fut1.set_result(result)
        self.fut2.cancel()

        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), True)

        self.assertIs(self.fut1.result(), result)
        assert self.fut2.cancelled()
        self.assertIs(self.fut3.result(), result)
        self.assertIs(self.fut4.result(), result)

        self.assertIs(self.final_fut.result(), result)

    async it "sets result on final_fut unless it's already cancelled":
        result = mock.Mock(name="result")
        self.fut1.set_result(result)
        self.final_fut.cancel()

        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), False)
        assert self.final_fut.cancelled()

    async it "cancels final_fut if any of our futs are cancelled":
        self.fut1.cancel()
        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), True)
        assert self.final_fut.cancelled()

    async it "does nothing if none of the futures are done":
        self.assertEqual(hp.find_and_apply_result(self.final_fut, self.available_futs), False)
        for f in self.available_futs:
            assert not f.done()
        assert not self.final_fut.done()
