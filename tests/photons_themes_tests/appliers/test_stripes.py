# coding: spec

from photons_themes.appliers.stripes import (
      TileApplierVerticalStripe, TileApplierHorizontalStripe
    , TileApplierDownDiagnoalStripe, TileApplierUpDiagnoalStripe
    , TileApplierSquareStripe
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

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierVerticalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            )

        assertTileHues(self, tiles[1]
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            , 7.5, 10.0, 20.0, 30.0, 40.0, 50.0
            )

        assertTileHues(self, tiles[2]
            , 22.5, 355.0, 327.5, 0.0, 2.5, 5.0
            , 22.5, 355.0, 327.5, 0.0, 2.5, 5.0
            , 22.5, 355.0, 327.5, 0.0, 2.5, 5.0
            , 22.5, 355.0, 327.5, 0.0, 2.5, 5.0
            , 22.5, 355.0, 327.5, 0.0, 2.5, 5.0
            , 22.5, 355.0, 327.5, 0.0, 2.5, 5.0
            )

    it "works with less colors in the theme":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierVerticalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            )

        assertTileHues(self, tiles[1]
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            )

        assertTileHues(self, tiles[2]
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            , 25.0, 37.5, 43.75, 0.0, 12.5, 18.75
            )

describe TestCase, "TileApplierHorizontalStripe":
    it "applies a vertical stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierHorizontalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 22.5, 22.5, 22.5, 22.5, 22.5, 22.5
            , 50.0, 50.0, 50.0, 50.0, 50.0, 50.0
            , 40.0, 40.0, 40.0, 40.0, 40.0, 40.0
            , 30.0, 30.0, 30.0, 30.0, 30.0, 30.0
            , 20.0, 20.0, 20.0, 20.0, 20.0, 20.0
            , 10.0, 10.0, 10.0, 10.0, 10.0, 10.0
            )

        assertTileHues(self, tiles[1]
            , 7.5, 7.5, 7.5, 7.5, 7.5, 7.5
            , 5.0, 5.0, 5.0, 5.0, 5.0, 5.0
            , 2.5, 2.5, 2.5, 2.5, 2.5, 2.5
            , 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            , 327.5, 327.5, 327.5, 327.5, 327.5, 327.5
            , 355.0, 355.0, 355.0, 355.0, 355.0, 355.0
            )

        assertTileHues(self, tiles[2]
            , 7.5, 7.5, 7.5, 7.5, 7.5, 7.5
            , 5.0, 5.0, 5.0, 5.0, 5.0, 5.0
            , 2.5, 2.5, 2.5, 2.5, 2.5, 2.5
            , 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            , 327.5, 327.5, 327.5, 327.5, 327.5, 327.5
            , 355.0, 355.0, 355.0, 355.0, 355.0, 355.0
            )

    it "works with less colors in the theme":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierHorizontalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 25.0, 25.0, 25.0, 25.0, 25.0, 25.0
            , 18.75, 18.75, 18.75, 18.75, 18.75, 18.75
            , 12.5, 12.5, 12.5, 12.5, 12.5, 12.5
            , 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            , 43.75, 43.75, 43.75, 43.75, 43.75, 43.75
            , 37.5, 37.5, 37.5, 37.5, 37.5, 37.5
            )

        assertTileHues(self, tiles[1]
            , 25.0, 25.0, 25.0, 25.0, 25.0, 25.0
            , 18.75, 18.75, 18.75, 18.75, 18.75
            , 18.75, 12.5, 12.5, 12.5, 12.5, 12.5, 12.5
            , 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            , 43.75, 43.75, 43.75, 43.75, 43.75, 43.75
            , 37.5, 37.5, 37.5, 37.5, 37.5, 37.5
            )

        assertTileHues(self, tiles[2]
            , 25.0, 25.0, 25.0, 25.0, 25.0, 25.0
            , 18.75, 18.75, 18.75, 18.75, 18.75
            , 18.75, 12.5, 12.5, 12.5, 12.5, 12.5, 12.5
            , 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            , 43.75, 43.75, 43.75, 43.75, 43.75, 43.75
            , 37.5, 37.5, 37.5, 37.5, 37.5, 37.5
            )

