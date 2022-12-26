# coding: spec

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


describe "callable_spec":
    it "returns val if callable", meta:

        def cb(*args):
            pass

        assert types.callable_spec(None).normalise(meta, cb) is cb

    it "uses the spec otherwise":
        normalised = mock.Mock(name="normalised")

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        s = types.callable_spec(spec)
        val = mock.NonCallableMock(name="val")
        meta = Meta.empty()

        assert s.normalise(meta, val) is normalised
        spec.normalise.assert_called_once_with(meta, val)

describe "transform_spec":
    it "normalises spec with transformed value", meta:
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

    it "does not call the transform if value is sb.NotSpecified", meta:
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

    it "does not call the transform if value is Optional", meta:
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

describe "expand_spec":

    @pytest.fixture()
    def spec(self):
        return T.Bytes(20)

    @pytest.fixture()
    def kls(self):
        class Kls(dictobj.PacketSpec):
            fields = [("one", T.Bool), ("two", T.Int8)]

        return Kls

    it "takes in kls, spec and unpacking":
        kls = mock.Mock(name="kls")
        spec = mock.Mock(name="spec")
        unpacking = mock.Mock(name="unpacking")

        s = types.expand_spec(kls, spec, unpacking)

        assert s.kls is kls
        assert s.spec is spec
        assert s.unpacking is unpacking

    describe "packing into bytes":

        @pytest.fixture()
        def subject(self, spec, pkt, kls):
            spec = spec.spec(pkt, False)
            return types.expand_spec(kls, spec, False)

        it "returns bitarray value as bytes", meta, subject, kls:
            val = kls.create(one=True, two=127)
            b = val.pack()
            assert len(b) == 9

            b2 = subject.normalise(meta, b)
            assert len(b2) == 20

            assert b2[:9] == b
            assert b2[9:20] == bitarray("0" * 11)

        it "returns bytes value as bytes", meta, subject, kls:
            val = kls.create(one=True, two=127)
            b = val.pack()
            assert len(b) == 9

            b2 = subject.normalise(meta, b.tobytes())
            assert len(b2) == 20

            assert b2[:9] == b
            assert b2[9:20] == bitarray("0" * 11)

        it "returns a dictionary as bytes", meta, subject, kls:
            val = kls.create(one=True, two=12)
            b = val.pack()
            assert len(b) == 9

            b2 = subject.normalise(meta, {"one": True, "two": 12})
            assert len(b2) == 20

            assert b2[:9] == b
            assert b2[9:20] == bitarray("0" * 11)

        it "complains if something other than dictionary, bytes or bitarray is given", meta, subject:
            for thing in (0, 1, False, True, [], [1], "adsf", None, lambda: True):
                with assertRaises(
                    BadSpecValue, "Sorry, dynamic fields only supports a dictionary of values"
                ):
                    subject.normalise(meta, thing)

    describe "unpacking from bytes":

        @pytest.fixture()
        def subject(self, spec, pkt, kls):
            spec = spec.spec(pkt, True)
            return types.expand_spec(kls, spec, True)

        it "returns instance of kls if NotSpecified", meta, spec, pkt:

            class Kls(dictobj.PacketSpec):
                fields = [("one", T.Bool.default(False)), ("two", T.Int8.default(10))]

            spec = spec.spec(pkt, True)
            subject = types.expand_spec(Kls, spec, True)

            val = Kls.create()
            assert subject.normalise(meta, sb.NotSpecified) == val

        it "returns instance of kls if a dictionary", meta, subject, kls:
            val = kls.create(one=True, two=12)
            assert subject.normalise(meta, {"one": True, "two": 12}) == val

        it "returns as is if already of the kls type", meta, subject, kls:
            val = kls.create(one=True, two=12)
            assert subject.normalise(meta, val) is val

        it "returns as instance of the kls if bitarray", meta, subject, kls:
            val = kls.create(one=True, two=6)
            assert subject.normalise(meta, val.pack()) == val

        it "returns as instance of the kls if bytes", meta, subject, kls:
            val = kls.create(one=True, two=120)
            assert subject.normalise(meta, val.pack().tobytes()) == val

        it "complains if not bitarray, bytes or instance of kls", meta, subject, kls:
            for thing in (0, 1, False, True, [], [1], None, "adsf", lambda: True):
                with assertRaises(
                    BadSpecValue, "Expected to unpack bytes", found=thing, transforming_into=kls
                ):
                    subject.normalise(meta, thing)

