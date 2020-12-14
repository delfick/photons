from photons_app import helpers as hp

from delfick_project.norms import dictobj, sb
import time


def Gaps(*, gap_between_results, gap_between_ack_and_res, timeouts):
    default_timeouts = timeouts
    default_gap_between_results = gap_between_results
    default_gap_between_ack_and_res = gap_between_ack_and_res

    class tuple_spec(sb.Spec):
        def setup(self, *specs):
            self.spec = sb.tuple_spec(*specs)

        def normalise_filled(self, meta, val):
            if isinstance(val, list):
                val = tuple(val)
            return self.spec.normalise(meta, val)

    class timeouts_default_spec(sb.Spec):
        def normalise_empty(self, meta):
            return default_timeouts

        def normalise_filled(self, meta, val):
            return sb.listof(tuple_spec(sb.float_spec(), sb.float_spec())).normalise(meta, val)

    class ResultGaps(dictobj.Spec):
        gap_between_results = dictobj.Field(
            sb.float_spec,
            default=default_gap_between_results,
            help="""
            When a packet has an unbound number of results we uses this number to
            determine when we have enough results. Essentially the answer is yes if
            it's been this long since the last result
            """,
        )

        gap_between_ack_and_res = dictobj.Field(
            sb.float_spec,
            default=default_gap_between_ack_and_res,
            help="""
            When a packet has a received an acknowledgment but not a result, this
            number is used to determine if we should wait for the result or send
            the request again.

            i.e. only send a retry if it's been longer than this time since the
            acknowledgement
            """,
        )

        timeouts = dictobj.Field(
            timeouts_default_spec,
            help="""
            A list of (step, end) tuples that is used to determine the retry backoff.

            Essentially, starting with the first step, increase by step until you
            reach end and then use the next tuple to determine backoff from there.

            So ``[(0.1, 0.1), (0.2, 0.5), (0.5, 3)]`` would go
            ``0.1, 0.3, 0.5, 1, 1.5, 2, 2.5, 3, 3, 3, ...``
            """,
        )

        @property
        def finish_multi_gap(self):
            """
            When a packet has an unbound number of results or acks, this number is
            used to schedule the next check to see if we should finish this result

            This defaults to being ``gap_between_results + 0.05``
            """
            return self.gap_between_results + 0.05

        def retry_ticker(self, name=None):
            return RetryTicker(timeouts=self.timeouts, name=name)

    return ResultGaps.FieldSpec()


class RetryTicker:
    def __init__(self, *, timeouts, name=None):
        self.name = name
        self.timeouts = timeouts

        self.timeout = None
        self.timeout_item = None

    async def tick(self, final_future, timeout, min_wait=0.1):
        timeouts = list(self.timeouts)
        step, end = timeouts.pop(0)
        ticker = hp.ATicker(
            every=step,
            final_future=final_future,
            max_time=timeout,
            min_wait=min_wait,
            name=f"RetryTicker({self.name})::tick[ticker]",
        )

        start = time.time()
        final_time = time.time() + timeout

        async with ticker as ticks:
            async for _, nxt in ticks:
                now = time.time()

                if end and now - start > end:
                    if timeouts:
                        step, end = timeouts.pop(0)
                        ticker.change_after(step)
                    else:
                        end = None

                yield round(final_time - now, 3), nxt
