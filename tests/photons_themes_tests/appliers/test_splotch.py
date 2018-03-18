# coding: spec

from photons_themes.appliers.splotch import StripApplierSplotch, TileApplierSplotch
from photons_themes.theme import Theme, ThemeColor
from photons_themes.canvas import Canvas

from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from contextlib import contextmanager
import mock

describe TestCase, "StripApplierSplotch":
    before_each:
        self.theme = Theme()
        self.theme.add_hsbk(0, 1, 1, 3500)
        self.theme.add_hsbk(100, 1, 1, 3500)
        self.theme.add_hsbk(200, 1, 1, 3500)
        self.theme.add_hsbk(300, 1, 1, 3500)

    def assertHues(self, got, *expect):
        self.assertEqual(len(got), len(expect), "Expected {} to be {}".format(got, expect))

        expected = []
        i = 0
        for thing in expect:
            if type(thing) is tuple:
                num_zones, _ = thing
                expected.append((i, i + num_zones))
                i += num_zones
            else:
                expected.append((i, i))
                i += 1

        self.assertEqual([z for z, _ in got], expected)

        got_hues = []
        expected_hues = []

        for _, c in got:
            self.assertEqual(c.saturation, 1)
            self.assertEqual(c.brightness, 1)
            self.assertEqual(c.kelvin, 3500)
            got_hues.append("{:.3f}".format(c.hue))

        for thing in expect:
            h = thing
            if type(thing) is tuple:
                h = thing[1]
            expected_hues.append("{:.3f}".format(h))

        self.assertEqual(got_hues, expected_hues)

    @contextmanager
    def not_shuffled_theme(self):
        shuffled = mock.Mock(name="shuffled", return_value=self.theme)
        with mock.patch.object(self.theme, "shuffled", shuffled):
            yield
        shuffled.assert_called_once_with()

    it "distributes the theme to the strip":
        applier = StripApplierSplotch(4)
        with self.not_shuffled_theme():
            got = applier.apply_theme(self.theme)

        self.assertHues(got
            , 0
            , 100
            , 200
            , 300
            )

    it "transitions to each color":
        applier = StripApplierSplotch(16)
        with self.not_shuffled_theme():
            got = applier.apply_theme(self.theme)

        self.assertHues(got
            , 0, 25.0, 50.0, 75.0, 87.5, 100
            , 125, 150.0, 175.0, 187.5, 200
            , 225.0, 250.0, 275.0, 287.5, 300
            )

    it "transitions nicely when the colors aren't sequential":
        self.theme.colors.insert(2, ThemeColor(40, 1, 1, 3500))

        applier = StripApplierSplotch(16)
        with self.not_shuffled_theme():
            got = applier.apply_theme(self.theme)

        self.assertHues(got
            , 0, 25.0, 50.0, 75.0, 100
            , 85.0, 70.0, 55.0, 40
            , 80.0, 120.0, 160.0, 200
            , 225.0, 250.0, 275.0
            )