describe "optional":
    it "says NotSpecified is Optional":
        spec = types.optional(mock.Mock(name="spec"))
        assert spec.normalise(Meta.empty(), sb.NotSpecified) is types.Optional

    it "normalises Optional as is":
        spec = types.optional(mock.Mock(name="spec"))
        assert spec.normalise(Meta.empty(), types.Optional) is types.Optional

    it "normalises anything else using self.spec":
        res = mock.Mock(name="res")
        ultimate_spec = mock.Mock(name="ultimate-spec")
        ultimate_spec.normalise.return_value = res

        meta = Meta.empty()

        spec = types.optional(ultimate_spec)
        thing = mock.Mock(name="thing")
        assert spec.normalise(meta, thing) is res

        ultimate_spec.normalise.assert_called_once_with(meta, thing)

describe "version_number_spec":
    it "takes in many things":
        unpacking = mock.Mock(name="unpacking")
        spec = types.version_number_spec(unpacking=unpacking)
        assert spec.unpacking is unpacking

    it "defaults unpacking":
        spec = types.version_number_spec()
        assert spec.unpacking is False

    describe "normalise":
        it "can go back and forward between string and integer", meta:
            for (want_int, want_str) in [(65538, "1.2"), (131092, "2.20"), (131272, "2.200")]:
                unpacker = types.version_number_spec(unpacking=False)
                as_int = unpacker.normalise(meta, want_str)
                assert as_int == want_int

                packer = types.version_number_spec(unpacking=True)
                as_str = packer.normalise(meta, as_int)
                assert as_str == want_str

        it "complains if val is not a valid version number", meta:
            for v in ("", "0", "0.wat", "wat.0", "wat"):
                with assertRaises(BadSpecValue, "Expected version string to match", wanted=v):
                    types.version_number_spec(unpacking=False).normalise(meta, v)

        it "can pack an integer", meta:
            assert types.version_number_spec(unpacking=False).normalise(meta, 100) == 100

        it "can unpack an string", meta:
            assert types.version_number_spec(unpacking=True).normalise(meta, "1.1") == "1.1"

        it "can unpack an incorect string", meta:
            with assertRaises(BadSpecValue, "Expected string to match", got="1"):
                types.version_number_spec(unpacking=True).normalise(meta, "1")

describe "integer_spec":
    it "takes in many things":
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

    it "complains if enum and bitmask are both specified":
        with assertRaises(
            ProgrammerError, "Sorry, can't specify enum and bitmask for the same type"
        ):
            types.integer_spec(
                mock.Mock(name="pkt"), mock.Mock(name="enum"), mock.Mock(name="bitmask")
            )

    it "defaults unpacking and allow_float":
        spec = types.integer_spec(mock.Mock(name="pkt"), None, None)
        assert spec.unpacking is False
        assert spec.allow_float is False

    describe "normalise":
        it "returns as is if not enum and not bitmask and allow_float and is a float", meta, pkt:
            spec = types.integer_spec(pkt, None, None, allow_float=True)
            assert spec.normalise(meta, 1.2) == 1.2

        it "asserts number is integer if no enum or bitmask and not allow_float", meta, pkt:
            spec = types.integer_spec(pkt, None, None, allow_float=False)
            with assertRaises(BadSpecValue, "Expected an integer"):
                spec.normalise(meta, 1.2)

        it "returns integer if not enum or bitmask", meta, pkt:
            spec = types.integer_spec(pkt, None, None)
            assert spec.normalise(meta, 1) == 1

        it "does an enum spec if we have an enum", pkt:
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
                spec = types.integer_spec(
                    pkt, enum, None, unpacking=unpacking, unknown_enum_values=uev
                )
                assert spec.normalise(meta, val) is ret

            enum_spec.assert_called_once_with(pkt, enum, unpacking=unpacking, allow_unknown=uev)
            es.normalise.assert_called_once_with(meta, val)

        it "does a bitmask spec if we have a bitmask", pkt:
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

