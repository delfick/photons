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


describe "ResettableFuture":
    async it "ensure_future returns the ResettableFuture as is":
        fut = hp.ResettableFuture()
        assert asyncio.ensure_future(fut) is fut

    describe "Reset":
        async it "can be reset":
            res = mock.Mock(name="res")
            res2 = mock.Mock(name="res2")
            fut = hp.ResettableFuture()

            fut.set_result(res)
            assert await fut is res

            assert fut.done()
            fut.reset()

            assert not fut.done()
            fut.set_result(res2)
            assert await fut is res2

        async it "passes on the done callbacks to the new future":
            called = []

            def done1(fut):
                called.append(1)

            def done2(fut):
                called.append(2)

            fut = hp.ResettableFuture()
            fut.add_done_callback(done1)
            fut.add_done_callback(done2)

            assert called == []
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            assert called == [1, 2]

            fut.reset()
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            assert called == [1, 2, 1, 2]

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

            assert called == []
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            assert called == [1, 2, 3]

            fut.remove_done_callback(done1)
            fut.remove_done_callback(thing.done3)

            fut.reset()
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            assert called == [1, 2, 3, 2]

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

            assert called == []
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            assert called == [2]

            fut.reset()
            fut.set_result(True)
            # Allow the callbacks to be called
            await asyncio.sleep(0)
            assert called == [2, 2]

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

            assert called == []
            fut.set_result(res)

            await asyncio.sleep(0)
            assert called == [(1, res), (2, res)]

            assert fut.info["fut"].result() == res

    describe "future interface":
        async it "fulfills the future interface":
            fut = hp.ResettableFuture()
            assert not fut.done()
            fut.set_result(True)
            assert fut.done()
            assert fut.result() is True
            assert not fut.cancelled()
            assert fut.exception() is None
            assert await fut is True

            fut2 = hp.ResettableFuture()
            error = PhotonsAppError("lol")
            assert not fut2.done()
            fut2.set_exception(error)
            assert fut2.done()
            assert fut2.exception() == error
            assert not fut2.cancelled()
            with assertRaises(PhotonsAppError, "lol"):
                await fut2

            fut3 = hp.ResettableFuture()
            assert not fut3.done()
            assert not fut3.cancelled()
            fut3.cancel()
            assert fut3.cancelled()

            with assertRaises(asyncio.CancelledError):
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

            assert called == []
            res = mock.Mock(name="res")
            frozen.set_result(res)
            await asyncio.sleep(0)

            assert called == [("on_creation", res), "on_done"]
            assert await frozen == res

            assert not fut.done()

    describe "__repr__":
        async it "reprs the fut it has":

            class Fut:
                def __repr__(s):
                    return "REPRED_YO"

            fut = hp.ResettableFuture()
            fut.info["fut"] = Fut()

            assert repr(fut) == "<ResettableFuture: REPRED_YO>"

    describe "await":
        async it "yield from the fut if it's done":
            res = mock.Mock(name="res")
            fut = hp.ResettableFuture()
            fut.set_result(res)
            assert await fut is res

        async it "works across resets", loop:
            called = []
            fut = hp.ResettableFuture()

            async def waiter():
                called.append(await fut)

            try:
                task = asyncio.ensure_future(loop.create_task(waiter()))

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

            assert called == [res]

