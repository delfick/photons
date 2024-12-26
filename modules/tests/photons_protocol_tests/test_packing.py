import binascii
import struct
import uuid
from contextlib import contextmanager
from textwrap import dedent
from unittest import mock

import pytest
from bitarray import bitarray
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from photons_app import helpers as hp
from photons_protocol.errors import BadConversion
from photons_protocol.packets import dictobj
from photons_protocol.packing import (
    BitarraySlice,
    FieldInfo,
    PacketPacking,
    val_to_bitarray,
)
from photons_protocol.types import Optional
from photons_protocol.types import Type as T


def ba(thing):
    b = bitarray(endian="little")
    b.frombytes(thing)
    return b


class TestValToBitarray:
    def test_it_returns_value_as_is_if_already_bitarray(self):
        b = bitarray(endian="little")
        b.frombytes(b"asdf")
        assert val_to_bitarray(b, "test") is b

    def test_it_unhexlifies_if_a_str(self):
        expected = bitarray(endian="little")
        expected.frombytes(binascii.unhexlify("d073d5"))
        assert val_to_bitarray("d073d5", "test") == expected

    def test_it_creates_bitarray_from_bytes(self):
        expected = bitarray(endian="little")
        bts = binascii.unhexlify("d073d5")
        expected.frombytes(bts)
        assert val_to_bitarray(bts, "test") == expected

    def test_it_creates_bitarray_from_sbNotSpecified(self):
        expected = bitarray(endian="little")
        assert val_to_bitarray(sb.NotSpecified, "test") == expected

    def test_it_complains_otherwise(self):
        doing = mock.Mock(name="doing")
        for val in (0, 1, None, True, False, [], [1], {1: 2}, lambda: 1):
            with assertRaises(BadConversion, "Couldn't get bitarray from a value", doing=doing):
                val_to_bitarray(val, doing)


class TestBitarraySlice:
    @pytest.fixture()
    def slce(self):
        name = mock.Mock(name="name")
        typ = mock.Mock(name="typ")
        val = mock.Mock(name="val")
        size_bits = mock.Mock(name="size_bits")
        group = mock.Mock(name="group")
        return BitarraySlice(name, typ, val, size_bits, group)

    def test_it_takes_in_things(self):
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

    def test_it_gets_fmt_from_typstruct_format(self, slce):
        fmt = str(uuid.uuid1())
        slce.typ.struct_format = fmt
        assert slce.fmt is fmt

    class TestUnpackd:
        def test_it_returns_as_is_if_fmt_is_None(self, slce):
            bts = b"wat"
            val = bitarray(endian="little")
            val.frombytes(bts)

            slce.val = val
            slce.typ.struct_format = None

            assert slce.unpackd == val

        def test_it_returns_as_boolean_value_if_fmt_is_bool_and_size_bits_is_1(self, slce):
            slce.typ.struct_format = bool
            slce.size_bits = 1

            slce.val = bitarray("0")
            assert slce.unpackd is False

            slce.val = bitarray("1")
            assert slce.unpackd is True

        def test_it_pads_left_if_original_size_is_greater_than_actual_val_and_we_have_left_cut(self, slce):
            slce.typ = T.Int8.S(6, left=True)
            slce.val = bitarray("000010", endian="little")

            use = bitarray("00000010", endian="little").tobytes()
            not_use = bitarray("00001000", endian="little").tobytes()

            assert struct.unpack("<b", use)[0] == 64
            assert struct.unpack("<b", not_use)[0] == 16

            assert slce.unpackd == 64

        def test_it_pads_right_if_original_size_is_greater_than_actual_val_and_we_dont_have_left_cut(self, slce):
            slce.typ = T.Int8.S(6)
            slce.val = bitarray("000010", endian="little")

            use = bitarray("00001000", endian="little").tobytes()
            not_use = bitarray("00000010", endian="little").tobytes()

            assert struct.unpack("<b", use)[0] == 16
            assert struct.unpack("<b", not_use)[0] == 64

            assert slce.unpackd == 16

        def test_it_raises_BadConversion_if_it_cant_unpack_the_field(self, slce):
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


