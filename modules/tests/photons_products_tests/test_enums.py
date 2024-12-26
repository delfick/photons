from photons_products.enums import Vendor, VendorRegistry


class TestVendor:
    def test_it_takes_in_vid_and_has_default_name(self):
        v = Vendor(99)
        assert v.vid == 99
        assert v.name == "UNKNOWN"

    def test_it_equals_other_integers_and_other_Vendor(self):
        v = Vendor(1)
        v2 = Vendor(1)

        assert v == 1
        assert v == v2
        assert v == v

    def test_it_can_be_given_a_name(self):
        class T:
            BLAH = Vendor(1)

        assert T.BLAH.vid == 1
        assert T.BLAH.name == "BLAH"

        class OO:
            OTHER = T.BLAH

        assert OO.OTHER.name == "BLAH"

    def test_it_has_a_repr(self):
        v = Vendor(2)
        v.__set_name__(None, "thing")
        assert repr(v) == "<Vendor 2:thing>"

    def test_it_can_be_used_as_a_key_in_a_dictionary(self):
        v = Vendor(1)
        d = {v: "thing"}
        assert d[1] == "thing"
        assert d[Vendor(1)] == "thing"
        assert d[v] == "thing"


class TestVendorRegistry:
    class TestChoose:
        def test_it_returns_objects_in_the_registry(self):
            v = VendorRegistry.choose(1)
            assert v is VendorRegistry.LIFX

            v = VendorRegistry.choose(2)
            assert v is VendorRegistry.QUALCOMM

        def test_it_returns_unknown_vendor(self):
            v = VendorRegistry.choose(99)
            assert v.vid == 99
            assert v.name == "UNKNOWN"
