from photons_app import helpers as hp

import asyncio
import logging

log = logging.getLogger("photons_transport.target.waiter")

class Waiter(object):
    """
    Keep writing till we get a response!

    It's up to the caller to cancel this if we take too long

    This object is a future, the result of which is the final response from our
    writer.

    We keep using writer until we have a result that is complete.

    When this happens we set the result/error/cancellation on all the other
    futures that were created in the process.

    We keep writing writer with an exponential backoff.
    """
    def __init__(self, stop_fut, writer, retry_options):
        self.writer = writer

        self.results = []
        self.retry_options = retry_options
        self.final_future = hp.ChildOfFuture(stop_fut)

        def ignore(f):
            # Make sure we don't leak tasks
            if hasattr(self, "_writings"):
                self._writings.cancel()
                del self._writings
                del self._writings_cb
            self.results = []

            # I don't care about the exception from final_future
            if not f.cancelled():
                f.exception()
        self.add_done_callback(ignore)

    def add_done_callback(self, cb):
        self.final_future.add_done_callback(cb)

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

        There are four cases where this function gets called:

        * When we start awaiting for this waiter
        * retry_options.next_time after a write is done
        * retry_options.next_check_after_wait_for_result after detecting a partial result
        * When a result is done
        """
        if args:
            # prevent "Task exception was never retrieved" errors
            args[0].exception()

        if self.results:
            # Find a value in our futs and set it everywhere
            hp.find_and_apply_result(self.final_future, self.results)

        if self.final_future.done():
            return

        loop = asyncio.get_event_loop()

        if any(result.wait_for_result() for result in self.results):
            next_check = self.retry_options.next_check_after_wait_for_result
            loop.call_later(next_check, self._writings_cb)
            return

        t = loop.create_task(self.do_write())
        t.add_done_callback(hp.transfer_result(self.final_future, errors_only=True))

        loop.call_later(self.retry_options.next_time, self._writings_cb)

    async def do_write(self):
        """
        Use our write to ensure we have a connection and then get a result
        object by writing to our device.

        If the result object is already done then we call _writings_cb straight
        away, otherwise we tell the result object to call _writigs_cb when it's
        done
        """
        await self.writer.ensure_conn()

        result = await self.writer()
        self.results.append(result)

        if result.done():
            asyncio.get_event_loop().call_soon(self._writings_cb)
        else:
            result.add_done_callback(self._writings_cb)
