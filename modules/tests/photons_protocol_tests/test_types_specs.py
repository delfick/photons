import binascii
import uuid
from enum import Enum
from unittest import mock

import pytest
from bitarray import bitarray
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta, sb
from photons_app.errors import ProgrammerError
from photons_protocol import types
from photons_protocol.errors import BadConversion, BadSpecValue
from photons_protocol.packets import dictobj
from photons_protocol.types import Type as T


@pytest.fixture()
def meta():
    return Meta.empty()


@pytest.fixture()
def pkt():
    return mock.Mock(name="pkt")


class TestCallableSpec:
    def test_it_returns_val_if_callable(self, meta):
        def cb(*args):
            pass

        assert types.callable_spec(None).normalise(meta, cb) is cb

    def test_it_uses_the_spec_otherwise(self):
        normalised = mock.Mock(name="normalised")

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        s = types.callable_spec(spec)
        val = mock.NonCallableMock(name="val")
        meta = Meta.empty()

        assert s.normalise(meta, val) is normalised
        spec.normalise.assert_called_once_with(meta, val)


class TestTransformSpec:
    def test_it_normalises_spec_with_transformed_value(self, meta):
        val = mock.Mock(name="val")
        transformed = mock.Mock(name="transformed")
        do_transform = mock.Mock(name="do_transform", return_value=transformed)

        pkt = mock.Mock(name="pkt")
        normalised = mock.Mock(name="normalised")

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        ts = types.transform_spec(pkt, spec, do_transform)
        assert ts.normalise(meta, val) is normalised

        do_transform.assert_called_once_with(pkt, val)
        spec.normalise.assert_called_once_with(meta, transformed)

    def test_it_does_not_call_the_transform_if_value_is_sbNotSpecified(self, meta):
        transformed = mock.Mock(name="transformed")
        do_transform = mock.Mock(name="do_transform", return_value=transformed)

        pkt = mock.Mock(name="pkt")
        normalised = mock.Mock(name="normalised")

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        ts = types.transform_spec(pkt, spec, do_transform)
        assert ts.normalise(meta, sb.NotSpecified) is normalised

        assert len(do_transform.mock_calls) == 0
        spec.normalise.assert_called_once_with(meta, sb.NotSpecified)

    def test_it_does_not_call_the_transform_if_value_is_Optional(self, meta):
        transformed = mock.Mock(name="transformed")
        do_transform = mock.Mock(name="do_transform", return_value=transformed)

        pkt = mock.Mock(name="pkt")
        normalised = mock.Mock(name="normalised")

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        ts = types.transform_spec(pkt, spec, do_transform)
        assert ts.normalise(meta, types.Optional) is normalised

        assert len(do_transform.mock_calls) == 0
        spec.normalise.assert_called_once_with(meta, types.Optional)


class TestExpandSpec:
    @pytest.fixture()
    def spec(self):
        return T.Bytes(20)

    @pytest.fixture()
    def kls(self):
        class Kls(dictobj.PacketSpec):
            fields = [("one", T.Bool), ("two", T.Int8)]

        return Kls

    def test_it_takes_in_kls_spec_and_unpacking(self):
        kls = mock.Mock(name="kls")
        spec = mock.Mock(name="spec")
        unpacking = mock.Mock(name="unpacking")

        s = types.expand_spec(kls, spec, unpacking)

        assert s.kls is kls
        assert s.spec is spec
        assert s.unpacking is unpacking

    class TestPackingIntoBytes:
        @pytest.fixture()
        def subject(self, spec, pkt, kls):
            spec = spec.spec(pkt, False)
            return types.expand_spec(kls, spec, False)

        def test_it_returns_bitarray_value_as_bytes(self, meta, subject, kls):
            val = kls.create(one=True, two=127)
            b = val.pack()
            assert len(b) == 9

            b2 = subject.normalise(meta, b)
            assert len(b2) == 20

            assert b2[:9] == b
            assert b2[9:20] == bitarray("0" * 11)

        def test_it_returns_bytes_value_as_bytes(self, meta, subject, kls):
            val = kls.create(one=True, two=127)
            b = val.pack()
            assert len(b) == 9

            b2 = subject.normalise(meta, b.tobytes())
            assert len(b2) == 20

            assert b2[:9] == b
            assert b2[9:20] == bitarray("0" * 11)

        def test_it_returns_a_dictionary_as_bytes(self, meta, subject, kls):
            val = kls.create(one=True, two=12)
            b = val.pack()
            assert len(b) == 9

            b2 = subject.normalise(meta, {"one": True, "two": 12})
            assert len(b2) == 20

            assert b2[:9] == b
            assert b2[9:20] == bitarray("0" * 11)

        def test_it_complains_if_something_other_than_dictionary_bytes_or_bitarray_is_given(self, meta, subject):
            for thing in (0, 1, False, True, [], [1], "adsf", None, lambda: True):
                with assertRaises(BadSpecValue, "Sorry, dynamic fields only supports a dictionary of values"):
                    subject.normalise(meta, thing)

    class TestUnpackingFromBytes:
        @pytest.fixture()
        def subject(self, spec, pkt, kls):
            spec = spec.spec(pkt, True)
            return types.expand_spec(kls, spec, True)

        def test_it_returns_instance_of_kls_if_NotSpecified(self, meta, spec, pkt):
            class Kls(dictobj.PacketSpec):
                fields = [("one", T.Bool.default(False)), ("two", T.Int8.default(10))]

            spec = spec.spec(pkt, True)
            subject = types.expand_spec(Kls, spec, True)

            val = Kls.create()
            assert subject.normalise(meta, sb.NotSpecified) == val

        def test_it_returns_instance_of_kls_if_a_dictionary(self, meta, subject, kls):
            val = kls.create(one=True, two=12)
            assert subject.normalise(meta, {"one": True, "two": 12}) == val

        def test_it_returns_as_is_if_already_of_the_kls_type(self, meta, subject, kls):
            val = kls.create(one=True, two=12)
            assert subject.normalise(meta, val) is val

        def test_it_returns_as_instance_of_the_kls_if_bitarray(self, meta, subject, kls):
            val = kls.create(one=True, two=6)
            assert subject.normalise(meta, val.pack()) == val

        def test_it_returns_as_instance_of_the_kls_if_bytes(self, meta, subject, kls):
            val = kls.create(one=True, two=120)
            assert subject.normalise(meta, val.pack().tobytes()) == val

        def test_it_complains_if_not_bitarray_bytes_or_instance_of_kls(self, meta, subject, kls):
            for thing in (0, 1, False, True, [], [1], None, "adsf", lambda: True):
                with assertRaises(BadSpecValue, "Expected to unpack bytes", found=thing, transforming_into=kls):
                    subject.normalise(meta, thing)


