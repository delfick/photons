# coding: spec

from photons_transport.target.retry_options import RetryOptions

from photons_app.test_helpers import TestCase

describe TestCase, "RetryOptions":
    it "has some options":
        options = RetryOptions()
        for attr in ("finish_multi_gap", "gap_between_results", "gap_between_ack_and_res", "next_check_after_wait_for_result"):
            self.assertEqual(type(getattr(options, attr)), float)
            self.assertGreater(getattr(options, attr), 0)

        self.assertEqual(type(options.timeouts), list)
        for i, thing in enumerate(options.timeouts):
            self.assertEqual(type(thing), tuple, f"Item {i} is not a tuple: {thing}")
            self.assertEqual(len(thing), 2, f"Item {i} is not length two: {thing}")
            assert all(type(t) in (float, int) for t in thing), f"Item {i} has not numbers: {thing}"

        self.assertIs(options.timeout, None)
        self.assertIs(options.timeout_item, None)

    describe "next_time":
        it "returns first time from timeouts if first time":
            self.assertEqual(RetryOptions().next_time, 0.2)

            class Options(RetryOptions):
                timeouts = [(0.3, 0.4)]
            self.assertEqual(Options().next_time, 0.3)

        it "keeps adding step till we get past end, before going to next timeout item":
            class Options(RetryOptions):
                timeouts = [(0.1, 0.1), (0.2, 0.5), (0.3, 0.9), (1, 5)]

            options = Options()
            expected = [0.1, 0.3, 0.5, 0.8, 1.1, 2.1, 3.1, 4.1, 5.1, 5.1, 5.1]

            for i, want in enumerate(expected):
                nxt = options.next_time
                self.assertAlmostEqual(nxt, want, 3, f"Expected item {i} to be {want}, got {nxt}")
