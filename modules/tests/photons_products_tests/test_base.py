from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_products import Family, VendorRegistry, base
from photons_products.errors import IncompleteProduct


class TestCapability:
    def test_it_takes_in_product_and_firmware_info(self):
        product = mock.Mock(name="product")
        firmware_major = mock.Mock(name="firmware_major")
        firmware_minor = mock.Mock(name="firmware_minor")
        cap = base.Capability(product, firmware_major, firmware_minor)

        assert cap.product is product
        assert cap.firmware_major is firmware_major
        assert cap.firmware_minor is firmware_minor

    def test_it_defaults_firmware_info(self):
        product = mock.Mock(name="product")
        cap = base.Capability(product)

        assert cap.product is product
        assert cap.firmware_major == 0
        assert cap.firmware_minor == 0

    def test_it_can_create_a_clone_with_new_firmware_info(self):
        product = mock.Mock(name="product")
        cap = base.Capability(product)

        firmware_major = mock.Mock(name="firmware_major")
        firmware_minor = mock.Mock(name="firmware_minor")
        clone = cap(firmware_major=firmware_major, firmware_minor=firmware_minor)
        assert clone.product is product
        assert clone.firmware_major is firmware_major
        assert clone.firmware_minor is firmware_minor

        assert cap.product is product
        assert cap.firmware_major == 0
        assert cap.firmware_minor == 0

    def test_it_has_a_repr(self):
        product = mock.Mock(name="product")
        product.name = "LIFX_Amaze"
        cap = base.Capability(product)
        assert repr(cap) == "<Capability LIFX_Amaze>"

    def test_it_equals_if_product_and_firmware_are_the_same(self):
        product = mock.Mock(name="product")
        cap = base.Capability(product)
        cap2 = base.Capability(product)

        assert cap == cap2

        cap3 = cap2(firmware_major=3, firmware_minor=4)
        assert cap2 != cap3

        product2 = mock.Mock(name="product")
        cap4 = base.Capability(product2)
        assert cap != cap4

    def test_it_returns_no_items_by_default(self):
        product = mock.Mock(name="product")
        cap = base.Capability(product)
        assert list(cap.items()) == []


class TestProduct:
    def test_it_complains_about_not_having_a_cap(self):
        with assertRaises(IncompleteProduct, "Product doesn't have a capability specified", name="P"):

            class P(base.Product):
                pass

    def test_it_complains_about_attributes_not_implemented(self):
        with assertRaises(IncompleteProduct, "Attribute wasn't overridden", attr="family", name="P"):

            class P(base.Product):
                class cap(base.Capability):
                    pass

    def test_it_sets_the_cap_as_an_instance_of_the_cap_class(self):
        class P(base.Product):
            pid = 1
            family = Family.LCM1
            vendor = VendorRegistry.LIFX
            friendly = "P"

            class cap(base.Capability):
                pass

        assert isinstance(P.cap, P.cap_kls)
        assert P.cap.product == P

    def test_it_does_not_set_a_default_for_friendly(self):
        msg = "Attribute wasn't overridden"
        with assertRaises(IncompleteProduct, msg, attr="friendly"):

            class LCM9_AMAZE_SPHERE(base.Product):
                pid = 1
                family = Family.LCM1
                vendor = VendorRegistry.LIFX

                class cap(base.Capability):
                    pass

    def test_it_has_company(self):
        class CUBE(base.Product):
            pid = 1
            family = Family.LCM3
            vendor = VendorRegistry.LIFX
            friendly = "Cube"

            class cap(base.Capability):
                pass

        assert CUBE.company == "LIFX"

    def test_it_is_equal_if_pid_and_vendor_match(self):
        class capability(base.Capability):
            pass

        class P1(base.Product):
            pid = 1
            family = Family.LCM1
            vendor = VendorRegistry.LIFX
            cap = capability
            friendly = "P1"

        class P2(base.Product):
            pid = 1
            family = Family.LCM2
            vendor = VendorRegistry.LIFX
            cap = capability
            friendly = "P2"

        class P3(base.Product):
            pid = 2
            family = Family.LCM2
            vendor = VendorRegistry.LIFX
            cap = capability
            friendly = "P3"

        class P4(base.Product):
            pid = 1
            family = Family.LCM2
            vendor = VendorRegistry.choose(5)
            cap = capability
            friendly = "P4"

        assert P1 == P1
        assert P1 == P2
        assert P1 != P4
        assert P1 != P3

        assert P1 == (VendorRegistry.LIFX, 1)
        assert P1 == (1, 1)

        assert P4 == (5, 1)
        assert P3 == (1, 2)

    def test_it_can_be_used_as_a_key_in_a_dictionary(self):
        class P1(base.Product):
            pid = 29
            family = Family.LCM1
            vendor = VendorRegistry.LIFX
            friendly = "P1"

            class cap(base.Capability):
                pass

        d = {P1: "thing"}
        assert d[P1] == "thing"
        assert d[(1, 29)] == "thing"
        assert d[(VendorRegistry.LIFX, 29)] == "thing"

    def test_it_has_a_repr(self):
        class capability(base.Capability):
            pass

        class LCM1_BOUNCY_BALL(base.Product):
            pid = 1
            family = Family.LCM1
            vendor = VendorRegistry.LIFX
            cap = capability
            friendly = "Bouncy Ball"

        class LCM2_DESK(base.Product):
            pid = 1
            family = Family.LCM2
            vendor = VendorRegistry.LIFX
            cap = capability
            friendly = "Desk"

        class LCM2_MONITOR_STAND(base.Product):
            pid = 29
            family = Family.LCM2
            vendor = VendorRegistry.choose(5)
            cap = capability
            friendly = "Monitor Stand"

        assert repr(LCM1_BOUNCY_BALL) == "<Product 1(LIFX):1(LCM1_BOUNCY_BALL)>"
        assert repr(LCM2_DESK) == "<Product 1(LIFX):1(LCM2_DESK)>"
        assert repr(LCM2_MONITOR_STAND) == "<Product 5(UNKNOWN):29(LCM2_MONITOR_STAND)>"

    def test_it_has_an_as_dict(self):
        class LCM2_MONITOR_STAND(base.Product):
            pid = 29
            family = Family.LCM2
            vendor = VendorRegistry.choose(1)
            friendly = "Monitor Stand"

            class cap(base.Capability):
                def items(s):
                    yield "one", "blah"
                    yield "two", "other"

        dct = LCM2_MONITOR_STAND.as_dict()
        assert dct == {
            "cap": {"one": "blah", "two": "other"},
            "family": Family.LCM2,
            "friendly": "Monitor Stand",
            "name": "LCM2_MONITOR_STAND",
            "pid": 29,
            "vendor": VendorRegistry.LIFX,
        }


