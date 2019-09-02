# coding: spec

from photons_themes.appliers.stripes import (
    TileApplierVerticalStripe,
    TileApplierHorizontalStripe,
    TileApplierDownDiagnoalStripe,
    TileApplierUpDiagnoalStripe,
    TileApplierSquareStripe,
)
from photons_themes.theme import Theme

from photons_app.test_helpers import TestCase

from contextlib import contextmanager
from unittest import mock


def assertTileHues(t, got, *expect):
    t.assertEqual(len(got), len(expect))
    got_hues = [float("{:.3f}".format(c.hue)) for c in got]
    expect_hues = [float("{:.3f}".format(h)) for h in expect]
    t.assertEqual(got_hues, expect_hues)


@contextmanager
def no_shuffle(theme):
    shuffled = mock.Mock(name="shuffled", return_value=theme)
    with mock.patch.object(theme, "shuffled", shuffled):
        yield
    shuffled.assert_called_once_with()


describe TestCase, "TileApplierVerticalStripe":
    it "applies a vertical stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierVerticalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0
        )

        assertTileHues(
            self, tiles[1],
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0,
            7.5, 10.0, 20.0, 30.0, 40.0, 50.0
        )

        assertTileHues(
            self, tiles[2],
            22.5, 355.0, 327.5, 0.0, 2.5, 5.0,
            22.5, 355.0, 327.5, 0.0, 2.5, 5.0,
            22.5, 355.0, 327.5, 0.0, 2.5, 5.0,
            22.5, 355.0, 327.5, 0.0, 2.5, 5.0,
            22.5, 355.0, 327.5, 0.0, 2.5, 5.0,
            22.5, 355.0, 327.5, 0.0, 2.5, 5.0
        )
        # fmt: on

    it "works with less colors in the theme":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierVerticalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75
        )

        assertTileHues(
            self, tiles[1],
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75
        )

        assertTileHues(
            self, tiles[2],
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75,
            25.0, 37.5, 43.75, 0.0, 12.5, 18.75
        )
        # fmt: on

describe TestCase, "TileApplierHorizontalStripe":
    it "applies a vertical stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierHorizontalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            22.5, 22.5, 22.5, 22.5, 22.5, 22.5,
            50.0, 50.0, 50.0, 50.0, 50.0, 50.0,
            40.0, 40.0, 40.0, 40.0, 40.0, 40.0,
            30.0, 30.0, 30.0, 30.0, 30.0, 30.0,
            20.0, 20.0, 20.0, 20.0, 20.0, 20.0,
            10.0, 10.0, 10.0, 10.0, 10.0, 10.0
        )

        assertTileHues(
            self, tiles[1],
            7.5, 7.5, 7.5, 7.5, 7.5, 7.5,
            5.0, 5.0, 5.0, 5.0, 5.0, 5.0,
            2.5, 2.5, 2.5, 2.5, 2.5, 2.5,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            327.5, 327.5, 327.5, 327.5, 327.5, 327.5,
            355.0, 355.0, 355.0, 355.0, 355.0, 355.0
        )

        assertTileHues(
            self, tiles[2],
            7.5, 7.5, 7.5, 7.5, 7.5, 7.5,
            5.0, 5.0, 5.0, 5.0, 5.0, 5.0,
            2.5, 2.5, 2.5, 2.5, 2.5, 2.5,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            327.5, 327.5, 327.5, 327.5, 327.5, 327.5,
            355.0, 355.0, 355.0, 355.0, 355.0, 355.0
        )
        # fmt: on

    it "works with less colors in the theme":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierHorizontalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            25.0,  25.0,  25.0,  25.0,  25.0,  25.0, # noqa
            18.75, 18.75, 18.75, 18.75, 18.75, 18.75, # noqa
            12.5,  12.5,  12.5,  12.5,  12.5,  12.5, # noqa
            0.0,   0.0,   0.0,   0.0,   0.0,   0.0, # noqa
            43.75, 43.75, 43.75, 43.75, 43.75, 43.75, # noqa
            37.5,  37.5,  37.5,  37.5,  37.5,  37.5 # noqa
        )

        assertTileHues(
            self, tiles[1],
            25.0,  25.0,  25.0,  25.0,  25.0,  25.0, # noqa
            18.75, 18.75, 18.75, 18.75, 18.75, 18.75, # noqa
            12.5,  12.5,  12.5,  12.5,  12.5,  12.5, # noqa
            0.0,   0.0,   0.0,   0.0,   0.0,   0.0, # noqa
            43.75, 43.75, 43.75, 43.75, 43.75, 43.75, # noqa
            37.5,  37.5,  37.5,  37.5,  37.5,  37.5, # noqa
        )

        assertTileHues(
            self, tiles[2],
            25.0,  25.0,  25.0,  25.0,  25.0,  25.0, # noqa
            18.75, 18.75, 18.75, 18.75, 18.75, 18.75, # noqa
            12.5,  12.5,  12.5,  12.5,  12.5,  12.5, # noqa
            0.0,   0.0,   0.0,   0.0,   0.0,   0.0, # noqa
            43.75, 43.75, 43.75, 43.75, 43.75, 43.75, # noqa
            37.5,  37.5,  37.5,  37.5,  37.5,  37.5 # noqa
        )
        # fmt: on