describe "bitmask_spec":
    it "takes in some things":
        pkt = mock.Mock(name="pkt")
        bitmask = mock.Mock(name="bitmask")
        unpacking = mock.Mock(name="unpacking")

        spec = types.bitmask_spec(pkt, bitmask, unpacking=unpacking)

        assert spec.pkt is pkt
        assert spec.bitmask is bitmask
        assert spec.unpacking is unpacking

    describe "normalisation":

        @pytest.fixture()
        def bitmask(self):
            class Mask(Enum):
                ONE = 1 << 1
                TWO = 1 << 2
                THREE = 1 << 3
                FOUR = 1 << 4
                FIVE = 1 << 5

            return Mask

        it "complains if bitmask is not an Enum", meta, pkt:

            class Kls:
                def __init__(s, pkt):
                    pass

                def __call__(s, pkt):
                    return True

            for thing in (0, 1, [], [1], {}, {1: 2}, lambda pkt: 1, Kls(1), Kls, None, True, False):
                with assertRaises(ProgrammerError, "Bitmask is not an enum!"):
                    types.bitmask_spec(pkt, thing).normalise(meta, mock.Mock(name="val"))

        it "complains if bitmask has a zero value", meta, pkt:

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

        describe "packing into a number":

            @pytest.fixture()
            def subject(self, bitmask, pkt):
                return types.bitmask_spec(pkt, bitmask, unpacking=False)

            it "adds value if already part of the bitmask", meta, bitmask, subject:
                v = [bitmask.ONE, bitmask.THREE]
                final = (1 << 1) + (1 << 3)
                assert subject.normalise(meta, v) == final

            it "adds value if a matching number", meta, bitmask, subject:
                v = [bitmask.ONE, (1 << 3)]
                final = (1 << 1) + (1 << 3)
                assert subject.normalise(meta, v) == final

            it "adds value if a repr of the value", meta, bitmask, subject:
                r = "<Mask.FOUR: 16>"
                assert repr(bitmask.FOUR) == r
                v = [bitmask.ONE, r]
                final = (1 << 1) + (1 << 4)
                assert subject.normalise(meta, v) == final

            it "works with the string set()", meta, subject:
                assert subject.normalise(meta, "set()") == 0

            it "works with a set as a string", meta, subject:
                assert subject.normalise(meta, "{<Mask.ONE: 2>, <Mask.TWO: 4>}") == (1 << 1) + (
                    1 << 2
                )

            it "returns as is if the value is a number", meta, subject:
                assert subject.normalise(meta, 200) == 200

            it "complains if it can't convert the value", meta, bitmask, subject:
                for val in ("<Mask.SIX: 64>", "asdf", True, {}, {1: 2}, None, lambda: 1):
                    with assertRaises(
                        BadConversion, "Can't convert value into mask", mask=bitmask, got=val
                    ):
                        subject.normalise(meta, val)

            it "converts empty array into 0", meta, subject:
                assert subject.normalise(meta, []) == 0

            it "returns 0 as 0 or False", meta, subject:
                assert subject.normalise(meta, 0) == 0
                assert subject.normalise(meta, False) == 0

            it "works with a set of values", meta, bitmask, subject:
                v = set([bitmask.ONE, 1 << 3, "FIVE"])
                assert subject.normalise(meta, v) == (1 << 1) + (1 << 3) + (1 << 5)

            it "only counts values once", meta, bitmask, subject:
                v = set([bitmask.THREE, 1 << 3, "THREE"])
                assert subject.normalise(meta, v) == (1 << 3)

        describe "unpacking into a list":

            @pytest.fixture()
            def subject(self, bitmask, pkt):
                return types.bitmask_spec(pkt, bitmask, unpacking=True)

            it "returns as is if already bitmask items", meta, bitmask, subject:
                v = [bitmask.ONE, "THREE", "<Mask.FOUR: 16>"]
                assert subject.normalise(meta, v) == set([bitmask.ONE, bitmask.THREE, bitmask.FOUR])

            it "returns what values it can find in the value", meta, bitmask, subject:
                v = (1 << 1) + (1 << 3) + (1 << 4)
                assert subject.normalise(meta, v) == set([bitmask.ONE, bitmask.THREE, bitmask.FOUR])

            it "ignores left over", meta, bitmask, subject:
                v = (1 << 1) + (1 << 3) + (1 << 4)
                assert subject.normalise(meta, v + 1) == set(
                    [bitmask.ONE, bitmask.THREE, bitmask.FOUR]
                )

            it "works with the string set()", meta, subject:
                assert subject.normalise(meta, "set()") == set()

            it "works with a set as a string", meta, bitmask, subject:
                assert subject.normalise(meta, "{<Mask.ONE: 2>, <Mask.TWO: 4>}") == set(
                    [bitmask.ONE, bitmask.TWO]
                )

            it "complains if it finds a value from a different enum", meta, bitmask, subject:

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

            it "complains if it can't find a string value in the mask", meta, subject:
                with assertRaises(BadConversion, "Can't convert value into value from mask"):
                    subject.normalise(meta, "SEVEN")

            it "does not complain if it can't find an integer value in the mask", meta, subject:
                assert subject.normalise(meta, (1 << 24)) == set()

