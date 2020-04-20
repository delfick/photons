# coding: spec

from photons_themes.theme import Theme, ThemeColor

from unittest import mock
import pytest

describe "ThemeColor":
    it "takes in hsbk":
        hue = mock.Mock(name="hue")
        saturation = mock.Mock(name="saturation")
        brightness = mock.Mock(name="brightness")
        kelvin = 3500

        color = ThemeColor(hue, saturation, brightness, kelvin)

        assert color.hue is hue
        assert color.saturation is saturation
        assert color.brightness is brightness
        assert color.kelvin is kelvin

    it "can return as a dict":
        hue = mock.Mock(name="hue")
        saturation = mock.Mock(name="saturation")
        brightness = mock.Mock(name="brightness")
        kelvin = 3500

        color = ThemeColor(hue, saturation, brightness, kelvin)

        assert color.as_dict() == {
            "hue": hue,
            "saturation": saturation,
            "brightness": brightness,
            "kelvin": kelvin,
        }

    it "can return as a key suitable for a cache":
        hue = mock.Mock(name="hue")
        saturation = mock.Mock(name="saturation")
        brightness = mock.Mock(name="brightness")
        kelvin = 3500

        color = ThemeColor(hue, saturation, brightness, kelvin)

        assert color.cache_key == tuple(sorted(color.as_dict().items()))

    it "can be cloned":
        hue = mock.Mock(name="hue")
        saturation = mock.Mock(name="saturation")
        brightness = mock.Mock(name="brightness")
        kelvin = 3500
        color = ThemeColor(hue, saturation, brightness, kelvin)

        clone = color.clone()
        assert clone is not color

        assert clone.hue is hue
        assert clone.saturation is saturation
        assert clone.brightness is brightness
        assert clone.kelvin == kelvin

    it "makes sure kelvin is an integer":
        color = ThemeColor(320, 0, 0, 3500.5)
        assert color.kelvin == 3500

    describe "creating a set of ThemeColor":
        it "works":
            colors = [
                ThemeColor(0, 0, 0, 2500),
                ThemeColor(0, 0, 0, 2500),
                ThemeColor(100, 0, 0, 3500),
                ThemeColor(320, 0, 0, 3500),
                ThemeColor(0, 0, 0, 2500),
                ThemeColor(320, 0, 0, 3500),
                ThemeColor(100, 0, 0, 3500),
                ThemeColor(320, 0, 0, 3500),
                ThemeColor(0, 0, 0, 2500),
                ThemeColor(100, 0, 0, 3500),
                ThemeColor(100, 0, 0, 3500),
                ThemeColor(100, 0, 0, 3500),
            ]

            unique = list(set(colors))

            assert len(unique) == 3
            assert sorted([c.hue for c in unique]) == [0, 100, 320]

    describe "equality":
        it "is equal if it has the same hsbk":
            color = ThemeColor(230, 0, 0, 2500)
            color2 = ThemeColor(230, 0, 0, 2500)
            assert color == color2

        it "is not equal if it has different hsbk values":
            color = ThemeColor(230, 0, 0, 2400)
            assert color != ThemeColor(230, 0, 0, 2500)
            assert color != ThemeColor(230, 0, 1, 2400)
            assert color != ThemeColor(230, 1, 0, 2400)
            assert color != ThemeColor(231, 0, 0, 2400)
            assert color != ThemeColor(231, 1, 0, 2400)
            assert color != ThemeColor(231, 0, 1, 2400)
            assert color != ThemeColor(231, 0, 0, 2500)
            assert color != ThemeColor(231, 1, 0, 2500)
            assert color != ThemeColor(231, 1, 1, 2500)

    describe "limit distance to":

        def assertNewHue(self, hue1, hue2, expected_hue):
            color = ThemeColor(hue1, 0.1, 0.6, 3500)
            color2 = ThemeColor(hue2, 0.2, 0.5, 4500)
            limited = color.limit_distance_to(color2)
            assert limited == ThemeColor(expected_hue, 0.1, 0.6, 3500)

        it "adds 90 if the distance is greater than 180":
            # The distance wraps around 360
            self.assertNewHue(100, 0, 100 + 90)
            self.assertNewHue(200, 100, 200 + 90)

            self.assertNewHue(0, 182, 0 + 90)
            self.assertNewHue(100, 282, 100 + 90)

        it "takes 90 if the distance is less than 180":
            # The distance wraps around 360
            self.assertNewHue(300, 40, 300 - 90)

            self.assertNewHue(200, 300, 200 - 90)

            # Make sure we don't get negative numbers
            self.assertNewHue(0, 100, 360 + 0 - 90)

        it "returns the original hue if the distance is less than 90":
            self.assertNewHue(300, 10, 300)
            self.assertNewHue(200, 210, 200)
            self.assertNewHue(0, 70, 0)
            self.assertNewHue(100, 130, 100)

    describe "__repr__":
        it "returns the hsbk in a nice fashion":
            color = ThemeColor(320, 0.5, 0.6, 5600)
            assert repr(color) == "<Color (320, 0.5, 0.6, 5600)>"

    describe "averaging colors":

        def assertColorAlmostEqual(self, color, want):
            assert want.hue == pytest.approx(color.hue, rel=1e-3)
            assert want.saturation == pytest.approx(color.saturation, rel=1e-3)
            assert want.brightness == pytest.approx(color.brightness, rel=1e-3)
            assert want.kelvin == pytest.approx(color.kelvin, rel=1e-3)

        it "returns white if there are no colors":
            color = ThemeColor.average([])
            assert color == ThemeColor(0, 0, 1, 3500)

        it "averages saturation, brightness and kelvin":
            colors = [
                ThemeColor(0, 0.1, 0.2, 3500),
                ThemeColor(0, 0.2, 0.3, 4500),
                ThemeColor(0, 0.3, 0.4, 5500),
            ]

            color = ThemeColor.average(colors)
            self.assertColorAlmostEqual(color, ThemeColor(0, 0.2, 0.3, 4500))

        it "it sets kelvin to 3500 if 0":
            colors = [
                ThemeColor(0, 0.1, 0.2, 3500),
                ThemeColor(0, 0.2, 0.3, 0),
                ThemeColor(0, 0.3, 0.4, 3500),
            ]

            color = ThemeColor.average(colors)
            self.assertColorAlmostEqual(color, ThemeColor(0, 0.2, 0.3, 3500))

        it "does special math to the hue":
            #
            # NOTE: I'm not sure how to test this maths so I've just put these values into the algorithm
            #       and asserting the results I got back.
            #

            colors = [ThemeColor(hue, 1, 1, 3500) for hue in (10, 20, 30)]
            color = ThemeColor.average(colors)
            self.assertColorAlmostEqual(color, ThemeColor(19.9999, 1, 1, 3500))

            colors = [ThemeColor(hue, 1, 1, 3500) for hue in (100, 20, 30)]
            color = ThemeColor.average(colors)
            self.assertColorAlmostEqual(color, ThemeColor(48.2227, 1, 1, 3500))

            colors = [ThemeColor(hue, 1, 1, 3500) for hue in (100, 20, 30, 300)]
            color = ThemeColor.average(colors)
            self.assertColorAlmostEqual(color, ThemeColor(24.2583, 1, 1, 3500))

            colors = [ThemeColor(hue, 1, 1, 3500) for hue in (100, 300)]
            color = ThemeColor.average(colors)
            self.assertColorAlmostEqual(color, ThemeColor(20, 1, 1, 3500))

