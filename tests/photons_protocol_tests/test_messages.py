# coding: spec

from photons_protocol.messages import Messages
from photons_protocol.frame import LIFXPacket
from photons_protocol.types import Type as T

from photons_app.test_helpers import TestCase

import mock

describe TestCase, "MessagesMeta":
    it "calls any _lifx_packet_message attribute with the name and put onto resulting kls":
        omsg = mock.Mock(name="omsg")
        tmsg = mock.Mock(name="tmsg")

        one_msg = mock.Mock(name='one', _lifx_packet_message=True, return_value = omsg)
        two_msg = mock.Mock(name='two', _lifx_packet_message=True, return_value = tmsg)

        three_msg = mock.Mock(name="three", _lifx_packet_message=False)
        four_msg = mock.Mock(name="four", spec=[])

        class M(Messages):
            one = one_msg
            two = two_msg
            three = three_msg
            four = four_msg

        self.assertIs(M.one, omsg)
        self.assertIs(M.two, tmsg)
        self.assertIs(M.three, three_msg)
        self.assertIs(M.four, four_msg)

        one_msg.assert_called_once_with("one")
        two_msg.assert_called_once_with("two")

    it "creates a by_type record":
        omsg = mock.Mock(name="omsg")
        tmsg = mock.Mock(name="tmsg")

        one_msg = mock.Mock(name='one', _lifx_packet_message=True, return_value = omsg)
        two_msg = mock.Mock(name='two', _lifx_packet_message=True, return_value = tmsg)

        three_msg = mock.Mock(name="three", _lifx_packet_message=False)
        four_msg = mock.Mock(name="four", spec=[])

        class M(Messages):
            one = one_msg
            two = two_msg
            three = three_msg
            four = four_msg

        self.assertEqual(M.by_type
            , { omsg.Payload.message_type: omsg
              , tmsg.Payload.message_type: tmsg
              , three_msg.Payload.message_type: three_msg
              }
            )

    it "has the MessagesMixin":
        class M(Messages):
            pass

        assert hasattr(M, "pack")
        assert hasattr(M, "unpack")

    it "works with LIFXPacket":
        msg = LIFXPacket.message

        class M(Messages):
            One = msg(42
                , ("one", T.Int8)
                )

            Two = One.using(46)

        class M2(Messages):
            Three = M.One

        self.assertEqual(M.by_type
            , { 42: M.One
              , 46: M.Two
              }
            )

        self.assertEqual(M2.by_type
            , { 42: M.One
              }
            )

        o = M.One(one=27)
        self.assertEqual(o.one, 27)
        self.assertEqual(o.size, 37)
        self.assertEqual(o.pkt_type, 42)

        t = M2.Three(one=57)
        self.assertEqual(t.one, 57)
        self.assertEqual(t.size, 37)
        self.assertEqual(t.pkt_type, 42)
