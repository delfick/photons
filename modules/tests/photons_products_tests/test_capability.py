# coding: spec

from photons_products.base import Product, Capability, CapabilityValue, CapabilityRange

from photons_app.errors import ProgrammerError

from delfick_project.errors_pytest import assertRaises
import pytest


@pytest.fixture
def product():
    class P(Product):
        pid = 1
        name = "P"
        vendor = 1
        family = "computer"
        friendly = "P"

        class cap(Capability):
            pass

    return P


@pytest.fixture
def cap(product):
    return product.cap


describe "CapabilityValue":
    it "can have one value", cap:
        cv = CapabilityValue(1)
        assert cv.value(cap) == 1
        assert cv.value(cap(2, 80)) == 1

    it "can have upgrades", cap:
        cv = (
            CapabilityValue(1)
            .until(1, 40, becomes=2)
            .until(2, 50, becomes=3)
            .until(2, 60, becomes=4)
            .until(3, 70, becomes=5)
        )
        assert cv.value(cap) == 1
        assert cv.value(cap(1, 30)) == 1
        assert cv.value(cap(1, 40)) == 2
        assert cv.value(cap(2, 51)) == 3
        assert cv.value(cap(2, 60)) == 4
        assert cv.value(cap(2, 61)) == 4
        assert cv.value(cap(2, 90)) == 4
        assert cv.value(cap(3, 90)) == 5
        assert cv.value(cap(4, 60)) == 5

    it "complains if you give upgrades out of order":
        with assertRaises(ProgrammerError, "Each .until must be for a greater version number"):
            CapabilityValue(1).until(1, 40, becomes=2).until(2, 60, becomes=4).until(
                2, 50, becomes=3
            ).until(3, 70, becomes=5)

    it "has equality":
        cv1 = CapabilityValue(1)
        cv2 = CapabilityValue(1)
        cv3 = CapabilityValue(1).until(2, 70, becomes=20)
        cv4 = CapabilityValue(1).until(2, 70, becomes=20)
        cv5 = CapabilityValue(1).until(2, 70, becomes=20).until(3, 60, becomes=10)

        assert cv1 == cv2
        assert cv1 != cv3
        assert cv3 == cv4
        assert cv3 != cv5

describe "CapabilityRange":
    it "can create two CapabilityValue objects":

        class cap(Capability):
            one, two = CapabilityRange((1, 2))

        assert cap.Meta.capabilities["one"] == CapabilityValue(1)
        assert cap.Meta.capabilities["two"] == CapabilityValue(2)

        class cap(Capability):
            one, two = (
                CapabilityRange((1, 2)).until(2, 70, becomes=(3, 4)).until(7, 60, becomes=(5, 6))
            )

        assert cap.Meta.capabilities["one"] == CapabilityValue(1).until(2, 70, becomes=3).until(
            7, 60, becomes=5
        )
        assert cap.Meta.capabilities["two"] == CapabilityValue(2).until(2, 70, becomes=4).until(
            7, 60, becomes=6
        )

describe "Capability":
    it "puts capabilities on Meta", product:

        class cap(Capability):
            pass

        assert cap.Meta.capabilities == {}

        class cap2(cap):
            has_color = CapabilityValue(True)

        assert cap2(product).has_color is True
        assert cap2.Meta.capabilities == {"has_color": CapabilityValue(True)}
        assert not hasattr(cap2, "has_color")

        class cap3(cap2):
            other = 1
            has_color = CapabilityValue(True).until(2, 77, becomes=False)
            has_one, has_two = CapabilityRange((1, 2))

        assert cap2(product).has_color is True
        assert cap2.Meta.capabilities == {"has_color": CapabilityValue(True)}

        assert cap3(product).has_color is True
        assert cap3.Meta.capabilities == {
            "has_color": CapabilityValue(True).until(2, 77, becomes=False),
            "has_one": CapabilityValue(1),
            "has_two": CapabilityValue(2),
        }
        for attr in ("has_color", "has_one", "has_two"):
            assert not hasattr(cap3, attr)
        assert cap3.other == 1
        assert cap3(product)(2, 77).has_color is False

        class cap4(cap3):
            min_things = CapabilityValue(8.9)

        assert cap4(product).has_color is True
        assert cap4(product).min_things == 8.9
        assert cap4.Meta.capabilities == {
            "has_color": CapabilityValue(True).until(2, 77, becomes=False),
            "min_things": CapabilityValue(8.9),
            "has_one": CapabilityValue(1),
            "has_two": CapabilityValue(2),
        }
        for attr in ("has_color", "has_one", "has_two", "min_things"):
            assert not hasattr(cap4, attr)
        assert cap4.other == 1
        assert cap4(product)(2, 77).has_color is False

        class cap5(cap4):
            has_color = False
            has_one = None

        assert cap5(product).has_color is False
        assert cap5(product).has_one is None
        assert cap5.Meta.capabilities == {
            "has_color": CapabilityValue(False),
            "min_things": CapabilityValue(8.9),
            "has_one": CapabilityValue(None),
            "has_two": CapabilityValue(2),
        }
        for attr in ("has_color", "has_one", "has_two", "min_things"):
            assert not hasattr(cap5, attr), attr

        cap6 = type("cap6", (cap5,), {"has_two": True})
        assert cap6(product).has_two
        for attr in ("has_color", "has_one", "has_two", "min_things"):
            assert not hasattr(cap5, attr), attr
        assert cap6.Meta.capabilities == {
            "has_color": CapabilityValue(False),
            "min_things": CapabilityValue(8.9),
            "has_one": CapabilityValue(None),
            "has_two": CapabilityValue(True),
        }
