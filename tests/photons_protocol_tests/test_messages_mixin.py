# coding: spec

from photons_protocol.messages import MessagesMixin, Messages
from photons_protocol.errors import BadConversion
from photons_protocol.types import Type as T

from photons_app.test_helpers import TestCase
from photons_app.registers import ProtocolRegister

from photons_messages import LIFXPacket

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
from bitarray import bitarray
import binascii
import struct
import mock

describe TestCase, "MessagesMixin":
    before_each:
        self.protocol_register = ProtocolRegister()
        self.protocol_register.add(1024, LIFXPacket)
        self.protocol_register.message_register(1024).add(Messages)

        msg = LIFXPacket.message

        class M(Messages):
            One = msg(78
                , ("one", T.String(16))
                )

            Two = msg(99)

            Three = msg(98
                , ("three", T.Int8.transform(
                      lambda _, v: v + 5
                    , lambda v: v - 5
                    )
                  )
                )

        self.M = M

    describe "get_message_type":
        it "returns from a str, bytes or bitarray":
            msg = self.M.One(one="wa", source=1, sequence=1, target=None)
            payload = msg.payload.pack().tobytes()

            for val in (msg.pack(), msg.pack().tobytes(), binascii.hexlify(msg.pack().tobytes()).decode()):
                res = Messages.get_message_type(val, self.protocol_register)
                self.assertEqual(res, (78, LIFXPacket, None, mock.ANY))

                pkt = res[-1]
                self.assertEqual(pkt.payload, payload)
                self.assertIs(type(pkt), LIFXPacket)
                self.assertEqual(pkt.pack(), msg.pack())

        it "returns kls for found message_type ":
            self.protocol_register.message_register(1024).add(self.M)

            msg = self.M.One(one="wa", source=1, sequence=1, target=None)
            for val in (msg.pack(), msg.pack().tobytes(), binascii.hexlify(msg.pack().tobytes()).decode()):
                res = Messages.get_message_type(val, self.protocol_register)
                self.assertEqual(res, (78, LIFXPacket, self.M.One, mock.ANY))

                pkt = res[-1]
                self.assertIs(type(pkt), LIFXPacket)
                self.assertEqual(pkt.pack(), msg.pack())

        it "complains if we should have a payload and the data has none":
            self.protocol_register.message_register(1024).add(self.M)

            msg = self.M.One(one="wa", source=1, sequence=1, target=None)
            packd = msg.pack()[:-16]

            for val in (packd, packd.tobytes(), binascii.hexlify(packd.tobytes()).decode()):
                with self.fuzzyAssertRaisesError(BadConversion, "packet had no payload"):
                    Messages.get_message_type(val, self.protocol_register)

        it "does not complain if there are no fields on the payload":
            self.protocol_register.message_register(1024).add(self.M)

            msg = self.M.Two(source=1, sequence=1, target=None)
            packd = msg.pack()

            for val in (packd, packd.tobytes(), binascii.hexlify(packd.tobytes()).decode()):
                res = Messages.get_message_type(val, self.protocol_register)
                self.assertIs(res[-2], self.M.Two)

        it "complains if the protocol is unknown":
            msg = self.M.Two(protocol=65, source=1, sequence=1, target=None)
            packd = msg.pack()
            for val in (packd, packd.tobytes(), binascii.hexlify(packd.tobytes()).decode()):
                with self.fuzzyAssertRaisesError(BadConversion, "Unknown packet protocol", wanted=65, available=[1024]):
                    Messages.get_message_type(val, self.protocol_register)

    describe "unpack_pkt":
        it "creates an instance of the PacketKls from our instance of pkt":
            payload = self.M.One.Payload(one="yu").pack()
            pkt = LIFXPacket(payload=payload, source=1, sequence=1, target=None)

            unpackd = Messages.unpack_pkt(self.M.One, pkt)
            self.assertEqual(unpackd.payload.as_dict(), {"one": "yu"})

            self.assertEqual(sorted(unpackd.items())
                , sorted(
                      [ ('ack_required', sb.NotSpecified)
                      , ('addressable', sb.NotSpecified)
                      , ('one', b'yu')
                      , ('pkt_type', sb.NotSpecified)
                      , ('protocol', sb.NotSpecified)
                      , ('res_required', sb.NotSpecified)
                      , ('reserved1', sb.NotSpecified)
                      , ('reserved2', sb.NotSpecified)
                      , ('reserved3', sb.NotSpecified)
                      , ('reserved4', sb.NotSpecified)
                      , ('reserved5', sb.NotSpecified)
                      , ('sequence', 1)
                      , ('size', sb.NotSpecified)
                      , ('source', 1)
                      , ('tagged', sb.NotSpecified)
                      , ('target', None)
                      ]
                   )
                )

            self.assertEqual(unpackd.as_dict()
                , { 'frame_header':
                    { 'size': 38
                    , 'protocol': 1024
                    , 'addressable': True
                    , 'tagged': False
                    , 'reserved1': sb.NotSpecified
                    , 'source': 1
                    }
                  , 'frame_address':
                    { 'target': b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    , 'reserved2': sb.NotSpecified
                    , 'res_required': True
                    , 'ack_required': True
                    , 'reserved3': sb.NotSpecified
                    , 'sequence': 1
                    }
                  , 'protocol_header':
                    { 'reserved4': 0
                    , 'pkt_type': 78
                    , 'reserved5': sb.NotSpecified
                    }
                  , 'payload': { 'one': 'yu' }
                  }
                )

        it "creates an instance that's already filled out if original pkt is all filled out":
            pkt = self.M.One(one="yu", source=1, sequence=1, target=None)
            simplified = pkt.simplify()
            self.assertIs(type(simplified), LIFXPacket)

            unpackd = Messages.unpack_pkt(self.M.One, simplified)
            self.assertEqual(unpackd.payload.as_dict(), {"one": "yu"})

            self.assertEqual(sorted(unpackd.items())
                , sorted(
                      [ ('ack_required', True)
                      , ('addressable', True)
                      , ('one', b'yu')
                      , ('pkt_type', 78)
                      , ('protocol', 1024)
                      , ('res_required', True)
                      , ('reserved1', sb.NotSpecified)
                      , ('reserved2', sb.NotSpecified)
                      , ('reserved3', sb.NotSpecified)
                      , ('reserved4', 0)
                      , ('reserved5', sb.NotSpecified)
                      , ('sequence', 1)
                      , ('size', 38)
                      , ('source', 1)
                      , ('tagged', False)
                      , ('target', bitarray('0' * 64).tobytes())
                      ]
                   )
                )

            self.assertEqual(unpackd.as_dict()
                , { 'frame_header':
                    { 'size': 38
                    , 'protocol': 1024
                    , 'addressable': True
                    , 'tagged': False
                    , 'reserved1': sb.NotSpecified
                    , 'source': 1
                    }
                  , 'frame_address':
                    { 'target': b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    , 'reserved2': sb.NotSpecified
                    , 'res_required': True
                    , 'ack_required': True
                    , 'reserved3': sb.NotSpecified
                    , 'sequence': 1
                    }
                  , 'protocol_header':
                    { 'reserved4': 0
                    , 'pkt_type': 78
                    , 'reserved5': sb.NotSpecified
                    }
                  , 'payload': { 'one': 'yu' }
                  }
                )

    describe "unpack":
        before_each:
            self.message_type = mock.Mock(name='message_type')
            self.Packet = mock.Mock(name="Packet")
            self.PacketKls = mock.Mock(name="PacketKls")
            self.pkt = mock.Mock(name="pkt")

            self.get_message_type = mock.Mock(name="get_message_type")
            self.unpack_pkt = mock.Mock(name="unpack_pkt")

            self.data = mock.Mock(name="data")

        it "uses get_message_type and unpack_pkt":
            self.get_message_type.return_value = (self.message_type, self.Packet, self.PacketKls, self.pkt)

            val = mock.Mock(name='val')
            self.unpack_pkt.return_value = val

            with mock.patch.object(Messages, "get_message_type", self.get_message_type):
                with mock.patch.object(Messages, "unpack_pkt", self.unpack_pkt):
                    self.assertIs(Messages.unpack(self.data, self.protocol_register), val)

            self.get_message_type.assert_called_once_with(self.data, self.protocol_register)
            self.unpack_pkt.assert_called_once_with(self.PacketKls, self.pkt)

        it "returns pkt if unknown_ok and no PacketKls":
            self.get_message_type.return_value = (self.message_type, self.Packet, None, self.pkt)

            with mock.patch.object(Messages, "get_message_type", self.get_message_type):
                with mock.patch.object(Messages, "unpack_pkt", self.unpack_pkt):
                    self.assertIs(Messages.unpack(self.data, self.protocol_register, unknown_ok=True), self.pkt)

            self.get_message_type.assert_called_once_with(self.data, self.protocol_register)
            self.assertEqual(len(self.unpack_pkt.mock_calls), 0)

        it "complains if not unknown_ok and no PacketKls":
            self.get_message_type.return_value = (self.message_type, self.Packet, None, self.pkt)

            with mock.patch.object(Messages, "get_message_type", self.get_message_type):
                with mock.patch.object(Messages, "unpack_pkt", self.unpack_pkt):
                    with self.fuzzyAssertRaisesError(BadConversion, "Unknown message type!", pkt_type=self.message_type):
                        Messages.unpack(self.data, self.protocol_register, unknown_ok=False)

            self.get_message_type.assert_called_once_with(self.data, self.protocol_register)
            self.assertEqual(len(self.unpack_pkt.mock_calls), 0)

        it "works":
            self.protocol_register.message_register(1024).add(self.M)
            packd = self.M.One(one="iu", source=1, sequence=1, target=None).pack()
            res = Messages.unpack(packd, self.protocol_register)
            self.assertEqual(res.pack(), packd)
            self.assertEqual(res.payload.as_dict(), {"one": "iu"})

    describe "pack_payload":
        it "complains if it can't find the message_type":
            data = {"one": "po"}
            message_type = 90

            with self.fuzzyAssertRaisesError(BadConversion, "Unknown message type!", pkt_type=90):
                Messages.pack_payload(message_type, data)

            with self.fuzzyAssertRaisesError(BadConversion, "Unknown message type!", pkt_type=90):
                Messages.pack_payload(message_type, data, messages_register=self.protocol_register.message_register(1024))

        it "fills out the Payload and packs it for us when on kls":
            packd = self.M.One.Payload(one="po").pack()
            res = self.M.pack_payload(78, {"one": "po"})
            self.assertEqual(packd, res)

        it "fills out the Payload and packs it for us when on a kls in provided messages_register":
            self.protocol_register.message_register(1024).add(self.M)
            packd = self.M.One.Payload(one="po").pack()
            res = Messages.pack_payload(78, {"one": "po"}, messages_register=self.protocol_register.message_register(1024))
            self.assertEqual(packd, res)

        it "fills out the Payload and packs it for us":
            packd = mock.Mock(name="packd")
            normalised = mock.Mock(name="normalised")

            a = mock.Mock(name="a")
            b = mock.Mock(name="b")

            class P:
                Payload = mock.Mock(name="Payload")

            P.Payload.normalise.return_value = normalised
            normalised.pack.return_value = packd

            class M2:
                by_type = {78: P}

            messages_register = [M2]

            res = Messages.pack_payload(78, {"a": a, "b": b}, messages_register=messages_register)
            self.assertEqual(packd, packd)

            P.Payload.normalise.assert_called_once_with(mock.ANY, {"a": a, "b": b})
            normalised.pack.assert_called_once_with()

        it "works with transformed values":
            self.protocol_register.message_register(1024).add(self.M)
            packd = self.M.Three.Payload(three=10).pack()

            bts = packd.tobytes()
            self.assertEqual(struct.unpack("<b", bts)[0], 15)

            res = self.M.pack_payload(98, {"three": 10})
            self.assertEqual(res, packd)

            res2 = self.M.Three.Payload.unpack(res)
            self.assertEqual(res2.three, 10)
            self.assertEqual(res2.actual("three"), 15)

    describe "pack":
        it "works when the fields are not grouped":
            self.protocol_register.message_register(1024).add(self.M)
            pkt = self.M.Three(three=10, source=1, sequence=1, target=None)
            packd = pkt.pack()

            dct = {}
            for name in pkt.Meta.all_names:
                dct[name] = pkt[name]

            res = Messages.pack(dct, self.protocol_register)
            self.assertEqual(res, packd)

        it "works when the fields are grouped":
            self.protocol_register.message_register(1024).add(self.M)
            pkt = self.M.Three(three=10, source=1, sequence=1, target=None)
            packd = pkt.pack()

            dct = pkt.as_dict()
            self.assertEqual(list(dct.keys()), list(pkt.Meta.groups.keys()) )

            res = Messages.pack(dct, self.protocol_register)
            self.assertEqual(res, packd)

        it "complains if it can't find the message_type":
            for val in ({}, {"protocol_header": {}}):
                with self.fuzzyAssertRaisesError(BadConversion, "Don't know how to pack this dictionary, it doesn't specify a pkt_type!"):
                    Messages.pack(val, self.protocol_register)

        it "complains if it can't find the protocol in the data":
            for val in ({"pkt_type": 7}, {"protocol_header": {"pkt_type": 7}}):
                with self.fuzzyAssertRaisesError(BadConversion, "Don't know how to pack this dictionary, it doesn't specify a protocol!"):
                    Messages.pack(val, self.protocol_register)

        it "complains if it can't find the protocol in the protocol_register":
            for val in ({"pkt_type": 7, "protocol": 76}, {"protocol_header": {"pkt_type": 7}, "frame_header": {"protocol": 76}}):
                with self.fuzzyAssertRaisesError(BadConversion, "Unknown packet protocol", wanted=76, available=[1024]):
                    Messages.pack(val, self.protocol_register)

        it "complains if unknown packet":
            data = {"pkt_type": 8, "protocol": 1024}
            with self.fuzzyAssertRaisesError(BadConversion, "Unknown message type!", pkt_type=8):
                Messages.pack(data, self.protocol_register)

        it "uses parent_packet to pack if unknown_ok and message_type isn't found":
            pkt = self.M.Three(three=10, source=1, sequence=1, target=None)
            payload = pkt.payload.pack()

            # For LIFXPacket to work, the payload must already be bitarray like
            val = pkt.as_dict()
            val["payload"] = payload

            res = Messages.pack(val, self.protocol_register, unknown_ok=True)
            self.assertEqual(res, pkt.pack())