describe TestCase, "TileApplierSplotch":
    before_each:
        self.user_coords_and_sizes = [
              ((0.5, 1.5), (6, 6))
            , ((0.5, 0.5), (6, 6))
            , ((1.5, 0.5), (6, 6))
            ]

        self.applier = TileApplierSplotch.from_user_coords(self.user_coords_and_sizes)

        points = [
              (0, 12, 0),   None, None,        None, None, (5, 12, 300)
            , None
            , None
            , None
            , None
            , (0,  7, 200), None, None,        None, None, (5,  7, 10)
            , None
            , None
            , None,         None, (2,  4, 90), None, None, None,        (6,  4, 30), None, None, None, None, (11, 4, 45)
            , None
            , None
            , (0,  1, 30),  None, None,        None, None, None,        None,        None, None, None, None, (11, 1, 89)
            ]

        self.canvas = Canvas()
        for point in points:
            if point is not None:
                i, j, h = point
                self.canvas[(i, j)] = ThemeColor(h, 1, 1, 3500)

    def assertHues(self, got, *hues):
        got_hues = []
        expected_hues = []

        self.assertEqual(len(got), len(hues))

        for g, e in zip(got, hues):
            if e is None:
                self.assertEqual(g, ThemeColor(0, 0, 0.3, 3500))
                got_hues.append(0)
                expected_hues.append(0)
            else:
                self.assertEqual(g.saturation, 1)
                self.assertEqual(g.brightness, 1)
                self.assertEqual(g.kelvin, 3500)

                got_hues.append("{:.3f}".format(g.hue))
                expected_hues.append("{:.3f}".format(e))

        self.assertEqual(got_hues, expected_hues)

    it "can create the canvas":
        theme = Theme()
        theme.add_hsbk(0, 1, 1, 3500)
        theme.add_hsbk(100, 1, 1, 3500)
        theme.add_hsbk(200, 1, 1, 3500)
        theme.add_hsbk(300, 1, 1, 3500)

        user_coords_and_sizes = [
              ((0.5, 1.5), (8, 8))
            , ((0.5, 0.5), (8, 8))
            , ((1.5, 0.5), (8, 8))
            ]

        applier = TileApplierSplotch.from_user_coords(user_coords_and_sizes)
        applier.just_points = True

        tiles = applier.apply_theme(theme)

        all_hues = []
        for tile in tiles:
            hues = [c.hue for c in tile if c.saturation == 1]
            all_hues.extend(hues)
            self.assertGreater(len(hues), 2)
            self.assertLess(len(hues), (8 * 8) / 2)

        self.assertGreater(len(all_hues), 6)
        self.assertLess(len(all_hues), 3 * ((8 * 8) / 2))

    it "can return just the points":
        self.applier.just_points = True
        tiles = self.applier.apply_theme(Theme(), canvas=self.canvas)

        self.assertEqual(len(tiles), 3)
        self.assertHues(tiles[0]
            , 0,    None, None, None, None, 300
            , None, None, None, None, None, None
            , None, None, None, None, None, None
            , None, None, None, None, None, None
            , None, None, None, None, None, None
            , 200,  None, None, None, None, 10
            )

        self.assertHues(tiles[1]
            , None, None, None, None, None, None
            , None, None, None, None, None, None
            , None, None, 90,   None, None, None
            , None, None, None, None, None, None
            , None, None, None, None, None, None
            , 30,   None, None, None, None, None
            )

        self.assertHues(tiles[2]
            , None, None, None, None, None, None
            , None, None, None, None, None, None
            , 30,   None, None, None, None, 45
            , None, None, None, None, None, None
            , None, None, None, None, None, None
            , None, None, None, None, None, 89
            )

    it "fills in the blanks and blurs":
        tiles = self.applier.apply_theme(Theme(), canvas=self.canvas)

        self.assertEqual(len(tiles), 3)
        self.assertHues(tiles[0]
            , 357.354, 353.317, 339.287, 319.357, 306.107, 302.67
            , 353.766, 349.896, 337.188, 320.743, 309.286, 306.454
            , 328.112, 326.612, 325.32, 323.28, 322.627, 321.775
            , 232.074, 252.626, 302.539, 333.098, 344.066, 346.048
            , 205.009, 204.271, 222.976, 356.996, 4.18, 5.037
            , 193.706, 182.422, 146.255, 42.642, 18.126, 14.906
            )

        self.assertHues(tiles[1]
            , 174.107, 155.588, 106.686, 61.209, 32.368, 23.087
            , 132.642, 113.567, 92.548, 69.889, 45.433, 30.643
            , 90.336,  89.807,  84.9,   72.523, 52.64,  36.584
            , 63.926,  70.407,  74.462, 67.431, 51.996, 39.538
            , 45.367,  52.496,  59.94,  58.018, 49.092, 42.479
            , 36.441,  42.2,    49.52,  51.73,  46.591, 44.326
            )

        self.assertHues(tiles[2]
            , 23.207, 28.978, 34.586, 40.374, 43.704, 44.567
            , 27.579, 30.666, 35.917, 41.011, 44.356, 45.532
            , 31.345, 33.055, 38.142, 43.548, 47.317, 48.383
            , 34.193, 36.0,   41.615, 50.267, 56.07,  57.67
            , 40.739, 42.865, 50.169, 59.788, 68.084, 71.879
            , 45.655, 49.739, 55.671, 66.534, 76.223, 80.183
            )
