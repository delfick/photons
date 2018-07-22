from photons_app import helpers as hp

import asyncio
import logging
import time

log = logging.getLogger("photons_transport.target.waiter")

class FutPair(object):
    """
    A future who takes in a future that resolves to two futures.

    This future is cancelled or raises an error if any of these futures are
    cancelled or raise an error.

    This future eventually resolves to the result of the second result future if
    the first result future is also resolved.

    So say we have:

    .. code-block:: python

        import asyncio

        final_fut1 = asyncio.Future()
        final_fut2 = asyncio.Future()

        fut = asyncio.Future()
        fut.set_result((final_fut1, final_fut2))

    Then:

    .. code-block:: python

        final = FutPair(fut)

        final_fut1.set_result(True)
        final_fut1.set_result(final_result)

        assert (await final) is final_result
    """
    def __init__(self, parentfut):
        self.final = asyncio.Future()
        self.parentfut = parentfut
        self.done_callbacks = []
        self.ack_time = 0
        self.set_final_cb()

    @property
    def loop(self):
        return asyncio.get_event_loop()

    def set_final_cb(self):
        """Make sure we setup our callbacks, otherwise final will never be completed"""
        if self.parentfut.done():
            self.done_callbacks.append(self.set_final)
            self._parent_done_cb(self.parentfut)
        else:
            self.add_done_callback(self.set_final)

    def add_done_callback(self, func):
        """
        Ensure func gets put onto the loop when the FutPair is done.

        This means if our parentfut is not done, it gets registered in
        done_callback and used when parentfut and subsequent res_fut is done.

        Otherwise, if parentfut is already finished and the ack_fut is already finished,
        we may have missed the boat with the _parent_done_cb we add to the ack,
        so we put the func straight onto the res_fut itself
        """
        if self.parentfut.done() and not self.parentfut.cancelled():
            if self.parentfut.exception():
                self.loop.call_soon(func, self.parentfut)
            else:
                ack_fut, res_fut = self.parentfut.result()
                if ack_fut.done():
                    res_fut.add_done_callback(func)
                    return

        self.done_callbacks.append(func)
        if not hp.fut_has_callback(self.parentfut, self._parent_done_cb):
            self.parentfut.add_done_callback(self._parent_done_cb)

    def set_final(self, res):
        """
        This callback is called on the completion of FutPair, as registered
        by the __init__

        Essentially it's just transferring the result from the res_fut onto the
        self.final future.

        We also protect against setting a result on the final when it already has
        a result or cancellation.
        """
        if not self.final.cancelled() and not self.final.done():
            if res.cancelled():
                self.final.cancel()
            else:
                exc = res.exception()
                if exc:
                    self.final.set_exception(exc)
                else:
                    self.final.set_result(res.result())

    def remove_done_callback(self, func):
        self.done_callbacks = [cb for cb in self.done_callbacks if cb is not func]
        if not self.parentfut.cancelled() and self.parentfut.done():
            ack_fut, res_fut = self.parentfut.result()
            res_fut.remove_done_callback(func)

    def _parent_done_cb(self, res):
        """
        Register self._done_ack onto the ack_fut

        Also call and empty out our done_callbacks on cancellation/exception
        """
        if res.cancelled():
            self.cancel()
            while self.done_callbacks:
                cb = self.done_callbacks.pop(0)
                self.loop.call_soon(cb, res)

        elif res.exception():
            if not self.done():
                self.set_exception(res.exception())
                while self.done_callbacks:
                    cb = self.done_callbacks.pop(0)
                    self.loop.call_soon(cb, res)

        else:
            ack_fut, res_fut = res.result()
            if not hp.fut_has_callback(ack_fut, self._done_ack):
                ack_fut.add_done_callback(self._done_ack)

    def _done_ack(self, res):
        """
        Set self.ack_time if our ack_fut result is not False
        (False is set for acks that are not needed)

        And add all the done_callbacks to res_fut

        if ack_fut is cancelled, we shall also cancel res_fut and the futpair
        """
        if not res.cancelled() and not res.exception() and res.result() is not False:
            self.ack_time = time.time()

        if not self.parentfut.cancelled() and self.parentfut.done():
            ack_fut, res_fut = self.parentfut.result()

            # Empty out done_callbacks so if _done_ack gets called again
            # We don't re-add cbs to the res_fut
            while self.done_callbacks:
                cb = self.done_callbacks.pop(0)
                res_fut.add_done_callback(cb)

        if res.cancelled():
            self.cancel()
            return

        if res.exception() and not self.done():
            self.set_exception(res.exception())

    def cancel(self):
        if self.parentfut.done() and not self.parentfut.cancelled() and not self.parentfut.exception():
            ack_fut, res_fut = self.parentfut.result()
            ack_fut.cancel()
            res_fut.cancel()
        self.parentfut.cancel()
        self.final.cancel()

    def cancelled(self):
        if self.final.done() and not self.final.cancelled():
            return False

        if self.parentfut.cancelled():
            return True

        if self.parentfut.done() and not self.parentfut.exception():
            ack_fut, res_fut = self.parentfut.result()
            if ack_fut.cancelled() or res_fut.cancelled():
                return True

        return self.final.cancelled()

    def done(self):
        return self.final.done()

    def partial(self):
        return self.ack_time

    def exception(self):
        return self.final.exception()

    def set_exception(self, exc):
        if not self.parentfut.done() and not self.parentfut.cancelled():
            self.parentfut.set_exception(exc)

        elif self.parentfut.done() and not self.parentfut.exception():
            ack_fut, res_fut = self.parentfut.result()
            if not ack_fut.done() and not ack_fut.cancelled():
                ack_fut.set_exception(exc)
            if not res_fut.done() and not res_fut.cancelled():
                res_fut.set_exception(exc)

        self.final.set_exception(exc)

    def set_result(self, data):
        """
        Sets a result on final.

        Also cancels parentfut or ack_fut/res_fut if parentfut is already done

        This is because we are preferring the result from this call over whatever
        those futures provide, so we should stop them
        """
        self.final.set_result(data)

        if not self.parentfut.done() and not self.parentfut.cancelled():
            # hmm, is this the right thing to do?
            self.parentfut.cancel()

        elif self.parentfut.done():
            ack_fut, res_fut = self.parentfut.result()
            if not ack_fut.done() and not ack_fut.cancelled():
                ack_fut.cancel()
            if not res_fut.done() and not res_fut.cancelled():
                res_fut.cancel()

    def result(self):
        return self.final.result()

    def __repr__(self):
        if self.parentfut.cancelled() or not self.parentfut.done():
            return "<FutPair {0}>".format(repr(self.parentfut))
        else:
            ack_fut, res_fut = self.parentfut.result()
            return "<FutPair {0} |:| {1}>".format(repr(ack_fut), repr(res_fut))

    def __await__(self):
        return (yield from self.final)
    __iter__ = __await__

