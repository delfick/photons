import pytest
from photons_canvas.points import helpers as php


class TestColor:
    def test_it_has_ZERO(self):
        assert php.Color.ZERO == (0, 0, 0, 0)

    def test_it_has_WHITE(self):
        assert php.Color.WHITE == (0, 0, 1, 3500)

    def test_it_has_EMPTIES(self):
        assert php.Color.EMPTIES == (php.Color.ZERO, None)

    def test_it_can_tell_if_a_color_is_dead(self):
        assert php.Color.dead(None)
        assert php.Color.dead((0, 0, 0, 0))
        assert php.Color.dead((40, 1, 0, 3500))

        assert not php.Color.dead((1, 0, 0.2, 0))
        assert not php.Color.dead((40, 1, 0.1, 3500))

    class TestOverrideAColor:
        def test_it_does_nothing_if_no_overrides(self):
            color = (0, 1, 2, 3)
            assert php.Color.override(color) is color

        def test_it_can_override_properties(self):
            color = (0, 1, 2, 3)

            assert php.Color.override(color, hue=20) == (20, 1, 2, 3)

            assert php.Color.override(color, saturation=0.5) == (0, 0.5, 2, 3)

            assert php.Color.override(color, brightness=0.5) == (0, 1, 0.5, 3)

            assert php.Color.override(color, kelvin=20) == (0, 1, 2, 20)

            assert php.Color.override(
                color, hue=30, saturation=0.9, brightness=0.1, kelvin=9000
            ) == (30, 0.9, 0.1, 9000)

        def test_it_doesnt_allow_out_of_limits(self):
            color = (40, 1, 2, 3)

            assert php.Color.override(color, hue=-1) == (0, 1, 2, 3)
            assert php.Color.override(color, saturation=-1) == (40, 0, 2, 3)
            assert php.Color.override(color, brightness=-1) == (40, 1, 0, 3)
            assert php.Color.override(color, kelvin=-1) == (40, 1, 2, 0)

            want = (0, 0, 0, 0)
            assert (
                php.Color.override(color, hue=-1, saturation=-1, brightness=-1, kelvin=-1) == want
            )
            assert php.Color.override(color, hue=361) == (360, 1, 2, 3)
            assert php.Color.override(color, saturation=1.1) == (40, 1, 2, 3)
            assert php.Color.override(color, brightness=1.1) == (40, 1, 1, 3)
            assert php.Color.override(color, kelvin=666661) == (40, 1, 2, 65535)
            assert php.Color.override(
                color, hue=361, saturation=1.1, brightness=1.1, kelvin=66666
            ) == (360, 1, 1, 65535)

    class TestAdjust:
        def test_it_can_adjust_hue(self):
            color = (100, 0.1, 0.3, 9000)
            assert php.Color.adjust(color, hue_change=-50) == (50, 0.1, 0.3, 9000)
            assert php.Color.adjust(color, hue_change=50) == (150, 0.1, 0.3, 9000)
            assert php.Color.adjust(color, hue_change=(60,)) == (60, 0.1, 0.3, 9000)
            assert php.Color.adjust(color, hue_change=-150) == (0, 0.1, 0.3, 9000)
            assert php.Color.adjust(color, hue_change=400) == (360, 0.1, 0.3, 9000)

        def test_it_can_adjust_saturation(self):
            color = (100, 0.5, 0.3, 9000)
            assert php.Color.adjust(color, saturation_change=-0.1) == (100, 0.4, 0.3, 9000)
            assert php.Color.adjust(color, saturation_change=0.2) == (100, 0.7, 0.3, 9000)
            assert php.Color.adjust(color, saturation_change=(0.3,)) == (100, 0.3, 0.3, 9000)
            assert php.Color.adjust(color, saturation_change=-0.7) == (100, 0, 0.3, 9000)
            assert php.Color.adjust(color, saturation_change=0.9) == (100, 1, 0.3, 9000)

        def test_it_can_adjust_brightness(self):
            color = (100, 0.5, 0.3, 9000)
            assert php.Color.adjust(color, brightness_change=-0.1) == (100, 0.5, 0.3 - 0.1, 9000)
            assert php.Color.adjust(color, brightness_change=0.2) == (100, 0.5, 0.5, 9000)
            assert php.Color.adjust(color, brightness_change=(0.4,)) == (100, 0.5, 0.4, 9000)
            assert php.Color.adjust(color, brightness_change=-0.7) == (100, 0.5, 0, 9000)
            assert php.Color.adjust(color, brightness_change=0.9) == (100, 0.5, 1, 9000)

        def test_it_can_adjust_kelvin(self):
            color = (100, 0.5, 0.3, 9000)
            assert php.Color.adjust(color, kelvin_change=-1000) == (100, 0.5, 0.3, 8000)
            assert php.Color.adjust(color, kelvin_change=1000) == (100, 0.5, 0.3, 10000)
            assert php.Color.adjust(color, kelvin_change=(3500,)) == (100, 0.5, 0.3, 3500)
            assert php.Color.adjust(color, kelvin_change=-45000) == (100, 0.5, 0.3, 0)
            assert php.Color.adjust(color, kelvin_change=66666) == (100, 0.5, 0.3, 65535)

        def test_it_can_adjust_combination(self):
            got = php.Color.adjust(
                (100, 0.5, 0.3, 9000),
                hue_change=20,
                saturation_change=-0.2,
                brightness_change=(0.8,),
                kelvin_change=-3000,
            )
            assert got == (120, 0.3, 0.8, 6000)


