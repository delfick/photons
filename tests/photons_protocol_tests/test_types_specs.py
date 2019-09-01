# coding: spec

from photons_protocol.types import Type as T
from photons_protocol.packets import dictobj
from photons_protocol import types

from photons_app.errors import ProgrammerError
from photons_app.test_helpers import TestCase

from photons_protocol.errors import BadSpecValue, BadConversion
from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from bitarray import bitarray
from textwrap import dedent
from unittest import mock
from enum import Enum
import binascii
import json
import uuid

describe TestCase, "callable_spec":
    before_each:
        self.meta = Meta.empty()

    it "returns val if callable":
        def cb(*args):
            pass

        self.assertIs(types.callable_spec(None).normalise(self.meta, cb), cb)

    it "uses the spec otherwise":
        normalised = mock.Mock(name="normalised")

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        s = types.callable_spec(spec)
        val = mock.NonCallableMock(name="val")
        meta = Meta.empty()

        self.assertIs(s.normalise(meta, val), normalised)
        spec.normalise.assert_called_once_with(meta, val)

describe TestCase, "transform_spec":
    before_each:
        self.transformed = mock.Mock(name="transformed")
        self.do_transform = mock.Mock(name="do_transform", return_value=self.transformed)
        self.val = mock.Mock(name='val')
        self.meta = Meta.empty()

    it "normalises spec with transformed value":
        pkt = mock.Mock(name="pkt")
        unpacking = mock.Mock(name="unpacking")
        normalised = mock.Mock(name='normalised')

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        ts = types.transform_spec(pkt, spec, self.do_transform)
        self.assertIs(ts.normalise(self.meta, self.val), normalised)

        self.do_transform.assert_called_once_with(pkt, self.val)
        spec.normalise.assert_called_once_with(self.meta, self.transformed)

    it "does not call the transform if value is sb.NotSpecified":
        pkt = mock.Mock(name="pkt")
        unpacking = mock.Mock(name="unpacking")
        normalised = mock.Mock(name='normalised')

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        ts = types.transform_spec(pkt, spec, self.do_transform)
        self.assertIs(ts.normalise(self.meta, sb.NotSpecified), normalised)

        self.assertEqual(len(self.do_transform.mock_calls), 0)
        spec.normalise.assert_called_once_with(self.meta, sb.NotSpecified)

    it "does not call the transform if value is Optional":
        pkt = mock.Mock(name="pkt")
        unpacking = mock.Mock(name="unpacking")
        normalised = mock.Mock(name='normalised')

        spec = mock.Mock(name="spec")
        spec.normalise.return_value = normalised

        ts = types.transform_spec(pkt, spec, self.do_transform)
        self.assertIs(ts.normalise(self.meta, types.Optional), normalised)

        self.assertEqual(len(self.do_transform.mock_calls), 0)
        spec.normalise.assert_called_once_with(self.meta, types.Optional)

