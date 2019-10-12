# coding: spec

from photons_products.enums import Vendor, VendorRegistry

from photons_app.test_helpers import TestCase


describe TestCase, "Vendor":
    it "takes in vid and has default name":
        v = Vendor(99)
        self.assertEqual(v.vid, 99)
        self.assertEqual(v.name, "UNKNOWN")

    it "equals other integers and other Vendor":
        v = Vendor(1)
        v2 = Vendor(1)

        self.assertEqual(v, 1)
        self.assertEqual(v, v2)
        self.assertEqual(v, v)

    it "can be given a name":

        class T:
            BLAH = Vendor(1)

        self.assertEqual(T.BLAH.vid, 1)
        self.assertEqual(T.BLAH.name, "BLAH")

        class O:
            OTHER = T.BLAH

        self.assertEqual(O.OTHER.name, "BLAH")

    it "has a repr":
        v = Vendor(2)
        v.__set_name__(None, "thing")
        self.assertEqual(repr(v), "<Vendor 2:thing>")

    it "can be used as a key in a dictionary":
        v = Vendor(1)
        d = {v: "thing"}
        self.assertEqual(d[1], "thing")
        self.assertEqual(d[Vendor(1)], "thing")
        self.assertEqual(d[v], "thing")

describe TestCase, "VendorRegistry":
    describe "choose":
        it "returns objects in the registry":
            v = VendorRegistry.choose(1)
            self.assertIs(v, VendorRegistry.LIFX)

            v = VendorRegistry.choose(2)
            self.assertIs(v, VendorRegistry.QUALCOMM)

        it "returns unknown vendor":
            v = VendorRegistry.choose(99)
            self.assertEqual(v.vid, 99)
            self.assertEqual(v.name, "UNKNOWN")
