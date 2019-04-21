# coding: spec

from photons_socket.target import SocketTarget, SocketBridge, serials_to_targets

from photons_app.test_helpers import TestCase, AsyncTestCase, with_timeout, FakeTarget
from photons_app.errors import TimedOut, FoundNoDevices

from photons_messages import DiscoveryMessages, Services, protocol_register
from photons_transport.target.retry_options import RetryOptions

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from contextlib import contextmanager
from unittest import mock
import asynctest
import binascii
import asyncio

describe TestCase, "serials_to_targets":
    it "returns nothing if no serials":
        self.assertEqual(list(serials_to_targets(None)), [])
        self.assertEqual(list(serials_to_targets([])), [])

    it "understands bytes":
        target1 = binascii.unhexlify("d073d500000100")
        target2 = binascii.unhexlify("d073d500000200")
        self.assertEqual(list(serials_to_targets([target1, target2])), [target1[:6], target2[:6]])

    it "understands strings":
        serial1 = "d073d500000100"
        serial2 = "d073d500000200"

        target1 = binascii.unhexlify(serial1)[:6]
        target2 = binascii.unhexlify(serial2)[:6]

        self.assertEqual(list(serials_to_targets([serial1, serial2])), [target1, target2])

describe AsyncTestCase, "SocketBridge":
    async before_each:
        self.final_future = asyncio.Future()
        options = {"final_future": self.final_future, "protocol_register": protocol_register}
        self.target = SocketTarget.create(options)
        self.bridge = await self.target.args_for_run()

        self.serial1 = "d073d5000001"
        self.serial2 = "d073d5000002"
        self.serial3 = "d073d5000003"

        self.target1 = binascii.unhexlify(self.serial1)[:6]
        self.target2 = binascii.unhexlify(self.serial2)[:6]
        self.target3 = binascii.unhexlify(self.serial3)[:6]

        self.info1 = mock.Mock(name="info1")
        self.info2 = mock.Mock(name="info2")
        self.info3 = mock.Mock(name="info3")

        self.broadcast = mock.Mock(name="broadcast")

    async after_each:
        self.final_future.cancel()
        if hasattr(self, "bridge"):
            await self.target.close_args_for_run(self.bridge)

    async it "can be got from the target":
        bridge = None
        try:
            bridge = await self.target.args_for_run()
            self.assertEqual(type(bridge), SocketBridge)
        finally:
            if bridge:
                await self.target.close_args_for_run(bridge)

    describe "_find_specific_serials":
        @with_timeout
        async it "returns bridge.found after getting it from _do_search":
            async def do_search(*args, **kwargs):
                self.bridge.found[self.target1] = self.info1
                return [self.target1]
            do_search = asynctest.mock.CoroutineMock(name="do_search", side_effect=do_search)

            serials = mock.Mock(name="serials")
            timeout = mock.Mock(name="timeout")

            self.assertEqual(self.bridge.found, {})
            with mock.patch.object(self.bridge, "_do_search", do_search):
                f = await self.bridge._find_specific_serials(serials
                    , broadcast = self.broadcast
                    , timeout = timeout
                    , a = 1
                    )
                self.assertIs(f, self.bridge.found)
                self.assertEqual(f, {self.target1: self.info1})

            do_search.assert_called_once_with(serials, self.bridge.found, timeout, a=1, broadcast=self.broadcast)

        @with_timeout
        async it "removes items from found by default":
            self.bridge.found[self.target1] = self.info1

            async def do_search(*args, **kwargs):
                self.bridge.found[self.target2] = self.info2
                return [self.target2]
            do_search = asynctest.mock.CoroutineMock(name="do_search", side_effect=do_search)

            serials = mock.Mock(name="serials")

            with mock.patch.object(self.bridge, "_do_search", do_search):
                f = await self.bridge._find_specific_serials(serials
                    , a = 1
                    )
                self.assertIs(f, self.bridge.found)
                self.assertEqual(f, {self.target2: self.info2})

            do_search.assert_called_once_with(serials, self.bridge.found, 60, a=1)

        @with_timeout
        async it "doesn't remove existing items that were found":
            self.bridge.found[self.target1] = self.info1

            async def do_search(*args, **kwargs):
                self.bridge.found[self.target2] = self.info2
                return [self.target1, self.target2]
            do_search = asynctest.mock.CoroutineMock(name="do_search", side_effect=do_search)

            serials = mock.Mock(name="serials")

            with mock.patch.object(self.bridge, "_do_search", do_search):
                f = await self.bridge._find_specific_serials(serials
                    , a = 1
                    )
                self.assertIs(f, self.bridge.found)
                self.assertEqual(f, {self.target1: self.info1, self.target2: self.info2})

            do_search.assert_called_once_with(serials, self.bridge.found, 60, a=1)

        @with_timeout
        async it "doesn't remove if ignore_lost is True":
            self.bridge.found[self.target1] = self.info1

            async def do_search(*args, **kwargs):
                self.bridge.found[self.target2] = self.info2
                return [self.target2]
            do_search = asynctest.mock.CoroutineMock(name="do_search", side_effect=do_search)

            serials = mock.Mock(name="serials")

            with mock.patch.object(self.bridge, "_do_search", do_search):
                f = await self.bridge._find_specific_serials(serials
                    , ignore_lost = True
                    , a = 1
                    )
                self.assertIs(f, self.bridge.found)
                self.assertEqual(f, {self.target1: self.info1, self.target2: self.info2})

            do_search.assert_called_once_with(serials, self.bridge.found, 60, a=1)

        @with_timeout
        async it "complains if no serials and no found and raise_on_none is True":
            async def do_search(*args, **kwargs):
                return []
            do_search = asynctest.mock.CoroutineMock(name="do_search", side_effect=do_search)

            with self.fuzzyAssertRaisesError(FoundNoDevices):
                with mock.patch.object(self.bridge, "_do_search", do_search):
                    await self.bridge._find_specific_serials(None
                        , raise_on_none = True
                        , a = 1
                        )

            do_search.assert_called_once_with(None, self.bridge.found, 60, a=1)

        @with_timeout
        async it "does not complain if serials and no found and raise_on_none is True":
            async def do_search(*args, **kwargs):
                return []
            do_search = asynctest.mock.CoroutineMock(name="do_search", side_effect=do_search)

            serials = mock.Mock(name="serials")

            with mock.patch.object(self.bridge, "_do_search", do_search):
                f = await self.bridge._find_specific_serials(serials
                    , raise_on_none = True
                    , a = 1
                    )
                self.assertEqual(f, {})

            do_search.assert_called_once_with(serials, self.bridge.found, 60, a=1)

        @with_timeout
        async it "complains if raise_on_none is True and no found, but had existing found":
            self.bridge.found[self.target1] = self.info1

            async def do_search(*args, **kwargs):
                return []
            do_search = asynctest.mock.CoroutineMock(name="do_search", side_effect=do_search)

            with self.fuzzyAssertRaisesError(FoundNoDevices):
                with mock.patch.object(self.bridge, "_do_search", do_search):
                    await self.bridge._find_specific_serials(None
                        , raise_on_none = True
                        , a = 1
                        )

            self.assertEqual(self.bridge.found, {})
            do_search.assert_called_once_with(None, self.bridge.found, 60, a=1)

        @with_timeout
        async it "does not remove targets if ignore_lost is True and we raise FoundNoDevices":
            self.bridge.found[self.target1] = self.info1

            async def do_search(*args, **kwargs):
                return []
            do_search = asynctest.mock.CoroutineMock(name="do_search", side_effect=do_search)

            with self.fuzzyAssertRaisesError(FoundNoDevices):
                with mock.patch.object(self.bridge, "_do_search", do_search):
                    await self.bridge._find_specific_serials(None
                        , ignore_lost = True
                        , raise_on_none = True
                        , a = 1
                        )

            self.assertEqual(self.bridge.found, {self.target1: self.info1})
            do_search.assert_called_once_with(None, self.bridge.found, 60, a=1)

    describe "_search_retry_iterator":
        @with_timeout
        async it "uses a RetryOptions iterator":
            async def iterator(s, *, end_after):
                self.assertEqual(s.timeouts, [(0.6, 1.8), (1, 4)])
                self.assertEqual(end_after, 20)
                yield (3, 1)
                yield (2, 2)

            got = []
            with mock.patch.object(RetryOptions, "iterator", iterator):
                async for info in self.bridge._search_retry_iterator(20):
                    got.append(info)

            self.assertEqual(got, [(3, 1), (2, 2)])

    describe "_do_search":
        async before_each:
            self.bridge.transport_target = FakeTarget(mock.NonCallableMock(name="afr_maker"))

            self.get_service = DiscoveryMessages.GetService(
                  target = None
                , tagged = True
                , addressable = True
                , res_required = True
                , ack_required = False
                )

        @contextmanager
        def retries(self, results, expect_calls='all'):
            num_yielded = 0
            num_expected = len(results) if expect_calls == 'all' else expect_calls

            async def iterator(end_after):
                nonlocal num_yielded

                while results:
                    num_yielded += 1
                    yield results.pop(0)

            with mock.patch.object(self.bridge, "_search_retry_iterator", iterator):
                yield

            self.assertEqual(num_yielded, num_expected)

        @with_timeout
        async it "doesn't retry if we don't want serials and it finds something":
            a = mock.Mock(name="a")

            call = mock.call(self.get_service, None, self.bridge
                , no_retry = True
                , broadcast = True
                , accept_found = True
                , error_catcher = []
                , message_timeout = 0.5
                , a = a
                )

            services = [
                  (DiscoveryMessages.StateService(service=Services.UDP, port=100, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=101, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                ]
            self.bridge.transport_target.expect_call(call, services)

            found = {}
            with self.retries([(20, 0.5)]):
                fn = await self.bridge._do_search(None, found, 20, a=a)
                self.assertEqual(fn, [self.target2])

            self.assertEqual(self.bridge.transport_target.call, 0)
            self.assertEqual(found
                , { self.target2: (set([(Services.UDP, ("192.168.0.1", 100)), (Services.RESERVED1, ("192.168.0.1", 101))]), self.broadcast)
                  }
                )

        @with_timeout
        async it "it retries until we have all the targets":
            a = mock.Mock(name="a")

            call1 = mock.call(self.get_service, None, self.bridge
                , no_retry = True
                , broadcast = self.broadcast
                , accept_found = True
                , error_catcher = []
                , message_timeout = 0.5
                , a = a
                )

            call2 = mock.call(self.get_service, None, self.bridge
                , no_retry = True
                , broadcast = self.broadcast
                , accept_found = True
                , error_catcher = []
                , message_timeout = 0.6
                , a = a
                )

            call3 = mock.call(self.get_service, None, self.bridge
                , no_retry = True
                , broadcast = self.broadcast
                , accept_found = True
                , error_catcher = []
                , message_timeout = 0.8
                , a = a
                )

            services = [
                  (DiscoveryMessages.StateService(service=Services.UDP, port=100, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=101, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                ]
            self.bridge.transport_target.expect_call(call1, services)

            services = [
                  (DiscoveryMessages.StateService(service=Services.UDP, port=100, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=101, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)

                , (DiscoveryMessages.StateService(service=Services.UDP, port=102, target=self.serial3), ("192.168.0.2", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=103, target=self.serial3), ("192.168.0.2", 56700), self.broadcast)
                ]
            self.bridge.transport_target.expect_call(call2, services)

            services = [
                  (DiscoveryMessages.StateService(service=Services.UDP, port=105, target=self.serial1), ("192.168.0.3", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=106, target=self.serial1), ("192.168.0.3", 56700), self.broadcast)
                ]
            self.bridge.transport_target.expect_call(call3, services)

            found = {}
            with self.retries([(20, 0.5), (19.5, 0.6), (18.9, 0.8), (18.1, 1), (17.1, 1)], expect_calls=3):
                fn = await self.bridge._do_search([self.serial1, self.serial2, self.serial3], found, 20, broadcast=self.broadcast, a=a)
                self.assertEqual(sorted(fn), sorted([self.target1, self.target2, self.target3]))

            self.assertEqual(self.bridge.transport_target.call, 2)
            self.assertEqual(found
                , { self.target1: (set([(Services.UDP, ("192.168.0.3", 105)), (Services.RESERVED1, ("192.168.0.3", 106))]), self.broadcast)
                  , self.target2: (set([(Services.UDP, ("192.168.0.1", 100)), (Services.RESERVED1, ("192.168.0.1", 101))]), self.broadcast)
                  , self.target3: (set([(Services.UDP, ("192.168.0.2", 102)), (Services.RESERVED1, ("192.168.0.2", 103))]), self.broadcast)
                  }
                )

        @with_timeout
        async it "it doesn't complain if it runs out of retries":
            a = mock.Mock(name="a")

            call1 = mock.call(self.get_service, None, self.bridge
                , no_retry = True
                , broadcast = True
                , accept_found = True
                , error_catcher = []
                , message_timeout = 0.5
                , a = a
                )

            call2 = mock.call(self.get_service, None, self.bridge
                , no_retry = True
                , broadcast = True
                , accept_found = True
                , error_catcher = []
                , message_timeout = 0.6
                , a = a
                )

            services = [
                  (DiscoveryMessages.StateService(service=Services.UDP, port=100, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=101, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                ]
            self.bridge.transport_target.expect_call(call1, services)

            services = [
                  (DiscoveryMessages.StateService(service=Services.UDP, port=100, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=101, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)

                , (DiscoveryMessages.StateService(service=Services.UDP, port=102, target=self.serial3), ("192.168.0.2", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=103, target=self.serial3), ("192.168.0.2", 56700), self.broadcast)
                ]
            self.bridge.transport_target.expect_call(call2, services)

            found = {}
            with self.retries([(20, 0.5), (19.5, 0.6)]):
                fn = await self.bridge._do_search([self.serial1, self.serial2, self.serial3], found, 20, a=a)
                self.assertEqual(sorted(fn), sorted([self.target2, self.target3]))

            self.assertEqual(self.bridge.transport_target.call, 1)
            self.assertEqual(found
                , { self.target2: (set([(Services.UDP, ("192.168.0.1", 100)), (Services.RESERVED1, ("192.168.0.1", 101))]), self.broadcast)
                  , self.target3: (set([(Services.UDP, ("192.168.0.2", 102)), (Services.RESERVED1, ("192.168.0.2", 103))]), self.broadcast)
                  }
                )

        @with_timeout
        async it "doesn't remove existing entries":
            a = mock.Mock(name="a")

            call1 = mock.call(self.get_service, None, self.bridge
                , no_retry = True
                , broadcast = True
                , accept_found = True
                , error_catcher = []
                , message_timeout = 0.5
                , a = a
                )

            call2 = mock.call(self.get_service, None, self.bridge
                , no_retry = True
                , broadcast = True
                , accept_found = True
                , error_catcher = []
                , message_timeout = 0.6
                , a = a
                )

            services = [
                  (DiscoveryMessages.StateService(service=Services.UDP, port=100, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=101, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                ]
            self.bridge.transport_target.expect_call(call1, services)

            services = [
                  (DiscoveryMessages.StateService(service=Services.UDP, port=100, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=101, target=self.serial2), ("192.168.0.1", 56700), self.broadcast)

                , (DiscoveryMessages.StateService(service=Services.UDP, port=102, target=self.serial3), ("192.168.0.2", 56700), self.broadcast)
                , (DiscoveryMessages.StateService(service=Services.RESERVED1, port=103, target=self.serial3), ("192.168.0.2", 56700), self.broadcast)
                ]
            self.bridge.transport_target.expect_call(call2, services)

            found = {self.target1: self.info1}
            with self.retries([(20, 0.5), (19.5, 0.6)]):
                fn = await self.bridge._do_search([self.serial1, self.serial2, self.serial3], found, 20, a=a)
                self.assertEqual(sorted(fn), sorted([self.target2, self.target3]))

            self.assertEqual(self.bridge.transport_target.call, 1)
            self.assertEqual(found
                , { self.target1: self.info1
                  , self.target2: (set([(Services.UDP, ("192.168.0.1", 100)), (Services.RESERVED1, ("192.168.0.1", 101))]), self.broadcast)
                  , self.target3: (set([(Services.UDP, ("192.168.0.2", 102)), (Services.RESERVED1, ("192.168.0.2", 103))]), self.broadcast)
                  }
                )