class TestOptional:
    def test_it_says_NotSpecified_is_Optional(self):
        spec = types.optional(mock.Mock(name="spec"))
        assert spec.normalise(Meta.empty(), sb.NotSpecified) is types.Optional

    def test_it_normalises_Optional_as_is(self):
        spec = types.optional(mock.Mock(name="spec"))
        assert spec.normalise(Meta.empty(), types.Optional) is types.Optional

    def test_it_normalises_anything_else_using_selfspec(self):
        res = mock.Mock(name="res")
        ultimate_spec = mock.Mock(name="ultimate-spec")
        ultimate_spec.normalise.return_value = res

        meta = Meta.empty()

        spec = types.optional(ultimate_spec)
        thing = mock.Mock(name="thing")
        assert spec.normalise(meta, thing) is res

        ultimate_spec.normalise.assert_called_once_with(meta, thing)


class TestVersionNumberSpec:
    def test_it_takes_in_many_things(self):
        unpacking = mock.Mock(name="unpacking")
        spec = types.version_number_spec(unpacking=unpacking)
        assert spec.unpacking is unpacking

    def test_it_defaults_unpacking(self):
        spec = types.version_number_spec()
        assert spec.unpacking is False

    class TestNormalise:
        def test_it_can_go_back_and_forward_between_string_and_integer(self, meta):
            for want_int, want_str in [(65538, "1.2"), (131092, "2.20"), (131272, "2.200")]:
                unpacker = types.version_number_spec(unpacking=False)
                as_int = unpacker.normalise(meta, want_str)
                assert as_int == want_int

                packer = types.version_number_spec(unpacking=True)
                as_str = packer.normalise(meta, as_int)
                assert as_str == want_str

        def test_it_complains_if_val_is_not_a_valid_version_number(self, meta):
            for v in ("", "0", "0.wat", "wat.0", "wat"):
                with assertRaises(BadSpecValue, "Expected version string to match", wanted=v):
                    types.version_number_spec(unpacking=False).normalise(meta, v)

        def test_it_can_pack_an_integer(self, meta):
            assert types.version_number_spec(unpacking=False).normalise(meta, 100) == 100

        def test_it_can_unpack_an_string(self, meta):
            assert types.version_number_spec(unpacking=True).normalise(meta, "1.1") == "1.1"

        def test_it_can_unpack_an_incorect_string(self, meta):
            with assertRaises(BadSpecValue, "Expected string to match", got="1"):
                types.version_number_spec(unpacking=True).normalise(meta, "1")