describe "enum_spec":
    it "takes in some things":
        pkt = mock.Mock(name="pkt")
        em = mock.Mock(name="enum")
        unpacking = mock.Mock(name="unpacking")
        allow_unknown = mock.Mock(name="allow_unknown")

        spec = types.enum_spec(pkt, em, unpacking=unpacking, allow_unknown=allow_unknown)

        assert spec.pkt is pkt
        assert spec.enum is em
        assert spec.unpacking is unpacking
        assert spec.allow_unknown is allow_unknown

    describe "normalisation":

        @pytest.fixture()
        def enum(self):
            class Vals(Enum):
                ONE = 1
                TWO = 2
                THREE = 3
                FOUR = 4
                FIVE = 5

            return Vals

        it "complains if enum is not an Enum", meta, pkt:

            class Kls:
                def __init__(s, pkt):
                    pass

                def __call__(s, pkt):
                    return True

            for thing in (0, 1, [], [1], {}, {1: 2}, lambda pkt: 1, Kls(1), Kls, None, True, False):
                with assertRaises(ProgrammerError, "Enum is not an enum!"):
                    types.enum_spec(pkt, thing).normalise(meta, mock.Mock(name="val"))
                with assertRaises(ProgrammerError, "Enum is not an enum!"):
                    types.enum_spec(pkt, thing, allow_unknown=True).normalise(
                        meta, mock.Mock(name="val")
                    )

        describe "packing into a value":

            @pytest.fixture()
            def subject(self, pkt, enum):
                return types.enum_spec(pkt, enum, unpacking=False)

            @pytest.fixture()
            def subject_with_unknown(self, pkt, enum):
                return types.enum_spec(pkt, enum, unpacking=False, allow_unknown=True)

            it "can convert from the name", meta, subject, subject_with_unknown:
                assert subject.normalise(meta, "ONE") == 1
                assert subject_with_unknown.normalise(meta, "ONE") == 1

            it "can convert from repr of the member", meta, subject, subject_with_unknown:
                assert subject.normalise(meta, "<Vals.ONE: 1>") == 1
                assert subject_with_unknown.normalise(meta, "<Vals.ONE: 1>") == 1

            it "can convert from member itself", meta, subject, enum, subject_with_unknown:
                assert subject.normalise(meta, enum.TWO) == 2
                assert subject_with_unknown.normalise(meta, enum.TWO) == 2

            it "complains if it's not in the enum", meta, subject, subject_with_unknown:
                ue = types.UnknownEnum(20)
                for val in (0, 200, False, None, [], [1], {}, {1: 2}, ue, repr(ue), lambda: 1):
                    with assertRaises(BadConversion, "Value wasn't a valid enum value"):
                        subject.normalise(meta, val)
                for val in (False, None, [], [1], {}, {1: 2}, lambda: 1):
                    with assertRaises(BadConversion, "Value wasn't a valid enum value"):
                        subject_with_unknown.normalise(meta, val)

            it "does not complain if allow_unknown and value not in the enum and valid value", meta, subject, subject_with_unknown:
                ue = types.UnknownEnum(20)
                assert subject_with_unknown.normalise(meta, ue) == 20
                assert subject_with_unknown.normalise(meta, repr(ue)) == 20

                assert subject_with_unknown.normalise(meta, 40) == 40

            it "complains if we're using the wrong enum", meta, subject, subject_with_unknown:

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

        describe "unpacking into enum member":

            @pytest.fixture()
            def subject(self, pkt, enum):
                return types.enum_spec(pkt, enum, unpacking=True)

            @pytest.fixture()
            def subject_with_unknown(self, pkt, enum):
                return types.enum_spec(pkt, enum, unpacking=True, allow_unknown=True)

            it "returns as is if already a member", meta, subject, enum, subject_with_unknown:
                assert subject.normalise(meta, enum.TWO) is enum.TWO
                assert subject_with_unknown.normalise(meta, enum.TWO) is enum.TWO

            it "complains if from the wrong enum", meta, subject, subject_with_unknown:

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

            it "converts from name", meta, subject, enum, subject_with_unknown:
                assert subject.normalise(meta, "THREE") == enum.THREE
                assert subject_with_unknown.normalise(meta, "THREE") == enum.THREE

            it "converts from repr of member", meta, subject, enum, subject_with_unknown:
                assert subject.normalise(meta, "<Vals.THREE: 3>") == enum.THREE
                assert subject_with_unknown.normalise(meta, "<Vals.THREE: 3>") == enum.THREE

            it "converts from value of member", meta, subject, enum, subject_with_unknown:
                assert subject.normalise(meta, 4) == enum.FOUR
                assert subject_with_unknown.normalise(meta, 4) == enum.FOUR

            it "complains if value isn't in enum", meta, subject, subject_with_unknown:
                ue = repr(types.UnknownEnum(20))
                for val in ("SEVEN", 200, ue, False, None, [], [1], {}, {1: 2}, lambda: 1):
                    with assertRaises(BadConversion, "Value is not a valid value of the enum"):
                        subject.normalise(meta, val)

                for val in ("SEVEN", False, None, [], [1], {}, {1: 2}, lambda: 1):
                    with assertRaises(BadConversion, "Value is not a valid value of the enum"):
                        subject_with_unknown.normalise(meta, val)

            it "does not complain if allow_unknown and valid unknown value", meta, subject, subject_with_unknown:
                ue = types.UnknownEnum(20)
                assert subject_with_unknown.normalise(meta, ue) is ue
                assert subject_with_unknown.normalise(meta, repr(ue)) == ue
                assert subject_with_unknown.normalise(meta, 20) == ue

