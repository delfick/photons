# coding: spec

from photons_products import VendorRegistry, Family, Zones, lifx
from photons_products.base import CapabilityValue

from unittest import mock

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
        product = mock.Mock(name="product")

        class cap(lifx.Capability):
            zones = Zones.MATRIX

        assert cap(product).has_matrix

        class cap(lifx.Capability):
            zones = Zones.LINEAR

        assert not cap(product).has_matrix

        class cap(lifx.Capability):
            zones = Zones.SINGLE

        assert not cap(product).has_matrix

    it "has has_multizone":
        product = mock.Mock(name="product")

        class cap(lifx.Capability):
            zones = Zones.MATRIX

        assert not cap(product).has_multizone

        class cap(lifx.Capability):
            zones = Zones.LINEAR

        assert cap(product).has_multizone

        class cap(lifx.Capability):
            zones = Zones.SINGLE

        assert not cap(product).has_multizone

    it "has has_extended_multizone":
        product = mock.Mock(name="product")

        print("TEST", lifx.Capability.Meta.capabilities["has_extended_multizone"].upgrades)

        class cap(lifx.Capability):
            pass

        c = cap(product)

        assert not c.has_extended_multizone
        assert not c(firmware_major=2, firmware_minor=77).has_extended_multizone

        class cap(lifx.Capability):
            has_extended_multizone = CapabilityValue(False).until(2, 77, becomes=True)

        c = cap(product)

        assert not c.has_extended_multizone
        assert c(firmware_major=2, firmware_minor=77).has_extended_multizone
        assert not c(firmware_major=1, firmware_minor=77).has_extended_multizone
        assert not c(firmware_major=2, firmware_minor=60).has_extended_multizone
        assert c(firmware_major=3, firmware_minor=60).has_extended_multizone

    it "has items":
        product = mock.Mock(name="product")

        class cap(lifx.Capability):
            pass

        c = cap(product, firmware_major=3, firmware_minor=77)

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

        c = cap(product, firmware_major=3, firmware_minor=77)

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
        product = mock.Mock(name="product")

        class cap(lifx.NonLightCapability):
            has_relays = True

        c = cap(product, firmware_major=3, firmware_minor=81)
        assert not c.is_light

        assert dict(c.items()) == {"has_relays": True, "has_buttons": False}
