# coding: spec

from photons_products import base, Family, VendorRegistry
from photons_products.errors import IncompleteProduct

from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from unittest import mock

describe TestCase, "Capability":
    it "takes in product and firmware info":
        product = mock.Mock(name="product")
        firmware_major = mock.Mock(name="firmware_major")
        firmware_minor = mock.Mock(name="firmware_minor")
        cap = base.Capability(product, firmware_major, firmware_minor)

        self.assertIs(cap.product, product)
        self.assertIs(cap.firmware_major, firmware_major)
        self.assertIs(cap.firmware_minor, firmware_minor)

    it "defaults firmware info":
        product = mock.Mock(name="product")
        cap = base.Capability(product)

        self.assertIs(cap.product, product)
        self.assertIs(cap.firmware_major, 0)
        self.assertIs(cap.firmware_minor, 0)

    it "can create a clone with new firmware info":
        product = mock.Mock(name="product")
        cap = base.Capability(product)

        firmware_major = mock.Mock(name="firmware_major")
        firmware_minor = mock.Mock(name="firmware_minor")
        clone = cap(firmware_major=firmware_major, firmware_minor=firmware_minor)
        self.assertIs(clone.product, product)
        self.assertIs(clone.firmware_major, firmware_major)
        self.assertIs(clone.firmware_minor, firmware_minor)

        self.assertIs(cap.product, product)
        self.assertIs(cap.firmware_major, 0)
        self.assertIs(cap.firmware_minor, 0)

    it "has a repr":
        product = mock.Mock(name="product")
        product.name = "LIFX_Amaze"
        cap = base.Capability(product)
        self.assertEqual(repr(cap), "<Capability LIFX_Amaze>")

    it "equals if product and firmware are the same":
        product = mock.Mock(name="product")
        cap = base.Capability(product)
        cap2 = base.Capability(product)

        self.assertEqual(cap, cap2)

        cap3 = cap2(firmware_major=3, firmware_minor=4)
        self.assertNotEqual(cap2, cap3)

        product2 = mock.Mock(name="product")
        cap4 = base.Capability(product2)
        self.assertNotEqual(cap, cap4)

    it "returns no items by default":
        product = mock.Mock(name="product")
        cap = base.Capability(product)
        self.assertEqual(list(cap.items()), [])

describe TestCase, "Product":
    it "complains about not having a cap":
        with self.fuzzyAssertRaisesError(
            IncompleteProduct, "Product doesn't have a capability specified", name="P"
        ):

            class P(base.Product):
                pass

    it "complains about attributes not implemented":
        with self.fuzzyAssertRaisesError(
            IncompleteProduct, "Attribute wasn't overridden", attr="family", name="P"
        ):

            class P(base.Product):
                class cap(base.Capability):
                    pass

    it "sets the cap as an instance of the cap class":

        class P(base.Product):
            pid = 1
            family = Family.LCM1
            vendor = VendorRegistry.LIFX

            class cap(base.Capability):
                pass

        self.assertIsInstance(P.cap, P.cap_kls)
        self.assertEqual(P.cap.product, P)

    it "sets a default for friendly and identifier":

        class LCM9_AMAZE_SPHERE(base.Product):
            pid = 1
            family = Family.LCM1
            vendor = VendorRegistry.LIFX

            class cap(base.Capability):
                pass

        self.assertEqual(LCM9_AMAZE_SPHERE.friendly, "lcm9 amaze sphere")
        self.assertEqual(LCM9_AMAZE_SPHERE.identifier, "lcm9_amaze_sphere")

    it "uses modifier methods on the baseclass if they exist":

        class Product(base.Product):
            @classmethod
            def _modify_family(s, val):
                self.assertIs(val, Family.LCM2)
                return "lcm9"

            @classmethod
            def _modify_friendly(s, val):
                self.assertEqual(val, "lcm9 amaze sphere")
                return "sphere"

        class LCM9_AMAZE_SPHERE(Product):
            pid = 1
            family = Family.LCM2
            vendor = VendorRegistry.LIFX

            class cap(base.Capability):
                pass

        self.assertEqual(LCM9_AMAZE_SPHERE.family, "lcm9")
        self.assertEqual(LCM9_AMAZE_SPHERE.friendly, "sphere")
        self.assertEqual(LCM9_AMAZE_SPHERE.identifier, "lcm9_amaze_sphere")

    it "has company":

        class CUBE(base.Product):
            pid = 1
            family = Family.LCM3
            vendor = VendorRegistry.LIFX

            class cap(base.Capability):
                pass

        self.assertEqual(CUBE.company, "LIFX")

    it "is equal if pid and vendor match":

        class capability(base.Capability):
            pass

        class P1(base.Product):
            pid = 1
            family = Family.LCM1
            vendor = VendorRegistry.LIFX
            cap = capability

        class P2(base.Product):
            pid = 1
            family = Family.LCM2
            vendor = VendorRegistry.LIFX
            cap = capability

        class P3(base.Product):
            pid = 2
            family = Family.LCM2
            vendor = VendorRegistry.LIFX
            cap = capability

        class P4(base.Product):
            pid = 1
            family = Family.LCM2
            vendor = VendorRegistry.choose(5)
            cap = capability

        self.assertEqual(P1, P1)
        self.assertEqual(P1, P2)
        self.assertNotEqual(P1, P4)
        self.assertNotEqual(P1, P3)

        self.assertEqual(P1, (VendorRegistry.LIFX, 1))
        self.assertEqual(P1, (1, 1))

        self.assertEqual(P4, (5, 1))
        self.assertEqual(P3, (1, 2))

    it "can be used as a key in a dictionary":

        class P1(base.Product):
            pid = 29
            family = Family.LCM1
            vendor = VendorRegistry.LIFX

            class cap(base.Capability):
                pass

        d = {P1: "thing"}
        self.assertEqual(d[P1], "thing")
        self.assertEqual(d[(1, 29)], "thing")
        self.assertEqual(d[(VendorRegistry.LIFX, 29)], "thing")

    it "has a repr":

        class capability(base.Capability):
            pass

        class LCM1_BOUNCY_BALL(base.Product):
            pid = 1
            family = Family.LCM1
            vendor = VendorRegistry.LIFX
            cap = capability

        class LCM2_DESK(base.Product):
            pid = 1
            family = Family.LCM2
            vendor = VendorRegistry.LIFX
            cap = capability

        class LCM2_MONITOR_STAND(base.Product):
            pid = 29
            family = Family.LCM2
            vendor = VendorRegistry.choose(5)
            cap = capability

        self.assertEqual(repr(LCM1_BOUNCY_BALL), "<Product 1(LIFX):1(LCM1_BOUNCY_BALL)>")
        self.assertEqual(repr(LCM2_DESK), "<Product 1(LIFX):1(LCM2_DESK)>")
        self.assertEqual(repr(LCM2_MONITOR_STAND), "<Product 5(UNKNOWN):29(LCM2_MONITOR_STAND)>")

    it "has an as_dict":

        class LCM2_MONITOR_STAND(base.Product):
            pid = 29
            family = Family.LCM2
            vendor = VendorRegistry.choose(1)

            class cap(base.Capability):
                def items(s):
                    yield "one", "blah"
                    yield "two", "other"

        dct = LCM2_MONITOR_STAND.as_dict()
        self.assertEqual(
            dct,
            {
                "cap": {"one": "blah", "two": "other"},
                "family": Family.LCM2,
                "friendly": "lcm2 monitor stand",
                "identifier": "lcm2_monitor_stand",
                "name": "LCM2_MONITOR_STAND",
                "pid": 29,
                "vendor": VendorRegistry.LIFX,
            },
        )

