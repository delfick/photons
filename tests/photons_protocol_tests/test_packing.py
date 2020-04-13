# coding: spec

from photons_protocol.packing import val_to_bitarray, BitarraySlice, FieldInfo, PacketPacking
from photons_protocol.types import Type as T, Optional
from photons_protocol.errors import BadConversion
from photons_protocol.packets import dictobj

from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from contextlib import contextmanager
from delfick_project.norms import sb
from bitarray import bitarray
from textwrap import dedent
from unittest import mock
import binascii
import pytest
import struct
import uuid


def ba(thing):
    b = bitarray(endian="little")
    b.frombytes(thing)
    return b


describe "val_to_bitarray":
    it "returns value as is if already bitarray":
        b = bitarray(endian="little")
        b.frombytes(b"asdf")
        assert val_to_bitarray(b, "test") is b

    it "unhexlifies if a str":
        expected = bitarray(endian="little")
        expected.frombytes(binascii.unhexlify("d073d5"))
        assert val_to_bitarray("d073d5", "test") == expected

    it "creates bitarray from bytes":
        expected = bitarray(endian="little")
        bts = binascii.unhexlify("d073d5")
        expected.frombytes(bts)
        assert val_to_bitarray(bts, "test") == expected

    it "creates bitarray from sb.NotSpecified":
        expected = bitarray(endian="little")
        assert val_to_bitarray(sb.NotSpecified, "test") == expected

    it "complains otherwise":
        doing = mock.Mock(name="doing")
        for val in (0, 1, None, True, False, [], [1], {1: 2}, lambda: 1):
            with assertRaises(BadConversion, "Couldn't get bitarray from a value", doing=doing):
                val_to_bitarray(val, doing)

describe "BitarraySlice":

    @pytest.fixture()
    def slce(self):
        name = mock.Mock(name="name")
        typ = mock.Mock(name="typ")
        val = mock.Mock(name="val")
        size_bits = mock.Mock(name="size_bits")
        group = mock.Mock(name="group")
        return BitarraySlice(name, typ, val, size_bits, group)

    it "takes in things":
        name = mock.Mock(name="name")
        typ = mock.Mock(name="typ")
        val = mock.Mock(name="val")
        size_bits = mock.Mock(name="size_bits")
        group = mock.Mock(name="group")

        slce = BitarraySlice(name, typ, val, size_bits, group)

        assert slce.name is name
        assert slce.typ is typ
        assert slce.val is val
        assert slce.size_bits is size_bits
        assert slce.group is group

    it "gets fmt from typ.struct_format", slce:
        fmt = str(uuid.uuid1())
        slce.typ.struct_format = fmt
        assert slce.fmt is fmt

    describe "unpackd":
        it "returns as is if fmt is None", slce:
            bts = b"wat"
            val = bitarray(endian="little")
            val.frombytes(bts)

            slce.val = val
            slce.typ.struct_format = None

            assert slce.unpackd == val

        it "returns as boolean value if fmt is bool and size_bits is 1", slce:
            slce.typ.struct_format = bool
            slce.size_bits = 1

            slce.val = bitarray("0")
            assert slce.unpackd is False

            slce.val = bitarray("1")
            assert slce.unpackd is True

        it "pads left if original_size is greater than actual val and we have left_cut", slce:
            slce.typ = T.Int8.S(6, left=True)
            slce.val = bitarray("000010", endian="little")

            use = bitarray("00000010", endian="little").tobytes()
            not_use = bitarray("00001000", endian="little").tobytes()

            assert struct.unpack("<b", use)[0] == 64
            assert struct.unpack("<b", not_use)[0] == 16

            assert slce.unpackd == 64

        it "pads right if original_size is greater than actual val and we don't have left_cut", slce:
            slce.typ = T.Int8.S(6)
            slce.val = bitarray("000010", endian="little")

            use = bitarray("00001000", endian="little").tobytes()
            not_use = bitarray("00000010", endian="little").tobytes()

            assert struct.unpack("<b", use)[0] == 16
            assert struct.unpack("<b", not_use)[0] == 64

            assert slce.unpackd == 16

        it "raises BadConversion if it can't unpack the field", slce:
            slce.typ = T.Int8
            slce.val = bitarray("000010111", endian="little")

            with assertRaises(
                BadConversion,
                "Failed to unpack field",
                group=slce.group,
                field=slce.name,
                typ=T.Int8,
            ):
                slce.unpackd

