# coding: spec

from photons_control import test_helpers as chp

from photons_app.test_helpers import TestCase

describe TestCase, "HSBKClose":
    it "is close if within 0.1 for saturation and brightness":
        target = chp.Color(0, 0.1, 0.5, 1500)

        close = lambda hue, saturation, brightness, kelvin: chp.HSBKClose({"hue": hue, "saturation": saturation, "brightness": brightness, "kelvin": kelvin})

        assert close(0, 0.1, 0.5, 1500) == target
        assert close(0, 0.2, 0.6, 1500) == target
        assert close(0, 0.0, 0.4, 1500) == target
        assert close(0, 0.000001, 0.4000001, 1500) == target

        assert close(0, 0.2100001, 0.6100001, 1500) != target
        assert close(0, 0.2100001, 0.6100001, 1500) != target
        assert close(0, 0.3, 0.7, 1500) != target
        assert close(0, 0.3, 0.5, 1500) != target
        assert close(0, 0.1, 0.7, 1500) != target

    it "is close if within 1 for hue and kelvin":
        target = chp.Color(100, 0.1, 0.5, 2500)

        close = lambda hue, saturation, brightness, kelvin: chp.HSBKClose({"hue": hue, "saturation": saturation, "brightness": brightness, "kelvin": kelvin})

        assert close(100, 0.1, 0.5, 2500) == target
        assert close(101, 0.1, 0.5, 2501) == target
        assert close(99, 0.1, 0.5, 2499) == target
        assert close(100.000002, 0.1, 0.5, 2500.0002) == target

        assert close(98, 0.1, 0.5, 2498) != target
        assert close(102, 0.1, 0.5, 2502) != target
        assert close(100, 0.1, 0.5, 2502) != target
        assert close(102, 0.1, 0.5, 2500) != target

    it "is False if the data is weird":
        assert not chp.HSBKClose({"hue": 0}) == chp.Color(0, 0, 0, 0)
        assert not chp.HSBKClose({"saturation": 0}) == chp.Color(0, 0, 0, 0)
        assert not chp.HSBKClose({"brightness": 0}) == chp.Color(0, 0, 0, 0)
        assert not chp.HSBKClose({"kelvin": 0}) == chp.Color(0, 0, 0, 0)

        assert chp.HSBKClose({"hue": 0, "saturation": 0, "brightness": 0, "kelvin": 0}) == chp.Color(0, 0, 0, 0)
        assert not chp.HSBKClose({"hue": 0, "saturation": 0, "brightness": 0, "kelvin": 0, "other": 0}) == chp.Color(0, 0, 0, 0)