class TestIntegerSpec:
    def test_it_takes_in_many_things(self):
        pkt = mock.Mock(name="pkt")
        enum = mock.Mock(name="enum")
        bitmask = mock.Mock(name="bitmask")
        unpacking = mock.Mock(name="unpacking")
        allow_float = mock.Mock(name="allow_float")
        unknown_enum_values = mock.Mock(name="unknown_enum_values")

        for kw in ({"enum": enum, "bitmask": None}, {"enum": None, "bitmask": bitmask}):
            kw["unpacking"] = unpacking
            kw["allow_float"] = allow_float
            kw["unknown_enum_values"] = unknown_enum_values

            spec = types.integer_spec(pkt, **kw)
            assert spec.pkt is pkt
            assert spec.enum is kw["enum"]
            assert spec.bitmask is kw["bitmask"]
            assert spec.unpacking is unpacking
            assert spec.allow_float is allow_float
            assert spec.unknown_enum_values is unknown_enum_values

    def test_it_complains_if_enum_and_bitmask_are_both_specified(self):
        with assertRaises(ProgrammerError, "Sorry, can't specify enum and bitmask for the same type"):
            types.integer_spec(mock.Mock(name="pkt"), mock.Mock(name="enum"), mock.Mock(name="bitmask"))

    def test_it_defaults_unpacking_and_allow_float(self):
        spec = types.integer_spec(mock.Mock(name="pkt"), None, None)
        assert spec.unpacking is False
        assert spec.allow_float is False

    class TestNormalise:
        def test_it_returns_as_is_if_not_enum_and_not_bitmask_and_allow_float_and_is_a_float(self, meta, pkt):
            spec = types.integer_spec(pkt, None, None, allow_float=True)
            assert spec.normalise(meta, 1.2) == 1.2

        def test_it_asserts_number_is_integer_if_no_enum_or_bitmask_and_not_allow_float(self, meta, pkt):
            spec = types.integer_spec(pkt, None, None, allow_float=False)
            with assertRaises(BadSpecValue, "Expected an integer"):
                spec.normalise(meta, 1.2)

        def test_it_returns_integer_if_not_enum_or_bitmask(self, meta, pkt):
            spec = types.integer_spec(pkt, None, None)
            assert spec.normalise(meta, 1) == 1

        def test_it_does_an_enum_spec_if_we_have_an_enum(self, pkt):
            ret = mock.Mock(name="ret")
            enum = mock.Mock(name="enum")
            unpacking = mock.Mock(name="unpacking")

            meta = Meta.empty()
            val = mock.Mock(name="val")

            es = mock.Mock(name="enum_spec()")
            uev = mock.Mock(name="unknown_enum_values")
            enum_spec = mock.Mock(name="enum_spec", return_value=es)
            es.normalise.return_value = ret
            with mock.patch("photons_protocol.types.enum_spec", enum_spec):
                spec = types.integer_spec(pkt, enum, None, unpacking=unpacking, unknown_enum_values=uev)
                assert spec.normalise(meta, val) is ret

            enum_spec.assert_called_once_with(pkt, enum, unpacking=unpacking, allow_unknown=uev)
            es.normalise.assert_called_once_with(meta, val)

        def test_it_does_a_bitmask_spec_if_we_have_a_bitmask(self, pkt):
            ret = mock.Mock(name="ret")
            bitmask = mock.Mock(name="bitmask")
            unpacking = mock.Mock(name="unpacking")

            meta = Meta.empty()
            val = mock.Mock(name="val")

            es = mock.Mock(name="bitmask_spec()")
            bitmask_spec = mock.Mock(name="bitmask_spec", return_value=es)
            es.normalise.return_value = ret
            with mock.patch("photons_protocol.types.bitmask_spec", bitmask_spec):
                spec = types.integer_spec(pkt, None, bitmask, unpacking=unpacking)
                assert spec.normalise(meta, val) is ret

            bitmask_spec.assert_called_once_with(pkt, bitmask, unpacking=unpacking)
            es.normalise.assert_called_once_with(meta, val)


