import asyncio
import time

class RetryIterator:
    """
    An async generator to help with retries.

    usage is like:

    .. code-block:: python

        import time

        retries = [1, 2, 3]
        def get_next_time():
            if len(retries) == 1:
                return retries[0]
            return retries.pop(0)

        end_at = time.time() + 10
        min_wait = 0.1

        async for time_left, time_till_next_retry in RetryIterator(end_at, get_next_time):
            # Do something that will take up to time_till_next_retry seconds

    The recommended way of creating one of these is via a RetryOptions object:

    .. code-block:: python

        async for time_left, time_till_next_retry in RetryOptions().iterator(end_after=10):
            # Do something that will take up to time_till_next_retry seconds

    The async generator will use get_next_time to determine the minimum amount of time to wait before
    letting the body of the loop run again. So let's say time_till_next_retry is 3 seconds and the
    body takes only 1 second, then we will wait 2 seconds before letting the body run again.

    You may also provided min_wait (defaults to 0.1). We will stop iteration if the time left till
    we should end is less than this amount. We will also use get_next_time() again if the time between
    now and the next time is less than min_wait
    """
    def __init__(self, end_at, get_next_time, min_wait=0.1, get_now=time.time):
        self.next = None
        self.end_at = end_at
        self.min_wait = min_wait
        self.get_now = get_now
        self.get_next_time = get_next_time

    def __aiter__(self):
        return self

    async def __anext__(self):
        t = self.next
        now = self.get_now()

        diff = self.end_at - now
        if diff <= self.min_wait:
            raise StopAsyncIteration

        if t is None:
            self.next = now + self.get_next_time()
            return self.end_at - now, self.next - now

        wait = t - now
        diff = self.end_at - now
        if diff - wait < self.min_wait:
            raise StopAsyncIteration

        await self.wait(wait)
        now = self.get_now()

        diff = self.end_at - now
        while self.next - now < self.min_wait:
            self.next += self.get_next_time()

        return diff, self.next - now

    async def wait(self, timeout):
        f = asyncio.Future()
        loop = asyncio.get_event_loop()
        loop.call_later(timeout, f.cancel)
        await asyncio.wait([f])

class RetryOptions:
    """
    Options for working out how long to wait for replies to our messages

    finish_multi_gap
        When a packet has an unbound number of results or acks, this number is
        used to schedule the next check to see if we should finish this result

    gap_between_results
        When a packet has an unbound number of results we uses this number to
        determine when we have enough results. Essentially the answer is yes if
        it's been this long since the last result

        It is a good idea to make this number less than finish_multi_gap so that
        when we check after a finish_multi_gap amount of time in the future we
        can mark the result as done

    gap_between_ack_and_res
        When a packet has a received an acknowledgment but not a result, this
        number is used to determine if we should wait for the result or send
        the request again.

        i.e. only send a retry if it's been longer than this time since the
        acknowledgement

    next_check_after_wait_for_result
        If we should wait for the next reply instead of sending a retry, then
        we use this time to schedule the next check.

    timeouts
        A list of (step, end) tuples that is used to determine the retry backoff.

        This is used by the ``next_time`` property on this object.

        Essentially, starting with the first step, increase by step until you
        reach end and then use the next tuple to determine backoff from there.

        So ``[(0.1, 0.1), (0.2, 0.5), (0.5, 3)]`` would go
        ``0.1, 0.3, 0.5, 1, 1.5, 2, 2.5, 3, 3, 3, ...``
    """
    finish_multi_gap = 0.4
    gap_between_results = 0.35
    gap_between_ack_and_res = 0.2

    next_check_after_wait_for_result = 0.15

    timeouts = [(0.2, 0.2), (0.1, 0.5), (0.2, 1), (1, 5)]

    def __init__(self, timeouts=None):
        self.timeout = None
        self.timeout_item = None
        if timeouts is not None:
            self.timeouts = timeouts

    @property
    def next_time(self):
        """
        Return the next backoff time
        """
        if self.timeout_item is None:
            self.timeout_item = 0

        if self.timeout is None:
            self.timeout = self.timeouts[self.timeout_item][0]
            return self.timeout

        step, end = self.timeouts[self.timeout_item]
        if self.timeout >= end:
            if self.timeout_item == len(self.timeouts) - 1:
                return self.timeout

            self.timeout_item += 1
            step, end = self.timeouts[self.timeout_item]

        self.timeout += step
        return self.timeout

    def iterator(self, *, end_after, min_wait=0.1, get_now=time.time):
        end_at = get_now() + end_after
        return RetryIterator(end_at, lambda: self.next_time, min_wait=min_wait, get_now=get_now)