describe "ChildOfFuture":

    @pytest.fixture()
    def V(self):
        class V:
            orig_fut = asyncio.Future()

            @hp.memoized_property
            def cof(s):
                return hp.ChildOfFuture(s.orig_fut)

        return V()

    async it "ensure_future returns the ChildOfFuture as is":
        fut = asyncio.Future()
        fut = hp.ChildOfFuture(fut)
        assert asyncio.ensure_future(fut) is fut

    describe "set_result":
        async it "complains if the original fut is already cancelled", V:
            V.orig_fut.cancel()
            with assertRaises(hp.InvalidStateError, "CANCELLED: .+"):
                V.cof.set_result(True)

        async it "Otherwise sets a result on the fut", V:
            assert not V.cof.done()
            V.cof.set_result(True)
            assert V.cof.done()
            assert not V.orig_fut.done()
            assert await V.cof is True

    describe "Getting  result":
        async it "cancels the future if original is done", V:
            res = mock.Mock(name="res")
            V.orig_fut.set_result(res)
            with assertRaises(asyncio.CancelledError):
                V.cof.result()

        async it "gets result from original if that is cancelled", V:
            V.orig_fut.cancel()
            V.cof.this_fut.set_result(True)
            with assertRaises(asyncio.CancelledError):
                V.cof.result()

        async it "gets result from this fut if it has a result", V:
            res = mock.Mock(name="res")
            assert not V.orig_fut.done() and not V.orig_fut.cancelled()
            V.cof.this_fut.set_result(res)
            assert V.cof.result() is res

        async it "gets result from this fut if it is cancelled", V:
            assert not V.orig_fut.done() and not V.orig_fut.cancelled()
            V.cof.this_fut.cancel()
            with assertRaises(asyncio.CancelledError):
                V.cof.result()

        async it "calls result on original_fut if neither are finished", V:
            with assertRaises(hp.InvalidStateError, "Result is not (ready|set)"):
                V.cof.result()

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
            with assertRaises(hp.InvalidStateError):
                cof.exception()

        async it "complains future is cancelled when either fut is cancelled":
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            o.cancel()
            with assertRaises(asyncio.CancelledError):
                cof.exception()

            o2 = asyncio.Future()
            cof2 = hp.ChildOfFuture(o2)
            cof2.cancel()
            assert not o2.cancelled()
            with assertRaises(asyncio.CancelledError):
                cof.exception()

        async it "returns the exception if original fut has an exception":
            error = PhotonsAppError("lol")
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            o.set_exception(error)
            assert cof.exception() is error

        async it "returns the exception if this_fut has an exception":
            error = PhotonsAppError("lol")
            o = asyncio.Future()
            cof = hp.ChildOfFuture(o)
            cof.set_exception(error)
            assert not o.done()
            assert cof.exception() is error

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
        async it "only cancels this_fut", V:
            V.cof.cancel()
            assert not V.orig_fut.cancelled()
            assert V.cof.cancelled()

    describe "extra future interface":
        async it "is ready if done and not cancelled", V:
            yes = lambda: True
            no = lambda: False

            with mock.patch.object(V.cof, "done", yes):
                with mock.patch.object(V.cof, "cancelled", no):
                    assert V.cof.ready()

            with mock.patch.object(V.cof, "done", no):
                with mock.patch.object(V.cof, "cancelled", no):
                    assert not V.cof.ready()

            with mock.patch.object(V.cof, "done", no):
                with mock.patch.object(V.cof, "cancelled", yes):
                    assert not V.cof.ready()

            with mock.patch.object(V.cof, "done", yes):
                with mock.patch.object(V.cof, "cancelled", yes):
                    assert not V.cof.ready()

        async it "is settable if not done and not cancelled", V:
            yes = lambda: True
            no = lambda: False

            with mock.patch.object(V.cof, "done", yes):
                with mock.patch.object(V.cof, "cancelled", no):
                    assert not V.cof.settable()

            with mock.patch.object(V.cof, "done", no):
                with mock.patch.object(V.cof, "cancelled", no):
                    assert V.cof.settable()

            with mock.patch.object(V.cof, "done", no):
                with mock.patch.object(V.cof, "cancelled", yes):
                    assert not V.cof.settable()

            with mock.patch.object(V.cof, "done", yes):
                with mock.patch.object(V.cof, "cancelled", yes):
                    assert not V.cof.settable()

        async it "is finished if done or cancelled", V:
            yes = lambda: True
            no = lambda: False

            with mock.patch.object(V.cof, "done", yes):
                with mock.patch.object(V.cof, "cancelled", no):
                    assert V.cof.finished()

            with mock.patch.object(V.cof, "done", no):
                with mock.patch.object(V.cof, "cancelled", no):
                    assert not V.cof.finished()

            with mock.patch.object(V.cof, "done", no):
                with mock.patch.object(V.cof, "cancelled", yes):
                    assert V.cof.finished()

            with mock.patch.object(V.cof, "done", yes):
                with mock.patch.object(V.cof, "cancelled", yes):
                    assert V.cof.finished()

    describe "set_exception":
        async it "sets exception on this_fut", V:
            error = PhotonsAppError("error")
            V.cof.set_exception(error)
            assert not V.orig_fut.done()
            assert V.cof.exception() is error

    describe "done_callbacks":
        async it "callbacks are called if original future is done first", V:
            called = []

            def done(res):
                called.append(res)

            V.cof.add_done_callback(done)
            assertFutCallbacks(V.orig_fut, V.cof._parent_done_cb)
            assertFutCallbacks(V.cof.this_fut, V.cof._done_cb)

            V.orig_fut.set_result(True)
            await asyncio.sleep(0)
            assert called == [V.orig_fut]

        async it "calls callbacks only once if both this_fut and orig_fut are called", V:
            called = []

            def done(res):
                called.append(res)

            V.cof.add_done_callback(done)
            assertFutCallbacks(V.orig_fut, V.cof._parent_done_cb)
            assertFutCallbacks(V.cof.this_fut, V.cof._done_cb)

            V.cof.set_result(True)
            await asyncio.sleep(0)
            assert called == [V.cof.this_fut]

            V.orig_fut.set_result(True)
            await asyncio.sleep(0)
            assert called == [V.cof.this_fut]

        async it "does only calls callback once if this_fut is cancelled first", V:
            called = []

            def done(res):
                called.append(res)

            V.cof.add_done_callback(done)
            assertFutCallbacks(V.orig_fut, V.cof._parent_done_cb)
            assertFutCallbacks(V.cof.this_fut, V.cof._done_cb)

            V.cof.cancel()
            await asyncio.sleep(0)
            assert called == [V.cof.this_fut]

            V.orig_fut.cancel()
            await asyncio.sleep(0)
            assert called == [V.cof.this_fut]

        async it "works with multiple callbacks", V:
            called = []

            def done(res):
                called.append(res)

            def done2(res):
                called.append((2, res))

            V.cof.add_done_callback(done)
            V.cof.add_done_callback(done2)

            assertFutCallbacks(V.orig_fut, V.cof._parent_done_cb)
            assertFutCallbacks(V.cof.this_fut, V.cof._done_cb)

            V.cof.set_result(True)
            await asyncio.sleep(0)
            assert called == [V.cof.this_fut, (2, V.cof.this_fut)]

        async it "calls callback if parent is killed first", V:
            called = []

            def done(res):
                called.append(res)

            V.cof.add_done_callback(done)
            assertFutCallbacks(V.orig_fut, V.cof._parent_done_cb)
            assertFutCallbacks(V.cof.this_fut, V.cof._done_cb)

            V.orig_fut.cancel()
            await asyncio.sleep(0)
            assert called == [V.orig_fut]

    describe "removing a done callback":
        async it "removes from cof.done_callbacks", V:
            cb = mock.Mock(name="cb")
            cb2 = mock.Mock(name="cb2")

            assert V.cof.done_callbacks == []

            V.cof.add_done_callback(cb)
            assert V.cof.done_callbacks == [cb]

            V.cof.add_done_callback(cb2)
            assert V.cof.done_callbacks == [cb, cb2]

            V.cof.remove_done_callback(cb)
            assert V.cof.done_callbacks == [cb2]

            V.cof.remove_done_callback(cb2)
            assert V.cof.done_callbacks == []

            V.cof.add_done_callback(V.cof._parent_done_cb)
            assert V.cof.done_callbacks == [V.cof._parent_done_cb]

            other = lambda: 1
            V.cof.add_done_callback(other)
            assert V.cof.done_callbacks == [V.cof._parent_done_cb, other]

            V.cof.remove_done_callback(V.cof._parent_done_cb)
            assert V.cof.done_callbacks == [other]

            V.cof.remove_done_callback(other)
            assert V.cof.done_callbacks == []

        async it "removes callback from the futures if no more callbacks", V:
            assertFutCallbacks(V.orig_fut)
            assertFutCallbacks(V.cof.this_fut)

            cb = mock.Mock(name="cb")
            cb2 = mock.Mock(name="c2")

            assert V.cof.done_callbacks == []

            V.cof.add_done_callback(cb)
            assert V.cof.done_callbacks == [cb]
            assertFutCallbacks(V.orig_fut, V.cof._parent_done_cb)
            assertFutCallbacks(V.cof.this_fut, V.cof._done_cb)

            V.cof.add_done_callback(cb2)
            assert V.cof.done_callbacks == [cb, cb2]
            assertFutCallbacks(V.orig_fut, V.cof._parent_done_cb)
            assertFutCallbacks(V.cof.this_fut, V.cof._done_cb)

            V.cof.remove_done_callback(cb)
            assert V.cof.done_callbacks == [cb2]
            assertFutCallbacks(V.orig_fut, V.cof._parent_done_cb)
            assertFutCallbacks(V.cof.this_fut, V.cof._done_cb)

            V.cof.remove_done_callback(cb2)
            assert V.cof.done_callbacks == []
            assertFutCallbacks(V.orig_fut)
            assertFutCallbacks(V.cof.this_fut)

    describe "repr":
        async it "gives repr for both futures":

            class OFut:
                def __repr__(s):
                    return "OFUT"

            class Fut:
                def __repr__(s):
                    return "TFUT"

            fut = hp.ChildOfFuture(OFut())
            fut.this_fut = Fut()
            assert repr(fut) == "<ChildOfFuture: OFUT |:| TFUT>"

    describe "awaiting":

        @pytest.fixture()
        def waiting_for(self, V, loop):
            def waiting_for(res):
                async def waiter():
                    return await V.cof

                class Waiter:
                    async def __aenter__(s):
                        V.task = loop.create_task(waiter())
                        return

                    async def __aexit__(s, exc_type, exc, tb):
                        if exc:
                            return False

                        if res is asyncio.CancelledError:
                            with assertRaises(res):
                                await V.task
                        elif type(res) is PhotonsAppError:
                            with assertRaises(PhotonsAppError, res.message):
                                await V.task
                        else:
                            assert (await V.task) == res

                return Waiter()

            return waiting_for

        async it "returns result from this_fut if that goes first", waiting_for, V:
            res = mock.Mock(name="res")
            async with waiting_for(res):
                V.cof.set_result(res)

        async it "cancels this_fut if original fut gets a result", waiting_for, V:
            res = mock.Mock(name="res")
            async with waiting_for(asyncio.CancelledError):
                V.orig_fut.set_result(res)

        async it "returns result from this_fut if that cancels first", waiting_for, V:
            async with waiting_for(asyncio.CancelledError):
                V.cof.cancel()

        async it "returns result from orig_fut if that goes first", waiting_for, V:
            async with waiting_for(asyncio.CancelledError):
                V.orig_fut.cancel()

        async it "returns result from this_fut if that exceptions first", waiting_for, V:
            error = PhotonsAppError("fail")
            async with waiting_for(error):
                V.cof.set_exception(error)