class TestBitmaskSpec:
    def test_it_takes_in_some_things(self):
        pkt = mock.Mock(name="pkt")
        bitmask = mock.Mock(name="bitmask")
        unpacking = mock.Mock(name="unpacking")

        spec = types.bitmask_spec(pkt, bitmask, unpacking=unpacking)

        assert spec.pkt is pkt
        assert spec.bitmask is bitmask
        assert spec.unpacking is unpacking

    class TestNormalisation:
        @pytest.fixture()
        def bitmask(self):
            class Mask(Enum):
                ONE = 1 << 1
                TWO = 1 << 2
                THREE = 1 << 3
                FOUR = 1 << 4
                FIVE = 1 << 5

            return Mask

        def test_it_complains_if_bitmask_is_not_an_Enum(self, meta, pkt):
            class Kls:
                def __init__(s, pkt):
                    pass

                def __call__(s, pkt):
                    return True

            for thing in (0, 1, [], [1], {}, {1: 2}, lambda pkt: 1, Kls(1), Kls, None, True, False):
                with assertRaises(ProgrammerError, "Bitmask is not an enum!"):
                    types.bitmask_spec(pkt, thing).normalise(meta, mock.Mock(name="val"))

        def test_it_complains_if_bitmask_has_a_zero_value(self, meta, pkt):
            class BM(Enum):
                ZERO = 0
                ONE = 1
                TWO = 2

            with assertRaises(
                ProgrammerError,
                "A bitmask with a zero value item makes no sense: ZERO in <enum 'BM'>",
            ):
                types.bitmask_spec(pkt, BM).normalise(meta, mock.Mock(name="val"))

            with assertRaises(
                ProgrammerError,
                "A bitmask with a zero value item makes no sense: ZERO in <enum 'BM'>",
            ):
                types.bitmask_spec(pkt, lambda pkt: BM).normalise(meta, mock.Mock(name="val"))

        class TestPackingIntoANumber:
            @pytest.fixture()
            def subject(self, bitmask, pkt):
                return types.bitmask_spec(pkt, bitmask, unpacking=False)

            def test_it_adds_value_if_already_part_of_the_bitmask(self, meta, bitmask, subject):
                v = [bitmask.ONE, bitmask.THREE]
                final = (1 << 1) + (1 << 3)
                assert subject.normalise(meta, v) == final

            def test_it_adds_value_if_a_matching_number(self, meta, bitmask, subject):
                v = [bitmask.ONE, (1 << 3)]
                final = (1 << 1) + (1 << 3)
                assert subject.normalise(meta, v) == final

            def test_it_adds_value_if_a_repr_of_the_value(self, meta, bitmask, subject):
                r = "<Mask.FOUR: 16>"
                assert repr(bitmask.FOUR) == r
                v = [bitmask.ONE, r]
                final = (1 << 1) + (1 << 4)
                assert subject.normalise(meta, v) == final

            def test_it_works_with_the_string_set(self, meta, subject):
                assert subject.normalise(meta, "set()") == 0

            def test_it_works_with_a_set_as_a_string(self, meta, subject):
                assert subject.normalise(meta, "{<Mask.ONE: 2>, <Mask.TWO: 4>}") == (1 << 1) + (1 << 2)

            def test_it_returns_as_is_if_the_value_is_a_number(self, meta, subject):
                assert subject.normalise(meta, 200) == 200

            def test_it_complains_if_it_cant_convert_the_value(self, meta, bitmask, subject):
                for val in ("<Mask.SIX: 64>", "asdf", True, {}, {1: 2}, None, lambda: 1):
                    with assertRaises(BadConversion, "Can't convert value into mask", mask=bitmask, got=val):
                        subject.normalise(meta, val)

            def test_it_converts_empty_array_into_0(self, meta, subject):
                assert subject.normalise(meta, []) == 0

            def test_it_returns_0_as_0_or_False(self, meta, subject):
                assert subject.normalise(meta, 0) == 0
                assert subject.normalise(meta, False) == 0

            def test_it_works_with_a_set_of_values(self, meta, bitmask, subject):
                v = set([bitmask.ONE, 1 << 3, "FIVE"])
                assert subject.normalise(meta, v) == (1 << 1) + (1 << 3) + (1 << 5)

            def test_it_only_counts_values_once(self, meta, bitmask, subject):
                v = set([bitmask.THREE, 1 << 3, "THREE"])
                assert subject.normalise(meta, v) == (1 << 3)

        class TestUnpackingIntoAList:
            @pytest.fixture()
            def subject(self, bitmask, pkt):
                return types.bitmask_spec(pkt, bitmask, unpacking=True)

            def test_it_returns_as_is_if_already_bitmask_items(self, meta, bitmask, subject):
                v = [bitmask.ONE, "THREE", "<Mask.FOUR: 16>"]
                assert subject.normalise(meta, v) == set([bitmask.ONE, bitmask.THREE, bitmask.FOUR])

            def test_it_returns_what_values_it_can_find_in_the_value(self, meta, bitmask, subject):
                v = (1 << 1) + (1 << 3) + (1 << 4)
                assert subject.normalise(meta, v) == set([bitmask.ONE, bitmask.THREE, bitmask.FOUR])

            def test_it_ignores_left_over(self, meta, bitmask, subject):
                v = (1 << 1) + (1 << 3) + (1 << 4)
                assert subject.normalise(meta, v + 1) == set([bitmask.ONE, bitmask.THREE, bitmask.FOUR])

            def test_it_works_with_the_string_set(self, meta, subject):
                assert subject.normalise(meta, "set()") == set()

            def test_it_works_with_a_set_as_a_string(self, meta, bitmask, subject):
                assert subject.normalise(meta, "{<Mask.ONE: 2>, <Mask.TWO: 4>}") == set([bitmask.ONE, bitmask.TWO])

            def test_it_complains_if_it_finds_a_value_from_a_different_enum(self, meta, bitmask, subject):
                class Mask2(Enum):
                    ONE = 1 << 1
                    TWO = 1 << 2

                with assertRaises(
                    BadConversion,
                    "Can't convert value of wrong Enum",
                    val=Mask2.ONE,
                    wanted=bitmask,
                    got=Mask2,
                ):
                    subject.normalise(meta, Mask2.ONE)

            def test_it_complains_if_it_cant_find_a_string_value_in_the_mask(self, meta, subject):
                with assertRaises(BadConversion, "Can't convert value into value from mask"):
                    subject.normalise(meta, "SEVEN")

            def test_it_does_not_complain_if_it_cant_find_an_integer_value_in_the_mask(self, meta, subject):
                assert subject.normalise(meta, (1 << 24)) == set()


