# coding: spec

from photons_transport.target.receiver import Receiver

from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import binascii
import asyncio
import mock
import time

describe AsyncTestCase, "Receiver":
    async it "inits some variables":
        receiver = Receiver()
        self.assertIs(receiver.loop, self.loop)
        self.assertEqual(receiver.multi_cache, {})
        self.assertEqual(receiver.multi_cache_futs, {})
        self.assertEqual(receiver.acks, {})
        self.assertEqual(receiver.received, {})
        self.assertEqual(receiver.blank_target, b'\x00\x00\x00\x00\x00\x00\x00\x00')

    describe "Usage":
        async before_each:
            self.receiver = Receiver()

        describe "registering a result":
            async it "understands when to expect zero source and zero sequence":
                source = mock.Mock(name="source")
                sequence = mock.Mock(name="sequence")
                target = binascii.unhexlify("d073d5000001")
                packet = mock.Mock(name="packet", source=source, sequence=sequence, target=target)

                self.assertEqual(self.receiver.received, {})
                fut = asyncio.Future()
                multiple_replies = mock.Mock(name="multiple_replies")

                self.receiver.register_res(packet, fut, multiple_replies, expect_zero=True)
                self.assertEqual(self.receiver.received, {(0, 0, target): (fut, multiple_replies)})
                await asyncio.sleep(0)
                self.assertEqual(self.receiver.received, {(0, 0, target): (fut, multiple_replies)})
                fut.set_result(True)
                await asyncio.sleep(1.1)
                self.assertEqual(self.receiver.received, {})

            async it "adds it to received and fut is removed when it's done or cancelled":
                source = mock.Mock(name="source")
                sequence = mock.Mock(name="sequence")
                target = mock.Mock(name="target")
                packet = mock.Mock(name="packet", source=source, sequence=sequence, target=target)

                self.assertEqual(self.receiver.received, {})
                fut = asyncio.Future()
                multiple_replies = mock.Mock(name="multiple_replies")

                self.receiver.register_res(packet, fut, multiple_replies)
                self.assertEqual(self.receiver.received, {(source, sequence, target): (fut, multiple_replies)})
                await asyncio.sleep(0)
                self.assertEqual(self.receiver.received, {(source, sequence, target): (fut, multiple_replies)})
                fut.set_result(True)
                await asyncio.sleep(1.1)
                self.assertEqual(self.receiver.received, {})

                fut2 = asyncio.Future()
                self.receiver.register_res(packet, fut2, multiple_replies)
                self.assertEqual(self.receiver.received, {(source, sequence, target): (fut2, multiple_replies)})
                await asyncio.sleep(0)
                self.assertEqual(self.receiver.received, {(source, sequence, target): (fut2, multiple_replies)})
                fut2.cancel()
                await asyncio.sleep(1.1)
                self.assertEqual(self.receiver.received, {})

        describe "registering an ack":
            async it "adds it to acks and fut is removed when it's done or cancelled":
                source = mock.Mock(name="source")
                sequence = mock.Mock(name="sequence")
                target = mock.Mock(name="target")
                packet = mock.Mock(name="packet", source=source, sequence=sequence, target=target)

                self.assertEqual(self.receiver.acks, {})
                fut = asyncio.Future()
                multiple_replies = mock.Mock(name="multiple_replies")

                self.receiver.register_ack(packet, fut, multiple_replies)
                self.assertEqual(self.receiver.acks, {(source, sequence, target): (fut, multiple_replies)})
                await asyncio.sleep(0)
                self.assertEqual(self.receiver.acks, {(source, sequence, target): (fut, multiple_replies)})
                fut.set_result(True)
                await asyncio.sleep(1.1)
                self.assertEqual(self.receiver.acks, {})

                fut2 = asyncio.Future()
                self.receiver.register_ack(packet, fut2, multiple_replies)
                self.assertEqual(self.receiver.acks, {(source, sequence, target): (fut2, multiple_replies)})
                await asyncio.sleep(0)
                self.assertEqual(self.receiver.acks, {(source, sequence, target): (fut2, multiple_replies)})
                fut2.cancel()
                await asyncio.sleep(1.1)
                self.assertEqual(self.receiver.acks, {})

        describe "giving it a msg":
            async it "puts acknowledgements into self.acks via self.recv":
                packet = mock.Mock(name="packet", represents_ack=True)

                addr = mock.Mock(name="addr")
                broadcast = mock.Mock(name="broadcast")
                msg = (packet, addr, broadcast)

                recv = mock.Mock(name="recv", return_value=True)
                with mock.patch.object(self.receiver, "recv", recv):
                    self.assertEqual(self.receiver(msg), [packet])

                recv.assert_called_once_with(packet, addr, broadcast, self.receiver.acks)

            async it "puts acknowledgements into self.received via self.recv":
                packet = mock.Mock(name="packet", represents_ack=False)

                addr = mock.Mock(name="addr")
                broadcast = mock.Mock(name="broadcast")
                msg = (packet, addr, broadcast)

                recv = mock.Mock(name="recv", return_value=True)
                with mock.patch.object(self.receiver, "recv", recv):
                    self.assertEqual(self.receiver(msg), [packet])

                recv.assert_called_once_with(packet, addr, broadcast, self.receiver.received)

            async it "doesn't complain if packet doesn't have represents_ack on it":
                packet = mock.Mock(name="packet", spec=["source", "sequence", "target"])

                addr = mock.Mock(name="addr")
                broadcast = mock.Mock(name="broadcast")
                msg = (packet, addr, broadcast)

                recv = mock.Mock(name="recv", return_value=True)
                with mock.patch.object(self.receiver, "recv", recv):
                    self.assertEqual(self.receiver(msg), [packet])

                recv.assert_called_once_with(packet, addr, broadcast, self.receiver.received)

            async it "doesn't return packet if recv says no":
                packet = mock.Mock(name="packet", spec=["source", "sequence", "target"])

                addr = mock.Mock(name="addr")
                broadcast = mock.Mock(name="broadcast")
                msg = (packet, addr, broadcast)

                recv = mock.Mock(name="recv", return_value=False)
                with mock.patch.object(self.receiver, "recv", recv):
                    self.assertEqual(self.receiver(msg), [])

                recv.assert_called_once_with(packet, addr, broadcast, self.receiver.received)

        describe "finish_multi_cache":
            async it "does nothing if key isn't in the multi_cache":
                key = mock.Mock(name="key")
                self.receiver.finish_multi_cache(key)
                assert True, "it didn't raise an exception"

            async it "sets the future if the last reply was more than 0.3 seconds ago":
                now = time.time()
                te = mock.Mock(name="time", return_value=now)

                res = mock.Mock(name="res")
                res2 = mock.Mock(name="res2")
                res3 = mock.Mock(name="res3")

                fut = asyncio.Future()
                key = mock.Mock(name="key")
                results = [(res, now - 0.4), (res2, now - 0.5), (res3, now - 0.6)]

                self.receiver.multi_cache[key] = (fut, results)

                with mock.patch("time.time", te):
                    self.receiver.finish_multi_cache(key)

                self.assertEqual(fut.result(), [res, res2, res3])
                self.assertEqual(self.receiver.multi_cache, {})

            async it "does not set the future if it's already set":
                now = time.time()
                te = mock.Mock(name="time", return_value=now)

                res = mock.Mock(name="res")
                res2 = mock.Mock(name="res2")
                res3 = mock.Mock(name="res3")

                fut = asyncio.Future()
                fut.set_result(True)

                key = mock.Mock(name="key")
                results = [(res, now - 0.4), (res2, now - 0.5), (res3, now - 0.6)]

                self.receiver.multi_cache[key] = (fut, results)

                with mock.patch("time.time", te):
                    self.receiver.finish_multi_cache(key)

                self.assertEqual(fut.result(), True)
                self.assertEqual(self.receiver.multi_cache, {})

            async it "does not set the future if the last reply was less than 0.3 seconds ago":
                now = time.time()
                te = mock.Mock(name="time", return_value=now)

                res = mock.Mock(name="res")
                res2 = mock.Mock(name="res2")
                res3 = mock.Mock(name="res3")
                res4 = mock.Mock(name="res4")

                fut = asyncio.Future()
                key = mock.Mock(name="key")
                results = [(res, now - 0.4), (res2, now - 0.5), (res3, now - 0.6), (res4, now - 0.1)]

                self.receiver.multi_cache[key] = (fut, results)

                with mock.patch("time.time", te):
                    self.receiver.finish_multi_cache(key)

                assert not fut.done()
                self.assertEqual(self.receiver.multi_cache, {key: (fut, results)})

        describe "recv":
            async before_each:
                self.target = binascii.unhexlify("d073d500000000")
                self.source = mock.Mock(name="source")
                self.sequence = mock.Mock(name="sequence")
                self.pkt = mock.Mock(name="pkt", source=self.source, sequence=self.sequence, target=self.target)
                self.addr = mock.Mock(name="addr")
                self.broadcast = mock.Mock(name="broadcast")

                self.fut = asyncio.Future()

            async it "does nothing if the source is 0 and sequence is 0":
                self.pkt.source = 0
                self.pkt.sequence = 0
                key = (self.pkt.source, self.pkt.sequence, self.pkt.target)
                dest = {key: (self.fut, False)}
                self.receiver.recv(self.pkt, self.addr, self.broadcast, dest)
                assert not self.fut.done()

            async it "matches when source and sequence are 0 if we are expecting that":
                self.pkt.source = 0
                self.pkt.sequence = 0
                key = (0, 0, self.pkt.target[:6])
                dest = {key: (self.fut, False)}
                self.receiver.recv(self.pkt, self.addr, self.broadcast, dest)
                assert self.fut.done()

            async it "does nothing if the key or broadcast key not in dest":
                dest = {}
                self.receiver.recv(self.pkt, self.addr, self.broadcast, dest)
                assert True, "No exception was raised"

            async it "calls message_catcher if we have one and the key or broadcast key not in dest":
                dest = {}
                message_catcher = mock.Mock(name="message_catcher")
                self.receiver.message_catcher = message_catcher
                self.receiver.recv(self.pkt, self.addr, self.broadcast, dest)
                message_catcher.assert_called_once_with(self.pkt)

            async it "finds the key if it's under the broadcast key":
                dest = {(self.pkt.source, self.pkt.sequence, self.receiver.blank_target): (self.fut, False)}
                self.receiver.recv(self.pkt, self.addr, self.broadcast, dest)
                self.assertEqual(self.fut.result(), [(self.pkt, self.addr, self.broadcast)])

            async it "finds the key if it's under the key from the packet":
                dest = {(self.pkt.source, self.pkt.sequence, self.pkt.target): (self.fut, False)}
                self.receiver.recv(self.pkt, self.addr, self.broadcast, dest)
                self.assertEqual(self.fut.result(), [(self.pkt, self.addr, self.broadcast)])

            async it "adds to the multi cache if we want multiple replies and sets a future to call finish_multi_cache":
                dest = {(self.pkt.source, self.pkt.sequence, self.pkt.target): (self.fut, True)}
                multi_key = (self.broadcast, (self.pkt.source, self.pkt.sequence, self.pkt.target))

                self.assertEqual(self.receiver.multi_cache, {})

                called = []
                original_call_later = self.loop.call_later
                def cl(t, cb, *args):
                    if cb == self.receiver.finish_multi_cache:
                        called.append((t, args))
                    else:
                        original_call_later(t, cb, *args)
                call_later = mock.Mock(name="call_later", side_effect=cl)

                now = time.time()

                with mock.patch("time.time", lambda: now):
                    with mock.patch.object(self.loop, "call_later", cl):
                        self.receiver.recv(self.pkt, self.addr, self.broadcast, dest)

                assert not self.fut.done()
                self.assertEqual(called, [(0.35, (multi_key, ))])
                self.assertEqual(self.receiver.multi_cache, {multi_key: (self.fut, [((self.pkt, self.addr, self.broadcast), now)])})

                with mock.patch("time.time", lambda: now+5):
                    with mock.patch.object(self.loop, "call_later", cl):
                        self.receiver.recv(self.pkt, self.addr, self.broadcast, dest)

                assert not self.fut.done()
                self.assertEqual(called, [(0.35, (multi_key, )), (0.35, (multi_key, ))])
                expected = {
                      multi_key:
                      ( self.fut
                      , [ ((self.pkt, self.addr, self.broadcast), now)
                        , ((self.pkt, self.addr, self.broadcast), now+5)
                        ]
                      )
                    }
                self.assertEqual(self.receiver.multi_cache, expected)