class TestMakeUnknownProduct:
    def test_it_works(self):
        class cap(base.Capability):
            has_lattice = True

        P = base.make_unknown_product(1, 9001, cap)

        assert P.pid == 9001
        assert P.vendor == VendorRegistry.LIFX
        assert P.family is Family.UNKNOWN
        assert P.cap.has_lattice
        assert repr(P) == "<Product 1(LIFX):9001(Unknown)>"


class TestProductsHolder:
    @pytest.fixture()
    def default_capability_kls(self):
        class capability(base.Capability):
            has_amaze = True

        return capability

    @pytest.fixture()
    def ProductRegistry(self, default_capability_kls):
        class ProductRegistry:
            class LCM1_BOUNCY_BALL(base.Product):
                pid = 1
                family = Family.LCM1
                vendor = VendorRegistry.LIFX
                cap = default_capability_kls
                friendly = "Bouncy Ball"

            class LCM2_DESK(base.Product):
                pid = 3
                family = Family.LCM2
                vendor = VendorRegistry.LIFX
                cap = default_capability_kls
                friendly = "Desk"

            class LCM2_MONITOR_STAND(base.Product):
                pid = 29
                family = Family.LCM2
                vendor = VendorRegistry.choose(5)
                cap = default_capability_kls
                friendly = "Monitor Stand"

        return ProductRegistry

    @pytest.fixture()
    def holder(self, ProductRegistry, default_capability_kls):
        return base.ProductsHolder(ProductRegistry, default_capability_kls)

    def test_it_holds_onto_the_products_and_creates_by_pair(self, ProductRegistry, holder, default_capability_kls):
        assert holder.products is ProductRegistry
        assert holder.default_capability_kls is default_capability_kls
        assert holder.by_pair == {
            (VendorRegistry.LIFX, 1): ProductRegistry.LCM1_BOUNCY_BALL,
            (VendorRegistry.LIFX, 3): ProductRegistry.LCM2_DESK,
            (VendorRegistry.choose(5), 29): ProductRegistry.LCM2_MONITOR_STAND,
        }

    def test_it_can_yield_product_names(self, holder, ProductRegistry):
        assert sorted(holder.names) == sorted(["LCM1_BOUNCY_BALL", "LCM2_DESK", "LCM2_MONITOR_STAND"])

    def test_it_can_access_products_by_name(self, holder, ProductRegistry):
        assert holder.LCM1_BOUNCY_BALL is ProductRegistry.LCM1_BOUNCY_BALL
        assert holder.LCM2_DESK is ProductRegistry.LCM2_DESK

    def test_it_complains_if_the_product_doesnt_exist(self, holder):
        with assertRaises(AttributeError, "'ProductsHolder' object has no attribute 'LCM9_SPHERE'"):
            holder.LCM9_SPHERE

    def test_it_can_still_get_hidden_things_from_the_holder(self, holder):
        assert holder.__name__ == "ProductRegistry"

    def test_it_can_access_products_by_dictionary_access(self, holder, ProductRegistry):
        assert holder["LCM1_BOUNCY_BALL"] is ProductRegistry.LCM1_BOUNCY_BALL
        assert holder[VendorRegistry.LIFX, 3] is ProductRegistry.LCM2_DESK
        assert holder[1, 3] is ProductRegistry.LCM2_DESK

        with assertRaises(KeyError, "No such product definition: LCM9_SPHERE"):
            holder["LCM9_SPHERE"]

        p = holder[9, 1]
        assert p.cap.has_amaze
        assert p.vendor == VendorRegistry.choose(9)
        assert p.pid == 1
        assert p.family is Family.UNKNOWN
