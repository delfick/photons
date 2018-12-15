# coding: spec

from photons_colour import split_color_string, Parser, InvalidColor, ValueOutOfRange

from photons_app.test_helpers import TestCase

from photons_messages import LightMessages, Waveform

from input_algorithms import spec_base as sb
import mock

describe TestCase, "split_color_string":
    it "returns empty list if not color_string":
        for thing in (None, ""):
            self.assertEqual(split_color_string(thing), [])

    it "splits by whitespace":
        cases = [
              ("", [])
            , ("one two", ["one", "two"])
            , ("  one two ", ["one", "two"])
            , ("one\ttwo", ["one", "two"])
            , ("one\ttwo    three four", ["one", "two", "three", "four"])
            , ("one\t\t two \tthree", ["one", "two", "three"])
            ]

        for thing, expected in cases:
            self.assertEqual(split_color_string(thing), expected)

describe TestCase, "Parser":
    it "has named_colors":
        for color, info in Parser.named_colors.items():
            h, s, b, k = info
            assert h is None or type(h) is int
            assert s is None or type(s) is int
            assert b is None or type(b) is int
            assert k is None or type(k) is int

    describe "getting hsbk":
        def assertCorrect(self, components, h, s, b, k):
            self.assertEqual(Parser.hsbk(components), (h, s, b, k))

            ho = mock.Mock(name="hue_override")
            so = mock.Mock(name="saturation_override")
            bo = mock.Mock(name="brightness_override")
            ko = mock.Mock(name="kelvin_override")

            overrides = {"hue": ho}
            self.assertEqual(Parser.hsbk(components, overrides), (ho, s, b, k))

            overrides["saturation"] = so
            self.assertEqual(Parser.hsbk(components, overrides), (ho, so, b, k))

            overrides["brightness"] = bo
            self.assertEqual(Parser.hsbk(components, overrides), (ho, so, bo, k))

            overrides["kelvin"] = ko
            self.assertEqual(Parser.hsbk(components, overrides), (ho, so, bo, ko))

        it "supports random generation":
            for _ in range(100):
                h, s, b, k = Parser.hsbk("random")
                assert b is None
                assert k is None
                self.assertEqual(s, 1)
                self.assertGreater(h, -1)
                self.assertLess(h, 361)

        it "supports just kelvin":
            self.assertCorrect("kelvin:2500", None, 0, None, 2500)
            self.assertCorrect("kelvin:3500", None, 0, None, 3500)

            with self.fuzzyAssertRaisesError(InvalidColor, "Unable to parse color"):
                Parser.hsbk("kelvin:-1")

            error = ValueOutOfRange("Value was not within bounds", component="kelvin", minimum=1500, maximum=9000, value=9001)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("kelvin:9001")

        it "supports just brightness":
            self.assertCorrect("brightness:0", None, None, 0, None)
            self.assertCorrect("brightness:0.8", None, None, 0.8, None)

            with self.fuzzyAssertRaisesError(InvalidColor, "Unable to parse color"):
                Parser.hsbk("brightness:-1")

            error = ValueOutOfRange("Value was not within bounds", component="brightness", minimum=0, maximum=1, value=2)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("brightness:2")

        it "supports just saturation":
            self.assertCorrect("saturation:0", None, 0, None, None)
            self.assertCorrect("saturation:0.8", None, 0.8, None, None)

            with self.fuzzyAssertRaisesError(InvalidColor, "Unable to parse color"):
                Parser.hsbk("saturation:-1")

            error = ValueOutOfRange("Value was not within bounds", component="saturation", minimum=0, maximum=1, value=2)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("saturation:2")

        it "supports just hue":
            self.assertCorrect("hue:0", 0, None, None, None)
            self.assertCorrect("hue:80", 80, None, None, None)
            self.assertCorrect("hue:20.5", 20.5, None, None, None)

            with self.fuzzyAssertRaisesError(InvalidColor, "Unable to parse color"):
                Parser.hsbk("hue:-1")

            error = ValueOutOfRange("Value was not within bounds", component="hue", minimum=0, maximum=360, value=361)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("hue:361")

        it "supports hex":
            expected = (144.66257668711654, 0.9939024390243902, 0.6431372549019608, None)
            self.assertCorrect("hex:01A444", *expected)
            self.assertCorrect("#01A444", *expected)
            self.assertCorrect("hex:#01A444", *expected)

        it "supports rgb":
            self.assertCorrect("rgb:0,200,100", 150.0, 1.0, 0.7843137254901961, None)
            self.assertCorrect("rgb:10,1,255", 242.12598425196848, 0.996078431372549, 1.0, None)

            error = ValueOutOfRange("Value was not within bounds", component="r", minimum=0, maximum=255, value=256)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("rgb:256,1,255")

            error = ValueOutOfRange("Value was not within bounds", component="g", minimum=0, maximum=255, value=256)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("rgb:255,256,255")

            error = ValueOutOfRange("Value was not within bounds", component="b", minimum=0, maximum=255, value=256)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("rgb:255,255,256")

        it "supports hsb":
            self.assertCorrect("hsb:240,0.1,0.8", 240, 0.1, 0.8, None)
            self.assertCorrect("hsb:240,1%,80%", 240, 0.01, 0.8, None)

            error = ValueOutOfRange("Value was not within bounds", component="hue", minimum=0, maximum=360, value=361)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("hsb:361,0,0.8")

            error = ValueOutOfRange("Value was not within bounds", component="saturation", minimum=0, maximum=1, value=10)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("hsb:240,1000%,0.8")

            error = ValueOutOfRange("Value was not within bounds", component="saturation", minimum=0, maximum=1, value=10)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("hsb:240,10,0.8")

            error = ValueOutOfRange("Value was not within bounds", component="brightness", minimum=0, maximum=1, value=1.2)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("hsb:240,1,120%")

            error = ValueOutOfRange("Value was not within bounds", component="brightness", minimum=0, maximum=1, value=8)
            with self.fuzzyAssertRaisesError(InvalidColor, error=error.as_dict()):
                Parser.hsbk("hsb:240,1,8")

        it "supports colors by name":
            for name in Parser.named_colors:
                self.assertCorrect(name, *Parser.named_colors[name])

        it "supports stacking":
            self.assertCorrect("hsb:240,0.1,0.8 kelvin:2500", 240, 0, 0.8, 2500)
            self.assertCorrect("#010101 hue:240 kelvin:2500", 240, 0, 0.00392156862745098, 2500)
            self.assertCorrect("blue kelvin:3500 saturation:0.4", 250, 0.4, None, 3500)

    describe "color_to_msg":
        it "creates a SetWaveformOptional":
            h, s, b, k = 240, 0.1, None, 2500
            hsbk = mock.Mock(name="hsbk", return_value=(h, s, b, k))
            components = mock.Mock(name="components")

            with mock.patch.object(Parser, "hsbk", hsbk):
                msg = Parser.color_to_msg(components)
                assert msg | LightMessages.SetWaveformOptional
                self.assertEqual(msg.payload.as_dict()
                    , { 'reserved6': sb.NotSpecified
                      , 'transient': 0
                      , 'hue': 240.0
                      , 'saturation': 0.09999237048905166
                      , 'brightness': 0.0
                      , 'kelvin': 2500
                      , 'period': 0.0
                      , 'cycles': 1.0
                      , 'skew_ratio': 0.0
                      , 'waveform': Waveform.SAW
                      , 'set_hue': 1
                      , 'set_saturation': 1
                      , 'set_brightness': 0
                      , 'set_kelvin': 1
                      }
                    )

            hsbk.assert_called_once_with(components, None)

        it "allows overrides":
            h, s, b, k = 240, 0.1, None, 2500
            hsbk = mock.Mock(name="hsbk", return_value=(h, s, b, k))
            components = mock.Mock(name="components")
            overrides = {"transient": 1, "period": 1}

            with mock.patch.object(Parser, "hsbk", hsbk):
                msg = Parser.color_to_msg(components, overrides)
                assert msg | LightMessages.SetWaveformOptional
                self.assertEqual(msg.payload.as_dict()
                    , { 'reserved6': sb.NotSpecified
                      , 'transient': 1
                      , 'hue': 240.0
                      , 'saturation': 0.09999237048905166
                      , 'brightness': 0.0
                      , 'kelvin': 2500
                      , 'period': 1
                      , 'cycles': 1.0
                      , 'skew_ratio': 0.0
                      , 'waveform': Waveform.SAW
                      , 'set_hue': 1
                      , 'set_saturation': 1
                      , 'set_brightness': 0
                      , 'set_kelvin': 1
                      }
                    )

            hsbk.assert_called_once_with(components, overrides)

        it "allows effects":
            h, s, b, k = 240, 0.1, None, 2500
            hsbk = mock.Mock(name="hsbk", return_value=(h, s, b, k))
            components = mock.Mock(name="components")
            overrides = {"effect": "sine"}

            with mock.patch.object(Parser, "hsbk", hsbk):
                msg = Parser.color_to_msg(components, overrides)
                assert msg | LightMessages.SetWaveformOptional
                self.assertEqual(msg.payload.as_dict()
                    , { 'reserved6': sb.NotSpecified
                      , 'transient': 1
                      , 'hue': 240.0
                      , 'saturation': 0.09999237048905166
                      , 'brightness': 0.0
                      , 'kelvin': 2500
                      , 'period': 1.0
                      , 'cycles': 1.0
                      , 'skew_ratio': 0.499984740745262
                      , 'waveform': Waveform.SINE
                      , 'set_hue': 1
                      , 'set_saturation': 1
                      , 'set_brightness': 0
                      , 'set_kelvin': 1
                      }
                    )

            hsbk.assert_called_once_with(components, overrides)

        it "allows overrides to effects":
            h, s, b, k = 240, 0.1, None, 2500
            hsbk = mock.Mock(name="hsbk", return_value=(h, s, b, k))
            components = mock.Mock(name="components")
            overrides = {"effect": "sine", "waveform": Waveform.PULSE, "skew_ratio": 0.2}

            with mock.patch.object(Parser, "hsbk", hsbk):
                msg = Parser.color_to_msg(components, overrides)
                assert msg | LightMessages.SetWaveformOptional
                self.assertEqual(msg.payload.as_dict()
                    , { 'reserved6': sb.NotSpecified
                      , 'transient': 1
                      , 'hue': 240.0
                      , 'saturation': 0.09999237048905166
                      , 'brightness': 0.0
                      , 'kelvin': 2500
                      , 'period': 1.0
                      , 'cycles': 1.0
                      , 'skew_ratio': 0.1999877925962096
                      , 'waveform': Waveform.PULSE
                      , 'set_hue': 1
                      , 'set_saturation': 1
                      , 'set_brightness': 0
                      , 'set_kelvin': 1
                      }
                    )

            hsbk.assert_called_once_with(components, overrides)
