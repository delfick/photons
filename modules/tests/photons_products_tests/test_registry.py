# coding: spec

from photons_products import VendorRegistry, Family, Zones, lifx
from photons_products.base import CapabilityValue

describe "lifx.Product":
    it "has default vendor":

        class P(lifx.Product):
            pid = 3
            family = Family.LCM3
            friendly = "P"

            class cap(lifx.Capability):
                pass

        assert P.vendor is VendorRegistry.LIFX


describe "Capability":
    it "has has_matrix":

        class P(lifx.Product):
            pid = 1
            name = "Product"
            family = Family.LCM3
            friendly = "Product"

            class cap(lifx.Capability):
                pass

        class cap(lifx.Capability):
            zones = Zones.MATRIX

        assert cap(P).has_matrix

        class cap(lifx.Capability):
            zones = Zones.LINEAR

        assert not cap(P).has_matrix

        class cap(lifx.Capability):
            zones = Zones.SINGLE

        assert not cap(P).has_matrix

    it "has has_multizone":

        class P(lifx.Product):
            pid = 1
            name = "Product"
            family = Family.LCM3
            friendly = "Product"

            class cap(lifx.Capability):
                pass

        class cap(lifx.Capability):
            zones = Zones.MATRIX

        assert not cap(P).has_multizone

        class cap(lifx.Capability):
            zones = Zones.LINEAR

        assert cap(P).has_multizone

        class cap(lifx.Capability):
            zones = Zones.SINGLE

        assert not cap(P).has_multizone

    it "has has_extended_multizone":

        class P(lifx.Product):
            pid = 1
            name = "Product"
            family = Family.LCM3
            friendly = "Product"

            class cap(lifx.Capability):
                pass

        class cap(lifx.Capability):
            pass

        c = cap(P)

        assert not c.has_extended_multizone
        assert not c(firmware_major=2, firmware_minor=77).has_extended_multizone

        class cap(lifx.Capability):
            has_extended_multizone = CapabilityValue(False).until(2, 77, becomes=True)

        c = cap(P)

        assert not c.has_extended_multizone
        assert c(firmware_major=2, firmware_minor=77).has_extended_multizone
        assert not c(firmware_major=1, firmware_minor=77).has_extended_multizone
        assert not c(firmware_major=2, firmware_minor=60).has_extended_multizone
        assert c(firmware_major=3, firmware_minor=60).has_extended_multizone

    it "has items":

        class P(lifx.Product):
            pid = 1
            name = "Product"
            family = Family.LCM3
            friendly = "Product"

            class cap(lifx.Capability):
                pass

        class cap(lifx.Capability):
            pass

        c = cap(P, firmware_major=3, firmware_minor=77)

        dct = dict(c.items())
        expected = {
            "zones": Zones.SINGLE,
            "has_color": False,
            "has_chain": False,
            "has_matrix": False,
            "has_multizone": False,
            "has_extended_multizone": False,
            "has_variable_color_temp": True,
            "min_kelvin": 2500,
            "max_kelvin": 9000,
        }

        for k in list(dct):
            if k not in expected:
                del dct[k]
        assert dct == expected

        class cap(lifx.Capability):
            has_extended_multizone = CapabilityValue(False).until(3, 60, becomes=True)
            has_color = True
            zones = Zones.LINEAR

        c = cap(P, firmware_major=3, firmware_minor=77)

        dct = dict(c.items())

        expected = {
            "zones": Zones.LINEAR,
            "has_color": True,
            "has_chain": False,
            "has_matrix": False,
            "has_multizone": True,
            "has_extended_multizone": True,
            "has_variable_color_temp": True,
            "min_kelvin": 2500,
            "max_kelvin": 9000,
        }

        for k in list(dct):
            if k not in expected:
                del dct[k]
        assert dct == expected

    it "has items for non light products":

        class P(lifx.Product):
            pid = 1
            name = "Product"
            family = Family.LCM3
            friendly = "Product"

            class cap(lifx.Capability):
                pass

        class cap(lifx.NonLightCapability):
            has_relays = True

        c = cap(P, firmware_major=3, firmware_minor=81)
        assert not c.is_light

        assert dict(c.items()) == {"has_relays": True, "has_buttons": False}
