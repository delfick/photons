# coding: spec

from photons_transport.base.bridge import TransportBridge
from photons_transport import RetryOptions

from photons_app.errors import PhotonsAppError, TimedOut
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from input_algorithms import spec_base as sb
from unittest import mock
import asynctest
import binascii
import asyncio
import time

describe AsyncTestCase, "TransportBridge":
    async before_each:
        self.stop_fut = asyncio.Future()
        self.transport_target = mock.Mock(name="transport_target")
        self.protocol_register = mock.Mock(name="protocol_register")

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
            bridge = TransportBridge(self.stop_fut, self.transport_target, self.protocol_register)

        assert not bridge.stop_fut.done()
        self.assertIs(bridge.transport_target, self.transport_target)
        self.assertIs(bridge.protocol_register, self.protocol_register)
        self.assertIs(bridge.device_source, s1)
        self.assertIs(bridge.broadcast_source, s2)

        self.stop_fut.cancel()
        assert bridge.stop_fut.cancelled()

    async it "has some defaults":
        bridge = TransportBridge(self.stop_fut, self.transport_target, self.protocol_register)

        assert not bridge.stop_fut.done()
        self.assertIs(bridge.transport_target, self.transport_target)
        self.assertIs(bridge.protocol_register, self.protocol_register)

        self.assertEqual(bridge.found, {})

    describe "usage":
        async before_each:
            self.bridge = TransportBridge(self.stop_fut, self.transport_target, self.protocol_register)

        describe "start":
            async it "does nothing by default":
                await self.bridge.start()
                assert True, "nothing broke... *shrugs*"

        describe "finish":
            async it "cancels the stop_fut":
                assert not self.bridge.stop_fut.done()
                await self.bridge.finish()
                assert self.bridge.stop_fut.cancelled()

            async it "doesn't break if the stop_fut hasn't been set yet":
                bridge = mock.Mock(name="bridge", spec=[])
                assert not hasattr(bridge, "stop_fut")
                await TransportBridge.finish(bridge)
                assert True, "nothing broke... *shrugs*"

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
                    await self.bridge._find_specific_serials(m("serials")
                        , ignore_lost = m("ignore_lost")
                        , raise_on_none = m("raise_on_none")
                        # And arbitrary kwargs
                        , random = m("random")
                        , other_random = m("other_random")
                        )

        describe "find_devices":
            async it "uses find_specific_serials":
                a = mock.Mock(name="a")
                broadcast = mock.Mock(name="broadcast")
                ignore_lost = mock.Mock(name="ignore_lost")
                raise_on_none = mock.Mock(name="raise_on_none")

                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                find_specific_serials = asynctest.mock.CoroutineMock(name="find_specific_serials")
                find_specific_serials.return_value = (found, missing)

                with mock.patch.object(self.bridge, "find_specific_serials", find_specific_serials):
                    f = await self.bridge.find_devices(
                          ignore_lost = ignore_lost
                        , raise_on_none = raise_on_none
                        , broadcast = broadcast
                        , a = a
                        )

                self.assertIs(f, found)
                find_specific_serials.assert_called_once_with(None
                    , ignore_lost = ignore_lost
                    , raise_on_none = raise_on_none
                    , broadcast = broadcast
                    , a = a
                    )

            async it "has defaults for ignore_lost and raise_on_none":
                a = mock.Mock(name="a")
                broadcast = mock.Mock(name="broadcast")

                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                find_specific_serials = asynctest.mock.CoroutineMock(name="find_specific_serials")
                find_specific_serials.return_value = (found, missing)

                with mock.patch.object(self.bridge, "find_specific_serials", find_specific_serials):
                    f = await self.bridge.find_devices(a=a)

                self.assertIs(f, found)
                find_specific_serials.assert_called_once_with(None
                    , ignore_lost = False
                    , raise_on_none = False
                    , a = a
                    )

        describe "find_specific_serials":
            async before_each:
                self.serial1 = "d073d5000001"
                self.serial2 = "d073d5000002"

                self.target1 = binascii.unhexlify(self.serial1)[:6]
                self.target2 = binascii.unhexlify(self.serial2)[:6]

                self.info1 = mock.Mock(name="info1")
                self.info2 = mock.Mock(name="info2")

            async def assertSpecificSerials(self, serials, found, missing):
                a = mock.Mock(name="a")
                broadcast = mock.Mock(name="broadcast")
                ignore_lost = mock.Mock(name="ignore_lost")
                raise_on_none = mock.Mock(name="raise_on_none")

                _find_specific_serials = asynctest.mock.CoroutineMock(name="_find_specific_serials")
                _find_specific_serials.return_value = found

                with mock.patch.object(self.bridge, "_find_specific_serials", _find_specific_serials):
                    f, m = await self.bridge.find_specific_serials(serials
                        , ignore_lost = ignore_lost
                        , raise_on_none = raise_on_none
                        , broadcast = broadcast
                        , a = a
                        )

                self.assertIs(f, found)
                self.assertEqual(m, missing)
                _find_specific_serials.assert_called_once_with(serials
                    , ignore_lost = ignore_lost
                    , raise_on_none = raise_on_none
                    , broadcast = broadcast
                    , a = a
                    )

                _find_specific_serials.reset_mock()
                with mock.patch.object(self.bridge, "_find_specific_serials", _find_specific_serials):
                    f, m = await self.bridge.find_specific_serials(serials
                        , broadcast = broadcast
                        , a = a
                        )

                self.assertIs(f, found)
                self.assertEqual(m, missing)
                _find_specific_serials.assert_called_once_with(serials
                    , ignore_lost = False
                    , raise_on_none = False
                    , broadcast = broadcast
                    , a = a
                    )

            async it "No missing if no found and no serials":
                serials = None
                found = {}
                missing = []
                await self.assertSpecificSerials(serials, found, missing)

            async it "No missing if found has all the serials":
                serials = [self.serial1, self.serial2]

                found = {self.target1: self.info1, self.target2: self.info2}
                missing = []
                await self.assertSpecificSerials(serials, found, missing)

            async it "No missing if more found than serials":
                serials = [self.serial1]

                found = {self.target1: self.info1, self.target2: self.info2}
                missing = []
                await self.assertSpecificSerials(serials, found, missing)

            async it "has missing if less found than serials":
                serials = [self.serial1, self.serial2]

                found = {self.target1: self.info1}
                missing = [self.serial2]
                await self.assertSpecificSerials(serials, found, missing)

            async it "has missing if no found":
                serials = [self.serial1, self.serial2]

                found = {}
                missing = [self.serial1, self.serial2]
                await self.assertSpecificSerials(serials, found, missing)

            async it "no missing if found and no serials":
                serials = None
                found = {self.target1: self.info1, self.target2: self.info2}
                missing = []
                await self.assertSpecificSerials(serials, found, missing)

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
                    self.bridge.received_data(self.data, self.addr, self.address)

                self.Messages.unpack.assert_called_once_with(self.data, self.protocol_register, unknown_ok=True)
                receiver.assert_called_with((pkt, self.addr, self.address))

            async it "does nothing if unpack raises an exception":
                pkt = mock.Mock(name="pkt")
                error = PhotonsAppError("error")
                self.Messages.unpack.side_effect = error
                receiver = mock.Mock(name="receiver")

                with mock.patch.object(self.bridge, "receiver", receiver):
                    self.bridge.received_data(self.data, self.addr, self.address)

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
                original = mock.Mock(name="original")
                packet = mock.Mock(name="packet")
                services = mock.Mock(name="services")

                FakeWriter = mock.Mock(name='Writer', return_value=res)

                self.bridge.Writer = FakeWriter
                self.assertIs(await self.bridge.make_writer(services, original, packet, a=a, b=b), executor)
                FakeWriter.assert_called_once_with(self.bridge, original, packet, a=a, b=b)
                make.assert_called_once_with(services)

        describe "make_retry_options":
            async it "creates RetryOptions by default":
                options = self.bridge.make_retry_options()
                self.assertIsInstance(options, RetryOptions)

            async it "uses the RetryOptions object on the bridge":
                res = mock.Mock(name='res')
                FakeRetryOptions = mock.Mock(name='Writer', return_value=res)

                self.bridge.RetryOptions = FakeRetryOptions
                options = self.bridge.make_retry_options(a=1)
                self.assertIs(options, res)
                FakeRetryOptions.assert_called_once_with(a=1)