describe TestCase, "TileApplierDownDiagnoalStripe":
    it "applies a vertical stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierDownDiagnoalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 0.0,   2.5,   5.0,   7.5,   10.0,  20.0
            , 327.5, 0.0,   2.5,   5.0,   7.5,   10.0
            , 355.0, 327.5, 0.0,   2.5,   5.0,   7.5
            , 22.5,  355.0, 327.5, 0.0,   2.5,   5.0
            , 50.0,  22.5,  355.0, 327.5, 0.0,   2.5
            , 40.0,  50.0,  22.5,  355.0, 327.5, 0.0
            )

        assertTileHues(self, tiles[1]
            , 30.0, 40.0, 50.0, 22.5, 355.0, 327.5
            , 20.0, 30.0, 40.0, 50.0, 22.5,  355.0
            , 10.0, 20.0, 30.0, 40.0, 50.0,  22.5
            , 7.5,  10.0, 20.0, 30.0, 40.0,  50.0
            , 5.0,  7.5,  10.0, 20.0, 30.0,  40.0
            , 2.5,  5.0,  7.5,  10.0, 20.0,  30.0
            )

        assertTileHues(self, tiles[2]
            , 0.0,   2.5,   5.0,   7.5,   10.0,  20.0
            , 327.5, 0.0,   2.5,   5.0,   7.5,   10.0
            , 355.0, 327.5, 0.0,   2.5,   5.0,   7.5
            , 22.5,  355.0, 327.5, 0.0,   2.5,   5.0
            , 50.0,  22.5,  355.0, 327.5, 0.0,   2.5
            , 40.0,  50.0,  22.5,  355.0, 327.5, 0.0
            )

    it "works with less colors in the theme":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierDownDiagnoalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 0.0,   12.5,  18.75, 25.0,  37.5,  43.75
            , 43.75, 0.0,   12.5,  18.75, 25.0,  37.5
            , 37.5,  43.75, 0.0,   12.5,  18.75, 25.0
            , 25.0,  37.5,  43.75, 0.0,   12.5,  18.75
            , 18.75, 25.0,  37.5,  43.75, 0.0,   12.5
            , 12.5,  18.75, 25.0,  37.5,  43.75, 0.0
            )

        assertTileHues(self, tiles[1]
            , 0.0,   12.5,  18.75, 25.0,  37.5,  43.75
            , 43.75, 0.0,   12.5,  18.75, 25.0,  37.5
            , 37.5,  43.75, 0.0,   12.5,  18.75, 25.0
            , 25.0,  37.5,  43.75, 0.0,   12.5,  18.75
            , 18.75, 25.0,  37.5,  43.75, 0.0,   12.5
            , 12.5,  18.75, 25.0,  37.5,  43.75, 0.0
            )

        assertTileHues(self, tiles[2]
            , 0.0,   12.5,  18.75, 25.0,  37.5,  43.75
            , 43.75, 0.0,   12.5,  18.75, 25.0,  37.5
            , 37.5,  43.75, 0.0,   12.5,  18.75, 25.0
            , 25.0,  37.5,  43.75, 0.0,   12.5,  18.75
            , 18.75, 25.0,  37.5,  43.75, 0.0,   12.5
            , 12.5,  18.75, 25.0,  37.5,  43.75, 0.0
            )