describe TestCase, "many_spec":
    before_each:
        # A packetspec for the tests
        class Kls(dictobj.PacketSpec):
            fields = [
                  ("one", T.Bool)
                , ("two", T.Int8)
                ]

        self.kls = Kls
        self.pkt = mock.Mock(name="pkt")
        self.sizer = 20
        self.spec = T.Bytes(20 * 3)
        self.unpacking = mock.Mock(name="unpacking")

    it "takes in a few things":
        spec = types.many_spec(self.kls, self.sizer, self.pkt, self.spec, self.unpacking)
        self.assertIs(self.kls, self.kls)
        self.assertIs(self.pkt, self.pkt)
        self.assertIs(self.spec, self.spec)
        self.assertIs(self.sizer, self.sizer)
        self.assertIs(self.unpacking, self.unpacking)

    describe "packing into bytes":
        before_each:
            self.meta = Meta({}, [])
            self.pkt = mock.Mock(name="pkt")
            spec = self.spec.spec(self.pkt, False)
            self.subject = types.many_spec(self.kls, self.sizer, self.pkt, spec, False)

        it "returns bitarray value as bytes":
            b = self.kls.empty_normalise(one=True, two=127).pack()
            self.assertEqual(len(b), 9)

            b2 = self.subject.normalise(self.meta, b)
            self.assertEqual(len(b2), 60)

            self.assertEqual(b2[:9], b)
            self.assertEqual(b2[9:], bitarray('0' * 51))

        it "returns bytes value as bytes":
            b = self.kls.empty_normalise(one=True, two=127).pack()
            self.assertEqual(len(b), 9)

            b2 = self.subject.normalise(self.meta, b.tobytes())
            self.assertEqual(len(b2), 60)

            self.assertEqual(b2[:9], b)
            self.assertEqual(b2[9:], bitarray('0' * 51))

        it "returns a list as bytes":
            val1 = self.kls.empty_normalise(one=True, two=127).pack()
            val2 = self.kls.empty_normalise(one=False, two=3).pack()
            val3 = self.kls.empty_normalise(one=True, two=8).pack()

            vb1 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val1)
            vb2 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val2)
            vb3 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val3)

            b = vb1 + vb2 + vb3
            self.assertEqual(len(b), 60)

            b2 = self.subject.normalise(self.meta, [{"one": True, "two": 127}, {"one": False, "two": 3}, {"one": True, "two": 8}])
            self.assertEqual(len(b2), 60)

            self.assertEqual(b2[:9], val1)
            self.assertEqual(b2[9:20], bitarray('0' * 11))

        it "complains if something other than list, bytes or bitarray is given":
            for thing in (0, 1, False, True, {}, {1: 2}, [1], "adsf", None, lambda: True):
                with self.fuzzyAssertRaisesError(BadSpecValue, "Sorry, many fields only supports a list of dictionary of values"):
                    self.subject.normalise(self.meta, thing)

        it "uses the cache on the kls if it has one":
            record = False
            packd = []

            class Kls(dictobj.PacketSpec):
                fields = [
                      ("one", T.Bool)
                    , ("two", T.Int8)
                    ]

                def pack(self):
                    if record:
                        packd.append(tuple(self.items()))
                    return super(Kls, self).pack()
            Kls.Meta.cache = {}
            spec = T.Bytes(self.sizer * 25).spec(self.pkt, False)
            subject = types.many_spec(Kls, self.sizer, self.pkt, spec, False)

            items1 = (("one", True), ("two", 1))
            items2 = (("one", True), ("two", 2))
            items3 = (("one", False), ("two", 1))

            val1 = Kls.empty_normalise(**dict(items1)).pack()
            val2 = Kls.empty_normalise(**dict(items2)).pack()
            val3 = Kls.empty_normalise(**dict(items3)).pack()

            vb1 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val1)
            vb2 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val2)
            vb3 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val3)

            expected = (vb1 * 5) + (vb2 * 5) + (vb1 * 5) + (vb3 * 5) + (vb2 * 5)
            self.assertEqual(Kls.Meta.cache, {})

            items = ([dict(items1)] * 5) + ([dict(items2)] * 5) + ([dict(items1)] * 5) + ([dict(items3)] * 5) + ([dict(items2)] * 5)

            record = True
            b = subject.normalise(self.meta, items)

            self.assertEqual(Kls.Meta.cache, {items1: val1, items2: val2, items3: val3})
            self.assertEqual(packd, [items1, items2, items3])
            self.assertEqual(b, expected)

    describe "unpacking from bytes":
        before_each:
            self.meta = Meta({}, [])
            self.pkt = mock.Mock(name="pkt")
            spec = self.spec.spec(self.pkt, True)
            self.subject = types.many_spec(self.kls, self.sizer, self.pkt, spec, True)

        it "returns as is if already a list":
            val1 = self.kls.empty_normalise(one=True, two=127)
            val2 = self.kls.empty_normalise(one=False, two=3)
            val3 = self.kls.empty_normalise(one=True, two=8)

            val = [val1, val2, val3]
            self.assertIs(self.subject.normalise(self.meta, val), val)

            val = []
            self.assertIs(self.subject.normalise(self.meta, val), val)

        it "returns as a list of instances of the kls if bitarray":
            val1 = self.kls.empty_normalise(one=True, two=127)
            val2 = self.kls.empty_normalise(one=False, two=3)
            val3 = self.kls.empty_normalise(one=True, two=8)

            vb1 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val1.pack())
            vb2 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val2.pack())
            vb3 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val3.pack())

            b = vb1 + vb2 + vb3
            self.assertEqual(self.subject.normalise(self.meta, b), [val1, val2, val3])

        it "returns as instance of the kls if bytes":
            val1 = self.kls.empty_normalise(one=True, two=127)
            val2 = self.kls.empty_normalise(one=False, two=3)
            val3 = self.kls.empty_normalise(one=True, two=8)

            vb1 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val1.pack())
            vb2 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val2.pack())
            vb3 = types.bytes_spec(self.pkt, self.sizer).normalise(self.meta, val3.pack())

            b = vb1 + vb2 + vb3
            self.assertEqual(self.subject.normalise(self.meta, b.tobytes()), [val1, val2, val3])

        it "complains if not bitarray, bytes or list of kls":
            for thing in (0, 1, False, True, {}, {1: 2}, None, "adsf", lambda: True):
                with self.fuzzyAssertRaisesError(BadSpecValue, "Expected to unpack bytes", found=thing, transforming_into_list_of=self.kls):
                    self.subject.normalise(self.meta, thing)

describe TestCase, "complex many_spec":
    it "works with different sizes for the items":
        # A packetspec for the tests
        class Kls(dictobj.PacketSpec):
            fields = [
                  ("size", T.Int8)
                , ("two", T.String(lambda pkt: pkt.size))
                , ('three', T.Uint16.transform(
                          lambda _, v: int(65535 * (0 if v is sb.NotSpecified else float(v)))
                        , lambda _, v: float(v) / 65535
                        ).allow_float()
                      )
                ]

        class Pkt(dictobj.PacketSpec):
            fields = [
                  ("things_size", T.Int16)
                , ("things", T.Bytes(lambda pkt: pkt.things_size).many(lambda pkt: Kls))
                ]

        things = [{"size": 40, "two": "wat", "three": 0.3}, {"size": 80, "two": "blah", "three": 0.5}]
        want = {"things_size": 168, "things": things}

        bts = Pkt.empty_normalise(**want).pack()
        expected = dedent("""
            000101010000000000010100111011101000011000101110000000000000000000110011001100100
            0001010010001100011011010000110000101100000000000000000000000000000000000000000000000001111111111111110
            """).replace("\n", "").strip()

        self.assertEqual(bts, bitarray(expected))

        got = Pkt.unpack(bts)
        self.assertEqual(got.things_size, 168)

        self.assertEqual(type(got.things), list, got.things)

        self.assertEqual(got.things[0].size, 40)
        self.assertEqual(got.things[0].two, "wat")
        self.assertAlmostEqual(got.things[0].three, 0.3, places=2)

        self.assertEqual(got.things[1].size, 80)
        self.assertEqual(got.things[1].two, "blah")
        self.assertAlmostEqual(got.things[1].three, 0.5, places=2)

