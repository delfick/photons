# coding: spec

from photons_products.enums import Vendor, VendorRegistry


describe "Vendor":
    it "takes in vid and has default name":
        v = Vendor(99)
        assert v.vid == 99
        assert v.name == "UNKNOWN"

    it "equals other integers and other Vendor":
        v = Vendor(1)
        v2 = Vendor(1)

        assert v == 1
        assert v == v2
        assert v == v

    it "can be given a name":

        class T:
            BLAH = Vendor(1)

        assert T.BLAH.vid == 1
        assert T.BLAH.name == "BLAH"

        class O:
            OTHER = T.BLAH

        assert O.OTHER.name == "BLAH"

    it "has a repr":
        v = Vendor(2)
        v.__set_name__(None, "thing")
        assert repr(v) == "<Vendor 2:thing>"

    it "can be used as a key in a dictionary":
        v = Vendor(1)
        d = {v: "thing"}
        assert d[1] == "thing"
        assert d[Vendor(1)] == "thing"
        assert d[v] == "thing"

describe "VendorRegistry":
    describe "choose":
        it "returns objects in the registry":
            v = VendorRegistry.choose(1)
            assert v is VendorRegistry.LIFX

            v = VendorRegistry.choose(2)
            assert v is VendorRegistry.QUALCOMM

        it "returns unknown vendor":
            v = VendorRegistry.choose(99)
            assert v.vid == 99
            assert v.name == "UNKNOWN"
