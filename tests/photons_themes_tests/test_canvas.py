# coding: spec

from photons_themes.canvas import color_weighting, shuffle_point, Canvas
from photons_themes.theme import ThemeColor, Theme

from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
import random
import mock

white = ThemeColor(0, 0, 1, 3500)

describe TestCase, "color_weighting":
    it "returns nothing if there are no distances":
        self.assertEqual(list(color_weighting([])), [])

    it "returns 0 distance items greatest distance number of times":
        distances = [(5, ThemeColor(0, 1, 1, 3500)), (6, ThemeColor(100, 1, 1, 3500)), (0, ThemeColor(300, 1, 1, 3500))]
        cs = list(color_weighting(distances))
        self.assertEqual(len([c for c in cs if c.hue == 300]), 6)

        distances.append((9, ThemeColor(40, 1, 1, 3400)))
        cs = list(color_weighting(distances))
        self.assertEqual(len([c for c in cs if c.hue == 300]), 9)

    it "returns each color more times the closer they are":
        distances = [
              (5, ThemeColor(0, 1, 1, 3500))
            , (3, ThemeColor(100, 1, 1, 3500))
            , (0, ThemeColor(300, 1, 1, 3500))
            , (9, ThemeColor(200, 1, 1, 3500))
            , (2, ThemeColor(150, 1, 1, 3500))
            ]
        cs = list(color_weighting(distances))
        expected = [0, *([100] * 3), *([300] * 9), 200, *([150] * 4)]
        self.assertEqual([c.hue for c in cs], expected)

describe TestCase, "shuffling a point":
    it "moves the point within a box of 3 pixels either side":
        canvas = Canvas()

        equald = 0

        for _ in range(5000):
            i, j = (random.randrange(-100, 100), random.randrange(-100, 100))
            ni, nj = shuffle_point(i, j)

            self.assertLess(abs(ni - i), 4)
            self.assertLess(abs(nj - j), 4)

            if (i, j) == (ni, nj):
                equald += 1

        self.assertLess(equald, 1000)

