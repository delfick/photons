import binascii
from textwrap import dedent
from unittest import mock

import pytest
from bitarray import bitarray
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from photons_app.errors import ProgrammerError
from photons_messages import frame
from photons_protocol.messages import Messages
from photons_protocol.packets import dictobj
from photons_protocol.packing import PacketPacking
from photons_protocol.types import MultiOptions
from photons_protocol.types import Type as T


@pytest.fixture()
def packet():
    return frame.LIFXPacket.create()


@pytest.fixture()
def emptybt():
    bt = bitarray("0000000000000000000000000000000000000000000000000000000000000000")
    assert bt.tobytes() == b"\x00" * 8
    return bt


class TestLIFXPacket:
    def test_it_defaults_size_to_size_bits_on_the_pkt_divided_by_8(self):
        msg = frame.LIFXPacket.message

        class M(Messages):
            P = msg(1)

            P2 = msg(2, ("thing", T.String(32 * 8)))

        p = M.P()
        assert p.size == 36

        p = M.P2()
        assert p.size == 68

    def test_it_defaults_protocol_to_1024(self, packet):
        assert packet.protocol == 1024

    def test_it_defaults_res_required_to_True(self, packet):
        assert packet.res_required is True

    def test_it_defaults_ack_required_to_True(self, packet):
        assert packet.ack_required is True

    def test_it_defaults_addressable_to_True(self, packet):
        assert packet.addressable is True

    def test_it_ensures_addressable_is_True_if_target_is_set_to_empty(self, emptybt, packet):
        for target in (None, b"\x00" * 8, emptybt):
            packet.addressable = False
            packet.target = target
            assert packet.addressable is True

    def test_it_defaults_tagged_to_False(self, packet):
        assert packet.tagged is False

    def test_it_ensures_tagged_is_True_if_target_is_set_to_empty(self, emptybt, packet):
        for target in (None, "0000000000000000", b"\x00" * 8, emptybt):
            packet.tagged = False
            packet.target = target
            assert packet.tagged is True

    def test_it_ensures_tagged_is_False_if_target_is_set_to_not_empty(self, packet):
        packet.target = None
        assert packet.tagged is True

        packet.target = "d073d5000001"
        assert packet.tagged is False

    def test_it_defaults_pkt_type_to_Payloadmessage_type(self):
        msg = frame.LIFXPacket.message

        class M(Messages):
            P = msg(10)
            P2 = msg(200)

        assert M.P().pkt_type == 10
        assert M.P2().pkt_type == 200

    def test_it_packs_without_target(self):
        p = frame.LIFXPacket(source=1, sequence=1, target=None, payload=b"")
        assert p.size == 36
        expected = bitarray(
            dedent(
                """
              001001000000000000000000001011001000000000000000000000000000000000
              000000000000000000000000000000000000000000000000000000000000000000
              000000000000000000000000000000000000000000001100000010000000000000
              000000000000000000000000000000000000000000000000000000000000000000
              000000000000000000000000"""
            )
            .replace("\n", "")
            .strip()
        )

        assert p.pack() == expected

    def test_it_is_an_ack_if_the_Payload_is_an_ack(self):

        class P(frame.LIFXPacket):
            class Payload(dictobj.PacketSpec):
                represents_ack = True
                fields = []

        p = P()
        assert p.represents_ack

    def test_it_is_not_an_ack_if_the_Payload_is_not_an_ack(self):

        class P(frame.LIFXPacket):
            class Payload(dictobj.PacketSpec):
                represents_ack = True
                fields = []

        p = P()
        assert p.represents_ack

    def test_it_has_the_right_size_bits_for_all_the_fields(self):

        class P(frame.LIFXPacket):
            class Payload(dictobj.PacketSpec):
                message_type = 52
                represents_ack = True
                fields = [("one", T.Bytes(16))]

        p = P(target=None, sequence=1, source=1, one=b"\x00")

        found = {}
        for info in PacketPacking.fields_in(p, p, None):
            assert info.name not in found
            found[info.name] = (info.val, info.to_sized_bitarray())

        expected = {
            "size": (38, bitarray("0110010000000000")),
            "protocol": (1024, bitarray("000000000010")),
            "addressable": (True, bitarray("1")),
            "tagged": (True, bitarray("1")),
            "source": (1, bitarray("10000000000000000000000000000000")),
            "target": (
                bitarray("0000000000000000000000000000000000000000000000000000000000000000"),
                bitarray("0000000000000000000000000000000000000000000000000000000000000000"),
            ),
            "res_required": (True, bitarray("1")),
            "ack_required": (True, bitarray("1")),
            "sequence": (1, bitarray("10000000")),
            "pkt_type": (52, bitarray("0010110000000000")),
            "one": (bitarray("0000000000000000"), bitarray("0000000000000000")),
        }

        for k in list(found):
            if k not in expected:
                del found[k]

        assert found == expected

    def test_it_is_a_parent_packet(self):
        assert frame.LIFXPacket.parent_packet is True

    def test_it_has_protocol_of_1024(self):
        assert frame.LIFXPacket.Meta.protocol == 1024
        assert frame.LIFXPacket.Payload.Meta.protocol == 1024

    def test_it_has_payload_with_message_type_of_0(self):
        assert frame.LIFXPacket.Payload.message_type == 0

    class TestOr:
        def test_it_says_yes_if_the_protocol_and_pkt_type_are_the_same_as_on_klsPayload(self):

            class One(frame.LIFXPacket):
                class Payload(dictobj.PacketSpec):
                    fields = []
                    message_type = 32

            One.Payload.Meta.protocol = 1024

            class Two(frame.LIFXPacket):
                class Payload(dictobj.PacketSpec):
                    fields = []
                    message_type = 33

            Two.Payload.Meta.protocol = 1024

            payloadone = One()
            payloadtwo = Two()

            assert payloadone.pkt_type == 32
            assert payloadone.protocol == 1024

            assert payloadtwo.pkt_type == 33
            assert payloadtwo.protocol == 1024

            assert payloadone | Two is False
            assert payloadone | One is True

            assert payloadtwo | Two is True
            assert payloadtwo | One is False

        def test_it_can_get_the_values_from_the_packet_data_if_already_defined(self):

            class One(frame.LIFXPacket):
                class Payload(dictobj.PacketSpec):
                    fields = []
                    message_type = 32

            One.Payload.Meta.protocol = 1024

            class Two(frame.LIFXPacket):
                class Payload(dictobj.PacketSpec):
                    fields = []
                    message_type = 33

            Two.Payload.Meta.protocol = 1024

            # These values are already there if it's been created from bytes for example
            # In this case we don't want to go through the __getattr__ mechanism on the packet
            # Because that is slow!
            payloadone = One(pkt_type=32, protocol=1024)
            payloadtwo = Two(pkt_type=33, protocol=1024)

            with mock.patch.object(
                frame.LIFXPacket, "__getitem__", mock.NonCallableMock(name="__getitem__")
            ):
                assert payloadone | Two is False
                assert payloadone | One is True

                assert payloadtwo | Two is True
                assert payloadtwo | One is False

    class TestSerial:
        def test_it_returns_None_if_target_isnt_specified(self):
            pkt = frame.LIFXPacket()
            assert pkt.target is sb.NotSpecified
            assert pkt.serial is None

        def test_it_returns_0s_if_target_is_None(self):
            pkt = frame.LIFXPacket(target=None)
            assert pkt.target == b"\x00\x00\x00\x00\x00\x00\x00\x00"
            assert pkt.serial == "000000000000"

        def test_it_hexlifies_otherwise(self):
            serial = "d073d5000001"
            target = binascii.unhexlify(serial)
            pkt = frame.LIFXPacket(target=target)
            assert pkt.target == target + b"\x00\x00"
            assert pkt.serial == serial

        def test_it_only_deals_with_first_six_bytes(self):
            serial = "d073d5000001"
            serialexpanded = "d073d50000010101"
            target = binascii.unhexlify(serialexpanded)
            pkt = frame.LIFXPacket(target=target)
            assert pkt.target == target
            assert pkt.serial == serial

    class TestCreatingAMessage:
        def test_it_has_the_provided_name(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.__name__ == "Name"
            assert msg.Payload.__name__ == "NamePayload"

        def test_it_has_the_provided_fields_on_the_Payload(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.Payload.Meta.original_fields == fields
            assert msg.Meta.original_fields == frame.LIFXPacket.Meta.original_fields

        def test_it_has_the_provided_message_type(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.Payload.message_type == 52

        def test_it_represents_ack_if_message_type_is_45(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(45, *fields)("Name")
            assert msg.Payload.represents_ack is True

            msg = frame.LIFXPacket.message(46, *fields)("Name")
            assert msg.Payload.represents_ack is False

        def test_it_has_a_lifx_packet_message_property(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)
            assert msg._lifx_packet_message is True

        def test_it_sets_PayloadMetaprotocol_to_1024(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.Payload.Meta.protocol == 1024

        def test_it_has_parent_packet_set_to_False(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.parent_packet is False

        def test_it_has_Metaparent_set_to_LIFXPacket(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.Meta.parent == frame.LIFXPacket

        def test_it_has_a_way_of_creating_another_packet_with_the_same_fields_but_different_message_type(
            self,
        ):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)
            using = msg.using(62)
            msg2 = using("Thing")

            assert msg2.Meta.original_fields == frame.LIFXPacket.Meta.original_fields
            assert msg2.Payload.Meta.original_fields == fields
            assert msg2.Payload.message_type == 62
            assert msg2.Payload.Meta.protocol == 1024
            assert msg2.__name__ == "Thing"
            assert msg2.Payload.__name__ == "ThingPayload"
            assert msg2.parent_packet is False
            assert msg2.Meta.parent == frame.LIFXPacket
            assert using._lifx_packet_message is True

        def test_it_sets_multi_on_Meta(self):
            msg = frame.LIFXPacket.message(52)("One")
            assert msg.Meta.multi is None
            assert msg.Payload.Meta.multi is None

            multi = mock.Mock(name="multi")
            msg = frame.LIFXPacket.message(52, multi=multi)("One")
            assert msg.Meta.multi is multi
            assert msg.Payload.Meta.multi is multi

    class TestKey:
        def test_it_is_able_to_get_a_memoized_Key_from_the_packet(self):
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("SetAmze")

            pkt1 = msg(one=True, two="hello")
            pkt2 = msg(one=False, two="there")

            assert pkt1.Key == (1024, 52, '{"one": true, "two": "hello"}')
            assert pkt2.Key == (1024, 52, '{"one": false, "two": "there"}')

            # For efficiency, the Key is cached, so if you change the payload
            # The key stays the same, but we can delete the key for it to be recreated
            pkt1.two = "tree"
            assert pkt1.Key == (1024, 52, '{"one": true, "two": "hello"}')
            del pkt1.Key
            assert pkt1.Key == (1024, 52, '{"one": true, "two": "tree"}')


class TestMultiOptions:
    def test_it_complains_if_we_dont_give_it_two_functions(self):
        for a, b in [(None, None), (lambda: 1, None), (None, lambda: 1), (1, 2)]:
            with assertRaises(ProgrammerError, "Multi Options expects two callables"):
                MultiOptions(a, b)

    def test_it_sets_the_two_callables(self):
        determine_res_packet = mock.Mock(name="determine_res_packet")
        adjust_expected_number = mock.Mock(name="adjust_expected_number")
        options = MultiOptions(determine_res_packet, adjust_expected_number)

        assert options.determine_res_packet is determine_res_packet
        assert options.adjust_expected_number is adjust_expected_number

    def test_it_has_a_Max_helper(self):
        num = MultiOptions.Max(5)

        assert num([1]) == -1
        assert num([0, 1, 2, 3]) == -1

        assert num([0, 1, 2, 3, 4]) == 5
        assert num([0, 1, 2, 3, 4, 5]) == 6


class TestMessages:
    def test_it_works(self):
        msg = frame.LIFXPacket.message

        class M(Messages):
            One = msg(42, ("one", T.Int8))

            Two = One.using(46)

        class M2(Messages):
            Three = M.One

        assert M.by_type == {42: M.One, 46: M.Two}

        assert M2.by_type == {42: M.One}

        o = M.One(one=27)
        assert o.one == 27
        assert o.size == 37
        assert o.pkt_type == 42

        t = M2.Three(one=57)
        assert t.one == 57
        assert t.size == 37
        assert t.pkt_type == 42
