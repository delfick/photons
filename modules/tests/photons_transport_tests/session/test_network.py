import binascii
from contextlib import contextmanager
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_messages import DeviceMessages, DiscoveryMessages, Services
from photons_transport.comms.base import Found
from photons_transport.errors import InvalidBroadcast, NoDesiredService, UnknownService
from photons_transport.retry_options import Gaps
from photons_transport.session.discovery_options import (
    NoDiscoveryOptions,
    NoEnvDiscoveryOptions,
)
from photons_transport.session.network import NetworkSession
from photons_transport.transports.udp import UDP


class TestNetworkSession:

    @pytest.fixture()
    def V(self):
        class V:
            final_future = hp.create_future()
            default_broadcast = "1.2.3.255"

            @hp.memoized_property
            def transport_target(s):
                transport_target = mock.Mock(
                    name="target",
                    spec=[
                        "script",
                        "final_future",
                        "default_broadcast",
                        "discovery_options",
                        "gaps",
                    ],
                )
                transport_target.gaps = s.gaps
                transport_target.final_future = s.final_future
                transport_target.default_broadcast = s.default_broadcast
                transport_target.discovery_options = (
                    NoDiscoveryOptions.FieldSpec().empty_normalise()
                )
                return transport_target

            @hp.memoized_property
            def session(s):
                return NetworkSession(s.transport_target)

            @hp.memoized_property
            def gaps(s):
                return Gaps(
                    gap_between_ack_and_res=0.2, gap_between_results=0.35, timeouts=[(1, 1)]
                )

        return V()

    @pytest.fixture(autouse=True)
    async def cleanup(self, V):
        try:
            yield
        finally:
            await V.session.finish()
            V.final_future.cancel()

    async def test_it_has_properties(self, V):
        assert V.session.UDPTransport is UDP
        assert V.session.broadcast_transports == {}

    class TestFinish:
        async def test_it_closes_all_the_broadcast_transports(self, V):
            b1 = mock.Mock(name="b1")
            b1.close = pytest.helpers.AsyncMock(name="close")

            b2 = mock.Mock(name="b2")
            b2.close = pytest.helpers.AsyncMock(name="close", side_effect=ValueError("NOPE"))

            b3 = mock.Mock(name="b3")
            b3.close = pytest.helpers.AsyncMock(name="close")

            V.session.broadcast_transports["one"] = b1
            V.session.broadcast_transports["two"] = b2
            V.session.broadcast_transports["three"] = b3

            await V.session.finish()
            b1.close.assert_called_once_with()
            b2.close.assert_called_once_with()
            b3.close.assert_called_once_with()

    class TestRetryGaps:
        async def test_it_returns_the_retry_gaps(self, V):
            kwargs = {"host": "192.168.0.3", "port": 56700}
            transport = await V.session.make_transport("d073d5", Services.UDP, kwargs)
            assert isinstance(transport, UDP)

            packet = mock.NonCallableMock(name="packet", spec=[])

            uro1 = V.session.retry_gaps(packet, transport)
            assert uro1 is V.transport_target.gaps

    class TestDetermineNeededTransport:
        async def test_it_says_udp(self, V):
            services = mock.NonCallableMock(name="services", spec=[])
            packets = [DeviceMessages.GetPower(), DeviceMessages.StateLabel()]

            for packet in packets:
                got = await V.session.determine_needed_transport(packet, services)
                assert got == [Services.UDP]

    class TestChooseTransport:
        async def test_it_complains_if_we_cant_determined_need_transport(self, V):
            determine_needed_transport = pytest.helpers.AsyncMock(name="determine_needed_transport")
            determine_needed_transport.return_value = []

            packet = mock.Mock(name="packet", protocol=9001, pkt_type=89)
            services = mock.Mock(name="services")

            msg = "Unable to determine what service to send packet to"
            kwargs = {"protocol": 9001, "pkt_type": 89}
            with assertRaises(NoDesiredService, msg, **kwargs):
                with mock.patch.object(
                    V.session, "determine_needed_transport", determine_needed_transport
                ):
                    await V.session.choose_transport(packet, services)

            determine_needed_transport.assert_awaited_once_with(packet, services)

        async def test_it_returns_the_desired_service_or_complains_if_cant_be_found(self, V):
            need = [Services.UDP]
            determine_needed_transport = pytest.helpers.AsyncMock(name="determine_needed_transport")
            determine_needed_transport.return_value = need

            udpservice = mock.Mock(name="udpservice")

            packet = mock.NonCallableMock(name="packet", spec=[])
            services = {Services.UDP: udpservice}

            with mock.patch.object(
                V.session, "determine_needed_transport", determine_needed_transport
            ):
                assert await V.session.choose_transport(packet, services) is udpservice

                msg = "Don't have a desired service"
                kwargs = {"need": need, "have": []}
                del services[Services.UDP]
                with assertRaises(NoDesiredService, msg, **kwargs):
                    await V.session.choose_transport(packet, services)

    class TestPrivateDoSearch:

        @pytest.fixture()
        def mocks(self, V):
            @contextmanager
            def mocks(timeout, run):
                async def iterator(timeout):
                    yield 10, 1
                    yield 9, 2
                    yield 7, 3
                    yield 4, 4

                _search_retry_iterator = pytest.helpers.MagicAsyncMock(
                    name="_search_retry_iterator", side_effect=iterator
                )

                script = mock.Mock(name="script", spec=["run"])
                script.run = pytest.helpers.MagicAsyncMock(name="run", side_effect=run)

                V.transport_target.script.return_value = script

                with mock.patch.object(V.session, "_search_retry_iterator", _search_retry_iterator):
                    yield script

                _search_retry_iterator.assert_called_once_with(timeout)

            return mocks

        async def test_it_can_use_hard_coded_discovery(self, V):
            V.transport_target.discovery_options = (
                NoEnvDiscoveryOptions.FieldSpec().empty_normalise(
                    hardcoded_discovery={
                        "d073d5000001": "192.168.0.1",
                        "d073d5000002": "192.168.0.2",
                    }
                )
            )

            assert V.session.found == Found()
            fn = await V.session._do_search(None, 20)

            assert sorted(fn) == sorted(
                [binascii.unhexlify(s) for s in ("d073d5000001", "d073d5000002")]
            )

            assert V.session.found.serials == ["d073d5000001", "d073d5000002"]
            assert V.session.found["d073d5000001"] == {
                Services.UDP: await V.session.make_transport(
                    "d073d5000001", Services.UDP, {"host": "192.168.0.1", "port": 56700}
                )
            }
            assert V.session.found["d073d5000002"] == {
                Services.UDP: await V.session.make_transport(
                    "d073d5000002", Services.UDP, {"host": "192.168.0.2", "port": 56700}
                )
            }

            assert len(V.transport_target.script.mock_calls) == 0

        async def test_it_finds(self, V, mocks):

            async def run(*args, **kwargs):
                s1 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=56, target="d073d5000001"
                )
                s1.Information.update(
                    remote_addr=("192.168.0.3", 56700),
                    sender_message=DiscoveryMessages.GetService(),
                )
                yield s1

                s3 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=58, target="d073d5000002"
                )
                s3.Information.update(
                    remote_addr=("192.168.0.4", 56700),
                    sender_message=DiscoveryMessages.GetService(),
                )
                yield s3

            assert V.session.found == Found()

            a = mock.Mock(name="a")
            with mocks(20, run) as script:
                fn = await V.session._do_search(["d073d5000001", "d073d5000002"], 20, a=a)

            kwargs = {
                "a": a,
                "no_retry": True,
                "broadcast": True,
                "accept_found": True,
                "error_catcher": [],
                "message_timeout": 1,
            }
            script.run.assert_called_once_with(None, V.session, **kwargs)

            V.transport_target.script.assert_called_once_with(
                DiscoveryMessages.GetService(
                    target=None,
                    tagged=True,
                    addressable=True,
                    res_required=True,
                    ack_required=False,
                )
            )

            assert sorted(fn) == sorted(
                [binascii.unhexlify(s) for s in ("d073d5000001", "d073d5000002")]
            )

            assert V.session.found.serials == ["d073d5000001", "d073d5000002"]
            assert V.session.found["d073d5000001"] == {
                Services.UDP: await V.session.make_transport(
                    "d073d5000001", Services.UDP, {"host": "192.168.0.3", "port": 56}
                )
            }
            assert V.session.found["d073d5000002"] == {
                Services.UDP: await V.session.make_transport(
                    "d073d5000002", Services.UDP, {"host": "192.168.0.4", "port": 58}
                )
            }

        async def test_it_can_filter_serials(self, V, mocks):

            async def run(*args, **kwargs):
                s1 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=56, target="d073d5000001"
                )
                s1.Information.update(
                    remote_addr=("192.168.0.3", 56700),
                    sender_message=DiscoveryMessages.GetService(),
                )
                yield s1

                s3 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=58, target="d073d5000002"
                )
                s3.Information.update(
                    remote_addr=("192.168.0.4", 56700),
                    sender_message=DiscoveryMessages.GetService(),
                )
                yield s3

            assert V.session.found == Found()
            V.transport_target.discovery_options = (
                NoEnvDiscoveryOptions.FieldSpec().empty_normalise(serial_filter=["d073d5000001"])
            )

            a = mock.Mock(name="a")
            with mocks(20, run) as script:
                fn = await V.session._do_search(None, 20, a=a)

            kwargs = {
                "a": a,
                "no_retry": True,
                "broadcast": True,
                "accept_found": True,
                "error_catcher": [],
                "message_timeout": 1,
            }
            script.run.assert_called_once_with(None, V.session, **kwargs)

            V.transport_target.script.assert_called_once_with(
                DiscoveryMessages.GetService(
                    target=None,
                    tagged=True,
                    addressable=True,
                    res_required=True,
                    ack_required=False,
                )
            )

            assert sorted(fn) == sorted([binascii.unhexlify(s) for s in ("d073d5000001",)])

            assert V.session.found.serials == ["d073d5000001"]
            assert V.session.found["d073d5000001"] == {
                Services.UDP: await V.session.make_transport(
                    "d073d5000001", Services.UDP, {"host": "192.168.0.3", "port": 56}
                )
            }

        async def test_it_stops_after_first_search_if_serials_is_None_and_we_found_serials(
            self, V, mocks
        ):

            async def run(*args, **kwargs):
                s1 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=56, target="d073d5000001"
                )
                s1.Information.update(
                    remote_addr=("192.168.0.3", 56700),
                    sender_message=DiscoveryMessages.GetService(),
                )
                yield s1

            assert V.session.found == Found()

            with mocks(30, run) as script:
                fn = await V.session._do_search(None, 30, broadcast="172.16.0.255")

            kwargs = {
                "no_retry": True,
                "broadcast": "172.16.0.255",
                "accept_found": True,
                "error_catcher": [],
                "message_timeout": 1,
            }
            script.run.assert_called_once_with(None, V.session, **kwargs)

            assert fn == [binascii.unhexlify("d073d5000001")]
            assert V.session.found.serials == ["d073d5000001"]

        async def test_it_keeps_trying_till_we_find_devices_if_serials_is_None(self, V, mocks):
            called = []

            async def run(*args, **kwargs):
                called.append("run")
                if len(called) != 3:
                    return

                s1 = DiscoveryMessages.StateService(
                    service=Services.UDP, port=56, target="d073d5000001"
                )
                s1.Information.update(
                    remote_addr=("192.168.0.3", 56700),
                    sender_message=DiscoveryMessages.GetService(),
                )
                yield s1

            assert V.session.found == Found()

            with mocks(40, run) as script:
                fn = await V.session._do_search(None, 40, broadcast=False)

            call1 = mock.call(
                None,
                V.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=1,
            )

            call2 = mock.call(
                None,
                V.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=2,
            )

            call3 = mock.call(
                None,
                V.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=3,
            )

            assert script.run.mock_calls == [call1, call2, call3]

            assert fn == [binascii.unhexlify("d073d5000001")]
            assert V.session.found.serials == ["d073d5000001"]

        async def test_it_keeps_trying_till_we_have_all_serials_if_serials_is_not_None(
            self, V, mocks
        ):
            called = []

            async def run(*args, **kwargs):
                called.append("run")

                if len(called) > 0:
                    s1 = DiscoveryMessages.StateService(
                        service=Services.UDP, port=56, target="d073d5000001"
                    )
                    s1.Information.update(
                        remote_addr=("192.168.0.3", 56700),
                        sender_message=DiscoveryMessages.GetService(),
                    )
                    yield s1

                if len(called) > 1:
                    s2 = DiscoveryMessages.StateService(
                        service=Services.UDP, port=58, target="d073d5000002"
                    )
                    s2.Information.update(
                        remote_addr=("192.168.0.4", 56700),
                        sender_message=DiscoveryMessages.GetService(),
                    )
                    yield s2

                if len(called) > 2:
                    s3 = DiscoveryMessages.StateService(
                        service=Services.UDP, port=59, target="d073d5000003"
                    )
                    s3.Information.update(
                        remote_addr=("192.168.0.5", 56700),
                        sender_message=DiscoveryMessages.GetService(),
                    )
                    yield s3

            assert V.session.found == Found()
            serials = ["d073d5000001", "d073d5000002", "d073d5000003"]

            with mocks(10, run) as script:
                fn = await V.session._do_search(serials, 10, broadcast=True)

            assert called == ["run", "run", "run"]

            call1 = mock.call(
                None,
                V.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=1,
            )

            call2 = mock.call(
                None,
                V.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=2,
            )

            call3 = mock.call(
                None,
                V.session,
                no_retry=True,
                broadcast=True,
                accept_found=True,
                error_catcher=[],
                message_timeout=3,
            )

            assert script.run.mock_calls == [call1, call2, call3]

            assert sorted(fn) == sorted([binascii.unhexlify(s) for s in serials])
            assert V.session.found.serials == serials

        async def test_it_keeps_trying_till_its_out_of_retries(self, V, mocks):
            called = []

            async def run(*args, **kwargs):
                called.append("run")

                if len(called) > 0:
                    s1 = DiscoveryMessages.StateService(
                        service=Services.UDP, port=56, target="d073d5000001"
                    )
                    s1.Information.update(
                        remote_addr=("192.168.0.3", 56700),
                        sender_message=DiscoveryMessages.GetService(),
                    )
                    yield s1

            assert V.session.found == Found()
            serials = ["d073d5000001", "d073d5000002", "d073d5000003"]

            with mocks(10, run):
                fn = await V.session._do_search(serials, 10, broadcast=True)

            assert called == ["run"] * 4

            assert fn == [binascii.unhexlify("d073d5000001")]
            assert V.session.found.serials == ["d073d5000001"]

    class TestMakeTransport:
        async def test_it_complains_if_the_service_isnt_a_valid_Service(self, V):
            serial = "d073d5000001"
            kwargs = {}
            service = mock.Mock(name="service", spec=[])

            with assertRaises(UnknownService, service=service):
                await V.session.make_transport(serial, service, kwargs)

        async def test_it_returns_None_for_reserved_services(self, V):
            serial = "d073d5000001"
            kwargs = {}
            service = Services.RESERVED4

            assert await V.session.make_transport(serial, service, kwargs) is None

        async def test_it_creates_a_UDP_transport_for_everything(self, V):
            transport = mock.Mock(name="transport")
            FakeUDPTransport = mock.Mock(name="UDPTransport", return_value=transport)

            serial = "d073d5001337"
            host = mock.Mock(name="host")
            port = mock.Mock(name="port")
            service = Services.UDP
            kwargs = {"host": host, "port": port}

            with mock.patch.object(V.session, "UDPTransport", FakeUDPTransport):
                assert await V.session.make_transport(serial, service, kwargs) is transport
            FakeUDPTransport.assert_called_once_with(V.session, host, port, serial=serial)

    class TestMakeBroadcastTransport:
        async def test_it_uses_default_broadcast_if_broadcast_is_True(self, V):
            transport = await V.session.make_broadcast_transport(True)
            want = UDP(V.session, host=V.default_broadcast, port=56700)
            assert V.session.broadcast_transports == {(V.default_broadcast, 56700): want}
            assert transport == want

        async def test_it_uses_provided_broadcast_if_its_a_string(self, V):
            transport = await V.session.make_broadcast_transport("192.168.0.255")
            want = UDP(V.session, host="192.168.0.255", port=56700)
            assert V.session.broadcast_transports == {("192.168.0.255", 56700): want}
            assert transport == want

        async def test_it_uses_provided_broacast_if_its_a_tuple_of_host_and_port(self, V):
            transport = await V.session.make_broadcast_transport(("192.168.0.255", 57))
            want = UDP(V.session, host="192.168.0.255", port=57)
            assert V.session.broadcast_transports == {("192.168.0.255", 57): want}
            assert transport == want

        async def test_it_complains_if_broadcast_isnt_a_good_type(self, V):
            for bad in (None, 0, False, 1, {}, [], (), (1,), (1, 1, 1), [1], {1: 1}, lambda: 1):
                msg = r"Expect a string or \(host, port\) tuple"
                with assertRaises(InvalidBroadcast, msg, got=bad):
                    await V.session.make_broadcast_transport(bad)