describe "FieldInfo":

    @pytest.fixture()
    def val(self):
        return mock.Mock(name="val")

    @pytest.fixture()
    def info(self, val):
        name = mock.Mock(name="name")
        typ = mock.Mock(name="typ")
        size_bits = mock.Mock(name="size_bits")
        group = mock.Mock(name="group")
        return FieldInfo(name, typ, val, size_bits, group)

    it "takes in things":
        name = mock.Mock(name="name")
        typ = mock.Mock(name="typ")
        val = mock.Mock(name="val")
        size_bits = mock.Mock(name="size_bits")
        group = mock.Mock(name="group")

        info = FieldInfo(name, typ, val, size_bits, group)

        assert info.name is name
        assert info.typ is typ
        assert info.val is val
        assert info.size_bits is size_bits
        assert info.group is group

    describe "value":
        it "returns value as is", info, val:
            assert info.value is val

        it "returns value as 0 bits if our typ is Reserved and val is NotSpecified", info:
            info.typ = T.Reserved(8)
            info.size_bits = 8
            info.val = sb.NotSpecified
            assert info.value == bitarray("0" * 8)

        it "returns value as is if typ is Reserved but value is not NotSpecified", info, val:
            info.typ = T.Reserved(8)
            assert info.value == val

    describe "to_sized_bitarray":
        it "removes from the right if no left_cut", info:
            info.typ.left_cut = False
            info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray("110000", endian="little")

            with mock.patch.object(info, "to_bitarray", to_bitarray):
                assert info.to_sized_bitarray() == bitarray("110")

            to_bitarray.assert_called_once_with()

        it "removes from the left if left_cut", info:
            info.typ.left_cut = True
            info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray("110001", endian="little")

            with mock.patch.object(info, "to_bitarray", to_bitarray):
                assert info.to_sized_bitarray() == bitarray("001")

            to_bitarray.assert_called_once_with()

        it "does nothing if too small", info:
            info.typ.left_cut = True
            info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray("1", endian="little")

            with mock.patch.object(info, "to_bitarray", to_bitarray):
                assert info.to_sized_bitarray() == bitarray("1")

            to_bitarray.assert_called_once_with()

        it "does nothing if correct size", info:
            info.typ.left_cut = True
            info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray("101", endian="little")

            with mock.patch.object(info, "to_bitarray", to_bitarray):
                assert info.to_sized_bitarray() == bitarray("101")

            to_bitarray.assert_called_once_with()

    describe "to_bitarray":

        @contextmanager
        def a_val(self, val):
            with mock.patch.object(FieldInfo, "value", val):
                yield

        it "complains if the value is NotSpecified", info:
            with assertRaises(
                BadConversion,
                "Cannot pack an unspecified value",
                got=sb.NotSpecified,
                field=info.name,
                group=info.group,
                typ=info.typ,
            ):
                with self.a_val(sb.NotSpecified):
                    info.to_bitarray()

        it "returns as is if it's a bitarray", info:
            val = bitarray("01")
            with self.a_val(val):
                assert info.to_bitarray() is val

        it "uses struct_format if the fmt is a string", info:
            val = bitarray("01").tobytes()
            res = mock.Mock(name="res")

            info.typ.struct_format = "<b"
            struct_format = mock.Mock(name="struct_format", return_value=res)

            with self.a_val(val):
                with mock.patch.object(info, "struct_format", struct_format):
                    assert info.to_bitarray() is res

            struct_format.assert_called_once_with("<b", val)

        it "complains if fmt is bool but value is not", info:
            for val in (0, 1, None, "", "adsf", b"asf", [], [1], {1: 2}, lambda: 1):
                with assertRaises(BadConversion, "Trying to convert a non boolean into 1 bit"):
                    info.typ.struct_format = bool
                    info.val = val
                    info.to_bitarray()

        it "converts True/False into a single bit if fmt is bool", info:
            info.typ.struct_format = bool
            info.val = True
            assert info.to_bitarray() == bitarray("1")

            info.val = False
            assert info.to_bitarray() == bitarray("0")

        it "creates bitarray from the bytes otherwise", info:
            info.typ.struct_format = None
            info.val = b"wat"

            expected = bitarray(endian="little")
            expected.frombytes(b"wat")

            assert info.to_bitarray() == expected

    describe "struct_format":
        it "creates bitarray from unpacking", info:
            fmt = mock.Mock(name="fmt")
            val = mock.Mock(name="val")
            bts = str(uuid.uuid1()).encode()

            expected = bitarray(endian="little")
            expected.frombytes(bts)

            struct = mock.Mock(name="struct")
            struct.pack.return_value = bts

            with mock.patch("photons_protocol.packing.struct", struct):
                assert info.struct_format(fmt, val) == expected

            struct.pack.assert_called_once_with(fmt, val)

        it "works", info:
            info.typ = T.Int16

            expected = bitarray(endian="little")
            expected.frombytes(struct.pack("<h", 200))

            assert info.struct_format(info.typ.struct_format, 200) == expected

        it "complains if can't pack", info:
            info.typ = T.Int8

            with assertRaises(
                BadConversion,
                "Failed trying to convert a value",
                val=9000,
                fmt="<b",
                group=info.group,
                name=info.name,
            ):
                info.struct_format(info.typ.struct_format, 9000)

        it "understands the Optional value", info:
            b = bitarray(endian="little")
            b.frombytes(struct.pack("<H", 0))
            assert info.struct_format("<H", Optional) == b

