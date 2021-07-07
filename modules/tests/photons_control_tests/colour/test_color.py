# coding: spec

from photons_control import test_helpers as chp
from photons_messages import fields

describe "Color":
    it "can be made and cloned":
        c1 = chp.Color(2, 0, 0.3, 3500)
        c2 = c1.clone()

        assert c1 is not c2

        for c in (c1, c2):
            assert c.hue == 2
            assert c["hue"] == 2

            assert c.saturation == 0
            assert c["saturation"] == 0

            assert c.brightness == 0.3
            assert c["brightness"] == 0.3

            assert c.kelvin == 3500
            assert c["kelvin"] == 3500

        c2.hue = 45
        c2.brightness = 1
        assert c2 == chp.Color(45, 0, 1, 3500)
        assert c1 == chp.Color(2, 0, 0.3, 3500)

    it "can be compared with a tuple":
        assert chp.Color(2, 0, 0, 3500) != (2,)
        assert chp.Color(2, 0, 0, 3500) != (2, 0)
        assert chp.Color(2, 0, 0, 3500) != (2, 0, 0)
        assert chp.Color(2, 0, 0, 3500) == (2, 0, 0, 3500)

        assert chp.Color(2, 0, 0, 3500) != (20, 0, 0, 3500)
        assert chp.Color(2, 0, 0, 3500) != (2, 1, 0, 3500)
        assert chp.Color(2, 0, 0, 3500) != (2, 0, 1, 3500)
        assert chp.Color(2, 0, 0, 3500) != (2, 0, 0, 3700)

    it "can be compared with a dictionary":
        assert chp.Color(2, 0, 0, 3500) != {"hue": 2}
        assert chp.Color(2, 0, 0, 3500) != {"hue": 2, "saturation": 0}
        assert chp.Color(2, 0, 0, 3500) != {"hue": 2, "saturation": 0, "brightness": 0}
        assert chp.Color(2, 0, 0, 3500) == {
            "hue": 2,
            "saturation": 0,
            "brightness": 0,
            "kelvin": 3500,
        }

        assert chp.Color(2, 0, 0, 3500) != {
            "hue": 20,
            "saturation": 0,
            "brightness": 0,
            "kelvin": 3500,
        }
        assert chp.Color(2, 0, 0, 3500) != {
            "hue": 2,
            "saturation": 1,
            "brightness": 0,
            "kelvin": 3500,
        }
        assert chp.Color(2, 0, 0, 3500) != {
            "hue": 2,
            "saturation": 0,
            "brightness": 1,
            "kelvin": 3500,
        }
        assert chp.Color(2, 0, 0, 3500) != {
            "hue": 2,
            "saturation": 0,
            "brightness": 0,
            "kelvin": 3700,
        }

    it "can be compared with another chp.Color":
        assert chp.Color(2, 0, 0, 3500) == chp.Color(2, 0, 0, 3500)

        assert chp.Color(2, 0, 0, 3500) != chp.Color(20, 0, 0, 3500)
        assert chp.Color(2, 0, 0, 3500) != chp.Color(2, 1, 0, 3500)
        assert chp.Color(2, 0, 0, 3500) != chp.Color(2, 0, 1, 3500)
        assert chp.Color(2, 0, 0, 3500) != chp.Color(2, 0, 0, 3700)

    it "can be compared with a real fields.Color":
        assert chp.Color(2, 0, 0, 3500) == fields.Color(
            hue=2, saturation=0, brightness=0, kelvin=3500
        )

        assert chp.Color(2, 0, 0, 3500) != fields.Color(
            hue=20, saturation=0, brightness=0, kelvin=3500
        )
        assert chp.Color(2, 0, 0, 3500) != fields.Color(
            hue=2, saturation=1, brightness=0, kelvin=3500
        )
        assert chp.Color(2, 0, 0, 3500) != fields.Color(
            hue=2, saturation=0, brightness=1, kelvin=3500
        )
        assert chp.Color(2, 0, 0, 3500) != fields.Color(
            hue=2, saturation=0, brightness=0, kelvin=3700
        )

    it "compares to 4 decimal places":
        assert chp.Color(250.245677, 0.134577, 0.765477, 4568) == (
            250.245699,
            0.134599,
            0.765499,
            4568,
        )
        assert chp.Color(250.245677, 0.134577, 0.765477, 4568) != (
            250.245799,
            0.134699,
            0.765599,
            4568,
        )

    it "compares hue 359.99 to hue 0.0":
        assert chp.Color(359.99, 1.0, 1.0, 3500) == (
            0.0,
            1.0,
            1.0,
            3500,
        )
