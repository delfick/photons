# coding: spec

from photons_protocol.messages import Messages, PacketTypeExtractor, sources_for
from photons_protocol.errors import BadConversion
from photons_protocol.types import Type as T

from photons_app.registers import ProtocolRegister
from photons_app.test_helpers import TestCase

from photons_messages import LIFXPacket

from noseOfYeti.tokeniser.support import noy_sup_setUp
from delfick_project.norms import Meta
from bitarray import bitarray
from textwrap import dedent
from unittest import mock
import binascii

msg = LIFXPacket.message


class M(Messages):
    # fmt:off
    One = msg(78
        , ("one", T.String(16))
        )

    Two = msg(99)

    Three = msg(98
        , ("three", T.Int8.transform(lambda _, v: v + 5, lambda _, v: v - 5))
        )
    # fmt:on


def ba(thing):
    b = bitarray(endian="little")
    b.frombytes(thing)
    return b


describe TestCase, "PacketTypeExtractor":
    describe "packet_type":
        it "delegates for dicts":
            res = mock.Mock(name="res")
            packet_type_from_dict = mock.Mock(name="packet_type_from_dict", return_value=res)

            data = {}
            with mock.patch.object(
                PacketTypeExtractor, "packet_type_from_dict", packet_type_from_dict
            ):
                self.assertIs(PacketTypeExtractor.packet_type(data), res)

            packet_type_from_dict.assert_called_once_with(data)

        it "delegates for bytes":
            res = mock.Mock(name="res")
            packet_type_from_bytes = mock.Mock(name="packet_type_from_bytes", return_value=res)

            data = b"AA"
            with mock.patch.object(
                PacketTypeExtractor, "packet_type_from_bytes", packet_type_from_bytes
            ):
                self.assertIs(PacketTypeExtractor.packet_type(data), res)

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
                self.assertIs(PacketTypeExtractor.packet_type(data), res)

            packet_type_from_bitarray.assert_called_once_with(data)

        it "otherwise complains":
            for data in (0, 1, True, False, None, [], [1], lambda: True):
                msg = "Can't determine packet type from data"
                with self.fuzzyAssertRaisesError(BadConversion, msg, got=data):
                    PacketTypeExtractor.packet_type(data)

    describe "packet_type_from_dict":
        it "can get pkt_type and protocol directory from data":
            data = {"pkt_type": 45, "protocol": 1024}
            self.assertEqual(PacketTypeExtractor.packet_type_from_dict(data), (1024, 45))

        it "can get pkt_type and protocol from groups":
            data = {"protocol_header": {"pkt_type": 45}, "frame_header": {"protocol": 1024}}
            self.assertEqual(PacketTypeExtractor.packet_type_from_dict(data), (1024, 45))

        it "complains if it can't get protocol":
            msg = "Couldn't work out protocol from dictionary"

            data = {}
            with self.fuzzyAssertRaisesError(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

            data = {"frame_header": {}}
            with self.fuzzyAssertRaisesError(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

        it "complains if it can't get pkt_type":
            msg = "Couldn't work out pkt_type from dictionary"

            data = {"protocol": 1024}
            with self.fuzzyAssertRaisesError(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

            data = {"protocol": 1024, "protocol_header": {}}
            with self.fuzzyAssertRaisesError(BadConversion, msg, got=data):
                PacketTypeExtractor.packet_type_from_dict(data)

    describe "packet_type_from_bitarray and bytes":
        it "complains if the length isn't correct":
            msg = "Data is too small to be a LIFX packet"

            bts = b""
            with self.fuzzyAssertRaisesError(BadConversion, msg, got=0):
                PacketTypeExtractor.packet_type_from_bytes(bts)
            with self.fuzzyAssertRaisesError(BadConversion, msg, got=0):
                PacketTypeExtractor.packet_type_from_bitarray(ba(bts))

            bts = LIFXPacket.empty_normalise(source=1, sequence=1, target=None).pack().tobytes()
            PacketTypeExtractor.packet_type_from_bytes(bts)
            PacketTypeExtractor.packet_type_from_bitarray(ba(bts))

            with self.fuzzyAssertRaisesError(BadConversion, msg, need_atleast=36, got=20):
                PacketTypeExtractor.packet_type_from_bytes(bts[:20])
            with self.fuzzyAssertRaisesError(BadConversion, msg, need_atleast=36, got=20):
                PacketTypeExtractor.packet_type_from_bitarray(ba(bts[:20]))

        it "returns None pkt_type if protocol is unknown":
            pkt = LIFXPacket.empty_normalise(
                protocol=234,
                pkt_type=15,
                addressable=True,
                tagged=True,
                source=1,
                sequence=1,
                target=None,
            )

            protocol, pkt_type = PacketTypeExtractor.packet_type_from_bytes(pkt.pack().tobytes())
            self.assertEqual(protocol, 234)
            self.assertEqual(pkt_type, None)

            protocol, pkt_type = PacketTypeExtractor.packet_type_from_bitarray(pkt.pack())
            self.assertEqual(protocol, 234)
            self.assertEqual(pkt_type, None)

        it "successfully gets protocol and pkt_type for 1024":
            pkt = LIFXPacket.empty_normalise(
                protocol=1024,
                pkt_type=78,
                addressable=True,
                tagged=True,
                source=1,
                sequence=1,
                target=None,
            )

            protocol, pkt_type = PacketTypeExtractor.packet_type_from_bytes(pkt.pack().tobytes())
            self.assertEqual(protocol, 1024)
            self.assertEqual(pkt_type, 78)

            protocol, pkt_type = PacketTypeExtractor.packet_type_from_bitarray(pkt.pack())
            self.assertEqual(protocol, 1024)
            self.assertEqual(pkt_type, 78)

describe TestCase, "sources_for":
    it "can get the source for packets":
        result = list(sources_for(M))

        self.assertEqual(len(result), 3)

        self.assertEqual(result[0][0], "One")
        self.assertEqual(result[1][0], "Two")
        self.assertEqual(result[2][0], "Three")

        one = """
        One = msg(78
            , ("one", T.String(16))
            )
        """

        self.assertEqual(result[0][1], dedent(one).lstrip())

        two = "Two = msg(99)\n"

        self.assertEqual(result[1][1], two)

        three = """
        Three = msg(98
            , ("three", T.Int8.transform(lambda _, v: v + 5, lambda _, v: v - 5))
            )
        """

        self.assertEqual(result[2][1], dedent(three).lstrip())

describe TestCase, "MessagesMixin":
    before_each:
        self.protocol_register = ProtocolRegister()
        self.protocol_register.add(1024, LIFXPacket)
        self.protocol_register.message_register(1024).add(M)

    describe "get_packet_type":

        it "can get us information about our data":
            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 78))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, self.protocol_register)
                self.assertEqual(info, (1024, 78, LIFXPacket, M.One, data))

            packet_type.assert_called_once_with(data)

            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 99))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, self.protocol_register)
                self.assertEqual(info, (1024, 99, LIFXPacket, M.Two, data))

            packet_type.assert_called_once_with(data)

        it "can get us information about unknown pkt types (known protocol)":
            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 88))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, self.protocol_register)
                self.assertEqual(info, (1024, 88, LIFXPacket, None, data))

            packet_type.assert_called_once_with(data)

        it "complains about unknown protocols":
            data = mock.Mock(name="data")
            packet_type = mock.Mock(name="packet_type", return_value=(1, 88))

            msg = "Unknown packet protocol"
            kwargs = {"wanted": 1, "available": [1024]}
            with self.fuzzyAssertRaisesError(BadConversion, msg, **kwargs):
                with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                    Messages.get_packet_type(data, self.protocol_register)

            packet_type.assert_called_once_with(data)

        it "converts str to bytes":
            data = "AA"
            asbytes = binascii.unhexlify(data)
            packet_type = mock.Mock(name="packet_type", return_value=(1024, 78))

            with mock.patch.object(PacketTypeExtractor, "packet_type", packet_type):
                info = Messages.get_packet_type(data, self.protocol_register)
                self.assertEqual(info, (1024, 78, LIFXPacket, M.One, asbytes))

            packet_type.assert_called_once_with(asbytes)

    describe "unpack":
        it "works":
            bts = M.One(source=1, sequence=2, target="d073d5000001", one="bl").pack()
            pkt = Messages.unpack(bts, self.protocol_register)

            assert pkt | M.One, pkt.__class__
            self.assertEqual(pkt.one, "bl")
            self.assertEqual(pkt.pack(), bts)

        it "works with unknown packet":
            bts = LIFXPacket(
                pkt_type=100, source=1, sequence=2, target="d073d5000001", payload="AA"
            ).pack()
            pkt = Messages.unpack(bts, self.protocol_register, unknown_ok=True)

            self.assertIsInstance(pkt, LIFXPacket)
            self.assertEqual(pkt.payload, binascii.unhexlify("AA"))
            self.assertEqual(pkt.pack(), bts)

        it "unpacks PacketKls if we have one":
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls")
            kls.unpack.return_value = res

            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, kls, data)

            with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                self.assertIs(Messages.unpack(data, self.protocol_register), res)

            kls.unpack.assert_called_once_with(data)
            get_packet_type.assert_called_once_with(data, self.protocol_register)

        it "unpacks Packet if we no PacketKls":
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls")
            kls.unpack.return_value = res

            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, kls, None, data)

            with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                self.assertIs(Messages.unpack(data, self.protocol_register, unknown_ok=True), res)

            kls.unpack.assert_called_once_with(data)
            get_packet_type.assert_called_once_with(data, self.protocol_register)

        it "complains if unknown and unknown_ok is False":
            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, None, data)

            msg = "Unknown message type!"
            with self.fuzzyAssertRaisesError(BadConversion, msg, protocol=1024, pkt_type=78):
                with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                    Messages.unpack(data, self.protocol_register, unknown_ok=False)

            get_packet_type.assert_called_once_with(data, self.protocol_register)

    describe "pack_payload":
        it "works":
            bts = M.One(one="sh").payload.pack()

            data = {"one": "sh"}
            mr = self.protocol_register.message_register(1024)
            self.assertEqual(Messages.pack_payload(78, data, mr), bts)

            self.assertEqual(M.pack_payload(78, data), bts)

        it "complains if the message_type is unknown":
            data = mock.Mock(name="data")
            with self.fuzzyAssertRaisesError(BadConversion, "Unknown message type!", pkt_type=87):
                Messages.pack_payload(87, data, self.protocol_register.message_register(1024))

    describe "pack":
        it "works":
            data = {
                "protocol": 1024,
                "pkt_type": 78,
                "one": "ii",
                "source": 4,
                "sequence": 1,
                "target": "d073d5000001",
            }
            bts = M.One.empty_normalise(**data).pack()
            self.assertEqual(Messages.pack(data, self.protocol_register), bts)

        it "works with unknown packet":
            data = {
                "protocol": 1024,
                "pkt_type": 87,
                "payload": "AA",
                "source": 4,
                "sequence": 1,
                "target": "d073d5000001",
            }
            bts = LIFXPacket.empty_normalise(**data).pack()
            self.assertEqual(Messages.pack(data, self.protocol_register, unknown_ok=True), bts)

        it "works out packet type and packs when you have a PacketKls":
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls")
            pkt = mock.Mock(name="pkt")
            pkt.pack.return_value = res
            kls.normalise.return_value = pkt

            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, kls, data)

            with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                self.assertIs(Messages.pack(data, self.protocol_register), res)

            kls.normalise.assert_called_once_with(Meta.empty(), data)
            pkt.pack.assert_called_once_with()
            get_packet_type.assert_called_once_with(data, self.protocol_register)

        it "works out packet type and packs when you have don't have PacketKls but unknown is ok":
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls")
            pkt = mock.Mock(name="pkt")
            pkt.pack.return_value = res
            kls.normalise.return_value = pkt

            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, kls, None, data)

            with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                self.assertIs(Messages.pack(data, self.protocol_register, unknown_ok=True), res)

            kls.normalise.assert_called_once_with(Meta.empty(), data)
            pkt.pack.assert_called_once_with()
            get_packet_type.assert_called_once_with(data, self.protocol_register)

        it "complains if not unknown_ok and no PacketKls":
            data = mock.Mock(name="data")

            get_packet_type = mock.Mock(name="get_packet_type")
            get_packet_type.return_value = (1024, 78, LIFXPacket, None, data)

            msg = "Unknown message type!"
            with self.fuzzyAssertRaisesError(BadConversion, msg, protocol=1024, pkt_type=78):
                with mock.patch.object(Messages, "get_packet_type", get_packet_type):
                    Messages.pack(data, self.protocol_register, unknown_ok=False)

            get_packet_type.assert_called_once_with(data, self.protocol_register)
