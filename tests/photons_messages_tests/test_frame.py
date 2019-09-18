# coding: spec

from photons_protocol.types import Type as T, MultiOptions
from photons_protocol.packing import PacketPacking
from photons_protocol.messages import Messages
from photons_protocol.packets import dictobj

from photons_app.errors import ProgrammerError
from photons_app.test_helpers import TestCase

from photons_messages import frame

from noseOfYeti.tokeniser.support import noy_sup_setUp
from delfick_project.norms import sb, Meta
from bitarray import bitarray
from textwrap import dedent
from unittest import mock
import binascii

describe TestCase, "FrameHeader":
    before_each:
        self.frame_header = frame.FrameHeader()

    it "defaults size to size_bits on the pkt divided by 8":
        pkt = mock.Mock(name="pkt")
        pkt.size_bits.return_value = 16

        spec = self.frame_header.Meta.field_types_dict["size"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, 2)

    it "defaults protocol to 1024":
        pkt = mock.Mock(name="pkt")
        spec = self.frame_header.Meta.field_types_dict["protocol"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, 1024)

    it "defaults addressable to False if we have no target":
        pkt = mock.Mock(name="pkt", target=None)
        spec = self.frame_header.Meta.field_types_dict["addressable"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, False)

    it "defaults addressable to True if we do have a target":
        pkt = mock.Mock(name="pkt", target="d073d5")
        spec = self.frame_header.Meta.field_types_dict["addressable"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, True)

    it "defaults tagged to True if we have no target":
        pkt = mock.Mock(name="pkt", target=None)
        spec = self.frame_header.Meta.field_types_dict["tagged"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, True)

    it "defaults tagged to False if we do have a target":
        pkt = mock.Mock(name="pkt", target="d073d5")
        spec = self.frame_header.Meta.field_types_dict["tagged"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, False)

describe TestCase, "FrameAddress":
    before_each:
        self.frame_address = frame.FrameAddress()

    it "defaults res_required to True":
        pkt = mock.Mock(name="pkt")
        spec = self.frame_address.Meta.field_types_dict["res_required"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, True)

    it "defaults ack_required to True":
        pkt = mock.Mock(name="pkt")
        spec = self.frame_address.Meta.field_types_dict["ack_required"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, True)

describe TestCase, "ProtocolHeader":
    before_each:
        self.protocol_header = frame.ProtocolHeader()

    it "defaults pkt_type to Payload.message_type":

        class Payload:
            message_type = 62

        pkt = mock.Mock(name="pkt", Payload=Payload)
        spec = self.protocol_header.Meta.field_types_dict["pkt_type"].spec(pkt)
        val = spec.normalise(Meta.empty(), sb.NotSpecified)
        self.assertEqual(val, 62)

