# coding: spec

from photons_control.device_finder import boolean, str_ranges

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta, BadSpecValue

describe "boolean":
    it "transforms int into a boolean":
        spec = boolean()
        meta = Meta.empty()

        assert spec.normalise(meta, 0) is False
        assert spec.normalise(meta, [0]) is False
        for i in (1, 20, 100):
            assert spec.normalise(meta, i) is True
            assert spec.normalise(meta, [i]) is True

    it "transforms a str into boolean":
        spec = boolean()
        meta = Meta.empty()

        for s in ("no", "false", "No", "NO", "False", "FALSE"):
            assert spec.normalise(meta, s) is False
            assert spec.normalise(meta, [s]) is False

        for s in ("yes", "true", "True", "TRUE", "YES"):
            assert spec.normalise(meta, s) is True
            assert spec.normalise(meta, [s]) is True

    it "passes through booleans":
        spec = boolean()
        meta = Meta.empty()

        assert spec.normalise(meta, False) is False
        assert spec.normalise(meta, [False]) is False
        assert spec.normalise(meta, True) is True
        assert spec.normalise(meta, [True]) is True

    it "complains about anything else":

        class Wat:
            pass

        for thing in ([], [1, 2], [True, False], {}, {1: 2}, lambda: 1, Wat, Wat()):
            with assertRaises(BadSpecValue):
                boolean().normalise(Meta.empty(), thing)

describe "str_ranges":
    it "converts comma separated pairs into list of tuples":
        wanted = "1-2,3-5.5,5,6.7-9,10.1-45.6"
        got = str_ranges().normalise(Meta.empty(), wanted)
        assert got == [(1.0, 2.0), (3.0, 5.5), (5.0, 5.0), (6.7, 9.0), (10.1, 45.6)]

    it "can take in list of tuples":
        wanted = [(1.0, 2.0), (3.0, 5.5), (5.0, 5.0), (6.7, 9.0), (10.1, 45.6)]
        got = str_ranges().normalise(Meta.empty(), wanted)
        assert wanted == got

    it "can take in list of strings":
        provided = ["1.0-2.0", "3.0-5.5", "5.0", "6.7-9.0", "10.1-45.6"]
        wanted = [(1.0, 2.0), (3.0, 5.5), (5.0, 5.0), (6.7, 9.0), (10.1, 45.6)]
        got = str_ranges().normalise(Meta.empty(), provided)
        assert wanted == got

    it "complains if we can't make numbers":
        wanted = "1-2-3"
        try:
            str_ranges().normalise(Meta.empty(), wanted)
            assert False, "Expected an error"
        except BadSpecValue as error:
            assert len(error.errors) == 1
            assert len(error.errors[0].errors) == 1
            error = error.errors[0].errors[0]
            assert type(error) == BadSpecValue
            assert str(error.kwargs["error"]) == "could not convert string to float: '2-3'"