describe "fut_has_callback":
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

describe "async_as_normal":
    async it "returns a function that spawns the coroutine as a task":

        async def func(one, two, three=None):
            return "{0}.{1}.{2}".format(one, two, three)

        normal = hp.async_as_normal(func)
        t = normal(1, 2, three=4)
        assert isinstance(t, asyncio.Task)
        assert await t == "1.2.4"

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
        fut = asyncio.Future()
        fut.cancel()
        assert hp.silent_reporter(fut) is None

    async it "does nothing if the future has an exception":
        fut = asyncio.Future()
        fut.set_exception(Exception("wat"))
        assert hp.silent_reporter(fut) is None

    async it "returns true if we have a result":
        fut = asyncio.Future()
        fut.set_result(mock.Mock(name="result"))
        assert hp.silent_reporter(fut) is True

describe "reporter":
    async it "does nothing if the future was cancelled":
        fut = asyncio.Future()
        fut.cancel()
        assert hp.reporter(fut) is None

    async it "does nothing if the future has an exception":
        fut = asyncio.Future()
        fut.set_exception(Exception("wat"))
        assert hp.reporter(fut) is None

    async it "returns true if we have a result":
        fut = asyncio.Future()
        fut.set_result(mock.Mock(name="result"))
        assert hp.reporter(fut) is True

