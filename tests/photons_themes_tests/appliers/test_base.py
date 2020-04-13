# coding: spec

from photons_themes.appliers.base import TileApplier, TileApplierPattern
from photons_themes.theme import ThemeColor, Theme

from contextlib import contextmanager
from unittest import mock

describe "TileApplier":
    it "takes in coords and sizes":
        coords_and_sizes = mock.Mock(name="coords_and_sizes")
        applier = TileApplier(coords_and_sizes)
        assert applier.coords_and_sizes is coords_and_sizes

    describe "from_user_coords":
        it "translates to top left corner":
            # fmt: off
            coords_and_sizes = [
                ((1, 1), (8, 8)),
                ((2, 2), (10, 9)),
                ((3, 3), (6, 6))
            ]

            applier = TileApplier.from_user_coords(coords_and_sizes)
            assert applier.coords_and_sizes == [
                    ((8 - 4, 8 + 4), (8, 8)),
                    ((20 - 5, int(18 + 4.5)), (10, 9)),
                    ((18 - 3, 18 + 3), (6, 6))
                ]
            # fmt: on

describe "TileApplierPattern":
    it "can apply a theme using the color func":
        theme = Theme()

        class Applier(TileApplierPattern):
            def color_func_generator(s, t, c):
                assert t is theme

                def f(i, j):
                    return ThemeColor(i * 10 + j, 1, 1, 3500)

                return f

        user_coords_and_sizes = [((2, 2), (6, 6)), ((3, 3), (6, 6))]

        applier = Applier.from_user_coords(user_coords_and_sizes)
        tiles = applier.apply_theme(theme)

        # fmt: off
        assert [c.hue for c in tiles[0]] == [
                105, 115, 125, 135, 145, 155,
                104, 114, 124, 134, 144, 154,
                103, 113, 123, 133, 143, 153,
                102, 112, 122, 132, 142, 152,
                101, 111, 121, 131, 141, 151,
                100, 110, 120, 130, 140, 150
            ]

        assert [c.hue for c in tiles[1]] == [
                171, 181, 191, 201, 211, 221,
                170, 180, 190, 200, 210, 220,
                169, 179, 189, 199, 209, 219,
                168, 178, 188, 198, 208, 218,
                167, 177, 187, 197, 207, 217,
                166, 176, 186, 196, 206, 216
            ]

        assert applier.coords_and_sizes == [
                ((9, 15), (6, 6)),
                ((15, 21), (6, 6))
            ]
        # fmt: on

    it "puts the corners of the tiles on the canvas":
        theme = Theme()

        class Applier(TileApplierPattern):
            def color_func_generator(s, t, c):
                assert t is theme

                def f(i, j):
                    return ThemeColor(i * 10 + j, 1, 1, 3500)

                return f

        # fmt: off
        user_coords_and_sizes = [
            ((2, 2), (6, 6)),
            ((4, 3), (6, 6))
        ]
        # fmt: on

        applier = Applier.from_user_coords(user_coords_and_sizes)
        _, canvas = applier.apply_theme(theme, return_canvas=True)

        assert sorted(canvas.points.keys()) == sorted(
            [(9, 15), (9 + 6, 15 - 6), (21, 21), (21 + 6, 21 - 6)]
        )

        # 1 is added to the actual width and height
        assert canvas.width == 19
        assert canvas.height == 13

    it "can get a range of colors":

        def assertHues(got, *expect):
            assert len(got) == len(expect)
            got_hues = [float("{:.3f}".format(c.hue)) for c in got]
            expect_hues = [float("{:.3f}".format(h)) for h in expect]
            assert got_hues == expect_hues

        theme = Theme()

        @contextmanager
        def no_shuffle():
            shuffled = mock.Mock(name="shuffled", return_value=theme)
            with mock.patch.object(theme, "shuffled", shuffled):
                yield
            shuffled.assert_called_once_with()

        applier = TileApplierPattern([])

        with no_shuffle():
            assert applier.make_colors(theme) == [ThemeColor(0, 0, 1, 3500)] * 3

        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(100, 1, 1, 3500)
        with no_shuffle():
            # fmt: off
            assertHues(
                applier.make_colors(theme),
                0.0, 2.5, 5.0, 7.5, 10.0, 32.5, 55.0, 77.5, 100.0
            )
            # fmt: on

        with no_shuffle():
            # fmt: off
            assertHues(
                applier.make_colors(theme, multiplier=4),
                0.0, 2.5, 3.75, 5.0, 7.5, 8.75, 10.0, 32.5, 43.75, 55.0, 77.5, 88.75
            )
            # fmt: on

        theme.add_hsbk(30, 1, 1, 3500)
        theme.add_hsbk(200, 1, 1, 3500)

        with no_shuffle():
            # fmt: off
            assertHues(
                applier.make_colors(theme),
                0.0, 5.0, 7.5, 10.0, 55.0, 77.5, 100.0, 65.0, 47.5, 30.0, 115.0, 157.5, 200.0, 200.0, 200.0
            )
            # fmt: on
