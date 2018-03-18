# coding: spec

from photons_protocol.packing import val_to_bitarray, BitarraySlice, FieldInfo, PacketPacking
from photons_protocol.errors import BadConversion
from photons_protocol.packets import dictobj
from photons_protocol.types import Type as T

from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
from contextlib import contextmanager
from bitarray import bitarray
from textwrap import dedent
import binascii
import struct
import uuid
import mock

describe TestCase, "val_to_bitarray":
    it "returns value as is if already bitarray":
        b = bitarray(endian="little")
        b.frombytes(b"asdf")
        self.assertIs(val_to_bitarray(b, "test"), b)

    it "unhexlifies if a str":
        expected = bitarray(endian="little")
        expected.frombytes(binascii.unhexlify("d073d5"))
        self.assertEqual(val_to_bitarray("d073d5", "test"), expected)

    it "creates bitarray from bytes":
        expected = bitarray(endian="little")
        bts = binascii.unhexlify("d073d5")
        expected.frombytes(bts)
        self.assertEqual(val_to_bitarray(bts, "test"), expected)

    it "complains otherwise":
        doing = mock.Mock(name="doing")
        for val in (0, 1, None, True, False, [], [1], {1: 2}, lambda: 1, sb.NotSpecified):
            with self.fuzzyAssertRaisesError(BadConversion, "Couldn't get bitarray from a value", doing=doing):
                val_to_bitarray(val, doing)

describe TestCase, "BitarraySlice":
    before_each:
        self.name = mock.Mock(name="name")
        self.typ = mock.Mock(name='typ')
        self.val = mock.Mock(name="val")
        self.size_bits = mock.Mock(name="size_bits")
        self.group = mock.Mock(name="group")
        self.slce = BitarraySlice(self.name, self.typ, self.val, self.size_bits, self.group)

    it "takes in things":
        slce = BitarraySlice(self.name, self.typ, self.val, self.size_bits, self.group)

        self.assertIs(slce.name, self.name)
        self.assertIs(slce.typ, self.typ)
        self.assertIs(slce.val, self.val)
        self.assertIs(slce.size_bits, self.size_bits)
        self.assertIs(slce.group, self.group)

    it "gets fmt from typ.struct_format":
        fmt = str(uuid.uuid1())
        self.typ.struct_format = fmt
        self.assertIs(self.slce.fmt, fmt)

    describe "unpackd":
        it "returns as bytes if fmt is None":
            bts = b"wat"
            val = bitarray(endian="little")
            val.frombytes(bts)

            self.slce.val = val
            self.slce.typ.struct_format = None

            self.assertEqual(self.slce.unpackd, bts)

        it "returns as boolean value if fmt is bool and size_bits is 1":
            self.slce.typ.struct_format = bool
            self.slce.size_bits = 1

            self.slce.val = bitarray('0')
            self.assertEqual(self.slce.unpackd, False)

            self.slce.val = bitarray('1')
            self.assertEqual(self.slce.unpackd, True)

        it "pads left if original_size is greater than actual val and we have left_cut":
            self.slce.typ = T.Int8.S(6, left=True)
            self.slce.val = bitarray("000010", endian="little")

            use = bitarray("00000010", endian="little").tobytes()
            not_use = bitarray("00001000", endian="little").tobytes()

            self.assertEqual(struct.unpack("<b", use)[0], 64)
            self.assertEqual(struct.unpack("<b", not_use)[0], 16)

            self.assertEqual(self.slce.unpackd, 64)

        it "pads right if original_size is greater than actual val and we don't have left_cut":
            self.slce.typ = T.Int8.S(6)
            self.slce.val = bitarray("000010", endian="little")

            use = bitarray("00001000", endian="little").tobytes()
            not_use = bitarray("00000010", endian="little").tobytes()

            self.assertEqual(struct.unpack("<b", use)[0], 16)
            self.assertEqual(struct.unpack("<b", not_use)[0], 64)

            self.assertEqual(self.slce.unpackd, 16)

        it "raises BadConversion if it can't unpack the field":
            self.slce.typ = T.Int8
            self.slce.val = bitarray("000010111", endian="little")

            with self.fuzzyAssertRaisesError(BadConversion, "Failed to unpack field", group=self.group, field=self.name, typ=T.Int8):
                self.slce.unpackd