describe TestCase, "expand_spec":
    before_each:
        # A packetspec for the tests
        class Kls(dictobj.PacketSpec):
            fields = [
                  ("one", T.Bool)
                , ("two", T.Int8)
                ]

        self.kls = Kls
        self.spec = T.Bytes(20)
        self.unpacking = mock.Mock(name="unpacking")

    it "takes in kls, spec and unpacking":
        spec = types.expand_spec(self.kls, self.spec, self.unpacking)
        self.assertIs(self.kls, self.kls)
        self.assertIs(self.spec, self.spec)
        self.assertIs(self.unpacking, self.unpacking)

    describe "packing into bytes":
        before_each:
            self.meta = Meta({}, [])
            self.pkt = mock.Mock(name="pkt")
            spec = self.spec.spec(self.pkt, False)
            self.subject = types.expand_spec(self.kls, spec, False)

        it "returns bitarray value as bytes":
            val = self.kls.empty_normalise(one=True, two=127)
            b = val.pack()
            self.assertEqual(len(b), 9)

            b2 = self.subject.normalise(self.meta, b)
            self.assertEqual(len(b2), 20)

            self.assertEqual(b2[:9], b)
            self.assertEqual(b2[9:20], bitarray('0' * 11))

        it "returns bytes value as bytes":
            val = self.kls.empty_normalise(one=True, two=127)
            b = val.pack()
            self.assertEqual(len(b), 9)

            b2 = self.subject.normalise(self.meta, b.tobytes())
            self.assertEqual(len(b2), 20)

            self.assertEqual(b2[:9], b)
            self.assertEqual(b2[9:20], bitarray('0' * 11))

        it "returns a dictionary as bytes":
            val = self.kls.empty_normalise(one=True, two=12)
            b = val.pack()
            self.assertEqual(len(b), 9)

            b2 = self.subject.normalise(self.meta, {"one": True, "two": 12})
            self.assertEqual(len(b2), 20)

            self.assertEqual(b2[:9], b)
            self.assertEqual(b2[9:20], bitarray('0' * 11))

        it "complains if something other than dictionary, bytes or bitarray is given":
            for thing in (0, 1, False, True, [], [1], "adsf", None, lambda: True):
                with self.fuzzyAssertRaisesError(BadSpecValue, "Sorry, dynamic fields only supports a dictionary of values"):
                    self.subject.normalise(self.meta, thing)

    describe "unpacking from bytes":
        before_each:
            self.meta = Meta({}, [])
            self.pkt = mock.Mock(name="pkt")
            spec = self.spec.spec(self.pkt, True)
            self.subject = types.expand_spec(self.kls, spec, True)

        it "returns as is if already of the kls type":
            val = self.kls.empty_normalise(one=True, two=12)
            self.assertIs(self.subject.normalise(self.meta, val), val)

        it "returns as instance of the kls if bitarray":
            val = self.kls.empty_normalise(one=True, two=6)
            self.assertEqual(self.subject.normalise(self.meta, val.pack()), val)

        it "returns as instance of the kls if bytes":
            val = self.kls.empty_normalise(one=True, two=120)
            self.assertEqual(self.subject.normalise(self.meta, val.pack().tobytes()), val)

        it "complains if not bitarray, bytes or instance of kls":
            for thing in (0, 1, False, True, [], [1], {}, {1: 2}, None, "adsf", lambda: True):
                with self.fuzzyAssertRaisesError(BadSpecValue, "Expected to unpack bytes", found=thing, transforming_into=self.kls):
                    self.subject.normalise(self.meta, thing)

describe TestCase, "optional":
    it "says NotSpecified is Optional":
        spec = types.optional(mock.Mock(name="spec"))
        self.assertIs(spec.normalise(Meta.empty(), sb.NotSpecified), types.Optional)

    it "normalises Optional as is":
        spec = types.optional(mock.Mock(name="spec"))
        self.assertIs(spec.normalise(Meta.empty(), types.Optional), types.Optional)

    it "normalises anything else using self.spec":
        res = mock.Mock(name="res")
        ultimate_spec = mock.Mock(name="ultimate-spec")
        ultimate_spec.normalise.return_value = res

        meta = Meta.empty()

        spec = types.optional(ultimate_spec)
        thing = mock.Mock(name="thing")
        self.assertIs(spec.normalise(meta, thing), res)

        ultimate_spec.normalise.assert_called_once_with(meta, thing)

describe TestCase, "version_number_spec":
    it "takes in many things":
        unpacking = mock.Mock(name="unpacking")
        spec = types.version_number_spec(unpacking=unpacking)
        self.assertIs(spec.unpacking, unpacking)

    it "defaults unpacking":
        spec = types.version_number_spec()
        self.assertEqual(spec.unpacking, False)

    describe "normalise":
        before_each:
            self.meta = Meta.empty()

        it "can go back and forward between string and integer":
            for (want_int, want_str) in [(65538, "1.2"), (131092, "2.20"), (131272, "2.200")]:
                unpacker = types.version_number_spec(unpacking=False)
                as_int = unpacker.normalise(self.meta, want_str)
                self.assertEqual(as_int, want_int)

                packer = types.version_number_spec(unpacking=True)
                as_str = packer.normalise(self.meta, as_int)
                self.assertEqual(as_str, want_str)

        it "complains if val is not a valid version number":
            for v in ("", "0", "0.wat", "wat.0", "wat"):
                with self.fuzzyAssertRaisesError(BadSpecValue, "Expected version string to match", wanted=v):
                    types.version_number_spec(unpacking=False).normalise(self.meta, v)

        it "can pack an integer":
            self.assertEqual(types.version_number_spec(unpacking=False).normalise(self.meta, 100), 100)

        it "can unpack an string":
            self.assertEqual(types.version_number_spec(unpacking=True).normalise(self.meta, "1.1"), "1.1")

        it "can unpack an incorect string":
            with self.fuzzyAssertRaisesError(BadSpecValue, "Expected string to match", got="1"):
                types.version_number_spec(unpacking=True).normalise(self.meta, "1")