describe "transfer_result":
    async it "works as a done_callback", loop:
        fut = asyncio.Future()

        async def doit():
            return [1, 2]

        t = loop.create_task(doit())
        t.add_done_callback(hp.transfer_result(fut))
        await t

        assert fut.result() == [1, 2]

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
            assert fut.exception() == error

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
            assert fut.exception() == error

        async it "transfers result":
            fut = asyncio.Future()
            res = asyncio.Future()
            res.set_result([1, 2])

            hp.transfer_result(fut, errors_only=False)(res)
            assert fut.result() == [1, 2]

describe "noncancelled_results_from_futs":
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

        assert hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4]) == (
            None,
            [result1, result2],
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

        assert hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4]) == (error1, [result2])

    async it "squashes the same error into one error":
        fut1 = asyncio.Future()
        fut2 = asyncio.Future()
        fut3 = asyncio.Future()
        fut4 = asyncio.Future()

        error1 = PhotonsAppError("wat", one=1)
        error2 = PhotonsAppError("wat", one=1)

        fut2.set_exception(error1)
        fut3.cancel()
        fut4.set_exception(error2)

        assert hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4]) == (error1, [])

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

        assert hp.noncancelled_results_from_futs([fut1, fut2, fut3, fut4, fut5]) == (
            PhotonsAppError(_errors=[error1, error2]),
            [result2],
        )

describe "find_and_apply_result":

    @pytest.fixture()
    def V(self):
        class V:
            fut1 = asyncio.Future()
            fut2 = asyncio.Future()
            fut3 = asyncio.Future()
            fut4 = asyncio.Future()
            final_fut = asyncio.Future()

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