describe "overridden":
    it "takes in pkt and default_func":
        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        assert spec.default_func is default_func
        assert spec.pkt is pkt

    it "uses the default_func with pkt regardless of value":
        meta = Meta.empty()
        val = mock.Mock(name="val")

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        ret = mock.Mock(name="ret")
        default_func.return_value = ret

        assert spec.normalise(meta, val) is ret

        default_func.assert_called_once_with(pkt)

    it "uses the default_func with pkt even with NotSpecified":
        meta = Meta.empty()
        val = sb.NotSpecified

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        ret = mock.Mock(name="ret")
        default_func.return_value = ret

        assert spec.normalise(meta, val) is ret

        default_func.assert_called_once_with(pkt)

describe "defaulted":
    it "takes in spec, pkt and default_func":
        default_func = mock.Mock(name="default_func")
        spec = mock.Mock(name="spec")
        pkt = mock.Mock(name="pkt")
        subject = types.defaulted(spec, default_func, pkt)

        assert subject.spec is spec
        assert subject.default_func is default_func
        assert subject.pkt is pkt

    it "uses the spec with the value if not empty":
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

    it "uses the default_func with pkt when NotSpecified":
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

describe "boolean":
    it "complains if no value to normalise":
        with assertRaises(BadSpecValue, "Must specify boolean values"):
            types.boolean().normalise(Meta.empty(), sb.NotSpecified)

    it "returns as is if the value is a boolean":
        assert types.boolean().normalise(Meta.empty(), False) is False
        assert types.boolean().normalise(Meta.empty(), True) is True

    it "returns as boolean if 0 or 1":
        assert types.boolean().normalise(Meta.empty(), 0) is False
        assert types.boolean().normalise(Meta.empty(), 1) is True

    it "complains if not boolean, 0 or 1":
        for val in (None, [], [1], {}, {1: 2}, "asdf", b"asdf", lambda: 1):
            with assertRaises(BadSpecValue, "Could not convert value into a boolean", val=val):
                types.boolean().normalise(Meta.empty(), val)