class Waiter(object):
    """
    Keep writing till we get a response!

    It's up to the caller to cancel this if we take too long

    This object is a future, the result of which is the final response from our
    writer.

    We expect to get back ``(ack_fut, res_fut)`` from ``writer`` which we create
    a ``FutPair`` from. We keep collecting these until one of the ``FutPair``
    resolves and we have a result.

    When this happens we set the result/error/cancellation on all the other
    futures that were created in the process.

    We keep writing writer with an exponential backoff.
    """
    def __init__(self, stop_fut, writer
        , first_resend=0.1, first_wait=0.1
        ):
        self.writer = writer

        self.futs = []
        self.timeouts = [first_wait, first_resend]
        self.final_future = hp.ChildOfFuture(stop_fut)

        def ignore(f):
            # Make sure we don't leak tasks
            if hasattr(self, "_writings"):
                self._writings.cancel()
                del self._writings
                del self._writings_cb
            self.futs = []

            # I don't care about the exception from final_future
            if not f.cancelled():
                f.exception()
        self.final_future.add_done_callback(ignore)

        self.next_time = None

    def cancel(self):
        self.final_future.cancel()

    def set_exception(self, exc):
        self.final_future.set_exception(exc)

    def cancelled(self):
        return self.final_future.cancelled()

    def done(self):
        return self.final_future.done()

    def result(self):
        return self.final_future.result()

    def exception(self):
        return self.final_future.exception()

    def __await__(self):
        # Protect against starting multiple writings tasks
        if not hasattr(self, "_writings"):
            self._writings = hp.async_as_background(self.writings())

        return (yield from self.final_future)

    @hp.memoized_property
    def _writings_cb(self):
        return hp.async_as_normal(self.writings)

    async def writings(self, *args):
        """
        Keep writing till we fulfill that future!!!
        """
        if args:
            # prevent "Task exception was never retrieved" errors
            args[0].exception()

        if self.final_future.done() or self.final_future.cancelled():
            return

        if self.futs:
            # Find a value in our futs and set it everywhere
            hp.find_and_apply_result(self.final_future, self.futs)

        if self.final_future.cancelled():
            for f in self.futs:
                f.cancel()
            return

        if self.final_future.done():
            return

        loop = asyncio.get_event_loop()

        if self.next_time is None or time.time() > self.next_time:
            if any(time.time() - fut.partial() < 5 for fut in self.futs):
                log.info("Got a partial result, waiting till next write")
            else:
                await self.writer.ensure_conn()
                self.futs.append(self.do_write())
            self.next_time = self.determine_next_time()

        loop.call_later(self.next_time - time.time(), self._writings_cb)

    def do_write(self):
        fut = FutPair(asyncio.ensure_future(self.writer()))
        fut.add_done_callback(self._writings_cb)
        return fut

    def determine_next_time(self):
        """
        Determine when to write next.

        We are super optimistic at first, and lose interest quickly
        """
        if len(self.timeouts) > 1:
            timeout = self.timeouts.pop(0)
        else:
            timeout = self.timeouts[0]
            if timeout < 0.1:
                timeout += 0.05
            elif timeout < 0.3:
                timeout += 0.1
            elif timeout < 5:
                timeout += 0.5
            elif timeout > 5:
                timeout += 5
            self.timeouts[0] = timeout

        return time.time() + timeout