describe TestCase, "make_unknown_product":
    it "works":

        class cap(base.Capability):
            has_lattice = True

        P = base.make_unknown_product(1, 9001, cap)

        self.assertEqual(P.pid, 9001)
        self.assertEqual(P.vendor, VendorRegistry.LIFX)
        self.assertIs(P.family, Family.UNKNOWN)
        assert P.cap.has_lattice
        self.assertEqual(repr(P), "<Product 1(LIFX):9001(Unknown)>")

describe TestCase, "ProductsHolder":
    before_each:

        class capability(base.Capability):
            has_amaze = True

        class ProductRegistry:
            class LCM1_BOUNCY_BALL(base.Product):
                pid = 1
                family = Family.LCM1
                vendor = VendorRegistry.LIFX
                cap = capability

            class LCM2_DESK(base.Product):
                pid = 3
                family = Family.LCM2
                vendor = VendorRegistry.LIFX
                cap = capability

            class LCM2_MONITOR_STAND(base.Product):
                pid = 29
                family = Family.LCM2
                vendor = VendorRegistry.choose(5)
                cap = capability

        self.ProductRegistry = ProductRegistry
        self.default_capability_kls = capability
        self.holder = base.ProductsHolder(self.ProductRegistry, self.default_capability_kls)

    it "holds onto the products and creates by_pair":
        self.assertIs(self.holder.products, self.ProductRegistry)
        self.assertIs(self.holder.default_capability_kls, self.default_capability_kls)
        self.assertEqual(
            self.holder.by_pair,
            {
                (VendorRegistry.LIFX, 1): self.ProductRegistry.LCM1_BOUNCY_BALL,
                (VendorRegistry.LIFX, 3): self.ProductRegistry.LCM2_DESK,
                (VendorRegistry.choose(5), 29): self.ProductRegistry.LCM2_MONITOR_STAND,
            },
        )

    it "can yield product names":
        self.assertEqual(
            sorted(self.holder.names),
            sorted(["LCM1_BOUNCY_BALL", "LCM2_DESK", "LCM2_MONITOR_STAND"]),
        )

    it "can access products by name":
        self.assertIs(self.holder.LCM1_BOUNCY_BALL, self.ProductRegistry.LCM1_BOUNCY_BALL)
        self.assertIs(self.holder.LCM2_DESK, self.ProductRegistry.LCM2_DESK)

    it "complains if the product doesn't exist":
        with self.fuzzyAssertRaisesError(
            AttributeError, "'ProductsHolder' object has no attribute 'LCM9_SPHERE'"
        ):
            self.holder.LCM9_SPHERE

    it "can still get hidden things from the holder":
        self.assertEqual(self.holder.__name__, "ProductRegistry")

    it "can access products by dictionary access":
        self.assertIs(self.holder["LCM1_BOUNCY_BALL"], self.ProductRegistry.LCM1_BOUNCY_BALL)
        self.assertIs(self.holder[VendorRegistry.LIFX, 3], self.ProductRegistry.LCM2_DESK)
        self.assertIs(self.holder[1, 3], self.ProductRegistry.LCM2_DESK)

        with self.fuzzyAssertRaisesError(KeyError, "No such product definition: LCM9_SPHERE"):
            self.holder["LCM9_SPHERE"]

        p = self.holder[9, 1]
        assert p.cap.has_amaze
        self.assertEqual(p.vendor, VendorRegistry.choose(9))
        self.assertEqual(p.pid, 1)
        self.assertIs(p.family, Family.UNKNOWN)