describe "boolean_as_int_spec":
    it "complains if no value to normalise":
        with assertRaises(BadSpecValue, "Must specify boolean values"):
            types.boolean_as_int_spec().normalise(Meta.empty(), sb.NotSpecified)

    it "returns as is if the value is 0 or 1":
        assert types.boolean_as_int_spec().normalise(Meta.empty(), 0) == 0
        assert types.boolean_as_int_spec().normalise(Meta.empty(), 1) == 1

    it "returns as 0 or 1 if True or False":
        assert types.boolean_as_int_spec().normalise(Meta.empty(), False) == 0
        assert types.boolean_as_int_spec().normalise(Meta.empty(), True) == 1

    it "complains if not boolean, 0 or 1":
        for val in (None, [], [1], {}, {1: 2}, "asdf", b"asdf", lambda: 1):
            with assertRaises(BadSpecValue, "BoolInts must be True, False, 0 or 1", got=val):
                types.boolean_as_int_spec().normalise(Meta.empty(), val)

describe "csv_spec":
    it "takes in pkt, size_bits and unpacking":
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        unpacking = mock.Mock(name="unpacking")
        spec = types.csv_spec(pkt, size_bits, unpacking=unpacking)

        assert spec.pkt is pkt
        assert spec.size_bits is size_bits
        assert spec.unpacking is unpacking

    describe "packing into bitarray":

        @pytest.fixture()
        def subject(self, pkt):
            return types.csv_spec(pkt, 200 * 8, unpacking=False)

        @pytest.fixture()
        def val(self):
            v1 = str(uuid.uuid1())
            v2 = str(uuid.uuid1())
            return [v1, v2]

        it "converts a list into a comma separated string into bitarray", meta, val, subject:
            expected_bytes = ",".join(val).encode() + b"\x00"
            assert len(expected_bytes) == 74
            result = subject.normalise(meta, val).tobytes()

            assert result[:74] == expected_bytes
            assert result[74:] == bitarray("0" * (200 - 74) * 8).tobytes()

        it "converts a string into bitarray", meta, val, subject:
            s = ",".join(val)
            expected_bytes = s.encode() + b"\x00"
            assert len(expected_bytes) == 74

            result = subject.normalise(meta, s).tobytes()

            assert result[:74] == expected_bytes
            assert result[74:] == bitarray("0" * (200 - 74) * 8).tobytes()

        it "converts bytes into bitarray with correct size", meta, val, subject:
            b = ",".join(val).encode()
            expected_bytes = b + b"\x00"
            assert len(expected_bytes) == 74

            result = subject.normalise(meta, b).tobytes()

            assert result[:74] == expected_bytes
            assert result[74:] == bitarray("0" * (200 - 74) * 8).tobytes()

        it "converts bitarray into bitarray with correct size", meta, val, subject:
            b = ",".join(val).encode()
            expected_bytes = b + b"\x00"
            assert len(expected_bytes) == 74

            b2 = bitarray(endian="little")
            b2.frombytes(b)
            result = subject.normalise(meta, b2).tobytes()

            assert result[:74] == expected_bytes
            assert result[74:] == bitarray("0" * (200 - 74) * 8).tobytes()

    describe "unpacking into list":

        @pytest.fixture()
        def subject(self, pkt):
            return types.csv_spec(pkt, 200 * 8, unpacking=True)

        @pytest.fixture()
        def val(self):
            v1 = str(uuid.uuid1())
            v2 = str(uuid.uuid1())
            return [v1, v2]

        it "returns list as is if already a list", meta, val, subject:
            assert subject.normalise(meta, val) == val

        it "turns bitarray into a list", meta, val, subject:
            b = ",".join(val).encode() + b"\x00" + bitarray("0" * 100).tobytes()

            b2 = bitarray(endian="little")
            b2.frombytes(b)
            assert subject.normalise(meta, b2) == val

        it "turns bytes into a list", meta, val, subject:
            b = ",".join(val).encode() + b"\x00" + bitarray("0" * 100).tobytes()
            assert subject.normalise(meta, b) == val

        it "turns string into a list", meta, val, subject:
            s = ",".join(val)
            assert subject.normalise(meta, s) == val

