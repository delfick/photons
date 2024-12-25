from photons_canvas import orientation
from photons_canvas.orientation import Orientation as O


class TestRotatedIndex:
    def test_it_works(self):
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


class TestReverseOrientation:
    def test_it_works(self):
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


class TestNearestOrientation:
    def test_it_works(self):
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


class TestReorient:
    def test_it_does_nothing_if_it_doesnt_need_to(self):
        colors = list(range(64))
        for o in (O.RightSideUp, O.FaceUp, O.FaceDown):
            assert orientation.reorient(colors, o) == colors

    def test_it_can_fix_a_rotated_left_tile(self):
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

    def test_it_can_fix_a_rotated_right_tile(self):
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

    def test_it_can_fix_an_upside_down_tile(self):
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