describe TestCase, "LIFXPacket":
    it "packs without target":
        p = frame.LIFXPacket(source=1, sequence=1, target=None, payload=b"")
        self.assertEqual(p.size, 36)
        expected = bitarray(
            dedent(
                """
              001001000000000000000000001010001000000000000000000000000000000000
              000000000000000000000000000000000000000000000000000000000000000000
              000000000000000000000000000000000000000000001100000010000000000000
              000000000000000000000000000000000000000000000000000000000000000000
              000000000000000000000000"""
            )
            .replace("\n", "")
            .strip()
        )
        self.assertEqual(p.pack(), expected)

    it "is an ack if the Payload is an ack":

        class P(frame.LIFXPacket):
            class Payload(dictobj.PacketSpec):
                represents_ack = True
                fields = []

        p = P()
        assert p.represents_ack

    it "is not an ack if the Payload is not an ack":

        class P(frame.LIFXPacket):
            class Payload(dictobj.PacketSpec):
                represents_ack = True
                fields = []

        p = P()
        assert p.represents_ack

    it "has the right size_bits for all the fields":

        class P(frame.LIFXPacket):
            class Payload(dictobj.PacketSpec):
                message_type = 52
                represents_ack = True
                fields = [("one", T.Bytes(16))]

        p = P(target=None, sequence=1, source=1, one=b"\x00")

        found = []
        for info in PacketPacking.fields_in(p, p, None):
            found.append((info.name, info.val, info.to_sized_bitarray()))

        self.maxDiff = None
        self.assertEqual(
            found,
            [
                ("size", 38, bitarray("0110010000000000")),
                ("protocol", 1024, bitarray("000000000010")),
                ("addressable", True, bitarray("1")),
                ("tagged", False, bitarray("0")),
                ("reserved1", sb.NotSpecified, bitarray("00")),
                ("source", 1, bitarray("10000000000000000000000000000000")),
                (
                    "target",
                    bitarray("0000000000000000000000000000000000000000000000000000000000000000"),
                    bitarray("0000000000000000000000000000000000000000000000000000000000000000"),
                ),
                (
                    "reserved2",
                    sb.NotSpecified,
                    bitarray("000000000000000000000000000000000000000000000000"),
                ),
                ("res_required", True, bitarray("1")),
                ("ack_required", True, bitarray("1")),
                ("reserved3", sb.NotSpecified, bitarray("000000")),
                ("sequence", 1, bitarray("10000000")),
                (
                    "reserved4",
                    sb.NotSpecified,
                    bitarray("0000000000000000000000000000000000000000000000000000000000000000"),
                ),
                ("pkt_type", 52, bitarray("0010110000000000")),
                ("reserved5", sb.NotSpecified, bitarray("0000000000000000")),
                ("one", bitarray("0000000000000000"), bitarray("0000000000000000")),
            ],
        )

    it "is a parent_packet":
        self.assertEqual(frame.LIFXPacket.parent_packet, True)

    it "has protocol of 1024":
        self.assertEqual(frame.LIFXPacket.Meta.protocol, 1024)
        self.assertEqual(frame.LIFXPacket.Payload.Meta.protocol, 1024)

    it "has payload with message_type of 0":
        self.assertEqual(frame.LIFXPacket.Payload.message_type, 0)

    describe "__or__":
        it "says yes if the protocol and pkt_type are the same as on kls.Payload":

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

            self.assertEqual(payloadone.pkt_type, 32)
            self.assertEqual(payloadone.protocol, 1024)

            self.assertEqual(payloadtwo.pkt_type, 33)
            self.assertEqual(payloadtwo.protocol, 1024)

            self.assertEqual(payloadone | Two, False)
            self.assertEqual(payloadone | One, True)

            self.assertEqual(payloadtwo | Two, True)
            self.assertEqual(payloadtwo | One, False)

        it "can get the values from the packet data if already defined":

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

            # These values are already there if it's been unpacked from bytes for example
            # In this case we don't want to go through the __getattr__ mechanism on the packet
            # Because that is slow!
            payloadone = One(pkt_type=32, protocol=1024)
            payloadtwo = Two(pkt_type=33, protocol=1024)

            with mock.patch.object(
                frame.LIFXPacket, "__getitem__", mock.NonCallableMock(name="__getitem__")
            ):
                self.assertEqual(payloadone | Two, False)
                self.assertEqual(payloadone | One, True)

                self.assertEqual(payloadtwo | Two, True)
                self.assertEqual(payloadtwo | One, False)

    describe "serial":
        it "returns None if target isn't specified":
            pkt = frame.LIFXPacket()
            self.assertIs(pkt.target, sb.NotSpecified)
            self.assertIs(pkt.serial, None)

        it "returns 0s if target is None":
            pkt = frame.LIFXPacket(target=None)
            self.assertEqual(pkt.target, b"\x00\x00\x00\x00\x00\x00\x00\x00")
            self.assertEqual(pkt.serial, "000000000000")

        it "hexlifies otherwise":
            serial = "d073d5000001"
            target = binascii.unhexlify(serial)
            pkt = frame.LIFXPacket(target=target)
            self.assertEqual(pkt.target, target + b"\x00\x00")
            self.assertEqual(pkt.serial, serial)

        it "only deals with first six bytes":
            serial = "d073d5000001"
            serialexpanded = "d073d50000010101"
            target = binascii.unhexlify(serialexpanded)
            pkt = frame.LIFXPacket(target=target)
            self.assertEqual(pkt.target, target)
            self.assertEqual(pkt.serial, serial)

    describe "creating a message":
        it "has the provided name":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            self.assertEqual(msg.__name__, "Name")
            self.assertEqual(msg.Payload.__name__, "NamePayload")

        it "has the provided fields on the Payload":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            self.assertEqual(msg.Payload.Meta.original_fields, fields)
            self.assertEqual(msg.Meta.original_fields, frame.LIFXPacket.Meta.original_fields)

        it "has the provided message_type":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            self.assertEqual(msg.Payload.message_type, 52)

        it "represents_ack if message_type is 45":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(45, *fields)("Name")
            self.assertEqual(msg.Payload.represents_ack, True)

            msg = frame.LIFXPacket.message(46, *fields)("Name")
            self.assertEqual(msg.Payload.represents_ack, False)

        it "has a _lifx_packet_message property":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)
            self.assertEqual(msg._lifx_packet_message, True)

        it "sets Payload.Meta.protocol to 1024":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            self.assertEqual(msg.Payload.Meta.protocol, 1024)

        it "has parent_packet set to False":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            self.assertEqual(msg.parent_packet, False)

        it "has Meta.parent set to LIFXPacket":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            self.assertEqual(msg.Meta.parent, frame.LIFXPacket)

        it "has a way of creating another packet with the same fields but different message_type":
            fields = [("one", T.Bool), ("two", T.String)]
            msg = frame.LIFXPacket.message(52, *fields)
            using = msg.using(62)
            msg2 = using("Thing")

            self.assertEqual(msg2.Meta.original_fields, frame.LIFXPacket.Meta.original_fields)
            self.assertEqual(msg2.Payload.Meta.original_fields, fields)
            self.assertEqual(msg2.Payload.message_type, 62)
            self.assertEqual(msg2.Payload.Meta.protocol, 1024)
            self.assertEqual(msg2.__name__, "Thing")
            self.assertEqual(msg2.Payload.__name__, "ThingPayload")
            self.assertEqual(msg2.parent_packet, False)
            self.assertEqual(msg2.Meta.parent, frame.LIFXPacket)
            self.assertEqual(using._lifx_packet_message, True)

        it "sets multi on Meta":
            msg = frame.LIFXPacket.message(52)("One")
            self.assertIs(msg.Meta.multi, None)
            self.assertIs(msg.Payload.Meta.multi, None)

            multi = mock.Mock(name="multi")
            msg = frame.LIFXPacket.message(52, multi=multi)("One")
            self.assertIs(msg.Meta.multi, multi)
            self.assertIs(msg.Payload.Meta.multi, multi)