describe TestCase, "FieldInfo":
    before_each:
        self.name = mock.Mock(name="name")
        self.typ = mock.Mock(name='typ')
        self.val = mock.Mock(name="val")
        self.size_bits = mock.Mock(name="size_bits")
        self.group = mock.Mock(name="group")
        self.info = FieldInfo(self.name, self.typ, self.val, self.size_bits, self.group)

    it "takes in things":
        info = FieldInfo(self.name, self.typ, self.val, self.size_bits, self.group)

        self.assertIs(info.name, self.name)
        self.assertIs(info.typ, self.typ)
        self.assertIs(info.val, self.val)
        self.assertIs(info.size_bits, self.size_bits)
        self.assertIs(info.group, self.group)

    describe "value":
        it "returns value as is":
            self.assertIs(self.info.value, self.val)

        it "returns value as 0 bits if our typ is Reserved and val is NotSpecified":
            self.info.typ = T.Reserved(8)
            self.info.size_bits = 8
            self.info.val = sb.NotSpecified
            self.assertEqual(self.info.value, bitarray('0' * 8))

        it "returns value as is if typ is Reserved but value is not NotSpecified":
            self.info.typ = T.Reserved(8)
            self.assertEqual(self.info.value, self.val)

    describe "to_sized_bitarray":
        it "removes from the right if no left_cut":
            self.typ.left_cut = False
            self.info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray('110000', endian="little")

            with mock.patch.object(self.info, "to_bitarray", to_bitarray):
                self.assertEqual(self.info.to_sized_bitarray(), bitarray("110"))

            to_bitarray.assert_called_once_with()

        it "removes from the left if left_cut":
            self.typ.left_cut = True
            self.info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray('110001', endian="little")

            with mock.patch.object(self.info, "to_bitarray", to_bitarray):
                self.assertEqual(self.info.to_sized_bitarray(), bitarray("001"))

            to_bitarray.assert_called_once_with()

        it "does nothing if too small":
            self.typ.left_cut = True
            self.info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray('1', endian="little")

            with mock.patch.object(self.info, "to_bitarray", to_bitarray):
                self.assertEqual(self.info.to_sized_bitarray(), bitarray("1"))

            to_bitarray.assert_called_once_with()

        it "does nothing if correct size":
            self.typ.left_cut = True
            self.info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray('101', endian="little")

            with mock.patch.object(self.info, "to_bitarray", to_bitarray):
                self.assertEqual(self.info.to_sized_bitarray(), bitarray("101"))

            to_bitarray.assert_called_once_with()

    describe "to_bitarray":
        @contextmanager
        def a_val(self, val):
            with mock.patch.object(FieldInfo, "value", val):
                yield

        it "complains if the value is NotSpecified":
            with self.fuzzyAssertRaisesError(BadConversion
                , "Cannot pack an unspecified value", got=sb.NotSpecified, field=self.name, group=self.group, typ=self.typ
                ):
                with self.a_val(sb.NotSpecified):
                    self.info.to_bitarray()

        it "returns as is if it's a bitarray":
            val = bitarray('01')
            with self.a_val(val):
                self.assertIs(self.info.to_bitarray(), val)

        it "uses struct_format if the fmt is a string":
            val = bitarray('01').tobytes()
            res = mock.Mock(name="res")

            self.typ.struct_format = "<b"
            struct_format = mock.Mock(name="struct_format", return_value=res)

            with self.a_val(val):
                with mock.patch.object(self.info, "struct_format", struct_format):
                    self.assertIs(self.info.to_bitarray(), res)

            struct_format.assert_called_once_with("<b", val)

        it "complains if fmt is bool but value is not":
            for val in (0, 1, None, "", "adsf", b"asf", [], [1], {1: 2}, lambda: 1):
                with self.fuzzyAssertRaisesError(BadConversion, "Trying to convert a non boolean into 1 bit"):
                    self.info.typ.struct_format = bool
                    self.info.val = val
                    self.info.to_bitarray()

        it "converts True/False into a single bit if fmt is bool":
            self.info.typ.struct_format = bool
            self.info.val = True
            self.assertEqual(self.info.to_bitarray(), bitarray('1'))

            self.info.val = False
            self.assertEqual(self.info.to_bitarray(), bitarray('0'))

        it "creates bitarray from the bytes otherwise":
            self.info.typ.struct_format = None
            self.info.val = b"wat"

            expected = bitarray(endian="little")
            expected.frombytes(b"wat")

            self.assertEqual(self.info.to_bitarray(), expected)

    describe "struct_format":
        it "creates bitarray from unpacking":
            fmt = mock.Mock(name="fmt")
            val = mock.Mock(name="val")
            bts = str(uuid.uuid1()).encode()

            expected = bitarray(endian="little")
            expected.frombytes(bts)

            struct = mock.Mock(name="struct")
            struct.pack.return_value = bts

            with mock.patch("photons_protocol.packing.struct", struct):
                self.assertEqual(self.info.struct_format(fmt, val), expected)

            struct.pack.assert_called_once_with(fmt, val)

        it "works":
            self.info.typ = T.Int16

            expected = bitarray(endian="little")
            expected.frombytes(struct.pack("<h", 200))

            self.assertEqual(self.info.struct_format(self.info.typ.struct_format, 200), expected)

        it "complains if can't pack":
            self.info.typ = T.Int8

            with self.fuzzyAssertRaisesError(BadConversion, "Failed trying to convert a value", val=9000, fmt="<b", group=self.group, name=self.name):
                self.info.struct_format(self.info.typ.struct_format, 9000)