class TestAverageColor:

    def assertColorAlmostEqual(self, got, want):
        assert want[0] == pytest.approx(got[0], rel=1e-3)
        assert want[1] == pytest.approx(got[1], rel=1e-3)
        assert want[2] == pytest.approx(got[2], rel=1e-3)
        assert want[3] == pytest.approx(got[3], rel=1e-3)

    def test_it_returns_None_if_no_colors(self):
        color = php.average_color([])
        assert color is None

        color = php.average_color([None])
        assert color is None

    def test_it_averages_saturation_brightness_and_kelvin(self):
        colors = [
            (0, 0.1, 0.2, 3500),
            (0, 0.2, 0.3, 4500),
            (0, 0.3, 0.4, 5500),
        ]

        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (0, 0.2, 0.3, 4500))

    def test_it_it_sets_kelvin_to_3500_if_0(self):
        colors = [
            (0, 0.1, 0.2, 3500),
            (0, 0.2, 0.3, 0),
            (0, 0.3, 0.4, 3500),
        ]

        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (0, 0.2, 0.3, 3500))

    def test_it_does_special_math_to_the_hue(self):
        #
        # NOTE: I'm not sure how to test this maths so I've just put these values into the algorithm
        #       and asserting the results I got back.
        #

        colors = [(hue, 1, 1, 3500) for hue in (10, 20, 30)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (19.9999, 1, 1, 3500))

        colors = [(hue, 1, 1, 3500) for hue in (100, 20, 30)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (48.2227, 1, 1, 3500))

        colors = [(hue, 1, 1, 3500) for hue in (100, 20, 30, 300)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (24.2583, 1, 1, 3500))

        colors = [(hue, 1, 1, 3500) for hue in (100, 300)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (20, 1, 1, 3500))

        colors = [(100, 1, 1, 3500), None, (300, 1, 1, 3500)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (20, 1, 1, 3500))


class TestPoints:
    def test_it_can_get_cols(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        cols = php.Points.cols(bounds)

        assert cols == [
            [(3, 5), (3, 4), (3, 3), (3, 2)],
            [(4, 5), (4, 4), (4, 3), (4, 2)],
            [(5, 5), (5, 4), (5, 3), (5, 2)],
            [(6, 5), (6, 4), (6, 3), (6, 2)],
            [(7, 5), (7, 4), (7, 3), (7, 2)],
        ]

    def test_it_can_get_rows(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        rows = php.Points.rows(bounds)

        assert rows == [
            [(3, 5), (4, 5), (5, 5), (6, 5), (7, 5)],
            [(3, 4), (4, 4), (5, 4), (6, 4), (7, 4)],
            [(3, 3), (4, 3), (5, 3), (6, 3), (7, 3)],
            [(3, 2), (4, 2), (5, 2), (6, 2), (7, 2)],
        ]

    def test_it_can_get_all(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        all_points = php.Points.all_points(bounds)

        r1 = [(3, 5), (4, 5), (5, 5), (6, 5), (7, 5)]
        r2 = [(3, 4), (4, 4), (5, 4), (6, 4), (7, 4)]
        r3 = [(3, 3), (4, 3), (5, 3), (6, 3), (7, 3)]
        r4 = [(3, 2), (4, 2), (5, 2), (6, 2), (7, 2)]
        assert all_points == [*r1, *r2, *r3, *r4]

    def test_it_can_count_points(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        assert php.Points.count_points(bounds) == 20

        bounds = ((1, 8), (6, 0), (7, 6))
        assert php.Points.count_points(bounds) == 42

        bounds = ((1, 1), (6, 6), (1, 1))
        assert php.Points.count_points(bounds) == 0

    def test_it_can_get_points_for_a_row(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        row = php.Points.row(3, bounds)
        assert row == [(3, 3), (4, 3), (5, 3), (6, 3), (7, 3)]

    def test_it_can_get_points_for_a_column(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        col = php.Points.col(2, bounds)
        assert col == [(2, 5), (2, 4), (2, 3), (2, 2)]

    def test_it_can_expand_a_bounds(self):
        bounds = ((3, 8), (5, 1), (5, 4))

        assert php.Points.expand(bounds, 5) == ((-2, 13), (10, -4), (15, 14))
        assert php.Points.expand(bounds, 3) == ((0, 11), (8, -2), (11, 10))

    def test_it_can_get_a_point_relative_to_bounds(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        assert php.Points.relative((4, 4), bounds) == (1, 1)
        assert php.Points.relative((5, 2), bounds) == (2, 3)

    def test_it_can_get_the_bottom_row(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        assert php.Points.bottom_row(bounds) == 1

        bounds = ((3, 8), (11, 9), (5, 2))
        assert php.Points.bottom_row(bounds) == 9

    def test_it_can_get_the_top_row(self):
        bounds = ((3, 8), (5, 1), (5, 4))
        assert php.Points.top_row(bounds) == 5

        bounds = ((3, 8), (11, 9), (5, 2))
        assert php.Points.top_row(bounds) == 11
