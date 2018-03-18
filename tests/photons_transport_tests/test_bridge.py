# coding: spec

from photons_transport.target.bridge import TransportBridge

from photons_app.errors import PhotonsAppError, TimedOut
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from input_algorithms import spec_base as sb
import asynctest
import binascii
import asyncio
import mock
import time

describe AsyncTestCase, "TransportBridge":
    async before_each:
        self.stop_fut = asyncio.Future()
        self.transport_target = mock.Mock(name="transport_target")
        self.protocol_register = mock.Mock(name="protocol_register")
        self.found = mock.Mock(name="found")
        self.default_broadcast = mock.Mock(name="default_broadcast")

    async after_each:
        self.stop_fut.cancel()

    async it "takes in a few things":
        s1 = mock.Mock(name="s1")
        s2 = mock.Mock(name="s2")
        sources = [s1, s2]
        def generate_source():
            return sources.pop(0)
        generate_source = mock.Mock(name="generate_source", side_effect=generate_source)

        with mock.patch.object(TransportBridge, "generate_source", generate_source):
            bridge = TransportBridge(self.stop_fut, self.transport_target, self.protocol_register
                , found=self.found, default_broadcast=self.default_broadcast
                )

        assert not bridge.stop_fut.done()
        self.assertIs(bridge.transport_target, self.transport_target)
        self.assertIs(bridge.protocol_register, self.protocol_register)
        self.assertIs(bridge.device_source, s1)
        self.assertIs(bridge.found, self.found)
        self.assertIs(bridge.broadcast_source, s2)
        self.assertIs(bridge.default_broadcast, self.default_broadcast)

        self.stop_fut.cancel()
        assert bridge.stop_fut.cancelled()

    async it "has some defaults":
        bridge = TransportBridge(self.stop_fut, self.transport_target, self.protocol_register)

        assert not bridge.stop_fut.done()
        self.assertIs(bridge.transport_target, self.transport_target)
        self.assertIs(bridge.protocol_register, self.protocol_register)

        self.assertEqual(bridge.found, {})
        self.assertEqual(bridge.default_broadcast, "255.255.255.255")

    async it "doesn't use new found if given found is empty":
        found = {}
        bridge = TransportBridge(self.stop_fut, self.transport_target, self.protocol_register, found=found)
        self.assertEqual(bridge.found, {})
        found["a"] = 1
        self.assertEqual(bridge.found, {"a": 1})

    describe "usage":
        async before_each:
            self.bridge = TransportBridge(self.stop_fut, self.transport_target, self.protocol_register
                , found=self.found, default_broadcast=self.default_broadcast
                )

        describe "start":
            async it "does nothing by default":
                await self.bridge.start()
                assert True, "nothing broke... *shrugs*"

        describe "finish":
            async it "cancels the stop_fut":
                assert not self.bridge.stop_fut.done()
                self.bridge.finish()
                assert self.bridge.stop_fut.cancelled()

            async it "doesn't break if the stop_fut hasn't been set yet":
                bridge = mock.Mock(name="bridge", spec=[])
                assert not hasattr(bridge, "stop_fut")
                TransportBridge.finish(bridge)
                assert True, "nothing broke... *shrugs*"

            async it "is called when the bridge is deleted":
                stop_fut = self.bridge.stop_fut
                assert not stop_fut.done()
                del self.bridge
                assert stop_fut.cancelled()

        describe "hooks":
            async it "raise NotImplementedError for them":
                m = lambda n: mock.Mock(name=n)

                with self.fuzzyAssertRaisesError(NotImplementedError):
                    self.bridge.write_to_sock(m("sock"), m("addr"), m("packet"), m("bts"))

                with self.fuzzyAssertRaisesError(NotImplementedError):
                    await self.bridge.create_receiver(m("conn"), m("packet"), m("addr"))

                with self.fuzzyAssertRaisesError(NotImplementedError):
                    await self.bridge.spawn_conn(m("address"), backoff=m("backoff"), target=m("target"))

                with self.fuzzyAssertRaisesError(NotImplementedError):
                    await self.bridge.find_devices(m("broadcast")
                        , ignore_lost=m("ignore_lost"), raise_on_none=m("raise_on_none")
                        # And arbitrary kwargs
                        , random=m("random"), other_random=m("other_random")
                        )

        describe "generating source":
            async it "uses random to create a number in the particular range":
                res = mock.Mock(name="res")
                randrange = mock.Mock(name='randrange', return_value=res)
                with mock.patch("random.randrange", randrange):
                    self.assertIs(self.bridge.generate_source(), res)
                randrange.assert_called_once_with(1, 4294967296)

                real = self.bridge.generate_source()
                self.assertGreater(real, 0)
                self.assertLess(real, 4294967296)

        describe "getting source to use":
            async it "returns the broadcast source if is for broadcast":
                bs = mock.Mock(name='broadcast_source')
                self.bridge.broadcast_source = bs

                self.assertIs(self.bridge.source(True), bs)
                self.assertIs(self.bridge.source('255.255.255.255'), bs)

            async it "returns the device source if is not for broadcast":
                ds = mock.Mock(name='device_source')
                self.bridge.device_source = ds

                self.assertIs(self.bridge.source(sb.NotSpecified), ds)
                self.assertIs(self.bridge.source(False), ds)

        describe "Getting a sequence number":
            async it "records where we're at with the target":
                target = mock.Mock(name="target")
                assert not hasattr(self.bridge, "_seq")
                self.assertEqual(self.bridge.seq(target), 1)
                self.assertEqual(self.bridge._seq, {target: 1})

                self.assertEqual(self.bridge.seq(target), 2)
                self.assertEqual(self.bridge._seq, {target: 2})

                target2 = mock.Mock(name="target2")
                self.assertEqual(self.bridge.seq(target2), 1)
                self.assertEqual(self.bridge._seq, {target: 2, target2: 1})

                self.assertEqual(self.bridge.seq(target), 3)
                self.assertEqual(self.bridge._seq, {target: 3, target2: 1})

            async it "wraps around at 255":
                target = mock.Mock(name="target2")
                self.assertEqual(self.bridge.seq(target), 1)
                self.assertEqual(self.bridge._seq, {target: 1})

                self.bridge._seq[target] = 254
                self.assertEqual(self.bridge.seq(target), 255)
                self.assertEqual(self.bridge._seq, {target: 255})

                self.assertEqual(self.bridge.seq(target), 0)
                self.assertEqual(self.bridge._seq, {target: 0})

        describe "forget":
            async it "removes the target from found if it's in there":
                serial = "d073d5000001"
                target = binascii.unhexlify(serial)
                target2 = mock.Mock(name="target2")
                self.bridge.found = {target: True, target2: True}
                await self.bridge.forget(serial)
                self.assertEqual(self.bridge.found, {target2: True})

            async it "does nothing if target not in found":
                serial = "d073d5000001"
                target2 = mock.Mock(name="target2")
                self.bridge.found = {target2: True}
                await self.bridge.forget(serial)
                self.assertEqual(self.bridge.found, {target2: True})

        describe "setting found for a serial":
            async it "can be done":
                self.bridge.found = {}

                serial = "d073d5000001"
                target = binascii.unhexlify(serial)
                address = mock.Mock(name='address')
                port = mock.Mock(name="port")
                service = mock.Mock(name="service")

                self.bridge.target_is_at(serial, address, port, service)

                self.assertEqual(self.bridge.found, {target: (set([(service, (address, port))]), address)})

        describe "find":
            async before_each:
                self.find_devices = asynctest.mock.CoroutineMock(name="find_devices")

            async it "returns what it finds in found":
                serial = "d073d5000001"
                target = binascii.unhexlify(serial)

                res = mock.Mock(name='res')
                self.bridge.found = {target: res}

                self.assertIs(await self.bridge.find(serial), res)
                self.assertIs(await self.bridge.find(target), res)

            async it "uses find_devices to get found":
                serial = "d073d5000001"
                target = binascii.unhexlify(serial)

                res = mock.Mock(name='res')
                self.bridge.found = {}

                self.find_devices.return_value = {target: res}
                with mock.patch.object(self.bridge, "find_devices", self.find_devices):
                    self.assertIs(await self.bridge.find(serial), res)

                self.find_devices.assert_called_once_with(broadcast=self.default_broadcast, timeout=mock.ANY)

            async it "passes in broadcast and other kwargs into find_devices to get found":
                serial = "d073d5000001"
                target = binascii.unhexlify(serial)

                res = mock.Mock(name='res')
                self.bridge.found = {}

                a = mock.Mock(name="a")
                b = mock.Mock(name="b")
                broadcast = mock.Mock(name="broadcast")

                self.find_devices.return_value = {target: res}
                with mock.patch.object(self.bridge, "find_devices", self.find_devices):
                    self.assertIs(await self.bridge.find(serial, broadcast=broadcast, a=a, b=b), res)

                self.find_devices.assert_called_once_with(broadcast=broadcast, timeout=mock.ANY, a=a, b=b)

            async it "keeps trying till it finds it":
                serial = "d073d5000001"
                target = binascii.unhexlify(serial)
                target2 = mock.Mock(name="target2")

                res = mock.Mock(name='res')
                self.bridge.found = {}

                found = [{}, {target2: True}, {target: res}]

                def find_devices(**kwargs):
                    return found.pop(0)
                self.find_devices.side_effect = find_devices

                with mock.patch.object(self.bridge, "find_devices", self.find_devices):
                    self.assertIs(await self.bridge.find(serial), res)

                self.assertEqual(self.find_devices.mock_calls
                    , [ mock.call(broadcast=self.default_broadcast, timeout=mock.ANY)
                      , mock.call(broadcast=self.default_broadcast, timeout=mock.ANY)
                      , mock.call(broadcast=self.default_broadcast, timeout=mock.ANY)
                      ]
                    )

            async it "keeps trying till it times out":
                serial = "d073d5000001"
                target = binascii.unhexlify(serial)
                target2 = mock.Mock(name="target2")

                res = mock.Mock(name='res')
                self.bridge.found = {}

                fut = asyncio.Future()

                called = []
                async def find_devices(**kwargs):
                    if len(called) == 0:
                        called.append(1)
                        return {}

                    start = time.time()
                    try:
                        return await fut
                    finally:
                        called.append(time.time() - start)

                with mock.patch.object(self.bridge, "find_devices", find_devices):
                    with self.fuzzyAssertRaisesError(TimedOut, serial=serial):
                        await self.wait_for(self.bridge.find(serial, timeout=0.01))

                assert fut.cancelled()
                self.assertEqual(called[0], 1)
                self.assertLess(called[1], 0.02)

        describe "received_data":
            async before_each:
                self.Messages = mock.Mock(name="messages")
                self.bridge.Messages = self.Messages

                self.data = mock.Mock(name="data")
                self.addr = mock.Mock(name="addr")
                self.address = mock.Mock(name="address")

            async it "unpacks the data and passes to the receiver":
                pkt = mock.Mock(name="pkt")
                res = mock.Mock(name="res")
                self.Messages.unpack.return_value = pkt
                receiver = mock.Mock(name="receiver", return_value=res)

                with mock.patch.object(self.bridge, "receiver", receiver):
                    self.assertIs(self.bridge.received_data(self.data, self.addr, self.address), res)

                self.Messages.unpack.assert_called_once_with(self.data, self.protocol_register, unknown_ok=True)
                receiver.assert_called_with((pkt, self.addr, self.address))

            async it "does nothing if unpack raises an exception":
                pkt = mock.Mock(name="pkt")
                error = PhotonsAppError("error")
                self.Messages.unpack.side_effect = error
                receiver = mock.Mock(name="receiver")

                with mock.patch.object(self.bridge, "receiver", receiver):
                    self.assertIs(self.bridge.received_data(self.data, self.addr, self.address), None)

                self.Messages.unpack.assert_called_once_with(self.data, self.protocol_register, unknown_ok=True)
                self.assertEqual(receiver.mock_calls, [])

        describe "receiver":
            async it "creates the Receiver property and memoizes it":
                res = mock.Mock(name="res")
                FakeReceiver = mock.Mock(name='Receiver', return_value=res)

                self.bridge.Receiver = FakeReceiver
                self.assertIs(self.bridge.receiver, res)
                FakeReceiver.assert_called_once_with()

                self.assertIs(self.bridge.receiver, res)
                self.assertEqual(len(FakeReceiver.mock_calls), 1)

        describe "make_waiter":
            async it "creates a new waiter object":
                res = mock.Mock(name="res")
                a = mock.Mock(name="a")
                b = mock.Mock(name="b")
                writer = mock.Mock(name="writer")

                FakeWaiter = mock.Mock(name='Waiter', return_value=res)

                self.bridge.Waiter = FakeWaiter
                self.assertIs(self.bridge.make_waiter(writer, a=a, b=b), res)
                FakeWaiter.assert_called_once_with(self.bridge.stop_fut, writer, a=a, b=b)

        describe "make_writer":
            async it "creates a new writer and makes an executor from it":
                executor = mock.Mock(name="executor")
                make = asynctest.mock.CoroutineMock(name="make", return_value=executor)

                res = mock.Mock(name="res", make=make)
                a = mock.Mock(name="a")
                b = mock.Mock(name="b")
                packet = mock.Mock(name="packet")

                FakeWriter = mock.Mock(name='Writer', return_value=res)

                self.bridge.Writer = FakeWriter
                self.assertIs(await self.bridge.make_writer(packet, a=a, b=b), executor)
                FakeWriter.assert_called_once_with(self.bridge, packet, a=a, b=b)
                make.assert_called_once_with()