describe TestCase, "integer_spec":
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
            self.assertIs(spec.pkt, pkt)
            self.assertIs(spec.enum, kw["enum"])
            self.assertIs(spec.bitmask, kw["bitmask"])
            self.assertIs(spec.unpacking, unpacking)
            self.assertIs(spec.allow_float, allow_float)
            self.assertIs(spec.unknown_enum_values, unknown_enum_values)

    it "complains if enum and bitmask are both specified":
        with self.fuzzyAssertRaisesError(ProgrammerError, "Sorry, can't specify enum and bitmask for the same type"):
            types.integer_spec(mock.Mock(name="pkt"), mock.Mock(name="enum"), mock.Mock(name="bitmask"))

    it "defaults unpacking and allow_float":
        spec = types.integer_spec(mock.Mock(name="pkt"), None, None)
        self.assertEqual(spec.unpacking, False)
        self.assertEqual(spec.allow_float, False)

    describe "normalise":
        before_each:
            self.pkt = mock.Mock(name="pkt")
            self.meta = Meta.empty()

        it "returns as is if not enum and not bitmask and allow_float and is a float":
            spec = types.integer_spec(self.pkt, None, None, allow_float=True)
            self.assertEqual(spec.normalise(self.meta, 1.2), 1.2)

        it "asserts number is integer if no enum or bitmask and not allow_float":
            spec = types.integer_spec(self.pkt, None, None, allow_float=False)
            with self.fuzzyAssertRaisesError(BadSpecValue, "Expected an integer"):
                spec.normalise(self.meta, 1.2)

        it "returns integer if not enum or bitmask":
            spec = types.integer_spec(self.pkt, None, None)
            self.assertEqual(spec.normalise(self.meta, 1), 1)

        it "does an enum spec if we have an enum":
            ret = mock.Mock(name='ret')
            enum = mock.Mock(name='enum')
            unpacking = mock.Mock(name='unpacking')

            meta = Meta.empty()
            val = mock.Mock(name="val")

            es = mock.Mock(name="enum_spec()")
            uev = mock.Mock(name="unknown_enum_values")
            enum_spec = mock.Mock(name='enum_spec', return_value=es)
            es.normalise.return_value = ret
            with mock.patch("photons_protocol.types.enum_spec", enum_spec):
                spec = types.integer_spec(self.pkt, enum, None, unpacking=unpacking, unknown_enum_values=uev)
                self.assertIs(spec.normalise(meta, val), ret)

            enum_spec.assert_called_once_with(self.pkt, enum, unpacking=unpacking, allow_unknown=uev)
            es.normalise.assert_called_once_with(meta, val)

        it "does a bitmask spec if we have a bitmask":
            ret = mock.Mock(name='ret')
            bitmask = mock.Mock(name='bitmask')
            unpacking = mock.Mock(name='unpacking')

            meta = Meta.empty()
            val = mock.Mock(name="val")

            es = mock.Mock(name="bitmask_spec()")
            bitmask_spec = mock.Mock(name='bitmask_spec', return_value=es)
            es.normalise.return_value = ret
            with mock.patch("photons_protocol.types.bitmask_spec", bitmask_spec):
                spec = types.integer_spec(self.pkt, None, bitmask, unpacking=unpacking)
                self.assertIs(spec.normalise(meta, val), ret)

            bitmask_spec.assert_called_once_with(self.pkt, bitmask, unpacking=unpacking)
            es.normalise.assert_called_once_with(meta, val)