describe TestCase, "MultiOptions":
    it "complains if we don't give it two functions":
        for a, b in [(None, None), (lambda: 1, None), (None, lambda: 1), (1, 2)]:
            with self.fuzzyAssertRaisesError(
                ProgrammerError, "Multi Options expects two callables"
            ):
                MultiOptions(a, b)

    it "sets the two callables":
        determine_res_packet = mock.Mock(name="determine_res_packet")
        adjust_expected_number = mock.Mock(name="adjust_expected_number")
        options = MultiOptions(determine_res_packet, adjust_expected_number)

        self.assertIs(options.determine_res_packet, determine_res_packet)
        self.assertIs(options.adjust_expected_number, adjust_expected_number)

    it "has a Max helper":
        num = MultiOptions.Max(5)

        self.assertEqual(num([1]), -1)
        self.assertEqual(num([0, 1, 2, 3]), -1)

        self.assertEqual(num([0, 1, 2, 3, 4]), 5)
        self.assertEqual(num([0, 1, 2, 3, 4, 5]), 6)

describe TestCase, "Messages":
    it "works":
        msg = frame.LIFXPacket.message

        class M(Messages):
            One = msg(42, ("one", T.Int8))

            Two = One.using(46)

        class M2(Messages):
            Three = M.One

        self.assertEqual(M.by_type, {42: M.One, 46: M.Two})

        self.assertEqual(M2.by_type, {42: M.One})

        o = M.One(one=27)
        self.assertEqual(o.one, 27)
        self.assertEqual(o.size, 37)
        self.assertEqual(o.pkt_type, 42)

        t = M2.Three(one=57)
        self.assertEqual(t.one, 57)
        self.assertEqual(t.size, 37)
        self.assertEqual(t.pkt_type, 42)
