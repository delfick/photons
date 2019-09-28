# coding: spec

from photons_transport.session.discovery_options import NoDiscoveryOptions, NoEnvDiscoveryOptions
from photons_transport.errors import NoDesiredService, UnknownService, InvalidBroadcast
from photons_transport.session.network import NetworkSession, udp_retry_options
from photons_transport.transports.udp import UDP
from photons_transport.targets import LanTarget
from photons_transport.comms.base import Found
from photons_transport.fake import FakeDevice

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app.errors import TimedOut

from photons_messages import Services, DeviceMessages, DiscoveryMessages, protocol_register
from photons_products_registry import LIFIProductRegistry, capability_for_ids
from photons_control import test_helpers as chp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from contextlib import contextmanager
from unittest import mock
import asynctest
import binascii
import asyncio

describe AsyncTestCase, "NetworkSession":
    async before_each:
        self.final_future = asyncio.Future()
        self.default_broadcast = "1.2.3.255"

        self.transport_target = mock.Mock(
            name="target", spec=["script", "final_future", "default_broadcast", "discovery_options"]
        )
        self.transport_target.final_future = self.final_future
        self.transport_target.default_broadcast = self.default_broadcast
        self.transport_target.discovery_options = NoDiscoveryOptions.FieldSpec().empty_normalise()

        self.session = NetworkSession(self.transport_target)

    async after_each:
        await self.session.finish()
        self.final_future.cancel()

    async it "has properties":
        self.assertIs(self.session.UDPTransport, UDP)
        self.assertEqual(self.session.broadcast_transports, {})

    describe "finish":
        async it "closes all the broadcast_transports":
            b1 = mock.Mock(name="b1")
            b1.close = asynctest.mock.CoroutineMock(name="close")

            b2 = mock.Mock(name="b2")
            b2.close = asynctest.mock.CoroutineMock(name="close", side_effect=ValueError("NOPE"))

            b3 = mock.Mock(name="b3")
            b3.close = asynctest.mock.CoroutineMock(name="close")

            self.session.broadcast_transports["one"] = b1
            self.session.broadcast_transports["two"] = b2
            self.session.broadcast_transports["three"] = b3

            await self.session.finish()
            b1.close.assert_called_once_with()
            b2.close.assert_called_once_with()
            b3.close.assert_called_once_with()

    describe "retry_options_for":
        async it "returns udp_retry_options if it's a UDP transport":
            kwargs = {"host": "192.168.0.3", "port": 56700}
            transport = await self.session.make_transport("d073d5", Services.UDP, kwargs)
            self.assertIsInstance(transport, UDP)

            packet = mock.NonCallableMock(name="packet", spec=[])
            self.assertIs(self.session.retry_options_for(packet, transport), udp_retry_options)

    describe "determine_needed_transport":
        async it "says udp":
            services = mock.NonCallableMock(name="services", spec=[])
            packets = [DeviceMessages.GetPower(), DeviceMessages.StateLabel()]

            for packet in packets:
                got = await self.session.determine_needed_transport(packet, services)
                self.assertEqual(got, [Services.UDP])

    describe "choose_transport":
        async it "complains if we can't determined need transport":
            determine_needed_transport = asynctest.mock.CoroutineMock(
                name="determine_needed_transport"
            )
            determine_needed_transport.return_value = []

            packet = mock.Mock(name="packet", protocol=9001, pkt_type=89)
            services = mock.Mock(name="services")

            msg = "Unable to determine what service to send packet to"
            kwargs = {"protocol": 9001, "pkt_type": 89}
            with self.fuzzyAssertRaisesError(NoDesiredService, msg, **kwargs):
                with mock.patch.object(
                    self.session, "determine_needed_transport", determine_needed_transport
                ):
                    await self.session.choose_transport(packet, services)

            determine_needed_transport.assert_awaited_once_with(packet, services)

        async it "returns the desired service or complains if can't be found":
            need = [Services.UDP]
            determine_needed_transport = asynctest.mock.CoroutineMock(
                name="determine_needed_transport"
            )
            determine_needed_transport.return_value = need

            udpservice = mock.Mock(name="udpservice")

            packet = mock.NonCallableMock(name="packet", spec=[])
            services = {Services.UDP: udpservice}

            with mock.patch.object(
                self.session, "determine_needed_transport", determine_needed_transport
            ):
                self.assertIs(await self.session.choose_transport(packet, services), udpservice)

                msg = "Don't have a desired service"
                kwargs = {"need": need, "have": []}
                del services[Services.UDP]
                with self.fuzzyAssertRaisesError(NoDesiredService, msg, **kwargs):
                    await self.session.choose_transport(packet, services)

    describe "private do_search":

        @contextmanager
        def mocks(self, timeout, run_with):
            async def iterator(timeout):
                yield 10, 1
                yield 9, 2
                yield 7, 3
                yield 4, 4

            _search_retry_iterator = asynctest.MagicMock(
                name="_search_retry_iterator", side_effect=iterator
            )

            script = mock.Mock(name="script", spec=["run_with"])
            script.run_with = asynctest.MagicMock(name="run_with", side_effect=run_with)

            self.transport_target.script.return_value = script

            with mock.patch.object(self.session, "_search_retry_iterator", _search_retry_iterator):
                yield script

            _search_retry_iterator.assert_called_once_with(timeout)

        async it "can use hard coded discovery":
            self.transport_target.discovery_options = NoEnvDiscoveryOptions.FieldSpec().empty_normalise(
                hardcoded_discovery={"d073d5000001": "192.168.0.1", "d073d5000002": "192.168.0.2"}
            )

            self.assertEqual(self.session.found, Found())
            fn = await self.session._do_search(None, 20)

            self.assertEqual(
                sorted(fn),
                sorted([binascii.unhexlify(s) for s in ("d073d5000001", "d073d5000002")]),
            )

            self.assertEqual(self.session.found.serials, ["d073d5000001", "d073d5000002"])
            self.assertEqual(
                self.session.found["d073d5000001"],
                {
                    Services.UDP: await self.session.make_transport(
                        "d073d5000001", Services.UDP, {"host": "192.168.0.1", "port": 56700}
                    )
                },
            )
            self.assertEqual(
                self.session.found["d073d5000002"],
                {
                    Services.UDP: await self.session.make_transport(
                        "d073d5000002", Services.UDP, {"host": "192.168.0.2", "port": 56700}
                    )
                },
            )

            self.assertEqual(len(self.transport_target.script.mock_calls), 0)

        async it "finds":

            async def run_with(*args, **kwargs):
                s1 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=56, target="d073d5000001"
                )
                yield (s1, ("192.168.0.3", 56700), DiscoveryMessages.GetService())

                s3 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=58, target="d073d5000002"
                )
                yield (s3, ("192.168.0.4", 56700), DiscoveryMessages.GetService())

            self.assertEqual(self.session.found, Found())

            a = mock.Mock(name="a")
            with self.mocks(20, run_with) as script:
                fn = await self.session._do_search(["d073d5000001", "d073d5000002"], 20, a=a)

            kwargs = {
                "a": a,
                "no_retry": True,
                "broadcast": True,
                "accept_found": True,
                "error_catcher": [],
                "message_timeout": 1,
            }
            script.run_with.assert_called_once_with(None, self.session, **kwargs)

            self.transport_target.script.assert_called_once_with(
                DiscoveryMessages.GetService(
                    target=None,
                    tagged=True,
                    addressable=True,
                    res_required=True,
                    ack_required=False,
                )
            )

            self.assertEqual(
                sorted(fn),
                sorted([binascii.unhexlify(s) for s in ("d073d5000001", "d073d5000002")]),
            )

            self.assertEqual(self.session.found.serials, ["d073d5000001", "d073d5000002"])
            self.assertEqual(
                self.session.found["d073d5000001"],
                {
                    Services.UDP: await self.session.make_transport(
                        "d073d5000001", Services.UDP, {"host": "192.168.0.3", "port": 56}
                    )
                },
            )
            self.assertEqual(
                self.session.found["d073d5000002"],
                {
                    Services.UDP: await self.session.make_transport(
                        "d073d5000002", Services.UDP, {"host": "192.168.0.4", "port": 58}
                    )
                },
            )

        async it "can filter serials":

            async def run_with(*args, **kwargs):
                s1 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=56, target="d073d5000001"
                )
                yield (s1, ("192.168.0.3", 56700), DiscoveryMessages.GetService())

                s3 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=58, target="d073d5000002"
                )
                yield (s3, ("192.168.0.4", 56700), DiscoveryMessages.GetService())

            self.assertEqual(self.session.found, Found())
            self.transport_target.discovery_options = NoEnvDiscoveryOptions.FieldSpec().empty_normalise(
                serial_filter=["d073d5000001"]
            )

            a = mock.Mock(name="a")
            with self.mocks(20, run_with) as script:
                fn = await self.session._do_search(None, 20, a=a)

            kwargs = {
                "a": a,
                "no_retry": True,
                "broadcast": True,
                "accept_found": True,
                "error_catcher": [],
                "message_timeout": 1,
            }
            script.run_with.assert_called_once_with(None, self.session, **kwargs)

            self.transport_target.script.assert_called_once_with(
                DiscoveryMessages.GetService(
                    target=None,
                    tagged=True,
                    addressable=True,
                    res_required=True,
                    ack_required=False,
                )
            )

            self.assertEqual(sorted(fn), sorted([binascii.unhexlify(s) for s in ("d073d5000001",)]))

            self.assertEqual(self.session.found.serials, ["d073d5000001"])
            self.assertEqual(
                self.session.found["d073d5000001"],
                {
                    Services.UDP: await self.session.make_transport(
                        "d073d5000001", Services.UDP, {"host": "192.168.0.3", "port": 56}
                    )
                },
            )

        async it "stops after first search if serials is None and we found serials":

            async def run_with(*args, **kwargs):
                s1 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=56, target="d073d5000001"
                )
                yield (s1, ("192.168.0.3", 56700), DiscoveryMessages.GetService())

            self.assertEqual(self.session.found, Found())

            with self.mocks(30, run_with) as script:
                fn = await self.session._do_search(None, 30, broadcast="172.16.0.255")

            kwargs = {
                "no_retry": True,
                "broadcast": "172.16.0.255",
                "accept_found": True,
                "error_catcher": [],
                "message_timeout": 1,
            }
            script.run_with.assert_called_once_with(None, self.session, **kwargs)

            self.assertEqual(fn, [binascii.unhexlify("d073d5000001")])
            self.assertEqual(self.session.found.serials, ["d073d5000001"])

        async it "keeps trying till we find devices if serials is None":
            called = []

            async def run_with(*args, **kwargs):
                called.append("run_with")
                if len(called) != 3:
                    return

                s1 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=56, target="d073d5000001"
                )
                yield (s1, ("192.168.0.3", 56700), DiscoveryMessages.GetService())

            self.assertEqual(self.session.found, Found())

            with self.mocks(40, run_with) as script:
                fn = await self.session._do_search(None, 40, broadcast=False)

            call1 = mock.call(
                None,
                self.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=1,
            )

            call2 = mock.call(
                None,
                self.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=2,
            )

            call3 = mock.call(
                None,
                self.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=3,
            )

            self.assertEqual(script.run_with.mock_calls, [call1, call2, call3])

            self.assertEqual(fn, [binascii.unhexlify("d073d5000001")])
            self.assertEqual(self.session.found.serials, ["d073d5000001"])

        async it "keeps trying till we have all serials if serials is not None":
            called = []

            async def run_with(*args, **kwargs):
                called.append("run_with")

                if len(called) > 0:
                    s1 = DiscoveryMessages.StateService(
                        service=Services.UDP, port=56, target="d073d5000001"
                    )
                    yield (s1, ("192.168.0.3", 56700), DiscoveryMessages.GetService())

                if len(called) > 1:
                    s2 = DiscoveryMessages.StateService(
                        service=Services.UDP, port=58, target="d073d5000002"
                    )
                    yield (s2, ("192.168.0.4", 56700), DiscoveryMessages.GetService())

                if len(called) > 2:
                    s3 = DiscoveryMessages.StateService(
                        service=Services.UDP, port=59, target="d073d5000003"
                    )
                    yield (s3, ("192.168.0.5", 56700), DiscoveryMessages.GetService())

            self.assertEqual(self.session.found, Found())
            serials = ["d073d5000001", "d073d5000002", "d073d5000003"]

            with self.mocks(10, run_with) as script:
                fn = await self.session._do_search(serials, 10, broadcast=True)

            self.assertEqual(called, ["run_with", "run_with", "run_with"])

            call1 = mock.call(
                None,
                self.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=1,
            )

            call2 = mock.call(
                None,
                self.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=2,
            )

            call3 = mock.call(
                None,
                self.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=3,
            )

            self.assertEqual(script.run_with.mock_calls, [call1, call2, call3])

            self.assertEqual(sorted(fn), sorted([binascii.unhexlify(s) for s in serials]))
            self.assertEqual(self.session.found.serials, serials)

        async it "keeps trying till it's out of retries":
            called = []

            async def run_with(*args, **kwargs):
                called.append("run_with")

                if len(called) > 0:
                    s1 = DiscoveryMessages.StateService(
                        service=Services.UDP, port=56, target="d073d5000001"
                    )
                    yield (s1, ("192.168.0.3", 56700), DiscoveryMessages.GetService())

            self.assertEqual(self.session.found, Found())
            serials = ["d073d5000001", "d073d5000002", "d073d5000003"]

            with self.mocks(10, run_with) as script:
                fn = await self.session._do_search(serials, 10, broadcast=True)

            self.assertEqual(called, ["run_with"] * 4)

            self.assertEqual(fn, [binascii.unhexlify("d073d5000001")])
            self.assertEqual(self.session.found.serials, ["d073d5000001"])

    describe "private _search_retry_iterator":

        @with_timeout
        async it "returns an iterator":

            class Now:
                def __init__(s):
                    s.value = 0

                def skip(s, val):
                    if val > 0:
                        s.value += val

                def __call__(s):
                    return s.value

            now = Now()
            sleeps = []

            def call_later(amount, func):
                sleeps.append(amount)
                now.skip(amount)
                func()

            call_later = mock.Mock(name="call_later", side_effect=call_later)

            additions = [0.5, 0.7, 1, 2, 4, 2, 20]

            res = []
            with mock.patch.object(self.loop, "call_later", call_later):
                async for r in self.session._search_retry_iterator(20, get_now=now):
                    res.append(r)
                    now.skip(additions.pop(0))

            self.assertEqual(additions, [])
            self.assertEqual(
                sleeps,
                [
                    0.09999999999999998,
                    0.5,
                    0.7999999999999998,
                    0.40000000000000036,
                    -0.5999999999999996,
                    1.8000000000000007,
                ],
            )
            self.assertEqual(
                res,
                [
                    (20, 0.6),
                    (19.4, 1.1999999999999997),
                    (18.2, 1.7999999999999998),
                    (16.4, 2.4000000000000004),
                    (14.0, 3.4000000000000004),
                    (10.0, 3.8000000000000007),
                    (6.199999999999999, 4.400000000000002),
                ],
            )

    describe "make_transport":
        async it "complains if the service isn't a valid Service":
            serial = "d073d5000001"
            kwargs = {}
            service = mock.Mock(name="service", spec=[])

            with self.fuzzyAssertRaisesError(UnknownService, service=service):
                await self.session.make_transport(serial, service, kwargs)

        async it "returns None for reserved services":
            serial = "d073d5000001"
            kwargs = {}
            service = Services.RESERVED4

            self.assertIs(await self.session.make_transport(serial, service, kwargs), None)

        async it "creates a UDP transport for everything":
            transport = mock.Mock(name="transport")
            FakeUDPTransport = mock.Mock(name="UDPTransport", return_value=transport)

            serial = "d073d5001337"
            host = mock.Mock(name="host")
            port = mock.Mock(name="port")
            service = Services.UDP
            kwargs = {"host": host, "port": port}

            with mock.patch.object(self.session, "UDPTransport", FakeUDPTransport):
                self.assertIs(await self.session.make_transport(serial, service, kwargs), transport)
            FakeUDPTransport.assert_called_once_with(self.session, host, port, serial=serial)

    describe "make_broadcast_transport":
        async it "uses default_broadcast if broadcast is True":
            transport = await self.session.make_broadcast_transport(True)
            want = UDP(self.session, host=self.default_broadcast, port=56700)
            self.assertEqual(
                self.session.broadcast_transports, {(self.default_broadcast, 56700): want}
            )
            self.assertEqual(transport, want)

        async it "uses provided broadcast if it's a string":
            transport = await self.session.make_broadcast_transport("192.168.0.255")
            want = UDP(self.session, host="192.168.0.255", port=56700)
            self.assertEqual(self.session.broadcast_transports, {("192.168.0.255", 56700): want})
            self.assertEqual(transport, want)

        async it "uses provided broacast if it's a tuple of host and port":
            transport = await self.session.make_broadcast_transport(("192.168.0.255", 57))
            want = UDP(self.session, host="192.168.0.255", port=57)
            self.assertEqual(self.session.broadcast_transports, {("192.168.0.255", 57): want})
            self.assertEqual(transport, want)

        async it "complains if broadcast isn't a good type":
            for bad in (None, 0, False, 1, {}, [], (), (1,), (1, 1, 1), [1], {1: 1}, lambda: 1):
                msg = "Expect a string or \(host, port\) tuple"
                with self.fuzzyAssertRaisesError(InvalidBroadcast, msg, got=bad):
                    await self.session.make_broadcast_transport(bad)
