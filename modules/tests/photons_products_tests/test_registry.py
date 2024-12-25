
from photons_products import Family, VendorRegistry, Zones, lifx
from photons_products.base import CapabilityValue

class TestLifxProduct:
    def test_it_has_default_vendor(self):

        class P(lifx.Product):
            pid = 3
            family = Family.LCM3
            friendly = "P"

            class cap(lifx.Capability):
                pass

        assert P.vendor is VendorRegistry.LIFX


class TestCapability:
    def test_it_has_has_matrix(self):

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

    def test_it_has_has_multizone(self):

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

    def test_it_has_has_extended_multizone(self):

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

    def test_it_has_items(self):

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

    def test_it_has_items_for_non_light_products(self):

        class P_SWITCH(lifx.Product):
            pid = 1
            name = "Product"
            family = Family.LCM3
            friendly = "Product"

            class cap(lifx.Capability):
                pass

        class cap(lifx.NonLightCapability):
            has_relays = True

        c = cap(P_SWITCH, firmware_major=3, firmware_minor=81)
        assert not c.is_light

        caps = dict(c.items())
        assert caps["has_relays"]
        assert caps["has_unhandled"]
        assert caps["has_buttons"] is False
        for key, value in c.items():
            if key not in ("has_relays", "has_buttons", "has_unhandled"):
                assert value is None, key