describe TestCase, "bitmask_spec":
    it "takes in some things":
        pkt = mock.Mock(name="pkt")
        bitmask = mock.Mock(name='bitmask')
        unpacking = mock.Mock(name="unpacking")

        spec = types.bitmask_spec(pkt, bitmask, unpacking=unpacking)

        self.assertIs(spec.pkt, pkt)
        self.assertIs(spec.bitmask, bitmask)
        self.assertIs(spec.unpacking, unpacking)

    describe "normalisation":
        before_each:
            # And enum for out bitmask
            class Mask(Enum):
                ONE    = (1 << 1)
                TWO    = (1 << 2)
                THREE  = (1 << 3)
                FOUR   = (1 << 4)
                FIVE   = (1 << 5)

            self.pkt = mock.Mock(name="pkt")
            self.bitmask = Mask

            self.meta = Meta.empty()

        it "complains if bitmask is not an Enum":
            class Kls(object):
                def __init__(self, pkt):
                    pass
                def __call__(self, pkt):
                    return True

            for thing in (0, 1, [], [1], {}, {1:2}, lambda pkt: 1, Kls(1), Kls, None, True, False):
                with self.fuzzyAssertRaisesError(ProgrammerError, "Bitmask is not an enum!"):
                    types.bitmask_spec(self.pkt, thing).normalise(self.meta, mock.Mock(name='val'))

        it "complains if bitmask has a zero value":
            class BM(Enum):
                ZERO = 0
                ONE = 1
                TWO = 2

            with self.fuzzyAssertRaisesError(ProgrammerError, "A bitmask with a zero value item makes no sense: ZERO in <enum 'BM'>"):
                types.bitmask_spec(self.pkt, BM).normalise(self.meta, mock.Mock(name='val'))

            with self.fuzzyAssertRaisesError(ProgrammerError, "A bitmask with a zero value item makes no sense: ZERO in <enum 'BM'>"):
                types.bitmask_spec(self.pkt, lambda pkt: BM).normalise(self.meta, mock.Mock(name='val'))

        describe "packing into a number":
            before_each:
                self.subject = types.bitmask_spec(self.pkt, self.bitmask, unpacking=False)

            it "adds value if already part of the bitmask":
                v = [self.bitmask.ONE, self.bitmask.THREE]
                final = (1 << 1) + (1 << 3)
                self.assertEqual(self.subject.normalise(self.meta, v), final)

            it "adds value if a matching number":
                v = [self.bitmask.ONE, (1 << 3)]
                final = (1 << 1) + (1 << 3)
                self.assertEqual(self.subject.normalise(self.meta, v), final)

            it "adds value if a repr of the value":
                r = "<Mask.FOUR: 16>"
                self.assertEqual(repr(self.bitmask.FOUR), r)
                v = [self.bitmask.ONE, r]
                final = (1 << 1) + (1 << 4)
                self.assertEqual(self.subject.normalise(self.meta, v), final)

            it "works with the string set()":
                self.assertEqual(self.subject.normalise(self.meta, "set()"), 0)

            it "works with a set as a string":
                self.assertEqual(self.subject.normalise(self.meta, "{<Mask.ONE: 2>, <Mask.TWO: 4>}"), (1 << 1) + (1 << 2))

            it "returns as is if the value is a number":
                self.assertEqual(self.subject.normalise(self.meta, 200), 200)

            it "complains if it can't convert the value":
                for val in ("<Mask.SIX: 64>", "asdf", True, {}, {1:2}, None, lambda: 1):
                    with self.fuzzyAssertRaisesError(BadConversion, "Can't convert value into mask", mask=self.bitmask, got=val):
                        self.subject.normalise(self.meta, val)

            it "converts empty array into 0":
                self.assertEqual(self.subject.normalise(self.meta, []), 0)

            it "returns 0 as 0 or False":
                self.assertEqual(self.subject.normalise(self.meta, 0), 0)
                self.assertEqual(self.subject.normalise(self.meta, False), 0)

            it "works with a set of values":
                v = set([self.bitmask.ONE, 1<<3, "FIVE"])
                self.assertEqual(self.subject.normalise(self.meta, v), (1 << 1) + (1 << 3) + (1 << 5))

            it "only counts values once":
                v = set([self.bitmask.THREE, 1<<3, "THREE"])
                self.assertEqual(self.subject.normalise(self.meta, v), (1 << 3))

        describe "unpacking into a list":
            before_each:
                self.subject = types.bitmask_spec(self.pkt, self.bitmask, unpacking=True)

            it "returns as is if already bitmask items":
                v = [self.bitmask.ONE, "THREE", "<Mask.FOUR: 16>"]
                self.assertEqual(self.subject.normalise(self.meta, v), set([self.bitmask.ONE, self.bitmask.THREE, self.bitmask.FOUR]))

            it "returns what values it can find in the value":
                v = (1 << 1) + (1 << 3) + (1 << 4)
                self.assertEqual(self.subject.normalise(self.meta, v)
                    , set([self.bitmask.ONE, self.bitmask.THREE, self.bitmask.FOUR])
                    )

            it "ignores left over":
                v = (1 << 1) + (1 << 3) + (1 << 4)
                self.assertEqual(self.subject.normalise(self.meta, v + 1)
                    , set([self.bitmask.ONE, self.bitmask.THREE, self.bitmask.FOUR])
                    )

            it "works with the string set()":
                self.assertEqual(self.subject.normalise(self.meta, "set()"), set())

            it "works with a set as a string":
                self.assertEqual(self.subject.normalise(self.meta, "{<Mask.ONE: 2>, <Mask.TWO: 4>}"), set([self.bitmask.ONE, self.bitmask.TWO]))

            it "complains if it finds a value from a different enum":
                class Mask2(Enum):
                    ONE = 1 << 1
                    TWO = 1 << 2

                with self.fuzzyAssertRaisesError(BadConversion, "Can't convert value of wrong Enum", val=Mask2.ONE, wanted=self.bitmask, got=Mask2):
                    self.subject.normalise(self.meta, Mask2.ONE)

            it "complains if it can't find a string value in the mask":
                with self.fuzzyAssertRaisesError(BadConversion, "Can't convert value into value from mask"):
                    self.subject.normalise(self.meta, "SEVEN")

            it "does not complain if it can't find an integer value in the mask":
                self.assertEqual(self.subject.normalise(self.meta, (1 << 24)), set())