describe TestCase, "Canvas":
    it "has points":
        canvas = Canvas()
        self.assertEqual(canvas.points, {})

    it "can iterate the points":
        canvas = Canvas()
        canvas[(1, 1)] = ThemeColor(0, 1, 1, 2400)
        canvas[(2, 1)] = ThemeColor(100, 1, 1, 2400)
        canvas[(3, 4)] = ThemeColor(120, 1, 1, 2400)

        got = list(canvas)
        expected = list(canvas.points.items())
        self.assertEqual(sorted(got), sorted(expected))
        self.assertEqual(len(got), 3)

    it "can get a point":
        canvas = Canvas()
        with self.fuzzyAssertRaisesError(KeyError):
            canvas[(1, 1)]

        canvas[(1, 1)] = white
        self.assertIs(canvas[(1, 1)], white)

    it "can get a point when we have a color func":
        color = ThemeColor(0, 1, 1, 3500)
        canvas = Canvas()
        canvas.set_color_func(lambda i, j: ThemeColor(i + j, 1, 1, 3500))
        self.assertEqual(canvas[(1, 1)], ThemeColor(2, 1, 1, 3500))
        self.assertEqual(canvas[(10, 1)], ThemeColor(11, 1, 1, 3500))
        self.assertEqual(canvas[(10, 13)], ThemeColor(23, 1, 1, 3500))

        # Color func overrides set points
        canvas[(1, 1)] = ThemeColor(10, 1, 1, 3500)
        self.assertEqual(canvas[(1, 1)], ThemeColor(2, 1, 1, 3500))

    it "can get a point when we have a default color func":
        color = ThemeColor(0, 1, 1, 3500)
        canvas = Canvas()
        canvas.set_default_color_func(lambda i, j: ThemeColor(i + j, 1, 1, 3500))
        self.assertEqual(canvas[(1, 1)], ThemeColor(2, 1, 1, 3500))

        # default color func does not override set points
        canvas[(1, 1)] = ThemeColor(10, 1, 1, 3500)
        self.assertEqual(canvas[(1, 1)], ThemeColor(10, 1, 1, 3500))

    it "can set a point":
        canvas = Canvas()
        self.assertEqual(canvas.points, {})

        canvas[(1, 1)] = white
        self.assertEqual(canvas.points, {(1, 1): white})

        red = ThemeColor(0, 1, 1, 3400)
        canvas[(2, 3)] = red
        self.assertEqual(canvas.points, {(1, 1): white, (2, 3): red})

    it "can test whether a point is in the canvas":
        canvas = Canvas()
        assert (1, 1) not in canvas

        canvas[(1, 1)] = white
        assert (1, 1) in canvas

    it "can say how many points we have":
        canvas = Canvas()
        self.assertEqual(len(canvas), 0)

        canvas[(1, 1)] = white
        self.assertEqual(len(canvas), 1)

        canvas[(2, 1)] = white
        self.assertEqual(len(canvas), 2)

    describe "get":
        it "can get a point":
            canvas = Canvas()
            canvas[(1, 1)] = white
            self.assertIs(canvas.get((1, 1)), white)

        it "can get a default if point doesn't exist":
            canvas = Canvas()
            red = ThemeColor(0, 1, 1, 3400)
            self.assertIs(canvas.get((1, 1), red), red)
            self.assertIs(canvas.get((1, 1)), None)

        it "uses default_color_func instead of dflt":
            canvas = Canvas()
            red = ThemeColor(0, 1, 1, 3400)
            dflt_from_func = ThemeColor(100, 1, 1, 3400)
            canvas.set_default_color_func(lambda i, j: dflt_from_func)
            self.assertEqual(canvas.get((1, 1), red), ThemeColor(100, 1, 1, 3400))
            self.assertEqual(canvas.get((1, 1)), ThemeColor(100, 1, 1, 3400))

        it "uses the color_func if one is set":
            color = ThemeColor(0, 1, 1, 3500)
            canvas = Canvas()
            canvas.set_color_func(lambda i, j: ThemeColor(i + j, 1, 1, 3500))
            self.assertEqual(canvas.get((1, 1)), ThemeColor(2, 1, 1, 3500))
            self.assertEqual(canvas.get((10, 1)), ThemeColor(11, 1, 1, 3500))
            self.assertEqual(canvas.get((10, 13)), ThemeColor(23, 1, 1, 3500))

    describe "width":
        it "returns 0 if there are no points":
            self.assertEqual(Canvas().width, 0)

        it "returns 1 if there are is only one point":
            canvas = Canvas()
            canvas[(1, 1)] = white
            self.assertEqual(canvas.width, 1)

        it "returns the width depending on min and max x plus 1":
            canvas = Canvas()
            canvas[(1, 1)] = white
            canvas[(2, 1)] = white
            self.assertEqual(canvas.width, 2)

            canvas[(-2, 1)] = white
            self.assertEqual(canvas.width, 5)

            canvas[(4, 1)] = white
            self.assertEqual(canvas.width, 7)

    describe "height":
        it "returns 0 if there are no points":
            self.assertEqual(Canvas().height, 0)

        it "returns 1 if there are is only one point":
            canvas = Canvas()
            canvas[(1, 1)] = ThemeColor(0, 0, 0, 3500)
            self.assertEqual(canvas.height, 1)

        it "returns the height depending on min and max y plus 1":
            canvas = Canvas()
            canvas[(1, 1)] = white
            canvas[(1, 2)] = white
            self.assertEqual(canvas.height, 2)

            canvas[(1, -2)] = white
            self.assertEqual(canvas.height, 5)

            canvas[(1, 4)] = white
            self.assertEqual(canvas.height, 7)

    describe "min_x":
        it "returns 0 if there are no points":
            self.assertEqual(Canvas().min_x, 0)

        it "returns the min x point":
            canvas = Canvas()
            canvas[(1, 1)] = white
            self.assertEqual(canvas.min_x, 1)

            canvas[(2, 1)] = white
            self.assertEqual(canvas.min_x, 1)

            canvas[(-1, 1)] = white
            self.assertEqual(canvas.min_x, -1)

            canvas[(-5, 1)] = white
            self.assertEqual(canvas.min_x, -5)

    describe "max_x":
        it "returns 0 if there are no points":
            self.assertEqual(Canvas().max_x, 0)

        it "returns the max x point":
            canvas = Canvas()
            canvas[(2, 1)] = white
            self.assertEqual(canvas.max_x, 2)

            canvas[(1, 1)] = white
            self.assertEqual(canvas.max_x, 2)

            canvas[(3, 1)] = white
            self.assertEqual(canvas.max_x, 3)

            canvas[(5, 1)] = white
            self.assertEqual(canvas.max_x, 5)

    describe "min_y":
        it "returns 0 if there are no points":
            self.assertEqual(Canvas().min_y, 0)

        it "returns the min x point":
            canvas = Canvas()
            canvas[(1, 1)] = white
            self.assertEqual(canvas.min_y, 1)

            canvas[(2, 2)] = white
            self.assertEqual(canvas.min_y, 1)

            canvas[(1, -1)] = white
            self.assertEqual(canvas.min_y, -1)

            canvas[(-1, -5)] = white
            self.assertEqual(canvas.min_y, -5)

    describe "max_y":
        it "returns 0 if there are no points":
            self.assertEqual(Canvas().max_y, 0)

        it "returns the max y point":
            canvas = Canvas()
            canvas[(1, 1)] = white
            self.assertEqual(canvas.max_y, 1)

            canvas[(2, 2)] = white
            self.assertEqual(canvas.max_y, 2)

            canvas[(1, -1)] = white
            self.assertEqual(canvas.max_y, 2)

            canvas[(-1, 3)] = white
            self.assertEqual(canvas.max_y, 3)

    describe "center":
        it "returns (0, 0) if there are no points":
            self.assertEqual(Canvas().center, (0, 0))

        it "returns the center when there are points":
            canvas = Canvas()
            canvas[(1, 1)] = white
            self.assertEqual(canvas.center, (1, 1))

            canvas[(2, 2)] = white
            self.assertEqual(canvas.center, (2, 2))

            canvas[(-1, 2)] = white
            self.assertEqual(canvas.center, (1, 2))

            canvas[(5, 5)] = white
            self.assertEqual(canvas.center, (2, 3))

            canvas[(-100, -100)] = white
            canvas[(100, 100)] = white
            self.assertEqual(canvas.center, (0, 0))

            canvas[(200, 200)] = white
            self.assertEqual(canvas.center, (50, 50))

    describe "surrounding_colors":
        it "gets the colors that surround the provided i, j":
            canvas = Canvas()

            points = [
                  (0, 3), (1, 3), (2, 3)
                , (0, 2), (1, 2), (2, 2)
                , (0, 1), (1, 1), (2, 1)
                ]

            for i, point in enumerate(points):
                canvas[point] = ThemeColor(i, 0, 1, 3400)

            surrounding = canvas.surrounding_colors(1, 2)
            self.assertEqual([s.hue for s in surrounding]
                , [0, 1, 2, 3, 5, 6, 7, 8]
                )

        it "ignores points that don't exist":
            canvas = Canvas()

            points = [
                  (0, 3), (1, 3)
                , (0, 2), (1, 2)
                ]

            for i, point in enumerate(points):
                canvas[point] = ThemeColor(i, 0, 1, 3400)

            surrounding = canvas.surrounding_colors(1, 2)
            self.assertEqual([s.hue for s in surrounding]
                , [0, 1, 2]
                )

    describe "has_neighbour":
        it "says yes if there are atleast one neighbour":
            canvas = Canvas()
            surrounding_colors = mock.Mock(name="surrounding_colors", return_value=[white])

            with mock.patch.object(canvas, "surrounding_colors", surrounding_colors):
                assert canvas.has_neighbour(1, 2)

            surrounding_colors.assert_called_once_with(1, 2)

        it "says yes if there are multiple neighbours":
            canvas = Canvas()
            surrounding_colors = mock.Mock(name="surrounding_colors", return_value=[white, white])

            with mock.patch.object(canvas, "surrounding_colors", surrounding_colors):
                assert canvas.has_neighbour(1, 2)

            surrounding_colors.assert_called_once_with(1, 2)

        it "says no if there are no neighbours":
            canvas = Canvas()
            surrounding_colors = mock.Mock(name="surrounding_colors", return_value=[])

            with mock.patch.object(canvas, "surrounding_colors", surrounding_colors):
                assert not canvas.has_neighbour(1, 2)

            surrounding_colors.assert_called_once_with(1, 2)

    describe "set_all_points_for_tile":
        it "translates x, y to where the tile should be on the canvas":
            want = [
                  [0, 1, 0, 1, 0]
                , [1, 0, 1, 0, 1]
                , [0, 2, 0, 2, 0]
                , [1, 0, 1, 0, 1]
                , [0, 1, 0, 1, 0]
                , [0, 0, 3, 0, 0]
                ]

            def get_color(x, y):
                return ThemeColor(want[y][x], 1, 1, 3500)

            canvas = Canvas()
            canvas.set_all_points_for_tile(10, 2, 5, 6, get_color)
            tile = canvas.points_for_tile(10, 2, 5, 6)
            hues = [p.hue for p in tile]
            expected = [
                  0, 1, 0, 1, 0
                , 1, 0, 1, 0, 1
                , 0, 2, 0, 2, 0
                , 1, 0, 1, 0, 1
                , 0, 1, 0, 1, 0
                , 0, 0, 3, 0, 0
                ]
            self.assertEqual(hues, expected)

        it "ignores points where get_color returns None":
            N = None
            want = [
                  [0, N, 2]
                , [1, 0, N]
                ]

            def get_color(x, y):
                if want[y][x] is None:
                    return None
                return ThemeColor(want[y][x], 1, 1, 3500)

            canvas = Canvas()
            canvas.set_all_points_for_tile(0, 0, 3, 2, get_color)
            self.assertEqual(canvas.points
                , { (0, 0): ThemeColor(0, 1, 1, 3500)
                  , (0, -1): ThemeColor(1, 1, 1, 3500)
                  , (1, -1): ThemeColor(0, 1, 1, 3500)
                  , (2, 0): ThemeColor(2, 1, 1, 3500)
                  }
                )

    describe "add_points_for_tile":
        before_each:
            self.theme = Theme()
            self.theme.add_hsbk(0, 0, 1, 3500)
            self.theme.add_hsbk(100, 1, 0, 3400)
            self.theme.add_hsbk(320, 1, 1, 5900)

        it "adds points for the tile such that there are no neighbours and we cover just the tile":
            canvas = Canvas()
            canvas.add_points_for_tile(-2, 0, 8, 8, self.theme)

            self.assertGreater(len(canvas), 3)
            for (i, j), color in canvas:
                assert not canvas.has_neighbour(i, j)
                assert color in self.theme

            self.assertLess(canvas.width, 25)
            self.assertLess(canvas.height, 25)

            canvas.add_points_for_tile(200, 100, 8, 8, self.theme)
            self.assertLess(len(canvas), 244)
            for (i, j), color in canvas:
                assert not canvas.has_neighbour(i, j)
                assert color in self.theme

            canvas.add_points_for_tile(-3, 2, 8, 8, self.theme)
            for (i, j), color in canvas:
                assert not canvas.has_neighbour(i, j)
                assert color in self.theme

    describe "shuffling points":
        before_each:
            self.theme = Theme()
            self.theme.add_hsbk(0, 0, 1, 3500)
            self.theme.add_hsbk(100, 1, 0, 3400)
            self.theme.add_hsbk(320, 1, 1, 5900)

        it "moves the points around":
            canvas = Canvas()
            canvas.add_points_for_tile(-2, 0, 8, 8, self.theme)
            for (i, j), color in canvas:
                assert not canvas.has_neighbour(i, j)
                assert color in self.theme

            old_points = sorted(point for point, _ in canvas)

            canvas.shuffle_points()
            new_points = sorted(point for point, _ in canvas)

            self.assertNotEqual(new_points, old_points)
            assert any(canvas.has_neighbour(i, j) for (i, j), _ in canvas)
            for (i, j), color in canvas:
                assert color in self.theme

    describe "blur":
        it "averages all the points with the surrounding colors":
            one = ThemeColor(1, 0, 1, 3500)
            two = ThemeColor(2, 0, 1, 3500)
            three = ThemeColor(3, 0, 1, 3500)
            four = ThemeColor(4, 0, 1, 3500)

            red = ThemeColor(0, 1, 1, 3500)
            green = ThemeColor(100, 1, 1, 3500)

            avg1 = ThemeColor(20, 1, 1, 3400)
            avg2 = ThemeColor(30, 1, 1, 3400)

            canvas = Canvas()
            canvas[(1, 1)] = red
            canvas[(5, 5)] = green

            def surrounding_colors(i, j):
                return {
                      (1, 1): [two, three]
                    , (5, 5): [one, four]
                    }[(i, j)]
            surrounding_colors = mock.Mock(name="surrounding_colors", side_effect=surrounding_colors)

            def average(colors):
                return {
                      (red, red, two, three): avg1
                    , (green, green, one, four): avg2
                    }[tuple(colors)]
            average = mock.Mock(name="average", side_effect=average)

            with mock.patch.object(canvas, "surrounding_colors", surrounding_colors):
                with mock.patch.object(ThemeColor, "average", average):
                    canvas.blur()

            self.assertEqual(sorted(canvas)
                , sorted([((1, 1), avg1), ((5, 5), avg2)])
                )

    describe "points for tile":
        it "gets the points in the correct order":
            points = [
                  (0, 13,  1), (1, 13,  2), (2, 13,  3), (3, 13,  4), (4, 13,  5), (5, 13,  6)
                , (0, 12,  7), (1, 12,  8), (2, 12,  9), (3, 12, 10), (4, 12, 11), (5, 12, 12)
                , (0, 11, 13), (1, 11, 14), (2, 11, 15), (3, 11, 16), (4, 11, 17), (5, 11, 18)
                , (0, 10, 19), (1, 10, 20), (2, 10, 21), (3, 10, 22), (4, 10, 23), (5, 10, 24)
                , (0,  9, 25), (1,  9, 26), (2,  9, 27), (3,  9, 28), (4,  9, 29), (5,  9, 30)
                , (0,  8, 31), (1,  8, 32), (2,  8, 33), (3,  8, 34), (4,  8, 35), (5,  8, 36)
                ]
            canvas = Canvas()
            for i, j, h in points:
                canvas[(i, j)] = ThemeColor(h, 1, 1, 3500)

            tile = canvas.points_for_tile(0, 13, 6, 6)
            got_hues = []
            for c in tile:
                self.assertEqual(c.saturation, 1)
                self.assertEqual(c.brightness, 1)
                self.assertEqual(c.kelvin, 3500)
                got_hues.append(c.hue)
            self.assertEqual(got_hues, list(range(1, 37)))

        it "returns grey for values that don't exist":
            points = [
                  (0, 13,  1), (1, 13,  2), (2, 13,  3), (3, 13,  4), (4, 13,  5), (5, 13,  6)
                ]
            canvas = Canvas()
            for i, j, h in points:
                canvas[(i, j)] = ThemeColor(h, 1, 1, 3500)

            tile = canvas.points_for_tile(0, 13, 6, 6)
            got_hues = []
            for c in tile[:6]:
                self.assertEqual(c.saturation, 1)
                self.assertEqual(c.brightness, 1)
                self.assertEqual(c.kelvin, 3500)
                got_hues.append(c.hue)
            self.assertEqual(got_hues, list(range(1, 7)))

            for c in tile[6:]:
                self.assertEqual(c, ThemeColor(0, 0, 0.3, 3500))

    describe "filling in points for a tile":
        it "blurs together all the colors":
            canvas = Canvas()

            _ = None
            points = [
                  (0, 9), (1, 9), (_, _), (3, 9), (4, 9), (5, 9), (6, 9)
                , (0, 8), (_, _), (_, _), (_, _), (_, _), (_, _), (_, _)
                , (_, _), (_, _), (2, 7), (_, _), (_, _), (_, _), (6, 7)
                , (0, 6), (1, 6), (_, _), (3, 6), (_, _), (_, _), (6, 6)
                , (_, _), (1, 5), (2, 5), (_, _), (_, _), (_, _), (_, _)
                , (_, _), (_, _), (_, _), (_, _), (_, _), (_, _), (6, 4)
                , (_, _), (_, _), (2, 3), (_, _), (_, _), (_, _), (6, 3)
                , (0, 2), (_, _), (_, _), (_, _), (_, _), (_, _), (_, _)
                , (0, 1), (1, 1), (2, 1), (_, _), (_, _), (5, 1), (6, 1)
                , (0, 0), (1, 0), (_, _), (_, _), (4, 0), (5, 0), (6, 0)
                ]

            for i, point in enumerate(points):
                if point != (None, None):
                    canvas[point] = ThemeColor(i, 0, 0, 3500)

            expected = [
                  (1, 8, 5.326),  (2, 8, 8.777),  (3, 8, 8.423),  (4, 8, 4.200),  (5, 8, 7.984),  (6, 8, 12.808)
                , (1, 7, 17.341), (2, 7, 20.664), (3, 7, 17.266), (4, 7, 17.620), (5, 7, 18.132), (6, 7, 20.523)
                , (1, 6, 22.856), (2, 6, 23.000), (3, 6, 23.334), (4, 6, 22.877), (5, 6, 26.653), (6, 6, 24.327)
                , (1, 5, 26.144), (2, 5, 27.335), (3, 5, 26.254), (4, 5, 29.186), (5, 5, 29.988), (6, 5, 34.000)
                , (1, 4, 31.763), (2, 4, 34.610), (3, 4, 33.489), (4, 4, 34.754), (5, 4, 40.807), (6, 4, 41.701)
                , (1, 3, 45.014), (2, 3, 42.125), (3, 3, 42.641), (4, 3, 48.482), (5, 3, 49.431), (6, 3, 47.314)
                ]

            new_canvas = Canvas()
            new_canvas.fill_in_points(canvas, 1, 8, 6,6)

            self.assertEqual(len(new_canvas), len(expected))
            for x, y, hue in expected:
                self.assertEqual("{:.3f}".format(new_canvas[(x, y)].hue), "{:.3f}".format(hue))

    describe "getting closest points":
        it "gets the closest points":
            canvas = Canvas()

            _ = None
            points = [
                  (0, 9), (1, 9), (_, _), (3, 9), (4, 9), (5, 9), (6, 9)
                , (0, 8), (_, _), (_, _), (_, _), (_, _), (_, _), (_, _)
                , (_, _), (_, _), (2, 7), (_, _), (_, _), (_, _), (6, 7)
                , (0, 6), (1, 6), (_, _), (3, 6), (_, _), (_, _), (6, 6)
                , (_, _), (1, 5), (2, 5), (_, _), (_, _), (_, _), (_, _)
                , (_, _), (_, _), (_, _), (_, _), (_, _), (_, _), (6, 4)
                , (_, _), (_, _), (2, 3), (_, _), (_, _), (_, _), (6, 3)
                , (0, 2), (_, _), (_, _), (_, _), (_, _), (_, _), (_, _)
                , (0, 1), (1, 1), (2, 1), (_, _), (_, _), (5, 1), (6, 1)
                , (0, 0), (1, 0), (_, _), (_, _), (4, 0), (5, 0), (6, 0)
                ]

            for i, point in enumerate(points):
                if point != (None, None):
                    canvas[point] = ThemeColor(i, 0, 0, 3500)

            def assertClosest(i, j, *expected):
                got = canvas.closest_points(i, j, len(expected))
                expect = [(dist, canvas[point]) for dist, point in expected]
                self.assertEqual(sorted(got), sorted(expect))

            want = [(0, (2, 3)), (4, (2, 5)), (4, (2, 1)), (5, (1, 5)), (5, (0, 2)), (5, (1, 1))]
            assertClosest(2, 3, *want)

            want = [
                  (0, (4, 0)), (1, (5, 0)), (2, (5, 1)), (4, (6, 0))
                , (5, (2, 1)), (5, (6, 1)), (9, (1, 0)), (10, (1, 1))
                , (13, (2, 3)), (13, (6, 3))
                ]
            assertClosest(4, 0, *want)

            want = [(0, (0, 9)), (1, (0, 8)), (1, (1, 9))]
            assertClosest(0, 9, *want)

    describe "blurring by distance":
        it "blurs with the 8 closest points":
            one = ThemeColor(1, 0, 1, 3500)
            two = ThemeColor(2, 0, 1, 3500)
            three = ThemeColor(3, 0, 1, 3500)
            four = ThemeColor(4, 0, 1, 3500)

            red = ThemeColor(0, 1, 1, 3500)
            green = ThemeColor(100, 1, 1, 3500)

            distances1 = mock.Mock(name="distances1")
            distances2 = mock.Mock(name="distances2")

            avg1 = ThemeColor(20, 1, 1, 3400)
            avg2 = ThemeColor(30, 1, 1, 3400)

            canvas = Canvas()
            canvas[(1, 1)] = red
            canvas[(5, 5)] = green

            def closest_points(i, j, consider):
                self.assertEqual(consider, 8)
                return {(1, 1): distances1, (5, 5): distances2}[(i, j)]
            closest_points = mock.Mock(name="closest_points", side_effect=closest_points)

            def colorweighting(distances):
                return {
                      distances1: [two, three]
                    , distances2: [one, four]
                    }[distances]
            colorweighting = mock.Mock(name="colorweighting", side_effect=colorweighting)

            def average(colors):
                return {
                      (two, three): avg1
                    , (one, four): avg2
                    }[tuple(colors)]
            average = mock.Mock(name="average", side_effect=average)

            with mock.patch.object(canvas, "closest_points", closest_points):
                with mock.patch.object(ThemeColor, "average", average):
                    with mock.patch("photons_themes.canvas.color_weighting", colorweighting):
                        canvas.blur_by_distance()

            self.assertEqual(sorted(canvas)
                , sorted([((1, 1), avg1), ((5, 5), avg2)])
                )
