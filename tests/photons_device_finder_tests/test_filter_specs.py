# coding: spec

from photons_device_finder import boolean, str_ranges

from photons_app.test_helpers import TestCase

from delfick_project.norms import Meta, BadSpecValue

describe TestCase, "boolean":
    it "transforms int into a boolean":
        self.assertEqual(boolean().normalise(Meta.empty(), 0), False)
        for i in (1, 20, 100):
            self.assertEqual(boolean().normalise(Meta.empty(), i), True)

    it "transforms a str into boolean":
        for s in ("no", "false", "No", "NO", "False", "FALSE"):
            self.assertEqual(boolean().normalise(Meta.empty(), s), False)

        for s in ("yes", "true", "True", "TRUE", "YES"):
            self.assertEqual(boolean().normalise(Meta.empty(), s), True)

    it "passes through booleans":
        self.assertEqual(boolean().normalise(Meta.empty(), False), False)
        self.assertEqual(boolean().normalise(Meta.empty(), True), True)

    it "complains about anything else":

        class Wat:
            pass

        for thing in ([], [1], {}, {1: 2}, lambda: 1, Wat, Wat()):
            with self.fuzzyAssertRaisesError(BadSpecValue):
                boolean().normalise(Meta.empty(), thing)

describe TestCase, "str_ranges":
    it "converts comma separated pairs into list of tuples":
        wanted = "1-2,3-5.5,5,6.7-9,10.1-45.6"
        got = str_ranges().normalise(Meta.empty(), wanted)
        self.assertEqual(got, [(1.0, 2.0), (3.0, 5.5), (5.0, 5.0), (6.7, 9.0), (10.1, 45.6)])

    it "can take in list of tuples":
        wanted = [(1.0, 2.0), (3.0, 5.5), (5.0, 5.0), (6.7, 9.0), (10.1, 45.6)]
        got = str_ranges().normalise(Meta.empty(), wanted)
        self.assertEqual(wanted, got)

    it "can take in list of strings":
        provided = ["1.0-2.0", "3.0-5.5", "5.0", "6.7-9.0", "10.1-45.6"]
        wanted = [(1.0, 2.0), (3.0, 5.5), (5.0, 5.0), (6.7, 9.0), (10.1, 45.6)]
        got = str_ranges().normalise(Meta.empty(), provided)
        self.assertEqual(wanted, got)

    it "complains if we can't make numbers":
        wanted = "1-2-3"
        try:
            str_ranges().normalise(Meta.empty(), wanted)
            assert False, "Expected an error"
        except BadSpecValue as error:
            self.assertEqual(len(error.errors), 1)
            self.assertEqual(len(error.errors[0].errors), 1)
            error = error.errors[0].errors[0]
            self.assertEqual(type(error), BadSpecValue)
            self.assertEqual(str(error.kwargs["error"]), "could not convert string to float: '2-3'")