describe TestCase, "enum_spec":
    it "takes in some things":
        pkt = mock.Mock(name="pkt")
        em = mock.Mock(name='enum')
        unpacking = mock.Mock(name="unpacking")
        allow_unknown = mock.Mock(name="allow_unknown")

        spec = types.enum_spec(pkt, em, unpacking=unpacking, allow_unknown=allow_unknown)

        self.assertIs(spec.pkt, pkt)
        self.assertIs(spec.enum, em)
        self.assertIs(spec.unpacking, unpacking)
        self.assertIs(spec.allow_unknown, allow_unknown)

    describe "normalisation":
        before_each:
            # And our enum vals
            class Vals(Enum):
                ONE    = 1
                TWO    = 2
                THREE  = 3
                FOUR   = 4
                FIVE   = 5

            self.pkt = mock.Mock(name="pkt")
            self.enum = Vals

            self.meta = Meta.empty()

        it "complains if enum is not an Enum":
            class Kls(object):
                def __init__(self, pkt):
                    pass
                def __call__(self, pkt):
                    return True

            for thing in (0, 1, [], [1], {}, {1:2}, lambda pkt: 1, Kls(1), Kls, None, True, False):
                with self.fuzzyAssertRaisesError(ProgrammerError, "Enum is not an enum!"):
                    types.enum_spec(self.pkt, thing).normalise(self.meta, mock.Mock(name='val'))
                with self.fuzzyAssertRaisesError(ProgrammerError, "Enum is not an enum!"):
                    types.enum_spec(self.pkt, thing, allow_unknown=True).normalise(self.meta, mock.Mock(name='val'))

        describe "packing into a value":
            before_each:
                self.subject = types.enum_spec(self.pkt, self.enum, unpacking=False)
                self.subject_with_unknown = types.enum_spec(self.pkt, self.enum, unpacking=False, allow_unknown=True)

            it "can convert from the name":
                self.assertEqual(self.subject.normalise(self.meta, "ONE"), 1)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, "ONE"), 1)

            it "can convert from repr of the member":
                self.assertEqual(self.subject.normalise(self.meta, "<Vals.ONE: 1>"), 1)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, "<Vals.ONE: 1>"), 1)

            it "can convert from member itself":
                self.assertEqual(self.subject.normalise(self.meta, self.enum.TWO), 2)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, self.enum.TWO), 2)

            it "complains if it's not in the enum":
                ue = types.UnknownEnum(20)
                for val in (0, 200, False, None, [], [1], {}, {1:2}, ue, repr(ue), lambda: 1):
                    with self.fuzzyAssertRaisesError(BadConversion, "Value wasn't a valid enum value"):
                        self.subject.normalise(self.meta, val)
                for val in (False, None, [], [1], {}, {1:2}, lambda: 1):
                    with self.fuzzyAssertRaisesError(BadConversion, "Value wasn't a valid enum value"):
                        self.subject_with_unknown.normalise(self.meta, val)

            it "does not complain if allow_unknown and value not in the enum and valid value":
                ue = types.UnknownEnum(20)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, ue), 20)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, repr(ue)), 20)

                self.assertEqual(self.subject_with_unknown.normalise(self.meta, 40), 40)

            it "complains if we're using the wrong enum":
                class Vals2(Enum):
                    ONE    = 1
                    TWO    = 2
                    THREE  = 3
                    FOUR   = 4
                    FIVE   = 5

                with self.fuzzyAssertRaisesError(BadConversion, "Can't convert value of wrong Enum"):
                    self.subject.normalise(self.meta, Vals2.THREE)
                with self.fuzzyAssertRaisesError(BadConversion, "Can't convert value of wrong Enum"):
                    self.subject_with_unknown.normalise(self.meta, Vals2.THREE)

        describe "unpacking into enum member":
            before_each:
                self.subject = types.enum_spec(self.pkt, self.enum, unpacking=True)
                self.subject_with_unknown = types.enum_spec(self.pkt, self.enum, unpacking=True, allow_unknown=True)

            it "returns as is if already a member":
                self.assertIs(self.subject.normalise(self.meta, self.enum.TWO), self.enum.TWO)
                self.assertIs(self.subject_with_unknown.normalise(self.meta, self.enum.TWO), self.enum.TWO)

            it "complains if from the wrong enum":
                class Vals2(Enum):
                    ONE    = 1
                    TWO    = 2
                    THREE  = 3
                    FOUR   = 4
                    FIVE   = 5

                with self.fuzzyAssertRaisesError(BadConversion, "Can't convert value of wrong Enum"):
                    self.subject.normalise(self.meta, Vals2.THREE)
                with self.fuzzyAssertRaisesError(BadConversion, "Can't convert value of wrong Enum"):
                    self.subject_with_unknown.normalise(self.meta, Vals2.THREE)

            it "converts from name":
                self.assertEqual(self.subject.normalise(self.meta, "THREE"), self.enum.THREE)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, "THREE"), self.enum.THREE)

            it "converts from repr of member":
                self.assertEqual(self.subject.normalise(self.meta, "<Vals.THREE: 3>"), self.enum.THREE)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, "<Vals.THREE: 3>"), self.enum.THREE)

            it "converts from value of member":
                self.assertEqual(self.subject.normalise(self.meta, 4), self.enum.FOUR)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, 4), self.enum.FOUR)

            it "complains if value isn't in enum":
                ue = repr(types.UnknownEnum(20))
                for val in ("SEVEN", 200, ue, False, None, [], [1], {}, {1:2}, lambda: 1):
                    with self.fuzzyAssertRaisesError(BadConversion, "Value is not a valid value of the enum"):
                        self.subject.normalise(self.meta, val)

                for val in ("SEVEN", False, None, [], [1], {}, {1:2}, lambda: 1):
                    with self.fuzzyAssertRaisesError(BadConversion, "Value is not a valid value of the enum"):
                        self.subject_with_unknown.normalise(self.meta, val)

            it "does not complain if allow_unknown and valid unknown value":
                ue = types.UnknownEnum(20)
                self.assertIs(self.subject_with_unknown.normalise(self.meta, ue), ue)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, repr(ue)), ue)
                self.assertEqual(self.subject_with_unknown.normalise(self.meta, 20), ue)

describe TestCase, "overridden":
    it "takes in pkt and default_func":
        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        self.assertIs(spec.default_func, default_func)
        self.assertIs(spec.pkt, pkt)

    it "uses the default_func with pkt regardless of value":
        meta = Meta.empty()
        val = mock.Mock(name="val")

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        ret = mock.Mock(name="ret")
        default_func.return_value = ret

        self.assertIs(spec.normalise(meta, val), ret)

        default_func.assert_called_once_with(pkt)

    it "uses the default_func with pkt even with NotSpecified":
        meta = Meta.empty()
        val = sb.NotSpecified

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = types.overridden(default_func, pkt)

        ret = mock.Mock(name="ret")
        default_func.return_value = ret

        self.assertIs(spec.normalise(meta, val), ret)

        default_func.assert_called_once_with(pkt)

describe TestCase, "defaulted":
    it "takes in spec, pkt and default_func":
        default_func = mock.Mock(name="default_func")
        spec = mock.Mock(name="spec")
        pkt = mock.Mock(name="pkt")
        subject = types.defaulted(spec, default_func, pkt)

        self.assertIs(subject.spec, spec)
        self.assertIs(subject.default_func, default_func)
        self.assertIs(subject.pkt, pkt)

    it "uses the spec with the value if not empty":
        meta = Meta.empty()
        val = mock.Mock(name="val")

        default_func = mock.Mock(name="default_func")
        pkt = mock.Mock(name="pkt")
        spec = mock.Mock(name="spec")
        subject = types.defaulted(spec, default_func, pkt)

        ret = mock.Mock(name="ret")
        spec.normalise.return_value = ret

        self.assertIs(subject.normalise(meta, val), ret)

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

        self.assertIs(subject.normalise(meta, val), normalised)

        default_func.assert_called_once_with(pkt)
        spec.normalise.assert_called_once_with(meta, defaultvalue)

