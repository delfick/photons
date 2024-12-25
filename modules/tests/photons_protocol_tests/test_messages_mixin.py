import binascii
from textwrap import dedent
from unittest import mock

import pytest
from bitarray import bitarray
from delfick_project.errors_pytest import assertRaises
from photons_app.registers import ProtocolRegister
from photons_messages import LIFXPacket
from photons_protocol.errors import BadConversion
from photons_protocol.messages import Messages, PacketTypeExtractor, sources_for

msg = LIFXPacket.message


def ba(thing):
    b = bitarray(endian="little")
    b.frombytes(thing)
    return b


class TestPacketTypeExtractor:
    class TestPacketType:
        def test_it_delegates_for_dicts(self):
            res = mock.Mock(name="res")
            packet_type_from_dict = mock.Mock(name="packet_type_from_dict", return_value=res)

            data = {}
            with mock.patch.object(
                PacketTypeExtractor, "packet_type_from_dict", packet_type_from_dict
            ):
                assert PacketTypeExtractor.packet_type(data) is res

            packet_type_from_dict.assert_called_once_with(data)

        def test_it_delegates_for_bytes(self):
            res = mock.Mock(name="res")
            packet_type_from_bytes = mock.Mock(name="packet_type_from_bytes", return_value=res)

            data = b"AA"
            with mock.patch.object(
                PacketTypeExtractor, "packet_type_from_bytes", packet_type_from_bytes
            ):
                assert PacketTypeExtractor.packet_type(data) is res

            packet_type_from_bytes.assert_called_once_with(data)

        def test_it_delegates_for_bitarray(self):
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

        def test_it_otherwise_complains(self):
            for data in (0, 1, True, False, None, [], [1], lambda: True):
                msg = "Can't determine packet type from data"
                with assertRaises(BadConversion, msg, got=data):
                    PacketTypeExtractor.packet_type(data)

    class TestPacketTypeFromDict:
        def test_it_can_get_pkt_type_and_protocol_directory_from_data(self):
            data = {"pkt_type": 45, "protocol": 1024}
            assert PacketTypeExtractor.packet_type_from_dict(data) == (1024, 45)

        def test_it_can_get_pkt_type_and_protocol_from_groups(self):
            data = {"protocol_header": {"pkt_type": 45}, "frame_header": {"protocol": 1024}}
            assert PacketTypeExtractor.packet_type_from_dict(data) == (1024, 45)

        def test_it_complains_if_it_cant_get_protocol(self):
            msg = "Couldn't work out protocol from dictionary"

            data = {}
            with assertRaises(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

            data = {"frame_header": {}}
            with assertRaises(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

        def test_it_complains_if_it_cant_get_pkt_type(self):
            msg = "Couldn't work out pkt_type from dictionary"

            data = {"protocol": 1024}
            with assertRaises(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

            data = {"protocol": 1024, "protocol_header": {}}
            with assertRaises(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

    class TestPacketTypeFromBitarrayAndBytes:
        def test_it_complains_if_the_length_isnt_correct(self):
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

        def test_it_returns_None_pkt_type_if_protocol_is_unknown(self):
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

        def test_it_successfully_gets_protocol_and_pkt_type_for_1024(self):
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


class TestSourcesFor:
    def test_it_can_get_the_source_for_packets(self, TestMessages):
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


class TestMessagesMixin:

    @pytest.fixture()
    def protocol_register(self, TestMessages):
        protocol_register = ProtocolRegister()
        protocol_register.add(1024, LIFXPacket)
        protocol_register.message_register(1024).add(TestMessages)
        return protocol_register

    class TestGetPacketType:

        def test_it_can_get_us_information_about_our_data(self, protocol_register, TestMessages):
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

        def test_it_can_get_us_information_about_unknown_pkt_types_known_protocol(
            self, protocol_register
        ):
            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 88))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, protocol_register)
                assert info == (1024, 88, LIFXPacket, None, data)

            packet_type.assert_called_once_with(data)

        def test_it_complains_about_unknown_protocols(self, protocol_register):
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

        def test_it_converts_str_to_bytes(self, protocol_register, TestMessages):
            data = "AA"
            asbytes = binascii.unhexlify(data)
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 78))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, protocol_register)
                assert info == (1024, 78, LIFXPacket, TestMessages.One, asbytes)

            packet_type.assert_called_once_with(asbytes)

    class TestCreate:
        def test_it_works(self, protocol_register, TestMessages):
            bts = TestMessages.One(source=1, sequence=2, target="d073d5000001", one="bl").pack()
            pkt = Messages.create(bts, protocol_register)

            assert pkt | TestMessages.One, pkt.__class__
            assert pkt.one == "bl"
            assert pkt.pack() == bts

        def test_it_works_with_unknown_packet(self, protocol_register):
            bts = LIFXPacket(
                pkt_type=100, source=1, sequence=2, target="d073d5000001", payload="AA"
            ).pack()
            pkt = Messages.create(bts, protocol_register, unknown_ok=True)

            assert isinstance(pkt, LIFXPacket)
            assert pkt.payload == binascii.unhexlify("AA")
            assert pkt.pack() == bts

        def test_it_creates_PacketKls_if_we_have_one(self, protocol_register):
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

        def test_it_creates_Packet_if_we_no_PacketKls(self, protocol_register):
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

        def test_it_complains_if_unknown_and_unknown_ok_is_False(self, protocol_register):
            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, None, data)

            msg = "Unknown message type!"
            with assertRaises(BadConversion, msg, protocol=1024, pkt_type=78):
                with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                    Messages.create(data, protocol_register, unknown_ok=False)

            get_packet_type.assert_called_once_with(data, protocol_register)

    class TestPackPayload:
        def test_it_works(self, protocol_register, TestMessages):
            bts = TestMessages.One(one="sh").payload.pack()

            data = {"one": "sh"}
            mr = protocol_register.message_register(1024)
            assert Messages.pack_payload(78, data, mr) == bts

            assert TestMessages.pack_payload(78, data) == bts

        def test_it_complains_if_the_message_type_is_unknown(self, protocol_register):
            data = mock.Mock(name="data")
            with assertRaises(BadConversion, "Unknown message type!", pkt_type=87):
                Messages.pack_payload(87, data, protocol_register.message_register(1024))

    class TestPack:
        def test_it_works(self, protocol_register, TestMessages):
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

        def test_it_works_with_unknown_packet(self, protocol_register):
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

        def test_it_works_out_packet_type_and_packs_when_you_have_a_PacketKls(
            self, protocol_register
        ):
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

        def test_it_works_out_packet_type_and_packs_when_you_have_dont_have_PacketKls_but_unknown_is_ok(
            self, protocol_register
        ):
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

        def test_it_complains_if_not_unknown_ok_and_no_PacketKls(self, protocol_register):
            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, None, data)

            msg = "Unknown message type!"
            with assertRaises(BadConversion, msg, protocol=1024, pkt_type=78):
                with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                    Messages.pack(data, protocol_register, unknown_ok=False)

            get_packet_type.assert_called_once_with(data, protocol_register)
