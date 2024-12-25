
import pytest
from photons_canvas import font
from photons_canvas.points import helpers as php
from photons_canvas.points.canvas import Canvas

class TestSpace:
    def test_it_is_a_character_with_a_particular_width(self):
        s = font.Space(5)
        layer = s.layer(0, 0, (20, 1, 1, 3500))

        canvas = Canvas()

        for point in php.Points.all_points(((0, 5), (0, -3), (5, 3))):
            assert layer(point, canvas) is None

        assert s.width == 5
        assert s.height == 1

class TestCharacter:

    @pytest.fixture()
    def char(self):
        return font.Character(
            """
            ###__
            cc###
            _____
            ##rrg
        """,
            colors={"c": (20, 1, 1, 3500), "r": (0, 1, 1, 3500), "g": (120, 1, 1, 3500)},
        )

    def test_it_gets_information_from_map(self, char):
        assert char.rows == [
            "###__",
            "cc###",
            "_____",
            "##rrg",
        ]
        assert char.pixels == [
            *["#", "#", "#", "_", "_"],
            *["c", "c", "#", "#", "#"],
            *["_", "_", "_", "_", "_"],
            *["#", "#", "r", "r", "g"],
        ]
        assert char.width == 5
        assert char.height == 4

    def test_it_can_get_point_to_color_pairs(self, char):
        pairs = list(char.pairs(1, 3, (300, 1, 0, 3500)))
        assert pairs == [
            ((1, 3), (300, 1, 0, 3500)),
            ((2, 3), (300, 1, 0, 3500)),
            ((3, 3), (300, 1, 0, 3500)),
            ((4, 3), None),
            ((5, 3), None),
            ((1, 2), (20, 1, 1, 3500)),
            ((2, 2), (20, 1, 1, 3500)),
            ((3, 2), (300, 1, 0, 3500)),
            ((4, 2), (300, 1, 0, 3500)),
            ((5, 2), (300, 1, 0, 3500)),
            ((1, 1), None),
            ((2, 1), None),
            ((3, 1), None),
            ((4, 1), None),
            ((5, 1), None),
            ((1, 0), (300, 1, 0, 3500)),
            ((2, 0), (300, 1, 0, 3500)),
            ((3, 0), (0, 1, 1, 3500)),
            ((4, 0), (0, 1, 1, 3500)),
            ((5, 0), (120, 1, 1, 3500)),
        ]

    def test_it_turns_left_x_and_top_y_into_integers(self, char):
        pairs = list(char.pairs(1.6, 3.0, (300, 1, 0, 3500)))
        real = list(char.pairs(2, 3, (300, 1, 0, 3500)))
        assert pairs == real