describe "Theme":
    it "has colors":
        theme = Theme()
        assert theme.colors == []

    it "can have colors added":
        theme = Theme()
        assert theme.colors == []

        theme.add_hsbk(320, 1, 0, 3500)
        theme.add_hsbk(100, 0.5, 0.3, 3400)

        assert theme.colors == [
            ThemeColor(320, 1, 0, 3500),
            ThemeColor(100, 0.5, 0.3, 3400),
        ]

    it "iterates over the colors":
        theme = Theme()
        theme.add_hsbk(320, 1, 0, 3500)
        theme.add_hsbk(100, 0.5, 0.3, 3400)

        assert list(theme) == [
            ThemeColor(320, 1, 0, 3500),
            ThemeColor(100, 0.5, 0.3, 3400),
        ]

    it "can say if a color is in the theme":
        theme = Theme()

        assert ThemeColor(320, 1, 0, 3500) not in theme

        theme.add_hsbk(320, 1, 0, 3500)
        assert ThemeColor(320, 1, 0, 3500) in theme

    it "can choose a random color":
        theme = Theme()
        assert theme.colors == []

        for i in range(0, 100, 5):
            theme.add_hsbk(i, 1, 0, 3500)

        got = []
        for _ in range(100):
            got.append(theme.random())

        assert len(set(got)) > 10

    it "can return how many colors are in the theme":
        theme = Theme()
        assert len(theme) == 0

        theme.add_hsbk(320, 1, 0, 3500)
        assert len(theme) == 1

        theme.add_hsbk(100, 0.5, 0.3, 3400)
        assert len(theme) == 2

    it "can return the i'th item in the theme":
        theme = Theme()
        theme.add_hsbk(320, 1, 0, 3500)
        theme.add_hsbk(100, 0.5, 0.3, 3400)

        assert theme[0] == ThemeColor(320, 1, 0, 3500)
        assert theme[1] == ThemeColor(100, 0.5, 0.3, 3400)

    it "can return the next item in the theme or the current if there is no next":
        theme = Theme()
        theme.add_hsbk(320, 1, 0, 3500)
        theme.add_hsbk(0, 0.5, 0, 4500)
        theme.add_hsbk(100, 0.5, 0.3, 3400)

        assert theme.get_next_bounds_checked(0) == ThemeColor(0, 0.5, 0, 4500)
        assert theme.get_next_bounds_checked(1) == ThemeColor(100, 0.5, 0.3, 3400)
        assert theme.get_next_bounds_checked(2) == ThemeColor(100, 0.5, 0.3, 3400)

    it "can return a shuffled version of the theme":
        theme = Theme()
        ordered = []
        for i in range(0, 100, 5):
            theme.add_hsbk(i, 0.3, 0.4, 4500)
            ordered.append(i)

        shuffled = theme.shuffled()

        got = []
        for i in range(0, 20):
            theme[i].hue = i * 5
            got.append(shuffled[i].hue)

        assert got != ordered
        assert sorted(got) == ordered

    it "can make sure there is atleast one color":
        theme = Theme()
        assert theme.colors == []

        theme.ensure_color()
        assert theme.colors == [ThemeColor(0, 0, 1, 3500)]

        theme.ensure_color()
        assert theme.colors == [ThemeColor(0, 0, 1, 3500)]