class TestEnumSpec:
    def test_it_takes_in_some_things(self):
        pkt = mock.Mock(name="pkt")
        em = mock.Mock(name="enum")
        unpacking = mock.Mock(name="unpacking")
        allow_unknown = mock.Mock(name="allow_unknown")

        spec = types.enum_spec(pkt, em, unpacking=unpacking, allow_unknown=allow_unknown)

        assert spec.pkt is pkt
        assert spec.enum is em
        assert spec.unpacking is unpacking
        assert spec.allow_unknown is allow_unknown

    class TestNormalisation:
        @pytest.fixture()
        def enum(self):
            class Vals(Enum):
                ONE = 1
                TWO = 2
                THREE = 3
                FOUR = 4
                FIVE = 5

            return Vals

        def test_it_complains_if_enum_is_not_an_Enum(self, meta, pkt):
            class Kls:
                def __init__(s, pkt):
                    pass

                def __call__(s, pkt):
                    return True

            for thing in (0, 1, [], [1], {}, {1: 2}, lambda pkt: 1, Kls(1), Kls, None, True, False):
                with assertRaises(ProgrammerError, "Enum is not an enum!"):
                    types.enum_spec(pkt, thing).normalise(meta, mock.Mock(name="val"))
                with assertRaises(ProgrammerError, "Enum is not an enum!"):
                    types.enum_spec(pkt, thing, allow_unknown=True).normalise(meta, mock.Mock(name="val"))

        class TestPackingIntoAValue:
            @pytest.fixture()
            def subject(self, pkt, enum):
                return types.enum_spec(pkt, enum, unpacking=False)

            @pytest.fixture()
            def subject_with_unknown(self, pkt, enum):
                return types.enum_spec(pkt, enum, unpacking=False, allow_unknown=True)

            def test_it_can_convert_from_the_name(self, meta, subject, subject_with_unknown):
                assert subject.normalise(meta, "ONE") == 1
                assert subject_with_unknown.normalise(meta, "ONE") == 1

            def test_it_can_convert_from_repr_of_the_member(self, meta, subject, subject_with_unknown):
                assert subject.normalise(meta, "<Vals.ONE: 1>") == 1
                assert subject_with_unknown.normalise(meta, "<Vals.ONE: 1>") == 1

            def test_it_can_convert_from_member_itself(self, meta, subject, enum, subject_with_unknown):
                assert subject.normalise(meta, enum.TWO) == 2
                assert subject_with_unknown.normalise(meta, enum.TWO) == 2

            def test_it_complains_if_its_not_in_the_enum(self, meta, subject, subject_with_unknown):
                ue = types.UnknownEnum(20)
                for val in (0, 200, False, None, [], [1], {}, {1: 2}, ue, repr(ue), lambda: 1):
                    with assertRaises(BadConversion, "Value wasn't a valid enum value"):
                        subject.normalise(meta, val)
                for val in (False, None, [], [1], {}, {1: 2}, lambda: 1):
                    with assertRaises(BadConversion, "Value wasn't a valid enum value"):
                        subject_with_unknown.normalise(meta, val)

            def test_it_does_not_complain_if_allow_unknown_and_value_not_in_the_enum_and_valid_value(self, meta, subject, subject_with_unknown):
                ue = types.UnknownEnum(20)
                assert subject_with_unknown.normalise(meta, ue) == 20
                assert subject_with_unknown.normalise(meta, repr(ue)) == 20

                assert subject_with_unknown.normalise(meta, 40) == 40

            def test_it_complains_if_were_using_the_wrong_enum(self, meta, subject, subject_with_unknown):
                class Vals2(Enum):
                    ONE = 1
                    TWO = 2
                    THREE = 3
                    FOUR = 4
                    FIVE = 5

                with assertRaises(BadConversion, "Can't convert value of wrong Enum"):
                    subject.normalise(meta, Vals2.THREE)
                with assertRaises(BadConversion, "Can't convert value of wrong Enum"):
                    subject_with_unknown.normalise(meta, Vals2.THREE)

        class TestUnpackingIntoEnumMember:
            @pytest.fixture()
            def subject(self, pkt, enum):
                return types.enum_spec(pkt, enum, unpacking=True)

            @pytest.fixture()
            def subject_with_unknown(self, pkt, enum):
                return types.enum_spec(pkt, enum, unpacking=True, allow_unknown=True)

            def test_it_returns_as_is_if_already_a_member(self, meta, subject, enum, subject_with_unknown):
                assert subject.normalise(meta, enum.TWO) is enum.TWO
                assert subject_with_unknown.normalise(meta, enum.TWO) is enum.TWO

            def test_it_complains_if_from_the_wrong_enum(self, meta, subject, subject_with_unknown):
                class Vals2(Enum):
                    ONE = 1
                    TWO = 2
                    THREE = 3
                    FOUR = 4
                    FIVE = 5

                with assertRaises(BadConversion, "Can't convert value of wrong Enum"):
                    subject.normalise(meta, Vals2.THREE)
                with assertRaises(BadConversion, "Can't convert value of wrong Enum"):
                    subject_with_unknown.normalise(meta, Vals2.THREE)

            def test_it_converts_from_name(self, meta, subject, enum, subject_with_unknown):
                assert subject.normalise(meta, "THREE") == enum.THREE
                assert subject_with_unknown.normalise(meta, "THREE") == enum.THREE

            def test_it_converts_from_repr_of_member(self, meta, subject, enum, subject_with_unknown):
                assert subject.normalise(meta, "<Vals.THREE: 3>") == enum.THREE
                assert subject_with_unknown.normalise(meta, "<Vals.THREE: 3>") == enum.THREE

            def test_it_converts_from_value_of_member(self, meta, subject, enum, subject_with_unknown):
                assert subject.normalise(meta, 4) == enum.FOUR
                assert subject_with_unknown.normalise(meta, 4) == enum.FOUR

            def test_it_complains_if_value_isnt_in_enum(self, meta, subject, subject_with_unknown):
                ue = repr(types.UnknownEnum(20))
                for val in ("SEVEN", 200, ue, False, None, [], [1], {}, {1: 2}, lambda: 1):
                    with assertRaises(BadConversion, "Value is not a valid value of the enum"):
                        subject.normalise(meta, val)

                for val in ("SEVEN", False, None, [], [1], {}, {1: 2}, lambda: 1):
                    with assertRaises(BadConversion, "Value is not a valid value of the enum"):
                        subject_with_unknown.normalise(meta, val)

            def test_it_does_not_complain_if_allow_unknown_and_valid_unknown_value(self, meta, subject, subject_with_unknown):
                ue = types.UnknownEnum(20)
                assert subject_with_unknown.normalise(meta, ue) is ue
                assert subject_with_unknown.normalise(meta, repr(ue)) == ue
                assert subject_with_unknown.normalise(meta, 20) == ue