describe TestCase, "TileApplierUpDiagnoalStripe":
    it "applies a vertical stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierUpDiagnoalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 30.0,  40.0,  50.0,  22.5,  355.0, 327.5
            , 40.0,  50.0,  22.5,  355.0, 327.5, 0.0
            , 50.0,  22.5,  355.0, 327.5, 0.0,   2.5
            , 22.5,  355.0, 327.5, 0.0,   2.5,   5.0
            , 355.0, 327.5, 0.0,   2.5,   5.0,   7.5
            , 327.5, 0.0,   2.5,   5.0,   7.5,   10.0
            )

        assertTileHues(self, tiles[1]
            , 0.0,  2.5,  5.0,  7.5,  10.0, 20.0
            , 2.5,  5.0,  7.5,  10.0, 20.0, 30.0
            , 5.0,  7.5,  10.0, 20.0, 30.0, 40.0
            , 7.5,  10.0, 20.0, 30.0, 40.0, 50.0
            , 10.0, 20.0, 30.0, 40.0, 50.0, 22.5
            , 20.0, 30.0, 40.0, 50.0, 22.5, 355.0
            )

        assertTileHues(self, tiles[2]
            , 30.0,  40.0,  50.0,  22.5,  355.0, 327.5
            , 40.0,  50.0,  22.5,  355.0, 327.5, 0.0
            , 50.0,  22.5,  355.0, 327.5, 0.0,   2.5
            , 22.5,  355.0, 327.5, 0.0,   2.5,   5.0
            , 355.0, 327.5, 0.0,   2.5,   5.0,   7.5
            , 327.5, 0.0,   2.5,   5.0,   7.5,   10.0
            )

    it "works with less colors in the theme":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierUpDiagnoalStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 0.0,   12.5,  18.75, 25.0,  37.5,  43.75
            , 12.5,  18.75, 25.0,  37.5,  43.75, 0.0
            , 18.75, 25.0,  37.5,  43.75, 0.0,   12.5
            , 25.0,  37.5,  43.75, 0.0,   12.5,  18.75
            , 37.5,  43.75, 0.0,   12.5,  18.75, 25.0
            , 43.75, 0.0,   12.5,  18.75, 25.0,  37.5
            )

        assertTileHues(self, tiles[1]
            , 0.0,   12.5,  18.75, 25.0,  37.5,  43.75
            , 12.5,  18.75, 25.0,  37.5,  43.75, 0.0
            , 18.75, 25.0,  37.5,  43.75, 0.0,   12.5
            , 25.0,  37.5,  43.75, 0.0,   12.5,  18.75
            , 37.5,  43.75, 0.0,   12.5,  18.75, 25.0
            , 43.75, 0.0,   12.5,  18.75, 25.0,  37.5
            )

        assertTileHues(self, tiles[2]
            , 0.0,   12.5,  18.75, 25.0,  37.5,  43.75
            , 12.5,  18.75, 25.0,  37.5,  43.75, 0.0
            , 18.75, 25.0,  37.5,  43.75, 0.0,   12.5
            , 25.0,  37.5,  43.75, 0.0,   12.5,  18.75
            , 37.5,  43.75, 0.0,   12.5,  18.75, 25.0
            , 43.75, 0.0,   12.5,  18.75, 25.0,  37.5
            )

describe TestCase, "TileApplierSquareStripe":
    it "applies a vertical stripe":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(10, 1, 1, 3500)
        theme.add_hsbk(50, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        user_coords_and_sizes = [
              ((1, 1), (6, 6))
            , ((1, 0), (6, 6))
            , ((2, 0), (6, 6))
            ]

        applier = TileApplierSquareStripe.from_user_coords(user_coords_and_sizes)

        with no_shuffle(theme):
            tiles = applier.apply_theme(theme)

        assertTileHues(self, tiles[0]
            , 50.0,  50.0, 50.0, 50.0,  50.0,  50.0
            , 50.0,  10.0, 10.0, 10.0,  10.0,  10.0
            , 50.0,  10.0, 0.0,  0.0,   0.0,   0.0
            , 50.0,  10.0, 0.0,  300.0, 300.0, 300.0
            , 50.0,  10.0, 0.0,  300.0, 50.0,  50.0
            , 50.0,  10.0, 0.0,  300.0, 50.0,  10.0
            )

        assertTileHues(self, tiles[1]
            , 50.0, 10.0, 0.0,  300.0, 50.0,  10.0
            , 50.0, 10.0, 0.0,  300.0, 50.0,  10.0
            , 50.0, 10.0, 0.0,  300.0, 50.0,  50.0
            , 50.0, 10.0, 0.0,  300.0, 300.0, 300.0
            , 50.0, 10.0, 0.0,  0.0,   0.0,   0.0
            , 50.0, 10.0, 10.0, 10.0,  10.0,  10.0
            )

        assertTileHues(self, tiles[2]
            , 0.0,   10.0,  50.0,  300.0, 0.0,  10.0
            , 10.0,  10.0,  50.0,  300.0, 0.0,  10.0
            , 50.0,  50.0,  50.0,  300.0, 0.0,  10.0
            , 300.0, 300.0, 300.0, 300.0, 0.0,  10.0
            , 0.0,   0.0,   0.0,   0.0,   0.0,  10.0
            , 10.0,  10.0,  10.0,  10.0,  10.0, 10.0
            )