describe TestCase, "boolean":
    it "complains if no value to normalise":
        with self.fuzzyAssertRaisesError(BadSpecValue, "Must specify boolean values"):
            types.boolean().normalise(Meta.empty(), sb.NotSpecified)

    it "returns as is if the value is a boolean":
        self.assertIs(types.boolean().normalise(Meta.empty(), False), False)
        self.assertIs(types.boolean().normalise(Meta.empty(), True), True)

    it "returns as boolean if 0 or 1":
        self.assertIs(types.boolean().normalise(Meta.empty(), 0), False)
        self.assertIs(types.boolean().normalise(Meta.empty(), 1), True)

    it "complains if not boolean, 0 or 1":
        for val in (None, [], [1], {}, {1:2}, "asdf", b"asdf", lambda: 1):
            with self.fuzzyAssertRaisesError(BadSpecValue, "Could not convert value into a boolean", val=val):
                types.boolean().normalise(Meta.empty(), val)

describe TestCase, "boolean_as_int_spec":
    it "complains if no value to normalise":
        with self.fuzzyAssertRaisesError(BadSpecValue, "Must specify boolean values"):
            types.boolean_as_int_spec().normalise(Meta.empty(), sb.NotSpecified)

    it "returns as is if the value is 0 or 1":
        self.assertIs(types.boolean_as_int_spec().normalise(Meta.empty(), 0), 0)
        self.assertIs(types.boolean_as_int_spec().normalise(Meta.empty(), 1), 1)

    it "returns as 0 or 1 if True or False":
        self.assertIs(types.boolean_as_int_spec().normalise(Meta.empty(), False), 0)
        self.assertIs(types.boolean_as_int_spec().normalise(Meta.empty(), True), 1)

    it "complains if not boolean, 0 or 1":
        for val in (None, [], [1], {}, {1:2}, "asdf", b"asdf", lambda: 1):
            with self.fuzzyAssertRaisesError(BadSpecValue, "BoolInts must be True, False, 0 or 1", got=val):
                types.boolean_as_int_spec().normalise(Meta.empty(), val)

describe TestCase, "csv_spec":
    it "takes in pkt, size_bits and unpacking":
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        unpacking = mock.Mock(name="unpacking")
        spec = types.csv_spec(pkt, size_bits, unpacking=unpacking)

        self.assertIs(spec.pkt, pkt)
        self.assertIs(spec.size_bits, size_bits)
        self.assertIs(spec.unpacking, unpacking)

    describe "packing into bitarray":
        before_each:
            self.pkt = mock.Mock(name="pkt")
            self.subject = types.csv_spec(self.pkt, 200 * 8, unpacking=False)

            self.v1 = str(uuid.uuid1())
            self.v2 = str(uuid.uuid1())

            self.meta = Meta.empty()

        it "converts a list into a comma seperated string into bitarray":
            val = [self.v1, self.v2]
            expected_bytes = ",".join(val).encode() + b'\x00'
            self.assertEqual(len(expected_bytes), 74)
            result = self.subject.normalise(self.meta, val).tobytes()

            self.assertEqual(result[:74], expected_bytes)
            self.assertEqual(result[74:], bitarray('0' * (200 - 74) * 8).tobytes())

        it "converts a string into bitarray":
            val = [self.v1, self.v2]
            s = ",".join(val)
            expected_bytes = s.encode() + b'\x00'
            self.assertEqual(len(expected_bytes), 74)

            result = self.subject.normalise(self.meta, s).tobytes()

            self.assertEqual(result[:74], expected_bytes)
            self.assertEqual(result[74:], bitarray('0' * (200 - 74) * 8).tobytes())

        it "converts bytes into bitarray with correct size":
            val = [self.v1, self.v2]
            b = ",".join(val).encode()
            expected_bytes = b + b'\x00'
            self.assertEqual(len(expected_bytes), 74)

            result = self.subject.normalise(self.meta, b).tobytes()

            self.assertEqual(result[:74], expected_bytes)
            self.assertEqual(result[74:], bitarray('0' * (200 - 74) * 8).tobytes())

        it "converts bitarray into bitarray with correct size":
            val = [self.v1, self.v2]
            b = ",".join(val).encode()
            expected_bytes = b + b'\x00'
            self.assertEqual(len(expected_bytes), 74)

            b2 = bitarray(endian="little")
            b2.frombytes(b)
            result = self.subject.normalise(self.meta, b2).tobytes()

            self.assertEqual(result[:74], expected_bytes)
            self.assertEqual(result[74:], bitarray('0' * (200 - 74) * 8).tobytes())

    describe "unpacking into list":
        before_each:
            self.pkt = mock.Mock(name="pkt")
            self.subject = types.csv_spec(self.pkt, 200 * 8, unpacking=True)

            self.v1 = str(uuid.uuid1())
            self.v2 = str(uuid.uuid1())

            self.meta = Meta.empty()

        it "returns list as is if already a list":
            val = [self.v1, self.v2]
            self.assertEqual(self.subject.normalise(self.meta, val), val)

        it "turns bitarray into a list":
            val = [self.v1, self.v2]
            b = ",".join(val).encode() + b'\x00' + bitarray('0' * 100).tobytes()

            b2 = bitarray(endian="little")
            b2.frombytes(b)
            self.assertEqual(self.subject.normalise(self.meta, b2), val)

        it "turns bytes into a list":
            val = [self.v1, self.v2]
            b = ",".join(val).encode() + b'\x00' + bitarray('0' * 100).tobytes()
            self.assertEqual(self.subject.normalise(self.meta, b), val)

        it "turns string into a list":
            val = [self.v1, self.v2]
            s = ",".join(val)
            self.assertEqual(self.subject.normalise(self.meta, s), val)