class TestOverridden:
    def test_it_takes_in_pkt_and_default_func(self):
        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        assert spec.default_func is default_func
        assert spec.pkt is pkt

    def test_it_uses_the_default_func_with_pkt_regardless_of_value(self):
        meta = Meta.empty()
        val = mock.Mock(name="val")

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        ret = mock.Mock(name="ret")
        default_func.return_value = ret

        assert spec.normalise(meta, val) is ret

        default_func.assert_called_once_with(pkt)

    def test_it_uses_the_default_func_with_pkt_even_with_NotSpecified(self):
        meta = Meta.empty()
        val = sb.NotSpecified

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        ret = mock.Mock(name="ret")
        default_func.return_value = ret

        assert spec.normalise(meta, val) is ret

        default_func.assert_called_once_with(pkt)


class TestDefaulted:
    def test_it_takes_in_spec_pkt_and_default_func(self):
        default_func = mock.Mock(name="default_func")
        spec = mock.Mock(name="spec")
        pkt = mock.Mock(name="pkt")
        subject = types.defaulted(spec, default_func, pkt)

        assert subject.spec is spec
        assert subject.default_func is default_func
        assert subject.pkt is pkt

    def test_it_uses_the_spec_with_the_value_if_not_empty(self):
        meta = Meta.empty()
        val = mock.Mock(name="val")

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = mock.Mock(name="spec")
        subject = types.defaulted(spec, default_func, pkt)

        ret = mock.Mock(name="ret")
        spec.normalise.return_value = ret

        assert subject.normalise(meta, val) is ret

        spec.normalise.assert_called_once_with(meta, val)

    def test_it_uses_the_default_func_with_pkt_when_NotSpecified(self):
        meta = Meta.empty()
        val = sb.NotSpecified
        normalised = mock.Mock(name="normalised")

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = mock.NonCallableMock(name="spec")
        spec.normalise.return_value = normalised

        subject = types.defaulted(spec, default_func, pkt)

        defaultvalue = mock.Mock(name="ret")
        default_func.return_value = defaultvalue

        assert subject.normalise(meta, val) is normalised

        default_func.assert_called_once_with(pkt)
        spec.normalise.assert_called_once_with(meta, defaultvalue)


class TestBoolean:
    def test_it_complains_if_no_value_to_normalise(self):
        with assertRaises(BadSpecValue, "Must specify boolean values"):
            types.boolean().normalise(Meta.empty(), sb.NotSpecified)

    def test_it_returns_as_is_if_the_value_is_a_boolean(self):
        assert types.boolean().normalise(Meta.empty(), False) is False
        assert types.boolean().normalise(Meta.empty(), True) is True

    def test_it_returns_as_boolean_if_0_or_1(self):
        assert types.boolean().normalise(Meta.empty(), 0) is False
        assert types.boolean().normalise(Meta.empty(), 1) is True

    def test_it_complains_if_not_boolean_0_or_1(self):
        for val in (None, [], [1], {}, {1: 2}, "asdf", b"asdf", lambda: 1):
            with assertRaises(BadSpecValue, "Could not convert value into a boolean", val=val):
                types.boolean().normalise(Meta.empty(), val)