describe "bytes_spec":
    it "takes in pkt and size_bits":
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        spec = types.bytes_spec(pkt, size_bits)
        assert spec.pkt is pkt
        assert spec.size_bits is size_bits

    describe "normalising":
        it "works from the repr of sb.NotSpecified", meta, pkt:
            expected = bitarray("0" * 8)
            assert types.bytes_spec(pkt, 8).normalise(meta, repr(sb.NotSpecified)) == expected

            expected = bitarray("0" * 8)
            assert (
                types.bytes_spec(pkt, 8).normalise(meta, repr(sb.NotSpecified).replace("'", ""))
            ) == expected

        it "returns None as the size_bits of bitarray", meta, pkt:
            expected = bitarray("0" * 8)
            assert types.bytes_spec(pkt, 8).normalise(meta, None) == expected

            expected = bitarray("0" * 20)
            assert types.bytes_spec(pkt, 20).normalise(meta, None) == expected

        it "returns 0 as the size_bits of bitarray", meta, pkt:
            expected = bitarray("0" * 8)
            assert types.bytes_spec(pkt, 8).normalise(meta, 0) == expected

            expected = bitarray("0" * 20)
            assert types.bytes_spec(pkt, 20).normalise(meta, 0) == expected

        it "expands if not long enough", meta, pkt:
            val = bitarray("1" * 8)
            expected = bitarray("1" * 8 + "0" * 12)
            assert types.bytes_spec(pkt, 20).normalise(meta, val) == expected
            assert types.bytes_spec(pkt, 20).normalise(meta, val.tobytes()) == expected
            assert (
                types.bytes_spec(pkt, 20).normalise(meta, binascii.hexlify(val.tobytes()).decode())
            ) == expected

        it "cuts off if too long", meta, pkt:
            val = bitarray("1" * 24)
            expected = bitarray("1" * 9)
            assert types.bytes_spec(pkt, 9).normalise(meta, val) == expected
            assert types.bytes_spec(pkt, 9).normalise(meta, val.tobytes()) == expected
            assert (
                types.bytes_spec(pkt, 9).normalise(meta, binascii.hexlify(val.tobytes()).decode())
            ) == expected

        it "returns if just right", meta, pkt:
            val = bitarray("1" * 8)
            assert types.bytes_spec(pkt, 8).normalise(meta, val) == val
            assert types.bytes_spec(pkt, 8).normalise(meta, val.tobytes()) == val
            assert (
                types.bytes_spec(pkt, 8).normalise(meta, binascii.hexlify(val.tobytes()).decode())
            ) == val

        it "gets size_bits by calling it with the pkt if it's a callable", meta, pkt:
            size_bits = mock.Mock(name="size_bits", return_value=11)

            val = bitarray("1" * 8)
            expected = val + bitarray("0" * 3)

            assert types.bytes_spec(pkt, size_bits).normalise(meta, val) == expected

            size_bits.assert_called_with(pkt)