describe TestCase, "TileApplierDownDiagnoalStripe":
    it "applies a vertical stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierDownDiagnoalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            0.0,   2.5,   5.0,   7.5,   10.0,  20.0, # noqa
            327.5, 0.0,   2.5,   5.0,   7.5,   10.0, # noqa
            355.0, 327.5, 0.0,   2.5,   5.0,   7.5, # noqa
            22.5,  355.0, 327.5, 0.0,   2.5,   5.0, # noqa
            50.0,  22.5,  355.0, 327.5, 0.0,   2.5, # noqa
            40.0,  50.0,  22.5,  355.0, 327.5, 0.0 # noqa
        )

        assertTileHues(
            self, tiles[1],
            30.0, 40.0, 50.0, 22.5, 355.0, 327.5, # noqa
            20.0, 30.0, 40.0, 50.0, 22.5,  355.0, # noqa
            10.0, 20.0, 30.0, 40.0, 50.0,  22.5, # noqa
            7.5,  10.0, 20.0, 30.0, 40.0,  50.0, # noqa
            5.0,  7.5,  10.0, 20.0, 30.0,  40.0, # noqa
            2.5,  5.0,  7.5,  10.0, 20.0,  30.0 # noqa
        )

        assertTileHues(
            self, tiles[2],
            0.0,   2.5,   5.0,   7.5,   10.0,  20.0, # noqa
            327.5, 0.0,   2.5,   5.0,   7.5,   10.0, # noqa
            355.0, 327.5, 0.0,   2.5,   5.0,   7.5, # noqa
            22.5,  355.0, 327.5, 0.0,   2.5,   5.0, # noqa
            50.0,  22.5,  355.0, 327.5, 0.0,   2.5, # noqa
            40.0,  50.0,  22.5,  355.0, 327.5, 0.0 # noqa
        )
        # fmt: on

    it "works with less colors in the theme":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierDownDiagnoalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            0.0,   12.5,  18.75, 25.0,  37.5,  43.75, # noqa
            43.75, 0.0,   12.5,  18.75, 25.0,  37.5, # noqa
            37.5,  43.75, 0.0,   12.5,  18.75, 25.0, # noqa
            25.0,  37.5,  43.75, 0.0,   12.5,  18.75, # noqa
            18.75, 25.0,  37.5,  43.75, 0.0,   12.5, # noqa
            12.5,  18.75, 25.0,  37.5,  43.75, 0.0 # noqa
        )

        assertTileHues(
            self, tiles[1],
            0.0,   12.5,  18.75, 25.0,  37.5,  43.75, # noqa
            43.75, 0.0,   12.5,  18.75, 25.0,  37.5, # noqa
            37.5,  43.75, 0.0,   12.5,  18.75, 25.0, # noqa
            25.0,  37.5,  43.75, 0.0,   12.5,  18.75, # noqa
            18.75, 25.0,  37.5,  43.75, 0.0,   12.5, # noqa
            12.5,  18.75, 25.0,  37.5,  43.75, 0.0 # noqa
        )

        assertTileHues(
            self, tiles[2],
            0.0,   12.5,  18.75, 25.0,  37.5,  43.75, # noqa
            43.75, 0.0,   12.5,  18.75, 25.0,  37.5, # noqa
            37.5,  43.75, 0.0,   12.5,  18.75, 25.0, # noqa
            25.0,  37.5,  43.75, 0.0,   12.5,  18.75, # noqa
            18.75, 25.0,  37.5,  43.75, 0.0,   12.5, # noqa
            12.5,  18.75, 25.0,  37.5,  43.75, 0.0 # noqa
        )
        # fmt: on