class TestCharacters:

    @pytest.fixture()
    def char1(self):
        class Char1(font.Character):
            colors = {"w": (0, 0, 1, 3500)}

        return Char1(
            """
            www
            ___
        """
        )

    @pytest.fixture()
    def char2(self):
        return font.Character(
            """
            #__
            __#
            ###
        """
        )

    @pytest.fixture()
    def char3(self):
        return font.Character(
            """
            ##
            gg
            ##
            ##
            __
        """,
            colors={"g": (120, 1, 0, 3500)},
        )

    def test_it_gets_width_of_all_characters(self, char1, char2, char3):
        chars1 = font.Characters()
        assert chars1.characters == []
        assert chars1.width == 0

        chars1 = font.Characters(char1)
        assert chars1.characters == [char1]
        assert chars1.width == 3

        chars1 = font.Characters(char1, char3)
        assert chars1.characters == [char1, char3]
        assert chars1.width == 5

        chars1 = font.Characters(char1, char3, char2)
        assert chars1.characters == [char1, char3, char2]
        assert chars1.width == 8

    def test_it_can_get_pairs(self, char1, char2, char3):
        chars = font.Characters(char1, char2, char3)
        fill_color = (4, 1, 0.5, 6700)
        assert list(chars.pairs(3, 1, fill_color)) == [
            *char1.pairs(3, 1, fill_color),
            *char2.pairs(6, 1, fill_color),
            *char3.pairs(9, 1, fill_color),
        ]

        chars = font.Characters(char2, char3, char1)
        assert list(chars.pairs(3, 1, fill_color)) == [
            *char2.pairs(3, 1, fill_color),
            *char3.pairs(6, 1, fill_color),
            *char1.pairs(8, 1, fill_color),
        ]

    def test_it_turns_left_x_and_top_y_into_integers(self, char1, char2, char3):
        chars = font.Characters(char2, char3, char1)
        pairs = list(chars.pairs(1.6, 3.0, (300, 1, 0, 3500)))
        real = list(chars.pairs(2, 3, (300, 1, 0, 3500)))
        assert pairs == real

    def test_it_can_get_a_layer(self, char1, char2, char3):
        chars = font.Characters(char1, char2, char3)
        fill_color = (4, 1, 0.5, 6700)

        chars_pixels = {}
        per_char_pixels = {}

        full_bounds = ((3, 12), (1, -4), (9, 5))

        pairs1 = list(char1.pairs(3, 1, fill_color))
        pairs2 = list(char2.pairs(6, 1, fill_color))
        pairs3 = list(char3.pairs(9, 1, fill_color))

        all_pairs = list(chars.pairs(3, 1, fill_color))
        combined_pairs = pairs1 + pairs2 + pairs3
        assert len(all_pairs) == len(combined_pairs) == len(set(all_pairs))
        assert all_pairs == combined_pairs

        for pairs in (pairs1, pairs2, pairs3):
            for point, c in pairs:
                assert point not in per_char_pixels
                per_char_pixels[point] = c

        full_layer = chars.layer(3, 1, fill_color)
        for point in php.Points.all_points(full_bounds):
            if point not in per_char_pixels:
                per_char_pixels[point] = None

            assert point not in chars_pixels
            chars_pixels[point] = full_layer(point, None)

            if point not in per_char_pixels:
                per_char_pixels[point] = None

        assert sorted(per_char_pixels) == sorted(chars_pixels)

        for point in chars_pixels:
            got = chars_pixels[point]
            want = per_char_pixels[point]

            if got != want:
                print(point, got, want)

        assert per_char_pixels == chars_pixels

    def test_it_can_get_a_layer_after_converting_corner_to_integers(self, char1, char2, char3):
        chars = font.Characters(char1, char2, char3)
        fill_color = (4, 1, 0.5, 6700)

        chars_pixels = {}
        per_char_pixels = {}

        full_bounds = ((3, 12), (1, -4), (9, 5))

        pairs1 = list(char1.pairs(3, 1, fill_color))
        pairs2 = list(char2.pairs(6, 1, fill_color))
        pairs3 = list(char3.pairs(9, 1, fill_color))

        all_pairs = list(chars.pairs(3, 1, fill_color))
        combined_pairs = pairs1 + pairs2 + pairs3
        assert len(all_pairs) == len(combined_pairs) == len(set(all_pairs))
        assert all_pairs == combined_pairs

        for pairs in (pairs1, pairs2, pairs3):
            for point, c in pairs:
                assert point not in per_char_pixels
                per_char_pixels[point] = c

        full_layer = chars.layer(3.1, 1.0, fill_color)
        for point in php.Points.all_points(full_bounds):
            if point not in per_char_pixels:
                per_char_pixels[point] = None

            assert point not in chars_pixels
            chars_pixels[point] = full_layer(point, None)

            if point not in per_char_pixels:
                per_char_pixels[point] = None

        assert sorted(per_char_pixels) == sorted(chars_pixels)

        for point in chars_pixels:
            got = chars_pixels[point]
            want = per_char_pixels[point]

            if got != want:
                print(point, got, want)

        assert per_char_pixels == chars_pixels
