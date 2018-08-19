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

    def __init__(self):
        self.timeout = None
        self.timeout_item = None

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
