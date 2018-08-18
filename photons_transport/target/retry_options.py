import time

class RetryOptions:
    finish_multi_gap = 0.35
    gap_between_results = 0.4
    gap_between_ack_and_res = 0.2

    next_check_after_wait_for_result = 0.15

    timeouts = [(0.1, 0.1), (0.05, 0.3), (0.1, 1), (1, 5)]

    def __init__(self):
        self.timeout = None
        self.timeout_item = None

    @property
    def next_time(self):
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