class TestBooleanAsIntSpec:
    def test_it_complains_if_no_value_to_normalise(self):
        with assertRaises(BadSpecValue, "Must specify boolean values"):
            types.boolean_as_int_spec().normalise(Meta.empty(), sb.NotSpecified)

    def test_it_returns_as_is_if_the_value_is_0_or_1(self):
        assert types.boolean_as_int_spec().normalise(Meta.empty(), 0) == 0
        assert types.boolean_as_int_spec().normalise(Meta.empty(), 1) == 1

    def test_it_returns_as_0_or_1_if_True_or_False(self):
        assert types.boolean_as_int_spec().normalise(Meta.empty(), False) == 0
        assert types.boolean_as_int_spec().normalise(Meta.empty(), True) == 1

    def test_it_complains_if_not_boolean_0_or_1(self):
        for val in (None, [], [1], {}, {1: 2}, "asdf", b"asdf", lambda: 1):
            with assertRaises(BadSpecValue, "BoolInts must be True, False, 0 or 1", got=val):
                types.boolean_as_int_spec().normalise(Meta.empty(), val)


class TestCsvSpec:
    def test_it_takes_in_pkt_size_bits_and_unpacking(self):
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        unpacking = mock.Mock(name="unpacking")
        spec = types.csv_spec(pkt, size_bits, unpacking=unpacking)

        assert spec.pkt is pkt
        assert spec.size_bits is size_bits
        assert spec.unpacking is unpacking

    class TestPackingIntoBitarray:
        @pytest.fixture()
        def subject(self, pkt):
            return types.csv_spec(pkt, 200 * 8, unpacking=False)

        @pytest.fixture()
        def val(self):
            v1 = str(uuid.uuid1())
            v2 = str(uuid.uuid1())
            return [v1, v2]

        def test_it_converts_a_list_into_a_comma_separated_string_into_bitarray(self, meta, val, subject):
            expected_bytes = ",".join(val).encode() + b"\x00"
            assert len(expected_bytes) == 74
            result = subject.normalise(meta, val).tobytes()

            assert result[:74] == expected_bytes
            assert result[74:] == bitarray("0" * (200 - 74) * 8).tobytes()

        def test_it_converts_a_string_into_bitarray(self, meta, val, subject):
            s = ",".join(val)
            expected_bytes = s.encode() + b"\x00"
            assert len(expected_bytes) == 74

            result = subject.normalise(meta, s).tobytes()

            assert result[:74] == expected_bytes
            assert result[74:] == bitarray("0" * (200 - 74) * 8).tobytes()

        def test_it_converts_bytes_into_bitarray_with_correct_size(self, meta, val, subject):
            b = ",".join(val).encode()
            expected_bytes = b + b"\x00"
            assert len(expected_bytes) == 74

            result = subject.normalise(meta, b).tobytes()

            assert result[:74] == expected_bytes
            assert result[74:] == bitarray("0" * (200 - 74) * 8).tobytes()

        def test_it_converts_bitarray_into_bitarray_with_correct_size(self, meta, val, subject):
            b = ",".join(val).encode()
            expected_bytes = b + b"\x00"
            assert len(expected_bytes) == 74

            b2 = bitarray(endian="little")
            b2.frombytes(b)
            result = subject.normalise(meta, b2).tobytes()

            assert result[:74] == expected_bytes
            assert result[74:] == bitarray("0" * (200 - 74) * 8).tobytes()

    class TestUnpackingIntoList:
        @pytest.fixture()
        def subject(self, pkt):
            return types.csv_spec(pkt, 200 * 8, unpacking=True)

        @pytest.fixture()
        def val(self):
            v1 = str(uuid.uuid1())
            v2 = str(uuid.uuid1())
            return [v1, v2]

        def test_it_returns_list_as_is_if_already_a_list(self, meta, val, subject):
            assert subject.normalise(meta, val) == val

        def test_it_turns_bitarray_into_a_list(self, meta, val, subject):
            b = ",".join(val).encode() + b"\x00" + bitarray("0" * 100).tobytes()

            b2 = bitarray(endian="little")
            b2.frombytes(b)
            assert subject.normalise(meta, b2) == val

        def test_it_turns_bytes_into_a_list(self, meta, val, subject):
            b = ",".join(val).encode() + b"\x00" + bitarray("0" * 100).tobytes()
            assert subject.normalise(meta, b) == val

        def test_it_turns_string_into_a_list(self, meta, val, subject):
            s = ",".join(val)
            assert subject.normalise(meta, s) == val


