
import enum
import json
from functools import partial

from bitarray import bitarray
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue, Meta
from photons_protocol.errors import BadConversion
from photons_protocol.packets import dictobj
from photons_protocol.types import Type as T
from photons_protocol.types import UnknownEnum


def ba(val):
    b = bitarray(endian="little")
    b.frombytes(val)
    return b


def list_of_dicts(lst):
    """
    Helper to turn a list into dictionaries

    This is because depending on how an object is created, strings can be
    represented internally as either string or bitarray.

    This behaviour is due to a performance optimisation I don't want to remove
    so, I compare with normalised values instead
    """
    return [l.as_dict() for l in lst]


class TestTheMultipleModifier:

    def assertProperties(self, thing, checker):
        checker(thing)

        bts = thing.pack()
        thing2 = type(thing).create(bts)
        checker(thing2)

        thing3 = type(thing).create(json.loads(repr(thing)))
        checker(thing3)

    def test_it_allows_multiple_of_raw_types_and_structs(self):

        class Other(dictobj.PacketSpec):
            fields = [("four", T.Uint32)]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.BoolInt),
                ("two", T.Int32.multiple(2).default(0)),
                ("three", T.Bytes(4).multiple(2, kls=Other)),
            ]

        thing = Thing(one=True, two=[1], three=[{"four": 4}, {"four": 10}])

        def test_thing(thing):
            assert thing.one == 1
            assert thing.two == [1, 0]
            assert thing.three == [Other(four=4), Other(four=10)]
            assert thing.three.as_dict() == [{"four": 4}, {"four": 10}]

        self.assertProperties(thing, test_thing)

    def test_it_create_items_from_nothing(self):

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [
                ("one", T.BoolInt),
                ("five", T.Bytes(16).multiple(2).default(lambda pkt: b"")),
            ]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.Uint8.enum(E).multiple(3).default(E.ZERO)),
                ("two", T.Int32.multiple(3).default(0)),
                ("three", T.String(32).multiple(3).default(lambda pkt: "")),
                ("four", T.Bytes(40).multiple(3, kls=Other)),
            ]

        thing = Thing(
            one=["MEH", E.BLAH],
            two=[1, 2, 3],
            three=["on", "two"],
            four=[{"one": False, "five": [b"1", b"t"]}, {"one": True}],
        )

        assert thing.one == [E.MEH, E.BLAH, E.ZERO]
        assert thing.two == [1, 2, 3]
        assert thing.three == ["on", "two", ""]
        assert thing.four == [
            Other(one=False, five=[ba(b"1"), ba(b"t")]),
            Other(one=True, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
        ]

        thing = Thing()
        assert thing.one == [E.ZERO, E.ZERO, E.ZERO]
        assert thing.two == [0, 0, 0]
        assert thing.three == ["", "", ""]
        assert thing.four == [
            Other(one=False, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
        ]

    def test_it_allows_replacing_items_in_place(self):

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [
                ("one", T.BoolInt),
                ("five", T.Bytes(16).multiple(2).default(lambda pkt: b"")),
            ]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.Uint8.enum(E).multiple(3).default(E.ZERO)),
                ("two", T.Int32.multiple(3).default(0)),
                ("three", T.String(32).multiple(3)),
                ("four", T.Bytes(40).multiple(3, kls=Other)),
            ]

        thing = Thing(
            one=["MEH", E.BLAH],
            two=[1, 2, 3],
            three=["on", "two", "thre"],
            four=[{"one": False, "five": [b"1", b"t"]}, {"one": True}],
        )

        assert thing.one == [E.MEH, E.BLAH, E.ZERO]
        assert thing.one.as_dict() == [E.MEH, E.BLAH, E.ZERO]

        assert thing.two == [1, 2, 3]
        assert thing.two.as_dict() == [1, 2, 3]

        assert thing.three == ["on", "two", "thre"]
        assert thing.three.as_dict() == ["on", "two", "thre"]

        assert thing.four == [
            Other(one=False, five=[ba(b"1"), ba(b"t")]),
            Other(one=True, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
        ]

        pad = "0" * 8
        assert thing.four.as_dict() == [
            {"one": 0, "five": [ba(b"1") + pad, ba(b"t") + pad]},
            {"one": 1, "five": [ba(b"") + pad + pad, ba(b"") + pad + pad]},
            {"one": 0, "five": [ba(b"") + pad + pad, ba(b"") + pad + pad]},
        ]

        thing.one[-1] = 2
        thing.two[0] = 10
        thing.three[1] = "wat"
        thing.four[2] = {"one": False, "five": [b"y"]}

        def test_replacement(thing):
            assert thing.one == [E.MEH, E.BLAH, E.BLAH]
            assert thing.two == [10, 2, 3]
            assert thing.three == ["on", "wat", "thre"]

            assert thing.four == [
                Other(one=False, five=[ba(b"1"), ba(b"t")]),
                Other(one=True, five=[ba(b""), ba(b"")]),
                Other(one=False, five=[ba(b"y"), ba(b"")]),
            ]

        self.assertProperties(thing, test_replacement)

    def test_it_allows_replacing_items_in_place_when_from_nothing(self):

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [
                ("one", T.BoolInt),
                ("five", T.Bytes(16).multiple(2).default(lambda pkt: b"")),
            ]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.Uint8.enum(E).multiple(3).default(E.ZERO)),
                ("two", T.Int32.multiple(3).default(0)),
                ("three", T.String(32).multiple(3).default(lambda pkt: "")),
                ("four", T.Bytes(40).multiple(3, kls=Other)),
            ]

        thing = Thing()
        assert thing.one == [E.ZERO, E.ZERO, E.ZERO]
        assert thing.two == [0, 0, 0]
        assert thing.three == ["", "", ""]
        assert thing.four == [
            Other(one=False, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
        ]

        thing.one[-1] = 2
        thing.two[0] = 10
        thing.three[1] = "wat"
        thing.four[2] = {"one": True, "five": [b"y"]}

        def test_replacement(thing):
            assert thing.one == [E.ZERO, E.ZERO, E.BLAH]
            assert thing.two == [10, 0, 0]
            assert thing.three == ["", "wat", ""]
            assert thing.four == [
                Other(one=False, five=[ba(b""), ba(b"")]),
                Other(one=False, five=[ba(b""), ba(b"")]),
                Other(one=True, five=[ba(b"y"), ba(b"")]),
            ]

        self.assertProperties(thing, test_replacement)

    def test_it_complains_if_setting_a_value_incorrectly(self):

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [("one", T.BoolInt)]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.Uint8.enum(E).multiple(4).default(E.ZERO)),
                ("two", T.Int32.multiple(3).default(0)),
                ("three", T.String(32).multiple(3)),
                ("four", T.Bytes(8).multiple(1, kls=Other)),
                ("five", T.Uint8.enum(E, allow_unknown=False).multiple(3).default(E.ZERO)),
            ]

        thing = Thing(one=["MEH", E.BLAH], two=[1, 2, 3], three=["on", "two", "thre"])

        def test_thing(last_one_enum, thing):
            assert thing.one == [E.MEH, E.BLAH, E.ZERO, last_one_enum]
            assert thing.two == [1, 2, 3]
            assert thing.three == ["on", "two", "thre"]
            assert thing.four == [Other(one=False)]

        test_thing(E.ZERO, thing)

        # By default enums allow unknowns
        thing.one[-1] = 6
        assert thing.one[-1] == UnknownEnum(6)

        with assertRaises(BadConversion, "Value is not a valid value of the enum"):
            thing.five[1] = 6
        with assertRaises(BadSpecValue, "Expected an integer"):
            thing.two[0] = "asdf"
        with assertRaises(
            BadSpecValue, "BoolInts must be True, False, 0 or 1", meta=Meta.empty().at("one")
        ):
            thing.four[0] = {"one": "asdf"}

        self.assertProperties(thing, partial(test_thing, UnknownEnum(6)))

    def test_it_can_set_as_bytes(self):

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [("other", T.BoolInt), ("another", T.String(64).default(""))]

        one_fields = [("one", T.Uint8.enum(E).multiple(3).default(E.ZERO))]
        two_fields = [("two", T.Bytes(72).multiple(3, kls=Other))]

        class One(dictobj.PacketSpec):
            fields = one_fields

        class Two(dictobj.PacketSpec):
            fields = two_fields

        class Thing(dictobj.PacketSpec):
            fields = [*one_fields, *two_fields]

        one = One(one=[1, "BLAH", repr(E.ZERO)])
        two = Two(
            two=[
                {"other": False, "another": "wat"},
                {"other": True},
                {"other": False, "another": "hello"},
            ]
        )

        def check(thing):
            assert thing.one == [E.MEH, E.BLAH, E.ZERO]
            expected = [
                Other.create(other=0, another="wat"),
                Other.create(other=1, another=""),
                Other.create(other=0, another="hello"),
            ]
            assert thing.two == expected

        self.assertProperties(Thing(one=one.one, two=two.two), check)
        self.assertProperties(Thing(one=one.pack(), two=two.pack()), check)

        def check2(thing):
            assert thing.one == [E.MEH, E.BLAH, E.ZERO]
            expected = [
                Other.create(other=0, another="wat"),
                Other.create(other=0, another="yeap"),
                Other.create(other=0, another="hello"),
            ]
            assert thing.two == expected

        thing = Thing(one=one.pack(), two=two.pack())
        thing.two[1] = Other(other=0, another="yeap").pack()
        self.assertProperties(thing, check2)

    def test_it_can_edit_structs_inline(self):

        class Other(dictobj.PacketSpec):
            fields = [("other", T.BoolInt), ("another", T.String(64).default(""))]

        class Thing(dictobj.PacketSpec):
            fields = [("thing", T.Bytes(72).multiple(3, kls=Other))]

        thing = Thing(
            thing=[
                {"other": False, "another": "wat"},
                {"other": True},
                {"other": False, "another": "hello"},
            ]
        )

        def check(thing):
            expected = [
                Other.create(other=0, another="wat"),
                Other.create(other=1, another=""),
                Other.create(other=0, another="hello"),
            ]
            assert thing.thing == expected

        self.assertProperties(thing, check)

        thing.thing[1].another = "yo"

        def check2(thing):
            expected = [
                Other(other=0, another="wat"),
                Other(other=1, another="yo"),
                Other(other=0, another="hello"),
            ]
            assert list_of_dicts(thing.thing) == list_of_dicts(expected)

        self.assertProperties(thing, check2)

    def test_it_can_determine_class_and_number_based_off_other_fields(self):

        class One(dictobj.PacketSpec):
            fields = [("one", T.BoolInt.multiple(4).default(lambda pkt: False))]

        class Two(dictobj.PacketSpec):
            fields = [("two", T.String(32))]

        def choose_kls(pkt):
            if pkt.choice == "one":
                return One
            else:
                return Two

        class Chooser(dictobj.PacketSpec):
            fields = [
                ("choice", T.String(64)),
                ("amount", T.Uint8),
                ("val", T.Bytes(32).multiple(lambda pkt: pkt.amount, kls=choose_kls)),
            ]

        chooser = Chooser(
            choice="one", amount=3, val=[{"one": [True, True, False, True]}, {"one": [False, True]}]
        )

        def check(chooser):
            assert chooser.choice == "one"
            assert chooser.amount == 3
            assert chooser.val == [
                One(one=[True, True, False, True]),
                One(one=[False, True, False, False]),
                One(one=[False, False, False, False]),
            ]

        self.assertProperties(chooser, check)

        chooser = Chooser(choice="two", amount=2, val=[{"two": "wat"}, {"two": "1111"}])

        def check(chooser):
            assert chooser.choice == "two"
            assert chooser.amount == 2
            assert list_of_dicts(chooser.val) == list_of_dicts([Two(two="wat"), Two(two="1111")])

        self.assertProperties(chooser, check)

    def test_it_can_determine_number_based_off_other_fields(self):

        class Vals(dictobj.PacketSpec):
            fields = [
                ("amount", T.Uint8),
                ("vals", T.Uint8.multiple(lambda pkt: pkt.amount).default(99)),
            ]

        vals = Vals(amount=3, vals=[1, 2])

        def check(vals):
            assert vals.amount == 3
            assert vals.vals == [1, 2, 99]

        self.assertProperties(vals, check)

        vals = Vals(amount=5, vals=[1, 2, 1, 2, 3])

        def check(vals):
            assert vals.amount == 5
            assert vals.vals == [1, 2, 1, 2, 3]

        self.assertProperties(vals, check)
