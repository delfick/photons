# coding: spec

from photons_protocol.types import Type as T, MultiOptions
from photons_protocol.messages import Messages
from photons_protocol.packets import dictobj

from photons_app.errors import ProgrammerError

from photons_messages import frame

from delfick_project.errors_pytest import assertRaises
from bitarray import bitarray
from textwrap import dedent
from unittest import mock
import binascii
import pytest


@pytest.fixture()
def packet():
    return frame.LIFXPacket.create()


@pytest.fixture()
def emptybt():
    bt = bitarray("0000000000000000000000000000000000000000000000000000000000000000")
    assert bt.tobytes() == b"\x00" * 8
    return bt


describe "LIFXPacket":
    it "defaults size to size_bits on the pkt divided by 8":
        msg = frame.LIFXPacket.message

        class M(Messages):
            P = msg(1)

            P2 = msg(2, ("thing", T.String(32 * 8)))

        p = M.P()
        assert p.size == 36

        p = M.P2()
        assert p.size == 68

    it "defaults protocol to 1024", packet:
        assert packet.protocol == 1024

    it "defaults res_required to True", packet:
        assert packet.res_required is True

    it "defaults ack_required to True", packet:
        assert packet.ack_required is True

    it "defaults addressable to True", packet:
        assert packet.addressable is True

    it "ensures addressable is True if target is set to empty", emptybt, packet:
        for target in (None, b"\x00" * 8, emptybt):
            packet.addressable = False
            packet.target = target
            assert packet.addressable is True

    it "defaults tagged to False", packet:
        assert packet.tagged is False

    it "ensures tagged is True if target is set to empty", emptybt, packet:
        for target in (None, "0000000000000000", b"\x00" * 8, emptybt):
            packet.tagged = False
            packet.target = target
            assert packet.tagged is True

    it "ensures tagged is False if target is set to not empty", packet:
        packet.target = None
        assert packet.tagged is True

        packet.target = "d073d5000001"
        assert packet.tagged is False

    it "defaults pkt_type to Payload.message_type":
        msg = frame.LIFXPacket.message

        class M(Messages):
            P = msg(10)
            P2 = msg(200)

        assert M.P().pkt_type == 10
        assert M.P2().pkt_type == 200

    it "packs without target":
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

        found = {
            field.name: (field.transformed_val, field.raw)
            for field in p.fields
            if not field.is_reserved
        }

        expected = {
            "size": (38, bitarray("0110010000000000")),
            "protocol": (1024, bitarray("000000000010")),
            "addressable": (True, bitarray("1")),
            "tagged": (True, bitarray("1")),
            "source": (1, bitarray("10000000000000000000000000000000")),
            "target": (
                bitarray(
                    "0000000000000000000000000000000000000000000000000000000000000000"
                ).tobytes(),
                bitarray("0000000000000000000000000000000000000000000000000000000000000000"),
            ),
            "res_required": (True, bitarray("1")),
            "ack_required": (True, bitarray("1")),
            "sequence": (1, bitarray("10000000")),
            "pkt_type": (52, bitarray("0010110000000000")),
            "one": (bitarray("0000000000000000").tobytes(), bitarray("0000000000000000")),
        }

        assert set(found) == set(expected)

        for (fn, fv), (en, ev) in zip(found.items(), expected.items()):
            if fn != en:
                assert False, f"{fn} != {en}: {fv} => {ev}"
            if fv != ev:
                print("Found", fn)
                print("\t", fv)
                print("===")
                print("Expected", en)
                print("\t", ev)
                assert ev == fv

        assert found and expected

    it "is a parent":
        assert frame.LIFXPacket.Meta.parent is None

    it "has protocol of 1024":
        assert frame.LIFXPacket.Meta.protocol == 1024
        assert frame.LIFXPacket.Payload.Meta.protocol == 1024

    it "has payload with message_type of 0":
        assert frame.LIFXPacket.Payload.message_type == 0

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

            assert payloadone.pkt_type == 32
            assert payloadone.protocol == 1024

            assert payloadtwo.pkt_type == 33
            assert payloadtwo.protocol == 1024

            assert payloadone | Two is False
            assert payloadone | One is True

            assert payloadtwo | Two is True
            assert payloadtwo | One is False

    describe "serial":
        it "returns None if target isn't specified":
            pkt = frame.LIFXPacket()
            assert not pkt.fields.is_not_empty("target")
            assert pkt.serial == "000000000000"

        it "returns 0s if target is None":
            pkt = frame.LIFXPacket(target=None)
            assert pkt.target == b"\x00\x00\x00\x00\x00\x00\x00\x00"
            assert pkt.serial == "000000000000"

        it "hexlifies otherwise":
            serial = "d073d5000001"
            target = binascii.unhexlify(serial)
            pkt = frame.LIFXPacket(target=target)
            assert pkt.target == target + b"\x00\x00"
            assert pkt.serial == serial

        it "only deals with first six bytes":
            serial = "d073d5000001"
            serialexpanded = "d073d50000010101"
            target = binascii.unhexlify(serialexpanded)
            pkt = frame.LIFXPacket(target=target)
            assert pkt.target == target
            assert pkt.serial == serial

    describe "creating a message":
        it "has the provided name":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.__name__ == "Name"
            assert msg.Payload.__name__ == "NamePayload"

        it "has the provided fields on the Payload":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(52, *fields)("Name")

            p = msg(one=True, two="h")
            for name, _, _ in frame.LIFXPacket.Meta.fields:
                assert name in p
            assert "one" in p
            assert "two" in p

        it "has the provided message_type":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.Payload.message_type == 52

        it "represents_ack if message_type is 45":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(45, *fields)("Name")
            assert msg.Payload.represents_ack is True

            msg = frame.LIFXPacket.message(46, *fields)("Name")
            assert msg.Payload.represents_ack is False

        it "has a _lifx_packet_message property":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(52, *fields)
            assert msg._lifx_packet_message is True

        it "sets Payload.Meta.protocol to 1024":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.Payload.Meta.protocol == 1024

        it "has a parent":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.Meta.parent is frame.LIFXPacket

        it "has Meta.parent set to LIFXPacket":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(52, *fields)("Name")
            assert msg.Meta.parent == frame.LIFXPacket

        it "has a way of creating another packet with the same fields but different message_type":
            fields = [("one", T.Bool), ("two", T.String(4 * 8))]
            msg = frame.LIFXPacket.message(52, *fields)
            using = msg.using(62)

            m1 = msg("One")
            m2 = using("Thing")

            assert m1.Meta.fields[:-1] == m2.Meta.fields[:-1]
            assert m1.Meta.fields[-1] == ("payload", m1.Payload, False)
            assert m2.Meta.fields[-1] == ("payload", m2.Payload, False)
            assert m1.Payload.fields == m2.Payload.fields

            assert m2.Payload.message_type == 62
            assert m2.Payload.Meta.protocol == 1024
            assert m2.__name__ == "Thing"
            assert m2.Payload.__name__ == "ThingPayload"
            assert m2.Meta.parent is frame.LIFXPacket
            assert using._lifx_packet_message is True

        it "sets multi on Meta":
            msg = frame.LIFXPacket.message(52)("One")
            assert msg.Meta.multi is None
            assert msg.Payload.Meta.multi is None

            multi = mock.Mock(name="multi")
            msg = frame.LIFXPacket.message(52, multi=multi)("One")
            assert msg.Meta.multi is multi
            assert msg.Payload.Meta.multi is multi

    describe "Key":
        it "is able to get a memoized Key from the packet":
            fields = [("one", T.Bool), ("two", T.String(6 * 8))]
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

describe "MultiOptions":
    it "complains if we don't give it two functions":
        for a, b in [(None, None), (lambda: 1, None), (None, lambda: 1), (1, 2)]:
            with assertRaises(ProgrammerError, "Multi Options expects two callables"):
                MultiOptions(a, b)

    it "sets the two callables":
        determine_res_packet = mock.Mock(name="determine_res_packet")
        adjust_expected_number = mock.Mock(name="adjust_expected_number")
        options = MultiOptions(determine_res_packet, adjust_expected_number)

        assert options.determine_res_packet is determine_res_packet
        assert options.adjust_expected_number is adjust_expected_number

    it "has a Max helper":
        num = MultiOptions.Max(5)

        assert num([1]) == -1
        assert num([0, 1, 2, 3]) == -1

        assert num([0, 1, 2, 3, 4]) == 5
        assert num([0, 1, 2, 3, 4, 5]) == 6

describe "Messages":
    it "works":
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
