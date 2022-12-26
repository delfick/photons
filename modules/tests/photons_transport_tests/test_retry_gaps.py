# coding: spec

from photons_transport.retry_options import Gaps

describe "Gaps":
    it "can be given defaults":
        gaps = Gaps(gap_between_ack_and_res=0.5, gap_between_results=0.9, timeouts=[(0.1, 0.5)])
        obj = gaps.empty_normalise()

        assert obj.gap_between_ack_and_res == 0.5
        assert obj.gap_between_results == 0.9
        assert obj.timeouts == [(0.1, 0.5)]

        obj = gaps.empty_normalise(
            gap_between_ack_and_res=0.2, gap_between_results=0.1, timeouts=[(0.1, 0.6), (0.5, 3)]
        )

        assert obj.gap_between_ack_and_res == 0.2
        assert obj.gap_between_results == 0.1
        assert obj.timeouts == [(0.1, 0.6), (0.5, 3)]

    it "can make a retry ticker":
        gaps = Gaps(gap_between_ack_and_res=0.5, gap_between_results=0.9, timeouts=[(0.1, 0.5)])
        obj = gaps.empty_normalise()

        ticker = obj.retry_ticker(name="hello")
        assert ticker.name == "hello"
        assert ticker.timeouts == [(0.1, 0.5)]

        obj = gaps.empty_normalise(
            gap_between_ack_and_res=0.2, gap_between_results=0.1, timeouts=[[0.1, 0.6], [0.5, 3]]
        )

        ticker = obj.retry_ticker(name="there")
        assert ticker.name == "there"
        assert ticker.timeouts == [(0.1, 0.6), (0.5, 3)]