describe "bytes_as_string_spec":
    it "takes in pkt, size_bits and unpacking":
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        unpacking = mock.Mock(name="unpacking")

        spec = types.bytes_as_string_spec(pkt, size_bits, unpacking)

        assert spec.pkt is pkt
        assert spec.size_bits is size_bits
        assert spec.unpacking is unpacking

    describe "unpacking into a string":

        @pytest.fixture()
        def subject(self, pkt):
            return types.bytes_as_string_spec(pkt, 20 * 8, True)

        it "returns as is if already a string", meta, subject:
            val = "stuff"
            assert subject.normalise(meta, val) == val

        it "cuts from the null byte if bytes", meta, subject:
            val = b"asdfsadf\x00askdlf"
            expected = "asdfsadf"
            assert subject.normalise(meta, val) == expected

        it "does not cut if no null byte is found", meta, subject:
            val = b"asdfsadfaskdlf"
            assert subject.normalise(meta, val) == val.decode()

    describe "packing into bytes":

        @pytest.fixture()
        def subject(self, pkt):
            return types.bytes_as_string_spec(pkt, 20 * 8, False)

        it "encodes string into bytes and pads with zeros", meta, subject:
            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray("0" * (20 * 8 - len(b)))

            assert subject.normalise(meta, s) == b

        it "pads bytes with zeros", meta, subject:
            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray("0" * (20 * 8 - len(b)))

            assert subject.normalise(meta, s.encode()) == b

        it "gets size_bits by calling it with the pkt if it's a callable", meta, pkt:
            size_bits = mock.Mock(name="size_bits", return_value=11 * 8)

            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray("0" * (11 * 8 - len(b)))

            assert types.bytes_as_string_spec(pkt, size_bits).normalise(meta, s) == b

            size_bits.assert_called_with(pkt)

describe "float_spec":

    @pytest.fixture()
    def subject(self):
        return types.float_spec()

    it "complains if it's given a boolean", meta, subject:
        for val in (True, False):
            with assertRaises(BadSpecValue, "Converting a boolean into a float makes no sense"):
                subject.normalise(meta, val)

    it "converts value into a float", meta, subject:
        for val, expected in ((0, 0.0), (1, 1.0), (0.0, 0.0), (1.1, 1.1), (72.6666, 72.6666)):
            res = subject.normalise(meta, val)
            assert type(res) is float
            assert res == expected

    it "complains if it can't convert the value", meta, subject:
        for val in (None, [], [1], {}, {1: 2}, lambda: 1):
            with assertRaises(BadSpecValue, "Failed to convert value into a float"):
                subject.normalise(meta, val)