class TestFieldInfo:
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

    def test_it_takes_in_things(self):
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

    class TestValue:
        def test_it_returns_value_as_is(self, info, val):
            assert info.value is val

        def test_it_returns_value_as_0_bits_if_our_typ_is_Reserved_and_val_is_NotSpecified(self, info):
            info.typ = T.Reserved(8)
            info.size_bits = 8
            info.val = sb.NotSpecified
            assert info.value == bitarray("0" * 8)

        def test_it_returns_value_as_is_if_typ_is_Reserved_but_value_is_not_NotSpecified(self, info, val):
            info.typ = T.Reserved(8)
            assert info.value == val

    class TestToSizedBitarray:
        def test_it_removes_from_the_right_if_no_left_cut(self, info):
            info.typ.left_cut = False
            info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray("110000", endian="little")

            with mock.patch.object(info, "to_bitarray", to_bitarray):
                assert info.to_sized_bitarray() == bitarray("110")

            to_bitarray.assert_called_once_with()

        def test_it_removes_from_the_left_if_left_cut(self, info):
            info.typ.left_cut = True
            info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray("110001", endian="little")

            with mock.patch.object(info, "to_bitarray", to_bitarray):
                assert info.to_sized_bitarray() == bitarray("001")

            to_bitarray.assert_called_once_with()

        def test_it_does_nothing_if_too_small(self, info):
            info.typ.left_cut = True
            info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray("1", endian="little")

            with mock.patch.object(info, "to_bitarray", to_bitarray):
                assert info.to_sized_bitarray() == bitarray("1")

            to_bitarray.assert_called_once_with()

        def test_it_does_nothing_if_correct_size(self, info):
            info.typ.left_cut = True
            info.size_bits = 3

            to_bitarray = mock.Mock(name="to_bitarray")
            to_bitarray.return_value = bitarray("101", endian="little")

            with mock.patch.object(info, "to_bitarray", to_bitarray):
                assert info.to_sized_bitarray() == bitarray("101")

            to_bitarray.assert_called_once_with()

    class TestToBitarray:
        @contextmanager
        def a_val(self, val):
            with mock.patch.object(FieldInfo, "value", val):
                yield

        def test_it_complains_if_the_value_is_NotSpecified(self, info):
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

        def test_it_returns_as_is_if_its_a_bitarray(self, info):
            val = bitarray("01")
            with self.a_val(val):
                assert info.to_bitarray() is val

        def test_it_uses_struct_format_if_the_fmt_is_a_string(self, info):
            val = bitarray("01").tobytes()
            res = mock.Mock(name="res")

            info.typ.struct_format = "<b"
            struct_format = mock.Mock(name="struct_format", return_value=res)

            with self.a_val(val):
                with mock.patch.object(info, "struct_format", struct_format):
                    assert info.to_bitarray() is res

            struct_format.assert_called_once_with("<b", val)

        def test_it_turns_Optional_into_a_False(self, info):
            info.typ.struct_format = bool
            info.val = Optional
            assert info.to_bitarray() == bitarray("0")

        def test_it_complains_if_fmt_is_bool_but_value_is_not(self, info):
            for val in (0, 1, None, "", "adsf", b"asf", [], [1], {1: 2}, lambda: 1):
                with assertRaises(BadConversion, "Trying to convert a non boolean into 1 bit"):
                    info.typ.struct_format = bool
                    info.val = val
                    info.to_bitarray()

        def test_it_converts_True_False_into_a_single_bit_if_fmt_is_bool(self, info):
            info.typ.struct_format = bool
            info.val = True
            assert info.to_bitarray() == bitarray("1")

            info.val = False
            assert info.to_bitarray() == bitarray("0")

        def test_it_creates_bitarray_from_the_bytes_otherwise(self, info):
            info.typ.struct_format = None
            info.val = b"wat"

            expected = bitarray(endian="little")
            expected.frombytes(b"wat")

            assert info.to_bitarray() == expected

    class TestStructFormat:
        def test_it_creates_bitarray_from_unpacking(self, info):
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

        def test_it_works(self, info):
            info.typ = T.Int16

            expected = bitarray(endian="little")
            expected.frombytes(struct.pack("<h", 200))

            assert info.struct_format(info.typ.struct_format, 200) == expected

        def test_it_complains_if_cant_pack(self, info):
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

        def test_it_understands_the_Optional_value(self, info):
            b = bitarray(endian="little")
            b.frombytes(struct.pack("<H", 0))
            assert info.struct_format("<H", Optional) == b


class TestPacketPacking:
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

    class TestFieldsIn:
        def test_it_yields_FieldInfo_objects(self, V):
            def cb(pkt, serial):
                return f"{serial}.cb"

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

    class TestPktFromBitarray:
        def test_it_creates_a_pkt_field_by_field(self, V):
            def cb(pkt, serial):
                return f"{serial}.cb2"

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

        def test_it_returns_where_we_are_in_the_bitarray_which_is_helpful_when_we_have_an_empty_payload(
            self,
        ):
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

    class TestPack:
        def test_it_gets_fields_from_fields_in_and_joins_the_bitarrays_to_form_a_final_bitarray(
            self,
        ):
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
                assert PacketPacking.pack(pkt, parent=parent, serial=serial) == bitarray("01111010", endian="little")

            fields_in.assert_called_once_with(pkt, parent, serial)

        def test_it_attaches_provided_payload_to_the_end(self):
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
                assert PacketPacking.pack(pkt, payload=payload, parent=parent, serial=serial) == bitarray("0111101001010101", endian="little")

            fields_in.assert_called_once_with(pkt, parent, serial)

        def test_it_uses_payload_from_the_pkt_if_none_is_provided(self):
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
                assert PacketPacking.pack(pkt, parent=parent, serial=serial) == bitarray("0111101001010101", endian="little")

            fields_in.assert_called_once_with(pkt, parent, serial)

        def test_it_does_not_set_payload_if_we_arent_a_parent_packet(self):
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

        def test_it_complains_if_we_have_a_field_with_no_value(self):
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
                    assert PacketPacking.pack(pkt, parent=parent, serial=serial) == bitarray("01111010", endian="little")

            fields_in.assert_called_once_with(pkt, parent, serial)

    class TestUnpack:
        def test_it_uses_pkt_from_bitarray(self):
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

        def test_it_assigns_the_remainder_if_we_have_a_payload_with_message_type_0(self):
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
