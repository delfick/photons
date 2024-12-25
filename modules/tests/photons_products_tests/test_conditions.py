
from photons_products import conditions as cond
from photons_products.base import Capability, Product

class TestFamily:
    def test_it_compares_family(self):
        c1 = cond.Family("ghost")
        c2 = cond.Family("ghost")
        c3 = cond.Family("vampire")

        c1 == c2
        c1 != c3

        assert repr(c1) == "family=ghost"
        assert repr(c3) == "family=vampire"

        assert c1 != "one"

        class P1(Product):
            pid = 1
            vendor = 1
            family = "ghost"
            friendly = "P"

            class cap(Capability):
                pass

        assert c1(P1.cap)
        assert not c3(P1.cap)

        class P2(Product):
            pid = 2
            vendor = 1
            family = "vampire"
            friendly = "P"

            class cap(Capability):
                pass

        assert not c1(P2.cap)
        assert c3(P2.cap)

class TestCapability:
    def test_it_checks_capabilities(self):
        c1 = cond.Capability(one=1, two=2)
        c2 = cond.Capability(one=1, two=2)
        c3 = cond.Capability(one=1, three=4)

        assert c1 == c2
        assert c1 != c3
        assert c1 != {"one": 1, "two": 2}

        assert repr(c1) == "capabilities(one=1 two=2)"
        assert repr(c3) == "capabilities(one=1 three=4)"

        class P1(Product):
            pid = 1
            vendor = 1
            family = "vampire"
            friendly = "P"

            class cap(Capability):
                one = 1
                two = 2
                three = 3
                four = 4

        class P2(Product):
            pid = 2
            vendor = 1
            family = "vampire"
            friendly = "P"

            class cap(Capability):
                one = 2
                two = 2
                three = 4
                four = 5

        class P3(Product):
            pid = 3
            vendor = 1
            family = "vampire"
            friendly = "P"

            class cap(Capability):
                one = 1
                two = 3
                three = 4
                four = 5

        assert c1(P1.cap)
        assert not c3(P1.cap)
        assert not c1(P2.cap)
        assert not c3(P2.cap)
        assert not c1(P3.cap)
        assert c3(P3.cap)


class TestNameHas:
    def test_it_compares_if_name_of_product_contains_a_certain_fragment(self):
        c1 = cond.NameHas("APPLE")
        c2 = cond.NameHas("APPLE")
        c3 = cond.NameHas("BANANA")

        assert c1 == c2
        assert c1 != c3
        assert c1 != "APPLE"

        assert repr(c1) == "name_contains(APPLE)"
        assert repr(c3) == "name_contains(BANANA)"

        class FRUIT_APPLE(Product):
            pid = 1
            vendor = 1
            family = "edible"
            friendly = "Apple"

            class cap(Capability):
                pass

        class FRUIT_BANANA(Product):
            pid = 2
            vendor = 1
            family = "edible"
            friendly = "Banana"

            class cap(Capability):
                pass

        assert c1(FRUIT_APPLE.cap)
        assert not c3(FRUIT_APPLE.cap)
        assert not c1(FRUIT_BANANA.cap)
        assert c3(FRUIT_BANANA.cap)

class TestNameExcludes:
    def test_it_compares_if_name_of_product_does_not_contain_a_certain_fragment(self):
        c1 = cond.NameExcludes("APPLE")
        c2 = cond.NameExcludes("APPLE")
        c3 = cond.NameExcludes("BANANA")

        assert c1 == c2
        assert c1 != c3
        assert c1 != "APPLE"

        assert repr(c1) == "name_excludes(APPLE)"
        assert repr(c3) == "name_excludes(BANANA)"

        class FRUIT_APPLE(Product):
            pid = 1
            vendor = 1
            family = "edible"
            friendly = "Apple"

            class cap(Capability):
                pass

        class FRUIT_BANANA(Product):
            pid = 2
            vendor = 1
            family = "edible"
            friendly = "Banana"

            class cap(Capability):
                pass

        assert not c1(FRUIT_APPLE.cap)
        assert c3(FRUIT_APPLE.cap)
        assert c1(FRUIT_BANANA.cap)
        assert not c3(FRUIT_BANANA.cap)

class TestPidFrom:
    def test_it_compares_if_product_id_is_after_a_certain_amount(self):
        c1 = cond.PidFrom(3)
        c2 = cond.PidFrom(3)
        c3 = cond.PidFrom(5)

        assert c1 == c2
        assert c1 != c3
        assert c1 != 3

        assert repr(c1) == "pid>=3"
        assert repr(c3) == "pid>=5"

        class FRUIT_APPLE(Product):
            pid = 2
            vendor = 1
            family = "edible"
            friendly = "Apple"

            class cap(Capability):
                pass

        class FRUIT_BANANA(Product):
            pid = 3
            vendor = 1
            family = "edible"
            friendly = "Banana"

            class cap(Capability):
                pass

        class FRUIT_DRAGONFRUIT(Product):
            pid = 4
            vendor = 1
            family = "edible"
            friendly = "DragonFruit"

            class cap(Capability):
                pass

        class FRUIT_PASSIONFRUIT(Product):
            pid = 5
            vendor = 1
            family = "edible"
            friendly = "Passionfruit"

            class cap(Capability):
                pass

        class FRUIT_MELON(Product):
            pid = 6
            vendor = 1
            family = "edible"
            friendly = "Melon"

            class cap(Capability):
                pass

        assert not c1(FRUIT_APPLE.cap)
        assert not c3(FRUIT_APPLE.cap)
        assert c1(FRUIT_BANANA.cap)
        assert not c3(FRUIT_BANANA.cap)
        assert c1(FRUIT_PASSIONFRUIT.cap)
        assert c3(FRUIT_PASSIONFRUIT.cap)
        assert c1(FRUIT_MELON.cap)
        assert c3(FRUIT_MELON.cap)
