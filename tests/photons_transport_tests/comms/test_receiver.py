# coding: spec

from photons_transport.comms.receiver import Receiver

from photons_app.test_helpers import AsyncTestCase

from photons_messages import LIFXPacket

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
        self.assertEqual(receiver.blank_target, b"\x00\x00\x00\x00\x00\x00\x00\x00")

    describe "Usage":
        async before_each:
            self.receiver = Receiver()

            self.source = random.randrange(0, 100)
            self.sequence = random.randrange(0, 100)
            self.target = binascii.unhexlify("d073d50000000000")
            self.packet = LIFXPacket(
                source=self.source, pkt_type=20, sequence=self.sequence, target=self.target
            )

            self.addr = mock.Mock(name="addr")
            self.original = self.packet.clone()

            self.result = asyncio.Future()
            self.result.add_packet = mock.Mock(name="add_packet")

        def register(self, source, sequence, target):
            packet = LIFXPacket(source=source, sequence=sequence, target=target)

            self.receiver.register(packet, self.result, self.original)
            return (source, sequence, target)

        describe "register":
            async it "puts the result under a key of source, sequence, target":
                self.assertEqual(self.receiver.results, {})
                key = self.register(self.source, self.sequence, self.target)

                loop = mock.Mock(name="loop")
                fut = asyncio.Future()
                other = mock.Mock(name="other")
                called = []

                def call_later(t, cb):
                    called.append("call_later")

                    self.assertEqual(t, 0.5)
                    self.assertEqual(self.receiver.results, {key: (self.original, self.result)})

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

        describe "recv":
            async it "finds result based on source, sequence, target":
                self.register(self.source, self.sequence, self.target)
                self.receiver.recv(self.packet, self.addr)
                self.result.add_packet.assert_called_once_with(
                    self.packet, self.addr, self.original
                )

            async it "finds result based on broadcast key if that was used":
                self.register(self.source, self.sequence, self.receiver.blank_target)
                self.receiver.recv(self.packet, self.addr)
                self.result.add_packet.assert_called_once_with(
                    self.packet, self.addr, self.original
                )

            async it "does nothing if it can't find the key":
                self.register(1, 2, binascii.unhexlify("d073d5000001"))
                self.receiver.recv(self.packet, self.addr)
                self.assertEqual(len(self.result.add_packet.mock_calls), 0)

            async it "uses message_catcher if can't find the key and that's defined":
                message_catcher = mock.Mock(name="message_catcher")
                self.receiver.message_catcher = message_catcher
                self.receiver.recv(self.packet, self.addr)
                message_catcher.assert_called_once_with(self.packet)

            async it "does not use message_catcher if can find the key and that's defined":
                self.register(self.source, self.sequence, self.target)

                message_catcher = mock.Mock(name="message_catcher")
                self.receiver.message_catcher = message_catcher
                self.receiver.recv(self.packet, self.addr)

                self.result.add_packet.assert_called_once_with(
                    self.packet, self.addr, self.original
                )
                self.assertEqual(len(message_catcher.mock_calls), 0)

                self.result.add_packet.reset_mock()
                self.register(self.source, self.sequence, self.receiver.blank_target)

                message_catcher = mock.Mock(name="message_catcher")
                self.receiver.message_catcher = message_catcher
                self.receiver.recv(self.packet, self.addr)

                self.result.add_packet.assert_called_once_with(
                    self.packet, self.addr, self.original
                )
                self.assertEqual(len(message_catcher.mock_calls), 0)
