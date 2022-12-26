# coding: spec

from photons_canvas import orientation
from photons_canvas.orientation import Orientation as O

describe "rotated_index":
    it "works":
        testcases = [
            (0, O.RightSideUp, 0),
            (0, O.FaceUp, 0),
            (0, O.FaceDown, 0),
            (0, O.UpsideDown, 63),
            (0, O.RotatedLeft, 7),
            (0, O.RotatedRight, 56),
            (7, O.RightSideUp, 7),
            (7, O.FaceUp, 7),
            (7, O.FaceDown, 7),
            (7, O.UpsideDown, 56),
            (7, O.RotatedLeft, 63),
            (7, O.RotatedRight, 0),
        ]

        for i, o, expected in testcases:
            got = orientation.rotated_index(i, o)
            assert (
                got == expected
            ), f"Rotated {i} to {got} instead of {expected} with orientation {o.name}"

describe "reverse_orientation":
    it "works":
        testcases = [
            (O.RightSideUp, O.RightSideUp),
            (O.FaceUp, O.FaceUp),
            (O.FaceDown, O.FaceDown),
            (O.UpsideDown, O.UpsideDown),
            (O.RotatedLeft, O.RotatedRight),
            (O.RotatedRight, O.RotatedLeft),
        ]

        for o, expected in testcases:
            got = orientation.reverse_orientation(o)
            assert (
                got is expected
            ), f"Expected reverse of {o.name} to be {expected.name}, got {got.name}"

describe "nearest_orientation":
    it "works":
        testcases = [
            # empty
            (0, 0, 0, O.RightSideUp),
            # invalid
            (-1, -1, -1, O.RightSideUp),
            (1, -10, 5, O.RightSideUp),
            (-10, 1, 5, O.RotatedLeft),
            (10, 1, 5, O.RotatedRight),
            (1, 5, -10, O.FaceUp),
            (1, 5, 10, O.FaceDown),
        ]

        for x, y, z, expected in testcases:
            got = orientation.nearest_orientation(x, y, z)
            assert (
                got is expected
            ), f"Expected accel meas ({x}, {y}, {x}) to be orientated {expected.name}, got {got.name}"

describe "reorient":
    it "does nothing if it doesn't need to":
        colors = list(range(64))
        for o in (O.RightSideUp, O.FaceUp, O.FaceDown):
            assert orientation.reorient(colors, o) == colors

    it "can fix a rotated left tile":
        _ = "_"
        h = "#"

        # fmt: off

        colors = [
              _, _, _, h, _, _, _, _
            , _, _, h, _, h, _, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            ]

        expected = [
              _, _, _, _, _, _, _, _
            , h, h, h, h, h, h, _, _
            , _, _, _, _, _, _, h, _
            , _, _, _, _, _, _, _, h
            , _, _, _, _, _, _, h, _
            , h, h, h, h, h, h, _, _
            , _, _, _, _, _, _, _, _
            , _, _, _, _, _, _, _, _
            ]
        # fmt: on

        assert orientation.reorient(colors, O.RotatedLeft) == expected

    it "can fix a rotated right tile":
        _ = "_"
        h = "#"

        # fmt: off

        colors = [
              _, _, _, h, _, _, _, _
            , _, _, h, _, h, _, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            ]

        expected = [
              _, _, _, _, _, _, _, _
            , _, _, _, _, _, _, _, _
            , _, _, h, h, h, h, h, h
            , _, h, _, _, _, _, _, _
            , h, _, _, _, _, _, _, _
            , _, h, _, _, _, _, _, _
            , _, _, h, h, h, h, h, h
            , _, _, _, _, _, _, _, _
            ]

        # fmt: on

        assert orientation.reorient(colors, O.RotatedRight) == expected

    it "can fix an upside down tile":
        _ = "_"
        h = "#"

        # fmt: off

        colors = [
              _, _, _, h, _, _, _, _
            , _, _, h, _, h, _, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            , _, h, _, _, _, h, _, _
            ]

        expected = [
              _, _, h, _, _, _, h, _
            , _, _, h, _, _, _, h, _
            , _, _, h, _, _, _, h, _
            , _, _, h, _, _, _, h, _
            , _, _, h, _, _, _, h, _
            , _, _, h, _, _, _, h, _
            , _, _, _, h, _, h, _, _
            , _, _, _, _, h, _, _, _
            ]

        # fmt: on

        assert orientation.reorient(colors, O.UpsideDown) == expected