describe TestCase, "TileApplierUpDiagonalStripe":
    it "applies an up diagonal stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierUpDiagnoalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            30.0,  40.0,  50.0,  22.5,  355.0, 327.5, # noqa
            40.0,  50.0,  22.5,  355.0, 327.5, 0.0, # noqa
            50.0,  22.5,  355.0, 327.5, 0.0,   2.5, # noqa
            22.5,  355.0, 327.5, 0.0,   2.5,   5.0, # noqa
            355.0, 327.5, 0.0,   2.5,   5.0,   7.5, # noqa
            327.5, 0.0,   2.5,   5.0,   7.5,   10.0 # noqa
        )

        assertTileHues(
            self, tiles[1],
            0.0,  2.5,  5.0,  7.5,  10.0, 20.0, # noqa
            2.5,  5.0,  7.5,  10.0, 20.0, 30.0, # noqa
            5.0,  7.5,  10.0, 20.0, 30.0, 40.0, # noqa
            7.5,  10.0, 20.0, 30.0, 40.0, 50.0, # noqa
            10.0, 20.0, 30.0, 40.0, 50.0, 22.5, # noqa
            20.0, 30.0, 40.0, 50.0, 22.5, 355.0 # noqa
        )

        assertTileHues(
            self, tiles[2],
            30.0,  40.0,  50.0,  22.5,  355.0, 327.5, # noqa
            40.0,  50.0,  22.5,  355.0, 327.5, 0.0, # noqa
            50.0,  22.5,  355.0, 327.5, 0.0,   2.5, # noqa
            22.5,  355.0, 327.5, 0.0,   2.5,   5.0, # noqa
            355.0, 327.5, 0.0,   2.5,   5.0,   7.5, # noqa
            327.5, 0.0,   2.5,   5.0,   7.5,   10.0 # noqa
        )
        # fmt: on

    it "works with less colors in the theme":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierUpDiagnoalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            0.0,   12.5,  18.75, 25.0,  37.5,  43.75, # noqa
            12.5,  18.75, 25.0,  37.5,  43.75, 0.0, # noqa
            18.75, 25.0,  37.5,  43.75, 0.0,   12.5, # noqa
            25.0,  37.5,  43.75, 0.0,   12.5,  18.75, # noqa
            37.5,  43.75, 0.0,   12.5,  18.75, 25.0, # noqa
            43.75, 0.0,   12.5,  18.75, 25.0,  37.5 # noqa
        )

        assertTileHues(
            self, tiles[1],
            0.0,   12.5,  18.75, 25.0,  37.5,  43.75, # noqa
            12.5,  18.75, 25.0,  37.5,  43.75, 0.0, # noqa
            18.75, 25.0,  37.5,  43.75, 0.0,   12.5, # noqa
            25.0,  37.5,  43.75, 0.0,   12.5,  18.75, # noqa
            37.5,  43.75, 0.0,   12.5,  18.75, 25.0, # noqa
            43.75, 0.0,   12.5,  18.75, 25.0,  37.5 # noqa
        )

        assertTileHues(
            self, tiles[2],
            0.0,   12.5,  18.75, 25.0,  37.5,  43.75, # noqa
            12.5,  18.75, 25.0,  37.5,  43.75, 0.0, # noqa
            18.75, 25.0,  37.5,  43.75, 0.0,   12.5, # noqa
            25.0,  37.5,  43.75, 0.0,   12.5,  18.75, # noqa
            37.5,  43.75, 0.0,   12.5,  18.75, 25.0, # noqa
            43.75, 0.0,   12.5,  18.75, 25.0,  37.5 # noqa
        )
        # fmt: on

describe TestCase, "TileApplierSquareStripe":
    it "applies a vertical stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        # fmt: off
        user_coords_and_sizes = [
            ((1, 1), (6, 6)),
            ((1, 0), (6, 6)),
            ((2, 0), (6, 6))
        ]
        # fmt: on

        applier = TileApplierSquareStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        # fmt: off
        assertTileHues(
            self, tiles[0],
            50.0,  50.0, 50.0, 50.0,  50.0,  50.0, # noqa
            50.0,  10.0, 10.0, 10.0,  10.0,  10.0, # noqa
            50.0,  10.0, 0.0,  0.0,   0.0,   0.0, # noqa
            50.0,  10.0, 0.0,  300.0, 300.0, 300.0, # noqa
            50.0,  10.0, 0.0,  300.0, 50.0,  50.0, # noqa
            50.0,  10.0, 0.0,  300.0, 50.0,  10.0 # noqa
        )

        assertTileHues(
            self, tiles[1],
            50.0, 10.0, 0.0,  300.0, 50.0,  10.0, # noqa
            50.0, 10.0, 0.0,  300.0, 50.0,  10.0, # noqa
            50.0, 10.0, 0.0,  300.0, 50.0,  50.0, # noqa
            50.0, 10.0, 0.0,  300.0, 300.0, 300.0, # noqa
            50.0, 10.0, 0.0,  0.0,   0.0,   0.0, # noqa
            50.0, 10.0, 10.0, 10.0,  10.0,  10.0 # noqa
        )

        assertTileHues(
            self, tiles[2],
            0.0,   10.0,  50.0,  300.0, 0.0,  10.0, # noqa
            10.0,  10.0,  50.0,  300.0, 0.0,  10.0, # noqa
            50.0,  50.0,  50.0,  300.0, 0.0,  10.0, # noqa
            300.0, 300.0, 300.0, 300.0, 0.0,  10.0, # noqa
            0.0,   0.0,   0.0,   0.0,   0.0,  10.0, # noqa
            10.0,  10.0,  10.0,  10.0,  10.0, 10.0 # noqa
        )
        # fmt: on
