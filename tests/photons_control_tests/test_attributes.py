# coding: spec

from photons_control.attributes import make_colors

from photons_app.test_helpers import TestCase

from photons_colour import Parser

from noseOfYeti.tokeniser.support import noy_sup_setUp

describe TestCase, "make_colors":
    before_each:
        self.colors = [
              ["red", 10]
            , ["blue", 3]
            , ["hue:78 brightness:0.5", 5]
            , ["#234455", 2]
            , [[100], 1]
            , [[100, 0.5], 1]
            , [[100, 0.5, 0.5], 1]
            , [[100, 0.5, 0.5, 9000], 1]
            , [[0, 0, 0, 0], 1]
            , [{"hue": 100}, 1]
            , [{"hue": 100, "saturation": 0.5}, 1]
            , [{"hue": 100, "saturation": 0.5, "brightness": 0.5}, 1]
            , [{"hue": 100, "saturation": 0.5, "brightness": 0.5, "kelvin": 9000}, 1]
            , [{"hue": 0, "saturation": 0, "brightness": 0, "kelvin": 0}, 1]
            ]

    it "can make colors":
        def hsbk(*args, **kwargs):
            h, s, b, k = Parser.hsbk(*args, **kwargs)
            return {"hue": h, "saturation": s, "brightness": b, "kelvin": k}

        colorRed = hsbk("red", overrides={"brightness": 1.0, "kelvin": 3500})
        colorBlue = hsbk("blue", overrides={"brightness": 1.0, "kelvin": 3500})
        colorHSBK = hsbk("hue:78 brightness:0.5", overrides={"saturation": 0, "kelvin": 3500})
        colorHEX = hsbk("#234455", overrides={"kelvin": 3500})

        self.maxDiff = None
        expected = [colorRed] * 10 + [colorBlue] * 3 + [colorHSBK] * 5 + [colorHEX] * 2
        for _ in range(2):
            expected.append({"hue": 100, "saturation": 0, "brightness": 1, "kelvin": 3500})
            expected.append({"hue": 100, "saturation": 0.5, "brightness": 1, "kelvin": 3500})
            expected.append({"hue": 100, "saturation": 0.5, "brightness": 0.5, "kelvin": 3500})
            expected.append({"hue": 100, "saturation": 0.5, "brightness": 0.5, "kelvin": 9000})
            expected.append({"hue": 0, "saturation": 0, "brightness": 0, "kelvin": 0})

        self.assertEqual(list(make_colors(self.colors)), expected)

    it "can overrides hue":
        colors = list(make_colors(self.colors, overrides={"hue": 1}))
        for c in colors:
            self.assertEqual(c["hue"], 1)

    it "can overrides saturation":
        colors = list(make_colors(self.colors, overrides={"saturation": 0.3}))
        for c in colors:
            self.assertEqual(c["saturation"], 0.3)

    it "can overrides brightness":
        colors = list(make_colors(self.colors, overrides={"brightness": 0.6}))

        for c in colors:
            self.assertEqual(c["brightness"], 0.6)

    it "can overrides kelvin":
        colors = list(make_colors(self.colors, overrides={"kelvin": 8000}))

        for c in colors:
            self.assertEqual(c["kelvin"], 8000)
