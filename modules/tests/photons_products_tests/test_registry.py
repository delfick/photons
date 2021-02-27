# coding: spec

from photons_products import registry, VendorRegistry, Family, Zones, lifx

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue
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
    it "understands correct min_extended_fw":

        class cap(lifx.Capability):
            min_extended_fw = (1, 2)

        assert cap.min_extended_fw == (1, 2)

        class cap2(lifx.Capability):
            min_extended_fw = None

        assert cap2.min_extended_fw is None

        class cap3(lifx.Capability):
            pass

        assert cap3.min_extended_fw is None

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

        class cap(lifx.Capability):
            pass

        c = cap(product)

        assert not c.has_extended_multizone
        assert not c(firmware_major=2, firmware_minor=77).has_extended_multizone

        class cap(lifx.Capability):
            min_extended_fw = (2, 77)

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
            "min_extended_fw": None,
        }

        for k in list(dct):
            if k not in expected:
                del dct[k]
        assert dct == expected

        class cap(lifx.Capability):
            min_extended_fw = (3, 60)
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
            "min_extended_fw": (3, 60),
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