describe TestCase, "bytes_spec":
    it "takes in pkt and size_bits":
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        spec = types.bytes_spec(pkt, size_bits)
        self.assertIs(spec.pkt, pkt)
        self.assertIs(spec.size_bits, size_bits)

    describe "normalising":
        before_each:
            self.pkt = mock.Mock(name="pkt")
            self.meta = Meta.empty()

        it "works from the repr of sb.NotSpecified":
            expected = bitarray('0' * 8)
            self.assertEqual(types.bytes_spec(self.pkt, 8).normalise(self.meta, repr(sb.NotSpecified)), expected)

            expected = bitarray('0' * 8)
            self.assertEqual(types.bytes_spec(self.pkt, 8).normalise(self.meta, repr(sb.NotSpecified).replace("'", "")), expected)

        it "returns None as the size_bits of bitarray":
            expected = bitarray('0' * 8)
            self.assertEqual(types.bytes_spec(self.pkt, 8).normalise(self.meta, None), expected)

            expected = bitarray('0' * 20)
            self.assertEqual(types.bytes_spec(self.pkt, 20).normalise(self.meta, None), expected)

        it "returns 0 as the size_bits of bitarray":
            expected = bitarray('0' * 8)
            self.assertEqual(types.bytes_spec(self.pkt, 8).normalise(self.meta, 0), expected)

            expected = bitarray('0' * 20)
            self.assertEqual(types.bytes_spec(self.pkt, 20).normalise(self.meta, 0), expected)

        it "expands if not long enough":
            val = bitarray('1' * 8)
            expected = bitarray('1' * 8 + '0' * 12)
            self.assertEqual(types.bytes_spec(self.pkt, 20).normalise(self.meta, val), expected)
            self.assertEqual(types.bytes_spec(self.pkt, 20).normalise(self.meta, val.tobytes()), expected)
            self.assertEqual(types.bytes_spec(self.pkt, 20).normalise(self.meta, binascii.hexlify(val.tobytes()).decode()), expected)

        it "cuts off if too long":
            val = bitarray('1' * 24)
            expected = bitarray('1' * 9)
            self.assertEqual(types.bytes_spec(self.pkt, 9).normalise(self.meta, val), expected)
            self.assertEqual(types.bytes_spec(self.pkt, 9).normalise(self.meta, val.tobytes()), expected)
            self.assertEqual(types.bytes_spec(self.pkt, 9).normalise(self.meta, binascii.hexlify(val.tobytes()).decode()), expected)

        it "returns if just right":
            val = bitarray('1' * 8)
            self.assertEqual(types.bytes_spec(self.pkt, 8).normalise(self.meta, val), val)
            self.assertEqual(types.bytes_spec(self.pkt, 8).normalise(self.meta, val.tobytes()), val)
            self.assertEqual(types.bytes_spec(self.pkt, 8).normalise(self.meta, binascii.hexlify(val.tobytes()).decode()), val)

        it "gets size_bits by calling it with the pkt if it's a callable":
            size_bits = mock.Mock(name="size_bits", return_value=11)

            val = bitarray('1' * 8)
            expected = val + bitarray('0' * 3)

            self.assertEqual(types.bytes_spec(self.pkt, size_bits).normalise(self.meta, val), expected)

            size_bits.assert_called_with(self.pkt)

describe TestCase, "bytes_as_string_spec":
    it "takes in pkt, size_bits and unpacking":
        pkt = mock.Mock(name="pkt")
        size_bits = mock.Mock(name="size_bits")
        unpacking = mock.Mock(name="unpacking")

        spec = types.bytes_as_string_spec(pkt, size_bits, unpacking)

        self.assertIs(spec.pkt, pkt)
        self.assertIs(spec.size_bits, size_bits)
        self.assertIs(spec.unpacking, unpacking)

    describe "unpacking into a string":
        before_each:
            self.pkt = mock.Mock(name="pkt")
            self.meta = Meta.empty()
            self.subject = types.bytes_as_string_spec(self.pkt, 20 * 8, True)

        it "returns as is if already a string":
            val = "stuff"
            self.assertEqual(self.subject.normalise(self.meta, val), val)

        it "cuts from the null byte if bytes":
            val = b"asdfsadf\x00askdlf"
            expected = "asdfsadf"
            self.assertEqual(self.subject.normalise(self.meta, val), expected)

        it "does not cut if no null byte is found":
            val = b"asdfsadfaskdlf"
            self.assertEqual(self.subject.normalise(self.meta, val), val.decode())

    describe "packing into bytes":
        before_each:
            self.pkt = mock.Mock(name="pkt")
            self.meta = Meta.empty()
            self.subject = types.bytes_as_string_spec(self.pkt, 20*8, False)

        it "encodes string into bytes and pads with zeros":
            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray('0' * (20 * 8 - len(b)))

            self.assertEqual(self.subject.normalise(self.meta, s), b)

        it "pads bytes with zeros":
            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray('0' * (20 * 8 - len(b)))

            self.assertEqual(self.subject.normalise(self.meta, s.encode()), b)

        it "gets size_bits by calling it with the pkt if it's a callable":
            size_bits = mock.Mock(name="size_bits", return_value=11 * 8)

            s = "asdf"

            b = bitarray(endian="little")
            b.frombytes(s.encode())
            b += bitarray('0' * (11 * 8 - len(b)))

            self.assertEqual(types.bytes_as_string_spec(self.pkt, size_bits).normalise(self.meta, s), b)

            size_bits.assert_called_with(self.pkt)

describe TestCase, "float_spec":
    before_each:
        self.meta = Meta.empty()
        self.subject = types.float_spec()

    it "complains if it's given a boolean":
        for val in (True, False):
            with self.fuzzyAssertRaisesError(BadSpecValue, "Converting a boolean into a float makes no sense"):
                self.subject.normalise(self.meta, val)

    it "converts value into a float":
        for val, expected in ((0, 0.0), (1, 1.0), (0.0, 0.0), (1.1, 1.1), (72.6666, 72.6666)):
            res = self.subject.normalise(self.meta, val)
            self.assertIs(type(res), float)
            self.assertEqual(res, expected)

    it "complains if it can't convert the value":
        for val in (None, [], [1], {}, {1:2}, lambda: 1):
            with self.fuzzyAssertRaisesError(BadSpecValue, "Failed to convert value into a float"):
                self.subject.normalise(self.meta, val)