describe TestCase, "PacketPacking":
    before_each:
        self.other_typ = T.Int16.transform(
              lambda _, v: v + 5
            , lambda v: v - 5
            )

        self.two_typ = T.String(20 * 8).allow_callable()

        self.thing_typ = T.Reserved(lambda p: p.other * 8)

        class G1(dictobj.PacketSpec):
            fields = [
                  ("other", self.other_typ)
                , ("thing", self.thing_typ)
                ]

        class P(dictobj.PacketSpec):
            fields = [
                  ("one", T.Bool)
                , ("two", self.two_typ)
                , ("g1", G1)
                ]

        self.G1 = G1
        self.P = P

    describe "fields_in":
        it "yields FieldInfo objects":
            def cb(pkt, serial):
                return "{0}.cb".format(serial)

            p = self.P(one=True, two=cb, other=1)

            two_val = bitarray(endian="little")
            two_val.frombytes(b"d073d5.cb")
            two_val += bitarray('0' * (20 * 8 - len(two_val)))

            fields = list(PacketPacking.fields_in(p, None, "d073d5"))
            self.assertEqual(fields
                , [ FieldInfo("one", T.Bool, True, 1, "P")
                  , FieldInfo("two", self.two_typ, two_val, 20 * 8, "P")
                  , FieldInfo("other", self.other_typ, 6, 16, "g1")
                  , FieldInfo("thing", self.thing_typ, sb.NotSpecified, 8, "g1")
                  ]
                )

    describe "pkt_from_bitarray":
        it "creates a pkt field by field":
            def cb(pkt, serial):
                return "{0}.cb2".format(serial)

            p = self.P(one=True, two=cb, other=1)
            packd = p.pack(serial="d073d5")
            expected = bitarray(dedent('''
                   100100110000011001110110011001100001001101010110001110100110001100100011001001100
                   000000000000000000000000000000000000000000000000000000000000000000000000000000000
                   11000000000000000000000
                ''').replace('\n', '').strip())

            self.assertEqual(packd, expected)

            called = []
            original__setitem__ = dictobj.__setitem__

            def do_set(f, name, val):
                if type(f) is self.P:
                    called.append((name, val))
                original__setitem__(f, name, val)

            __setitem__ = mock.Mock(name="__setitem__", side_effect=do_set)

            with mock.patch.object(dictobj, "__setitem__", __setitem__):
                with mock.patch.object(BitarraySlice, "__setitem__", original__setitem__):
                    final, i = PacketPacking.pkt_from_bitarray(self.P, packd)

            self.assertEqual(sorted(final.items())
                , sorted(
                      [ ('one', True)
                      , ('two', b'd073d5.cb2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
                      , ('other', 6)
                      , ('thing', b'\x00')
                      ]
                    )
                )

            self.assertEqual(called
                , [ ("one", sb.NotSpecified)
                  , ("two", sb.NotSpecified)
                  , ("other", sb.NotSpecified)
                  , ("thing", sb.NotSpecified)
                  , ("one", True)
                  , ("two", b'd073d5.cb2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
                  , ("other", 6)
                  , ("thing", b"\x00")
                  ]
                )

            self.assertEqual(i, len(packd))

        it "returns where we are in the bitarray which is helpful when we have an empty payload":
            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("one", T.Int16), ("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            v = str(uuid.uuid1()).encode()
            p = P(one=16, payload=v)
            packd = p.pack()

            made, i = PacketPacking.pkt_from_bitarray(P, packd)
            self.assertEqual(i, 16)
            self.assertEqual(made.one, 16)
            self.assertEqual(made.payload, sb.NotSpecified)

            self.assertEqual(packd[i:].tobytes(), v)

    describe "pack":
        it "gets fields from fields_in and joins the bitarrays to form a final bitarray":
            b1 = bitarray('01', endian="little")
            b2 = bitarray("111", endian="little")
            b3 = bitarray("010", endian="little")

            info1 = mock.Mock(name="info1")
            info2 = mock.Mock(name="info2")
            info3 = mock.Mock(name="info3")

            info1.to_sized_bitarray.return_value = b1
            info2.to_sized_bitarray.return_value = b2
            info3.to_sized_bitarray.return_value = b3

            fields_in = mock.Mock(name="fields_in", return_value=[info1, info2, info3])

            pkt = mock.Mock(name="pkt", spec=[])
            parent = mock.Mock(name="parent")
            serial = mock.Mock(name="serial")
            with mock.patch.object(PacketPacking, "fields_in", fields_in):
                self.assertEqual(PacketPacking.pack(pkt, parent=parent, serial=serial), bitarray('01111010', endian="little"))

            fields_in.assert_called_once_with(pkt, parent, serial)

        it "attaches provided payload to the end":
            b1 = bitarray('01', endian="little")
            b2 = bitarray("111", endian="little")
            b3 = bitarray("010", endian="little")

            info1 = mock.Mock(name="info1")
            info2 = mock.Mock(name="info2")
            info3 = mock.Mock(name="info3")

            info1.to_sized_bitarray.return_value = b1
            info2.to_sized_bitarray.return_value = b2
            info3.to_sized_bitarray.return_value = b3

            fields_in = mock.Mock(name="fields_in", return_value=[info1, info2, info3])

            payload = bitarray('01010101', endian="little")

            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            pkt = P()
            parent = mock.Mock(name="parent")
            serial = mock.Mock(name="serial")
            with mock.patch.object(PacketPacking, "fields_in", fields_in):
                self.assertEqual(PacketPacking.pack(pkt, payload=payload, parent=parent, serial=serial), bitarray('0111101001010101', endian="little"))

            fields_in.assert_called_once_with(pkt, parent, serial)

        it "uses payload from the pkt if none is provided":
            b1 = bitarray('01', endian="little")
            b2 = bitarray("111", endian="little")
            b3 = bitarray("010", endian="little")

            info1 = mock.Mock(name="info1")
            info2 = mock.Mock(name="info2")
            info3 = mock.Mock(name="info3")

            info1.to_sized_bitarray.return_value = b1
            info2.to_sized_bitarray.return_value = b2
            info3.to_sized_bitarray.return_value = b3

            fields_in = mock.Mock(name="fields_in", return_value=[info1, info2, info3])

            payload = bitarray('01010101', endian="little")

            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            pkt = P(payload=payload)
            parent = mock.Mock(name="parent")
            serial = mock.Mock(name="serial")
            with mock.patch.object(PacketPacking, "fields_in", fields_in):
                self.assertEqual(PacketPacking.pack(pkt, parent=parent, serial=serial), bitarray('0111101001010101', endian="little"))

            fields_in.assert_called_once_with(pkt, parent, serial)

        it "does not set payload if we aren't a parent packet":
            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            class Child(P):
                parent_packet = False

                class Payload(dictobj.PacketSpec):
                    message_type = 2
                    fields = [("one", T.Int8)]

            pkt = Child(one=8)
            self.assertEqual(PacketPacking.pack(pkt), bitarray('00010000', endian="little"))

            payload = bitarray('010101', endian="little")
            self.assertEqual(PacketPacking.pack(pkt, payload=payload), bitarray('00010000', endian="little"))

        it "complains if we have a field with no value":
            b1 = bitarray('01', endian="little")
            b2 = None

            info1 = mock.Mock(name="info1")
            info2 = mock.Mock(name="info2")

            info1.to_sized_bitarray.return_value = b1
            info2.to_sized_bitarray.return_value = b2

            fields_in = mock.Mock(name="fields_in", return_value=[info1, info2])

            pkt = mock.Mock(name="pkt", spec=[])
            parent = mock.Mock(name="parent")
            serial = mock.Mock(name="serial")
            with self.fuzzyAssertRaisesError(BadConversion, "Failed to convert field into a bitarray"):
                with mock.patch.object(PacketPacking, "fields_in", fields_in):
                    self.assertEqual(PacketPacking.pack(pkt, parent=parent, serial=serial), bitarray('01111010', endian="little"))

            fields_in.assert_called_once_with(pkt, parent, serial)

    describe "unpack":
        it "uses pkt_from_bitarray":
            final = mock.Mock(name="final")
            pkt_kls = mock.Mock(name="pkt_kls", spec=[])

            val = "d073d5"
            expected = bitarray(endian="little")
            expected.frombytes(binascii.unhexlify(val))

            pkt_from_bitarray = mock.Mock(name="pkt_from_bitarray")
            pkt_from_bitarray.return_value = (final, len(expected))

            with mock.patch.object(PacketPacking, "pkt_from_bitarray", pkt_from_bitarray):
                self.assertEqual(PacketPacking.unpack(pkt_kls, val), final)

            with mock.patch.object(PacketPacking, "pkt_from_bitarray", pkt_from_bitarray):
                self.assertEqual(PacketPacking.unpack(pkt_kls, binascii.unhexlify(val)), final)

            with mock.patch.object(PacketPacking, "pkt_from_bitarray", pkt_from_bitarray):
                self.assertEqual(PacketPacking.unpack(pkt_kls, expected), final)

            self.assertEqual(pkt_from_bitarray.mock_calls
                , [ mock.call(pkt_kls, expected)
                  , mock.call(pkt_kls, expected)
                  , mock.call(pkt_kls, expected)
                  ]
                )

        it "assigns the remainder if we have a payload with message_type 0":
            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("one", T.Int8), ("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            val = bitarray('0000000101010101', endian="little")
            expected = bitarray('01010101', endian="little")

            f = PacketPacking.unpack(P, val)
            self.assertEqual(f.__getitem__("payload", allow_bitarray=True), expected)
            self.assertEqual(f.one, -128)
