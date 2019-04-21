# coding: spec

from photons_transport.target.receiver import Receiver

from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import binascii
import asyncio
import random

describe AsyncTestCase, "Receiver":
    async it "inits some variables":
        receiver = Receiver()
        self.assertIs(receiver.loop, self.loop)
        self.assertEqual(receiver.results, {})
        self.assertEqual(receiver.blank_target, b'\x00\x00\x00\x00\x00\x00\x00\x00')

    describe "Usage":
        async before_each:
            self.receiver = Receiver()

            self.source = random.randrange(0, 100)
            self.sequence = random.randrange(0, 100)
            self.target = binascii.unhexlify("d073d50000000000")
            self.packet = mock.Mock(name="packet"
                , spec=["source", "sequence", "target"]
                , source = self.source
                , sequence = self.sequence
                , target = self.target
                )

            self.addr = mock.Mock(name="addr")
            self.broadcast = mock.Mock(name="broadcast")

            self.result = asyncio.Future()
            self.result.add_packet = mock.Mock(name="add_packet")

        describe "register":
            async def assertRegister(self, key, expect_zero=False):
                self.assertEqual(self.receiver.results, {})
                self.receiver.register(self.packet, self.result, expect_zero=expect_zero)

                loop = mock.Mock(name="loop")
                fut = asyncio.Future()
                other = mock.Mock(name="other")
                called = []

                def call_later(t, cb):
                    called.append("call_later")

                    self.assertEqual(t, 0.5)
                    self.assertEqual(self.receiver.results, {key: self.result})

                    self.receiver.results["other"] = other
                    cb()
                    fut.set_result(True)
                loop.call_later.side_effect = call_later

                with mock.patch.object(Receiver, "loop", loop):
                    self.assertEqual(called, [])

                    self.result.set_result([])
                    await self.wait_for(fut)

                    self.assertEqual(called, ["call_later"])
                    self.assertEqual(self.receiver.results, {"other": other})

            async it "puts the result under a key of source, sequence, target":
                key = (self.source, self.sequence, self.target)
                await self.assertRegister(key, expect_zero=False)

            async it "puts the result under a key of 0, 0, target if expect_zero":
                key = (0, 0, self.target[:6])
                await self.assertRegister(key, expect_zero=True)

        describe "recv":
            async it "finds result based on source, sequence, target":
                key = (self.source, self.sequence, self.target)
                self.receiver.results[key] = self.result
                self.receiver.recv(self.packet, self.addr, self.broadcast)
                self.result.add_packet.assert_called_once_with(self.packet, self.addr, self.broadcast)

            async it "finds result based on broadcast key if that was used":
                key = (self.source, self.sequence, self.receiver.blank_target)
                self.receiver.results[key] = self.result
                self.receiver.recv(self.packet, self.addr, self.broadcast)
                self.result.add_packet.assert_called_once_with(self.packet, self.addr, self.broadcast)

            async it "finds result based on zero_key if that was used":
                key = (0, 0, binascii.unhexlify("d073d5000001"))
                self.packet.source = 0
                self.packet.sequence = 0
                # The corner case this fulfills means the target may have garbage after [:6]
                self.packet.target = binascii.unhexlify("d073d50000011234")

                self.receiver.results[key] = self.result
                self.receiver.recv(self.packet, self.addr, self.broadcast)
                self.result.add_packet.assert_called_once_with(self.packet, self.addr, self.broadcast)

            async it "does nothing if it can't find the key":
                key = (1, 2, binascii.unhexlify("d073d5000001"))
                self.receiver.results[key] = self.result
                self.receiver.recv(self.packet, self.addr, self.broadcast)
                self.assertEqual(len(self.result.add_packet.mock_calls), 0)

            async it "uses message_catcher if can't find the key and that's defined":
                message_catcher = mock.Mock(name="message_catcher")
                self.receiver.message_catcher = message_catcher
                self.receiver.recv(self.packet, self.addr, self.broadcast)
                message_catcher.assert_called_once_with(self.packet)

            async it "does not use message_catcher if can find the key and that's defined":
                key = (self.source, self.sequence, self.target)
                self.receiver.results[key] = self.result

                message_catcher = mock.Mock(name="message_catcher")
                self.receiver.message_catcher = message_catcher
                self.receiver.recv(self.packet, self.addr, self.broadcast)

                self.result.add_packet.assert_called_once_with(self.packet, self.addr, self.broadcast)
                self.assertEqual(len(message_catcher.mock_calls), 0)

                self.result.add_packet.reset_mock()
                key = (self.source, self.sequence, self.receiver.blank_target)
                self.receiver.results = {key: self.result}

                message_catcher = mock.Mock(name="message_catcher")
                self.receiver.message_catcher = message_catcher
                self.receiver.recv(self.packet, self.addr, self.broadcast)

                self.result.add_packet.assert_called_once_with(self.packet, self.addr, self.broadcast)
                self.assertEqual(len(message_catcher.mock_calls), 0)

        describe "call":
            async it "destructures msg into pkt, msg, broadcast for recv":
                packet = mock.Mock(name="packet", spec=["source", "sequence", "target"])
                msg = (packet, self.addr, self.broadcast)
                recv = mock.Mock(name="recv")

                with mock.patch.object(self.receiver, "recv", recv):
                    self.receiver(msg)

                recv.assert_called_once_with(packet, self.addr, self.broadcast)

            async it "doesn't fail on acks":
                packet = mock.Mock(name="packet"
                    , spec = ["source", "sequence", "target", "represents_ack"]
                    , represents_ack = True
                    )
                msg = (packet, self.addr, self.broadcast)
                recv = mock.Mock(name="recv")

                with mock.patch.object(self.receiver, "recv", recv):
                    self.receiver(msg)

                recv.assert_called_once_with(packet, self.addr, self.broadcast)