class TestBytesSpec:
    def test_it_takes_in_pkt_and_size_bits(self):
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        spec = types.bytes_spec(pkt, size_bits)
        assert spec.pkt is pkt
        assert spec.size_bits is size_bits

    class TestNormalising:
        def test_it_works_from_the_repr_of_sbNotSpecified(self, meta, pkt):
            expected = bitarray("0" * 8)
            assert types.bytes_spec(pkt, 8).normalise(meta, repr(sb.NotSpecified)) == expected

            expected = bitarray("0" * 8)
            assert (types.bytes_spec(pkt, 8).normalise(meta, repr(sb.NotSpecified).replace("'", ""))) == expected

        def test_it_returns_None_as_the_size_bits_of_bitarray(self, meta, pkt):
            expected = bitarray("0" * 8)
            assert types.bytes_spec(pkt, 8).normalise(meta, None) == expected

            expected = bitarray("0" * 20)
            assert types.bytes_spec(pkt, 20).normalise(meta, None) == expected

        def test_it_returns_0_as_the_size_bits_of_bitarray(self, meta, pkt):
            expected = bitarray("0" * 8)
            assert types.bytes_spec(pkt, 8).normalise(meta, 0) == expected

            expected = bitarray("0" * 20)
            assert types.bytes_spec(pkt, 20).normalise(meta, 0) == expected

        def test_it_expands_if_not_long_enough(self, meta, pkt):
            val = bitarray("1" * 8)
            expected = bitarray("1" * 8 + "0" * 12)
            assert types.bytes_spec(pkt, 20).normalise(meta, val) == expected
            assert types.bytes_spec(pkt, 20).normalise(meta, val.tobytes()) == expected
            assert (types.bytes_spec(pkt, 20).normalise(meta, binascii.hexlify(val.tobytes()).decode())) == expected

        def test_it_cuts_off_if_too_long(self, meta, pkt):
            val = bitarray("1" * 24)
            expected = bitarray("1" * 9)
            assert types.bytes_spec(pkt, 9).normalise(meta, val) == expected
            assert types.bytes_spec(pkt, 9).normalise(meta, val.tobytes()) == expected
            assert (types.bytes_spec(pkt, 9).normalise(meta, binascii.hexlify(val.tobytes()).decode())) == expected

        def test_it_returns_if_just_right(self, meta, pkt):
            val = bitarray("1" * 8)
            assert types.bytes_spec(pkt, 8).normalise(meta, val) == val
            assert types.bytes_spec(pkt, 8).normalise(meta, val.tobytes()) == val
            assert (types.bytes_spec(pkt, 8).normalise(meta, binascii.hexlify(val.tobytes()).decode())) == val

        def test_it_gets_size_bits_by_calling_it_with_the_pkt_if_its_a_callable(self, meta, pkt):
            size_bits = mock.Mock(name="size_bits", return_value=11)

            val = bitarray("1" * 8)
            expected = val + bitarray("0" * 3)

            assert types.bytes_spec(pkt, size_bits).normalise(meta, val) == expected

            size_bits.assert_called_with(pkt)


class TestBytesAsStringSpec:
    def test_it_takes_in_pkt_size_bits_and_unpacking(self):
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        unpacking = mock.Mock(name="unpacking")

        spec = types.bytes_as_string_spec(pkt, size_bits, unpacking)

        assert spec.pkt is pkt
        assert spec.size_bits is size_bits
        assert spec.unpacking is unpacking

    class TestUnpackingIntoAString:
        @pytest.fixture()
        def subject(self, pkt):
            return types.bytes_as_string_spec(pkt, 20 * 8, True)

        def test_it_returns_as_is_if_already_a_string(self, meta, subject):
            val = "stuff"
            assert subject.normalise(meta, val) == val

        def test_it_cuts_from_the_null_byte_if_bytes(self, meta, subject):
            val = b"asdfsadf\x00askdlf"
            expected = "asdfsadf"
            assert subject.normalise(meta, val) == expected

        def test_it_does_not_cut_if_no_null_byte_is_found(self, meta, subject):
            val = b"asdfsadfaskdlf"
            assert subject.normalise(meta, val) == val.decode()

    class TestPackingIntoBytes:
        @pytest.fixture()
        def subject(self, pkt):
            return types.bytes_as_string_spec(pkt, 20 * 8, False)

        def test_it_encodes_string_into_bytes_and_pads_with_zeros(self, meta, subject):
            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray("0" * (20 * 8 - len(b)))

            assert subject.normalise(meta, s) == b

        def test_it_pads_bytes_with_zeros(self, meta, subject):
            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray("0" * (20 * 8 - len(b)))

            assert subject.normalise(meta, s.encode()) == b

        def test_it_gets_size_bits_by_calling_it_with_the_pkt_if_its_a_callable(self, meta, pkt):
            size_bits = mock.Mock(name="size_bits", return_value=11 * 8)

            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray("0" * (11 * 8 - len(b)))

            assert types.bytes_as_string_spec(pkt, size_bits).normalise(meta, s) == b

            size_bits.assert_called_with(pkt)


class TestFloatSpec:
    @pytest.fixture()
    def subject(self):
        return types.float_spec()

    def test_it_complains_if_its_given_a_boolean(self, meta, subject):
        for val in (True, False):
            with assertRaises(BadSpecValue, "Converting a boolean into a float makes no sense"):
                subject.normalise(meta, val)

    def test_it_converts_value_into_a_float(self, meta, subject):
        for val, expected in ((0, 0.0), (1, 1.0), (0.0, 0.0), (1.1, 1.1), (72.6666, 72.6666)):
            res = subject.normalise(meta, val)
            assert type(res) is float
            assert res == expected

    def test_it_complains_if_it_cant_convert_the_value(self, meta, subject):
        for val in (None, [], [1], {}, {1: 2}, lambda: 1):
            with assertRaises(BadSpecValue, "Failed to convert value into a float"):
                subject.normalise(meta, val)
