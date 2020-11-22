# coding: spec

from photons_protocol.messages import Messages, PacketTypeExtractor, sources_for
from photons_protocol.errors import BadConversion

from photons_app.registers import ProtocolRegister

from photons_messages import LIFXPacket

from delfick_project.errors_pytest import assertRaises
from bitarray import bitarray
from textwrap import dedent
from unittest import mock
import binascii
import pytest

msg = LIFXPacket.message


def ba(thing):
    b = bitarray(endian="little")
    b.frombytes(thing)
    return b


describe "PacketTypeExtractor":
    describe "packet_type":
        it "delegates for dicts":
            res = mock.Mock(name="res")
            packet_type_from_dict = mock.Mock(name="packet_type_from_dict", return_value=res)

            data = {}
            with mock.patch.object(
                PacketTypeExtractor, "packet_type_from_dict", packet_type_from_dict
            ):
                assert PacketTypeExtractor.packet_type(data) is res

            packet_type_from_dict.assert_called_once_with(data)

        it "delegates for bytes":
            res = mock.Mock(name="res")
            packet_type_from_bytes = mock.Mock(name="packet_type_from_bytes", return_value=res)

            data = b"AA"
            with mock.patch.object(
                PacketTypeExtractor, "packet_type_from_bytes", packet_type_from_bytes
            ):
                assert PacketTypeExtractor.packet_type(data) is res

            packet_type_from_bytes.assert_called_once_with(data)

        it "delegates for bitarray":
            res = mock.Mock(name="res")
            packet_type_from_bitarray = mock.Mock(
                name="packet_type_from_bitarray", return_value=res
            )

            data = ba(b"AA")
            with mock.patch.object(
                PacketTypeExtractor, "packet_type_from_bitarray", packet_type_from_bitarray
            ):
                assert PacketTypeExtractor.packet_type(data) is res

            packet_type_from_bitarray.assert_called_once_with(data)

        it "otherwise complains":
            for data in (0, 1, True, False, None, [], [1], lambda: True):
                msg = "Can't determine packet type from data"
                with assertRaises(BadConversion, msg, got=data):
                    PacketTypeExtractor.packet_type(data)

    describe "packet_type_from_dict":
        it "can get pkt_type and protocol directory from data":
            data = {"pkt_type": 45, "protocol": 1024}
            assert PacketTypeExtractor.packet_type_from_dict(data) == (1024, 45)

        it "can get pkt_type and protocol from groups":
            data = {"protocol_header": {"pkt_type": 45}, "frame_header": {"protocol": 1024}}
            assert PacketTypeExtractor.packet_type_from_dict(data) == (1024, 45)

        it "complains if it can't get protocol":
            msg = "Couldn't work out protocol from dictionary"

            data = {}
            with assertRaises(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

            data = {"frame_header": {}}
            with assertRaises(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

        it "complains if it can't get pkt_type":
            msg = "Couldn't work out pkt_type from dictionary"

            data = {"protocol": 1024}
            with assertRaises(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

            data = {"protocol": 1024, "protocol_header": {}}
            with assertRaises(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

    describe "packet_type_from_bitarray and bytes":
        it "complains if the length isn't correct":
            msg = "Data is too small to be a LIFX packet"

            bts = b""
            with assertRaises(BadConversion, msg, got=0):
                PacketTypeExtractor.packet_type_from_bytes(bts)
            with assertRaises(BadConversion, msg, got=0):
                PacketTypeExtractor.packet_type_from_bitarray(ba(bts))

            bts = LIFXPacket.create(source=1, sequence=1, target=None).pack().tobytes()
            PacketTypeExtractor.packet_type_from_bytes(bts)
            PacketTypeExtractor.packet_type_from_bitarray(ba(bts))

            with assertRaises(BadConversion, msg, need_atleast=36, got=20):
                PacketTypeExtractor.packet_type_from_bytes(bts[:20])
            with assertRaises(BadConversion, msg, need_atleast=36, got=20):
                PacketTypeExtractor.packet_type_from_bitarray(ba(bts[:20]))

        it "returns None pkt_type if protocol is unknown":
            pkt = LIFXPacket.create(
                protocol=234,
                pkt_type=15,
                addressable=True,
                tagged=True,
                source=1,
                sequence=1,
                target=None,
            )

            protocol, pkt_type = PacketTypeExtractor.packet_type_from_bytes(pkt.pack().tobytes())
            assert protocol == 234
            assert pkt_type is None

            protocol, pkt_type = PacketTypeExtractor.packet_type_from_bitarray(pkt.pack())
            assert protocol == 234
            assert pkt_type is None

        it "successfully gets protocol and pkt_type for 1024":
            pkt = LIFXPacket.create(
                protocol=1024,
                pkt_type=78,
                addressable=True,
                tagged=True,
                source=1,
                sequence=1,
                target=None,
            )

            protocol, pkt_type = PacketTypeExtractor.packet_type_from_bytes(pkt.pack().tobytes())
            assert protocol == 1024
            assert pkt_type == 78

            protocol, pkt_type = PacketTypeExtractor.packet_type_from_bitarray(pkt.pack())
            assert protocol == 1024
            assert pkt_type == 78

describe "sources_for":
    it "can get the source for packets", TestMessages:
        result = list(sources_for(TestMessages))
        assert len(result) == 3

        assert result[0][0] == "One"
        assert result[1][0] == "Two"
        assert result[2][0] == "Three"

        one = """
        One = msg(78
            , ("one", T.String(16))
            )
        """

        assert result[0][1] == dedent(one).lstrip()

        two = "Two = msg(99)\n"

        assert result[1][1] == two

        three = """
        Three = msg(98
            , ("three", T.Int8.transform(lambda _, v: v + 5, lambda _, v: v - 5))
            )
        """

        assert result[2][1] == dedent(three).lstrip()

describe "MessagesMixin":

    @pytest.fixture()
    def protocol_register(self, TestMessages):
        protocol_register = ProtocolRegister()
        protocol_register.add(1024, LIFXPacket)
        protocol_register.message_register(1024).add(TestMessages)
        return protocol_register

    describe "get_packet_type":

        it "can get us information about our data", protocol_register, TestMessages:
            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 78))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, protocol_register)
                assert info == (1024, 78, LIFXPacket, TestMessages.One, data)

            packet_type.assert_called_once_with(data)

            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 99))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, protocol_register)
                assert info == (1024, 99, LIFXPacket, TestMessages.Two, data)

            packet_type.assert_called_once_with(data)

        it "can get us information about unknown pkt types (known protocol)", protocol_register:
            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 88))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, protocol_register)
                assert info == (1024, 88, LIFXPacket, None, data)

            packet_type.assert_called_once_with(data)

        it "complains about unknown protocols", protocol_register:
            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1, 88))

            msg = "Unknown packet protocol"

            class Contains1024:
                def __eq__(s, other):
                    return isinstance(other, list) and 1024 in other

            kwargs = {"wanted": 1, "available": Contains1024()}
            with assertRaises(BadConversion, msg, **kwargs):
                with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                    Messages.get_packet_type(data, protocol_register)

            packet_type.assert_called_once_with(data)

        it "converts str to bytes", protocol_register, TestMessages:
            data = "AA"
            asbytes = binascii.unhexlify(data)
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 78))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, protocol_register)
                assert info == (1024, 78, LIFXPacket, TestMessages.One, asbytes)

            packet_type.assert_called_once_with(asbytes)

    describe "create":
        it "works", protocol_register, TestMessages:
            bts = TestMessages.One(source=1, sequence=2, target="d073d5000001", one="bl").pack()
            pkt = Messages.create(bts, protocol_register)

            assert pkt | TestMessages.One, pkt.__class__
            assert pkt.one == "bl"
            assert pkt.pack() == bts

        it "works with unknown packet", protocol_register:
            bts = LIFXPacket(
                pkt_type=100, source=1, sequence=2, target="d073d5000001", payload="AA"
            ).pack()
            pkt = Messages.create(bts, protocol_register, unknown_ok=True)

            assert isinstance(pkt, LIFXPacket)
            assert pkt.payload == binascii.unhexlify("AA")
            assert pkt.pack() == bts

        it "creates PacketKls if we have one", protocol_register:
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls")
            kls.create.return_value = res

            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, kls, data)

            with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                assert Messages.create(data, protocol_register) is res

            kls.create.assert_called_once_with(data)
            get_packet_type.assert_called_once_with(data, protocol_register)

        it "creates Packet if we no PacketKls", protocol_register:
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls")
            kls.create.return_value = res

            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, kls, None, data)

            with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                assert Messages.create(data, protocol_register, unknown_ok=True) is res

            kls.create.assert_called_once_with(data)
            get_packet_type.assert_called_once_with(data, protocol_register)

        it "complains if unknown and unknown_ok is False", protocol_register:
            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, None, data)

            msg = "Unknown message type!"
            with assertRaises(BadConversion, msg, protocol=1024, pkt_type=78):
                with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                    Messages.create(data, protocol_register, unknown_ok=False)

            get_packet_type.assert_called_once_with(data, protocol_register)

    describe "pack_payload":
        it "works", protocol_register, TestMessages:
            bts = TestMessages.One(one="sh").payload.pack()

            data = {"one": "sh"}
            mr = protocol_register.message_register(1024)
            assert Messages.pack_payload(78, data, mr) == bts

            assert TestMessages.pack_payload(78, data) == bts

        it "complains if the message_type is unknown", protocol_register:
            data = mock.Mock(name="data")
            with assertRaises(BadConversion, "Unknown message type!", pkt_type=87):
                Messages.pack_payload(87, data, protocol_register.message_register(1024))

    describe "pack":
        it "works", protocol_register, TestMessages:
            data = {
                "protocol": 1024,
                "pkt_type": 78,
                "one": "ii",
                "source": 4,
                "sequence": 1,
                "target": "d073d5000001",
            }
            bts = TestMessages.One.create(**data).pack()
            assert Messages.pack(data, protocol_register) == bts

        it "works with unknown packet", protocol_register:
            data = {
                "protocol": 1024,
                "pkt_type": 87,
                "payload": "AA",
                "source": 4,
                "sequence": 1,
                "target": "d073d5000001",
            }
            bts = LIFXPacket.create(**data).pack()
            assert Messages.pack(data, protocol_register, unknown_ok=True) == bts

        it "works out packet type and packs when you have a PacketKls", protocol_register:
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls")
            pkt = mock.Mock(name="pkt")
            pkt.pack.return_value = res
            kls.create.return_value = pkt

            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, kls, data)

            with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                assert Messages.pack(data, protocol_register) is res

            kls.create.assert_called_once_with(data)
            pkt.pack.assert_called_once_with()
            get_packet_type.assert_called_once_with(data, protocol_register)

        it "works out packet type and packs when you have don't have PacketKls but unknown is ok", protocol_register:
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls")
            pkt = mock.Mock(name="pkt")
            pkt.pack.return_value = res
            kls.create.return_value = pkt

            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, kls, None, data)

            with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                assert Messages.pack(data, protocol_register, unknown_ok=True) is res

            kls.create.assert_called_once_with(data)
            pkt.pack.assert_called_once_with()
            get_packet_type.assert_called_once_with(data, protocol_register)

        it "complains if not unknown_ok and no PacketKls", protocol_register:
            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, None, data)

            msg = "Unknown message type!"
            with assertRaises(BadConversion, msg, protocol=1024, pkt_type=78):
                with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                    Messages.pack(data, protocol_register, unknown_ok=False)

            get_packet_type.assert_called_once_with(data, protocol_register)
