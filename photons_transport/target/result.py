import asyncio
import time

class Result(asyncio.Future):
    """
    Knows about acks and results from the device. It uses the request packet to
    determine when we are done based on ack_required, res_required and multi
    options
    """
    def __init__(self, request, broadcast, retry_options):
        self.request = request
        self.broadcast = broadcast
        self.retry_options = retry_options

        self.results = []
        self.last_ack_received = None
        self.last_res_received = None

        super().__init__()

        if not self.request.ack_required and not self.request.res_required:
            self.set_result([])

    def add_packet(self, pkt, addr, broadcast):
        """Determine if we should call add_ack or add_result"""
        if getattr(pkt, "represents_ack", False):
            self.add_ack()
        else:
            self.add_result((pkt, addr, broadcast))

    def add_ack(self):
        """
        If we are already done, do nothing

        Otherwise if we don't need a result and we didn't broadcast
        , set ourselves as done

        If we did broadcast and we don't need a result then wait for the next ack
        such that if we don't get another ack before our timeout, we mark
        ourselves as done
        """
        self.last_ack_received = time.time()

        if self.done():
            return

        if not self.request.res_required:
            if self.broadcast:
                self.schedule_finisher("last_ack_received")
            else:
                self.set_result([])

    def add_result(self, result):
        """
        Add a non ack reply from the device

        If we have all the packets we want then set result ourselves
        """
        self.last_res_received = time.time()

        if self.done():
            return

        self.results.append(result)
        expected_num = self.num_results

        if expected_num > -1 and len(self.results) >= expected_num:
            self.set_result(self.results)
            return

        if expected_num == -1:
            self.schedule_finisher("last_res_received")

    def schedule_finisher(self, attr):
        """
        Schedule maybe_finish to check in the future if we are done with this
        result
        """
        current = getattr(self, attr)
        asyncio.get_event_loop().call_later(self.retry_options.finish_multi_gap, self.maybe_finish, current, attr)

    def maybe_finish(self, last, attr):
        """
        Used by schedule_finisher to finish this Result when we don't know how
        many multiple replies we are expecting.

        The idea is that when this callback is called and we haven't received
        any newer packets, then we mark this result as done
        """
        if self.done():
            return

        if getattr(self, attr) == last:
            self.set_result(self.results)

    def _determine_num_results(self):
        """
        Determine how many packets we are expecting
        """
        if self.broadcast:
            return -1

        multi = self.request.Meta.multi

        if multi is None:
            return 1

        if multi == -1:
            return -1

        if hasattr(self, "_num_results"):
            return self._num_results

        res = multi.determine_res_packet(self.request)
        if type(res) is not list:
            res = [res]
        matching = [p for p, _, _ in self.results if any(p | r for r in res)]

        if matching:
            self._num_results = multi.adjust_expected_number(self.request, matching[0])
        else:
            return -1

        return self._num_results

    @property
    def num_results(self):
        expect = self._determine_num_results()
        if type(expect) is int:
            return expect
        else:
            return expect(self.results)

    def wait_for_result(self):
        """
        Return whether we should wait for a result

        If we expect both and ack and a result then we say yes only if it's been
        less than gap_between_ack_and_res since the ack if we have received one.

        If we expect a bound number of results and it's been less than
        gap_between_results since the last result, then say yes

        If we expect an unbond number of results, only return False if we haven't
        received anything yet
        """
        if self.request.ack_required and self.request.res_required:
            if self.last_ack_received is None:
                return False

            if self.results:
                return True

            return (time.time() - self.last_ack_received) < self.retry_options.gap_between_ack_and_res

        elif self.request.ack_required and self.last_ack_received is not None:
            return True

        elif self.request.res_required:
            if self.last_res_received is None:
                return False

            if self.num_results > 0:
                return (time.time() - self.last_res_received) < self.retry_options.gap_between_results

            return True

        return False