describe "PacketPacking":

    @pytest.fixture()
    def V(self):
        class V:
            other_typ = T.Int16.transform(lambda _, v: v + 5, lambda _, v: v - 5)

            two_typ = T.String(20 * 8).allow_callable()

            thing_typ = T.Reserved(lambda p: p.other * 8)

            @hp.memoized_property
            def G1(s):
                class G1(dictobj.PacketSpec):
                    fields = [("other", s.other_typ), ("thing", s.thing_typ)]

                return G1

            @hp.memoized_property
            def P(s):
                class P(dictobj.PacketSpec):
                    fields = [("one", T.Bool), ("two", s.two_typ), ("g1", s.G1)]

                return P

        return V()

    describe "fields_in":
        it "yields FieldInfo objects", V:

            def cb(pkt, serial):
                return "{0}.cb".format(serial)

            p = V.P(one=True, two=cb, other=1)

            two_val = bitarray(endian="little")
            two_val.frombytes(b"d073d5.cb")
            two_val += bitarray("0" * (20 * 8 - len(two_val)))

            fields = list(PacketPacking.fields_in(p, None, "d073d5"))
            assert fields == [
                FieldInfo("one", T.Bool, True, 1, "P"),
                FieldInfo("two", V.two_typ, two_val, 20 * 8, "P"),
                FieldInfo("other", V.other_typ, 6, 16, "g1"),
                FieldInfo("thing", V.thing_typ, sb.NotSpecified, 8, "g1"),
            ]

    describe "pkt_from_bitarray":
        it "creates a pkt field by field", V:

            def cb(pkt, serial):
                return "{0}.cb2".format(serial)

            p = V.P(one=True, two=cb, other=1)
            packd = p.pack(serial="d073d5")
            expected = bitarray(
                dedent(
                    """
                   100100110000011001110110011001100001001101010110001110100110001100100011001001100
                   000000000000000000000000000000000000000000000000000000000000000000000000000000000
                   11000000000000000000000
                """
                )
                .replace("\n", "")
                .strip()
            )

            assert packd == expected

            called = []
            original__setitem__ = dictobj.__setitem__

            def do_set(f, name, val):
                if type(f) is V.P:
                    called.append((name, val))
                original__setitem__(f, name, val)

            __setitem__ = mock.Mock(name="__setitem__", side_effect=do_set)

            with mock.patch.object(dictobj, "__setitem__", __setitem__):
                with mock.patch.object(BitarraySlice, "__setitem__", original__setitem__):
                    final, i = PacketPacking.pkt_from_bitarray(V.P, packd)

            assert sorted(final.actual_items()) == (
                sorted(
                    [
                        ("one", True),
                        ("two", ba(b"d073d5.cb2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")),
                        ("other", 6),
                        ("thing", ba(b"\x00")),
                    ]
                )
            )

            assert called == [
                ("one", sb.NotSpecified),
                ("two", sb.NotSpecified),
                ("other", sb.NotSpecified),
                ("thing", sb.NotSpecified),
                ("one", True),
                ("two", ba(b"d073d5.cb2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")),
                ("other", 6),
                ("thing", ba(b"\x00")),
            ]

            assert i == len(packd)

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
            assert i == 16
            assert made.one == 16
            assert made.payload == sb.NotSpecified

            assert packd[i:].tobytes() == v

    describe "pack":
        it "gets fields from fields_in and joins the bitarrays to form a final bitarray":
            b1 = bitarray("01", endian="little")
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
                assert PacketPacking.pack(pkt, parent=parent, serial=serial) == bitarray(
                    "01111010", endian="little"
                )

            fields_in.assert_called_once_with(pkt, parent, serial)

        it "attaches provided payload to the end":
            b1 = bitarray("01", endian="little")
            b2 = bitarray("111", endian="little")
            b3 = bitarray("010", endian="little")

            info1 = mock.Mock(name="info1")
            info2 = mock.Mock(name="info2")
            info3 = mock.Mock(name="info3")

            info1.to_sized_bitarray.return_value = b1
            info2.to_sized_bitarray.return_value = b2
            info3.to_sized_bitarray.return_value = b3

            fields_in = mock.Mock(name="fields_in", return_value=[info1, info2, info3])

            payload = bitarray("01010101", endian="little")

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
                assert PacketPacking.pack(
                    pkt, payload=payload, parent=parent, serial=serial
                ) == bitarray("0111101001010101", endian="little")

            fields_in.assert_called_once_with(pkt, parent, serial)

        it "uses payload from the pkt if none is provided":
            b1 = bitarray("01", endian="little")
            b2 = bitarray("111", endian="little")
            b3 = bitarray("010", endian="little")

            info1 = mock.Mock(name="info1")
            info2 = mock.Mock(name="info2")
            info3 = mock.Mock(name="info3")

            info1.to_sized_bitarray.return_value = b1
            info2.to_sized_bitarray.return_value = b2
            info3.to_sized_bitarray.return_value = b3

            fields_in = mock.Mock(name="fields_in", return_value=[info1, info2, info3])

            payload = bitarray("01010101", endian="little")

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
                assert PacketPacking.pack(pkt, parent=parent, serial=serial) == bitarray(
                    "0111101001010101", endian="little"
                )

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
            assert PacketPacking.pack(pkt) == bitarray("00010000", endian="little")

            payload = bitarray("010101", endian="little")
            assert PacketPacking.pack(pkt, payload=payload) == bitarray("00010000", endian="little")

        it "complains if we have a field with no value":
            b1 = bitarray("01", endian="little")
            b2 = None

            info1 = mock.Mock(name="info1")
            info2 = mock.Mock(name="info2")

            info1.to_sized_bitarray.return_value = b1
            info2.to_sized_bitarray.return_value = b2

            fields_in = mock.Mock(name="fields_in", return_value=[info1, info2])

            pkt = mock.Mock(name="pkt", spec=[])
            parent = mock.Mock(name="parent")
            serial = mock.Mock(name="serial")
            with assertRaises(BadConversion, "Failed to convert field into a bitarray"):
                with mock.patch.object(PacketPacking, "fields_in", fields_in):
                    assert PacketPacking.pack(pkt, parent=parent, serial=serial) == bitarray(
                        "01111010", endian="little"
                    )

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
                assert PacketPacking.unpack(pkt_kls, val) == final

            with mock.patch.object(PacketPacking, "pkt_from_bitarray", pkt_from_bitarray):
                assert PacketPacking.unpack(pkt_kls, binascii.unhexlify(val)) == final

            with mock.patch.object(PacketPacking, "pkt_from_bitarray", pkt_from_bitarray):
                assert PacketPacking.unpack(pkt_kls, expected) == final

            assert pkt_from_bitarray.mock_calls == [
                mock.call(pkt_kls, expected),
                mock.call(pkt_kls, expected),
                mock.call(pkt_kls, expected),
            ]

        it "assigns the remainder if we have a payload with message_type 0":

            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("one", T.Int8), ("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            val = bitarray("0000000101010101", endian="little")
            expected = bitarray("01010101", endian="little")

            f = PacketPacking.unpack(P, val)
            assert f.__getitem__("payload", allow_bitarray=True) == expected
            assert f.one == -128
