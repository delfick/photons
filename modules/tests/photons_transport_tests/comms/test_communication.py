# coding: spec

from photons_transport.comms.base import Communication, Found, FakeAck
from photons_transport.errors import FailedToFindDevice
from photons_transport.transports.base import Transport
from photons_transport.comms.receiver import Receiver
from photons_transport import RetryOptions

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import FoundNoDevices, TimedOut
from photons_app import helpers as hp

from photons_messages import DeviceMessages, protocol_register, LIFXPacket, CoreMessages
from photons_protocol.messages import Messages

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import dictobj, sb, Meta
from contextlib import contextmanager
from unittest import mock
import binascii
import asyncio
import pytest


@pytest.fixture()
def V():
    class V:
        final_future = asyncio.Future()

        @hp.memoized_property
        def transport_target(s):
            return mock.Mock(
                name="transport_target",
                final_future=s.final_future,
                protocol_register=protocol_register,
                spec=["final_future", "protocol_register"],
            )

        @hp.memoized_property
        def communication(s):
            return Communication(s.transport_target)

    return V()


@pytest.fixture(autouse=True)
async def cleanup(V):
    try:
        yield
    finally:
        V.final_future.cancel()
        await V.communication.finish()


describe "FakeAck":
    it "behaves like an Acknowledgement":
        addr = ("125.6.78.1", 3456)
        serial = "d073d5000001"

        ack = FakeAck(2, 20, binascii.unhexlify(serial), serial, addr)

        assert ack.source == 2
        assert ack.sequence == 20
        assert binascii.hexlify(ack.target).decode() == serial
        assert ack.serial == serial
        assert ack.Information.remote_addr == addr

        assert ack | CoreMessages.Acknowledgement

        assert repr(ack) == "<ACK source: 2, sequence: 20, serial: d073d5000001>"

describe "Communication":
    async it "is formattable", V:

        class Other:
            pass

        other = Other()
        options = {"comms": V.communication, "other": other}

        class Thing(dictobj.Spec):
            other = dictobj.Field(sb.overridden("{other}"), formatted=True)
            comms = dictobj.Field(sb.overridden("{comms}"), formatted=True)

        thing = Thing.FieldSpec(formatter=MergedOptionStringFormatter).normalise(
            Meta(options, []).at("thing"), {}
        )

        assert thing.comms is V.communication
        assert thing.other == str(other)

    async it "takes in a transport_target", V:
        assert V.communication.transport_target is V.transport_target
        assert V.communication.found == Found()
        assert isinstance(V.communication.receiver, Receiver)

    async it "has a stop fut", V:
        assert not V.communication.stop_fut.done()
        V.communication.stop_fut.cancel()
        assert not V.final_future.cancelled()

        comm2 = Communication(V.transport_target)
        assert not comm2.stop_fut.done()
        V.final_future.set_result(1)
        assert comm2.stop_fut.cancelled()

    async it "calls setup", V:
        called = []

        class C(Communication):
            def setup(s):
                for n in ("transport_target", "stop_fut", "receiver", "found"):
                    assert hasattr(s, n)
                called.append("setup")
                s.wat = 2

        c = C(V.transport_target)
        assert c.wat == 2

        assert called == ["setup"]

    describe "finish":
        async it "can finish", V:
            t1 = mock.Mock(name="t1")
            t1.close = pytest.helpers.AsyncMock(name="close")

            t2 = mock.Mock(name="t2")
            t2.close = pytest.helpers.AsyncMock(name="close")

            t3 = mock.Mock(name="t3")
            t3.close = pytest.helpers.AsyncMock(name="close")

            found = V.communication.found
            found["d073d5000001"] = {"UDP": t1, "OTH": t2}
            found["d073d5000002"] = {"MEM": t3}
            assert found

            assert not V.communication.stop_fut.done()
            await V.communication.finish()
            assert V.communication.stop_fut.done()
            assert not V.final_future.done()

            assert not found

            t1.close.assert_called_once_with()
            t2.close.assert_called_once_with()
            t3.close.assert_called_once_with()

        async it "can finish even if forget raise errors", V:
            called = []

            async def forget(serial):
                called.append(serial)
                raise Exception("NOPE")

            found = V.communication.found
            found["d073d5000001"] = {"UDP": mock.Mock(name="UDP"), "OTH": mock.Mock(name="OTH")}
            found["d073d5000002"] = {"MEM": mock.Mock(name="MEM")}

            assert not V.communication.stop_fut.done()

            with mock.patch.object(V.communication, "forget", forget):
                await V.communication.finish()

            assert V.communication.stop_fut.done()
            assert not V.final_future.done()

            assert called == ["d073d5000001", "d073d5000002"]

    describe "source":
        async it "generates a source", V:
            source = V.communication.source
            assert source > 0 and source < 1 << 32, source

            s2 = V.communication.source
            assert s2 == source

            del V.communication.source
            s3 = V.communication.source
            assert s3 != source

            for _ in range(1000):
                del V.communication.source
                s = V.communication.source
                assert s > 0 and s < 1 << 32, s

    describe "seq":
        async it "records where we're at with the target", V:
            target = mock.Mock(name="target")
            assert not hasattr(V.communication, "_seq")
            assert V.communication.seq(target) == 1
            assert V.communication._seq == {target: 1}

            assert V.communication.seq(target) == 2
            assert V.communication._seq == {target: 2}

            target2 = mock.Mock(name="target2")
            assert V.communication.seq(target2) == 1
            assert V.communication._seq == {target: 2, target2: 1}

            assert V.communication.seq(target) == 3
            assert V.communication._seq == {target: 3, target2: 1}

        async it "wraps around at 255", V:
            target = mock.Mock(name="target2")
            assert V.communication.seq(target) == 1
            assert V.communication._seq == {target: 1}

            V.communication._seq[target] = 254
            assert V.communication.seq(target) == 255
            assert V.communication._seq == {target: 255}

            assert V.communication.seq(target) == 0
            assert V.communication._seq == {target: 0}

    describe "forget":
        async it "does nothing if serial not in found", V:
            serial = "d073d5000001"
            assert serial not in V.communication.found
            await V.communication.forget(serial)

        async it "closes services and removes from found", V:
            t1 = mock.Mock(name="t1")
            t1.close = pytest.helpers.AsyncMock(name="close", side_effect=Exception("NOPE"))

            t2 = mock.Mock(name="t2")
            t2.close = pytest.helpers.AsyncMock(name="close")

            serial = "d073d5000001"

            found = V.communication.found
            found[serial] = {"UDP": t1, "OTH": t2}

            await V.communication.forget(serial)

            t1.close.assert_called_once_with()
            t2.close.assert_called_once_with()

            assert serial not in found

    describe "add_service":
        async it "can make a new transport when serial not already in found", V:
            assert not V.communication.found

            serial = "d073d5000001"
            service = mock.Mock(name="service")
            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = pytest.helpers.AsyncMock(name="make_transport", return_value=t)

            with mock.patch.object(V.communication, "make_transport", make_transport):
                await V.communication.add_service(serial, service, a=a)

            assert V.communication.found[serial] == {service: t}
            make_transport.assert_called_once_with(serial, service, {"a": a})

        async it "can make a new transport when serial already in found", V:
            serial = "d073d5000001"
            othertransport = mock.Mock(name="othertransport")
            V.communication.found[serial] = {"OTH": othertransport}

            service = mock.Mock(name="service")
            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = pytest.helpers.AsyncMock(name="make_transport", return_value=t)

            with mock.patch.object(V.communication, "make_transport", make_transport):
                await V.communication.add_service(serial, service, a=a)

            assert V.communication.found[serial] == {"OTH": othertransport, service: t}
            make_transport.assert_called_once_with(serial, service, {"a": a})

        async it "can replace a transport", V:
            serial = "d073d5000001"
            service = mock.Mock(name="service")
            othertransport = mock.Mock(name="othertransport")
            othertransport.close = pytest.helpers.AsyncMock(name="close")

            V.communication.found[serial] = {service: othertransport}

            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = pytest.helpers.AsyncMock(name="make_transport", return_value=t)

            with mock.patch.object(V.communication, "make_transport", make_transport):
                await V.communication.add_service(serial, service, a=a)

            assert V.communication.found[serial] == {service: t}
            make_transport.assert_called_once_with(serial, service, {"a": a})
            othertransport.close.assert_called_once_with()

        async it "can replace a transport when closing it fails", V:
            serial = "d073d5000001"
            service = mock.Mock(name="service")
            othertransport = mock.Mock(name="othertransport")
            othertransport.close = pytest.helpers.AsyncMock(
                name="close", side_effect=Exception("NOPE")
            )

            V.communication.found[serial] = {service: othertransport}

            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = pytest.helpers.AsyncMock(name="make_transport", return_value=t)

            with mock.patch.object(V.communication, "make_transport", make_transport):
                await V.communication.add_service(serial, service, a=a)

            assert V.communication.found[serial] == {service: t}
            make_transport.assert_called_once_with(serial, service, {"a": a})
            othertransport.close.assert_called_once_with()

        async it "does not replace if the transport is equal", V:

            class T:
                def __eq__(s, other):
                    return True

            t1 = T()
            t2 = T()

            serial = "d073d5000001"
            service = mock.Mock(name="service")

            V.communication.found[serial] = {service: t1}

            a = mock.Mock(name="a")

            make_transport = pytest.helpers.AsyncMock(name="make_transport", return_value=t2)

            with mock.patch.object(V.communication, "make_transport", make_transport):
                await V.communication.add_service(serial, service, a=a)

            assert V.communication.found[serial] == {service: t1}
            make_transport.assert_called_once_with(serial, service, {"a": a})

    describe "find_devices":
        async it "uses find_specific_serials", V:
            a = mock.Mock(name="a")
            broadcast = mock.Mock(name="broadcast")
            ignore_lost = mock.Mock(name="ignore_lost")
            raise_on_none = mock.Mock(name="raise_on_none")

            found = mock.Mock(name="found")
            missing = mock.Mock(name="missing")
            find_specific_serials = pytest.helpers.AsyncMock(name="find_specific_serials")
            find_specific_serials.return_value = (found, missing)

            with mock.patch.object(V.communication, "find_specific_serials", find_specific_serials):
                f = await V.communication.find_devices(
                    ignore_lost=ignore_lost, raise_on_none=raise_on_none, broadcast=broadcast, a=a
                )

            assert f is found
            find_specific_serials.assert_called_once_with(
                None, ignore_lost=ignore_lost, raise_on_none=raise_on_none, broadcast=broadcast, a=a
            )

        async it "has defaults for ignore_lost and raise_on_none", V:
            a = mock.Mock(name="a")

            found = mock.Mock(name="found")
            missing = mock.Mock(name="missing")
            find_specific_serials = pytest.helpers.AsyncMock(name="find_specific_serials")
            find_specific_serials.return_value = (found, missing)

            with mock.patch.object(V.communication, "find_specific_serials", find_specific_serials):
                f = await V.communication.find_devices(a=a)

            assert f is found
            find_specific_serials.assert_called_once_with(
                None, ignore_lost=False, raise_on_none=False, a=a
            )

    describe "find_specific_serials":

        @pytest.fixture()
        def V(self, V):
            class V(V.__class__):
                info1 = mock.Mock(name="info1")
                info2 = mock.Mock(name="info2")

                serial1 = "d073d5000001"
                serial2 = "d073d5000002"

                @hp.memoized_property
                def target1(s):
                    return binascii.unhexlify(s.serial1)[:6]

                @hp.memoized_property
                def target2(s):
                    return binascii.unhexlify(s.serial2)[:6]

                async def assertSpecificSerials(s, serials, found, missing):
                    a = mock.Mock(name="a")
                    broadcast = mock.Mock(name="broadcast")
                    ignore_lost = mock.Mock(name="ignore_lost")
                    raise_on_none = mock.Mock(name="raise_on_none")

                    f = Found()
                    for target, info in found.items():
                        f[target] = info

                    _find_specific_serials = pytest.helpers.AsyncMock(name="_find_specific_serials")
                    _find_specific_serials.return_value = f

                    with mock.patch.object(
                        s.communication, "_find_specific_serials", _find_specific_serials
                    ):
                        f2, m = await s.communication.find_specific_serials(
                            serials,
                            ignore_lost=ignore_lost,
                            raise_on_none=raise_on_none,
                            broadcast=broadcast,
                            a=a,
                        )

                    assert f2 is f
                    assert m == missing
                    _find_specific_serials.assert_called_once_with(
                        serials,
                        ignore_lost=ignore_lost,
                        raise_on_none=raise_on_none,
                        broadcast=broadcast,
                        a=a,
                    )

                    _find_specific_serials.reset_mock()
                    with mock.patch.object(
                        s.communication, "_find_specific_serials", _find_specific_serials
                    ):
                        f3, m = await s.communication.find_specific_serials(
                            serials, broadcast=broadcast, a=a
                        )

                    assert f3 is f
                    assert m == missing
                    _find_specific_serials.assert_called_once_with(
                        serials, ignore_lost=False, raise_on_none=False, broadcast=broadcast, a=a
                    )

            return V()

        async it "No missing if no found and no serials", V:
            serials = None
            found = {}
            missing = []
            await V.assertSpecificSerials(serials, found, missing)

        async it "No missing if found has all the serials", V:
            serials = [V.serial1, V.serial2]

            found = {V.target1: V.info1, V.target2: V.info2}
            missing = []
            await V.assertSpecificSerials(serials, found, missing)

        async it "No missing if more found than serials", V:
            serials = [V.serial1]

            found = {V.target1: V.info1, V.target2: V.info2}
            missing = []
            await V.assertSpecificSerials(serials, found, missing)

        async it "has missing if less found than serials", V:
            serials = [V.serial1, V.serial2]

            found = {V.target1: V.info1}
            missing = [V.serial2]
            await V.assertSpecificSerials(serials, found, missing)

        async it "has missing if no found", V:
            serials = [V.serial1, V.serial2]

            found = {}
            missing = [V.serial1, V.serial2]
            await V.assertSpecificSerials(serials, found, missing)

        async it "no missing if found and no serials", V:
            serials = None
            found = {V.target1: V.info1, V.target2: V.info2}
            missing = []
            await V.assertSpecificSerials(serials, found, missing)

    describe "private find_specific_serials":
        async it "uses _do_search", V:
            found = V.communication.found

            s1 = mock.Mock(name="s1")
            s2 = mock.Mock(name="s2")

            services = {"d073d5000001": s1, "d073d5000002": s2}

            async def _do_search(serials, timeout, **kwargs):
                for serial in serials:
                    V.communication.found[serial] = services[serial]
                return set(serials)

            _do_search = pytest.helpers.AsyncMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(V.communication, "_do_search", _do_search):
                assert (
                    await V.communication._find_specific_serials(serials, timeout=timeout, a=a)
                    is found
                )

            _do_search.assert_called_once_with(serials, timeout, a=a)

        async it "can remove lost", V:
            s1 = mock.Mock(name="s1", spec=[])
            s2 = mock.Mock(name="s2", spec=[])
            s3 = mock.Mock(name="s3", spec=["close"])
            s3.close = pytest.helpers.AsyncMock(name="s3")

            found = V.communication.found
            found["d073d5000003"] = {"UDP": s3}

            services = {"d073d5000001": s1, "d073d5000002": s2}

            async def _do_search(serials, timeout, **kwargs):
                for serial in serials:
                    V.communication.found[serial] = services[serial]
                return set(serials)

            _do_search = pytest.helpers.AsyncMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(V.communication, "_do_search", _do_search):
                assert (
                    await V.communication._find_specific_serials(serials, timeout=timeout, a=a)
                    is found
                )

            _do_search.assert_called_once_with(serials, timeout, a=a)

            assert "d073d5000003" not in found
            s3.close.assert_called_once_with()

        async it "does not remove lost if ignore_lost", V:
            s1 = mock.Mock(name="s1", spec=[])
            s2 = mock.Mock(name="s2", spec=[])
            s3 = mock.Mock(name="s3", spec=[])

            found = V.communication.found
            found["d073d5000003"] = {"UDP": s3}

            services = {"d073d5000001": s1, "d073d5000002": s2}

            async def _do_search(serials, timeout, **kwargs):
                for serial in serials:
                    V.communication.found[serial] = services[serial]
                return set(serials)

            _do_search = pytest.helpers.AsyncMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(V.communication, "_do_search", _do_search):
                assert (
                    await V.communication._find_specific_serials(
                        serials, timeout=timeout, ignore_lost=True, a=a
                    )
                ) is found

            _do_search.assert_called_once_with(serials, timeout, a=a)

            assert "d073d5000003" in found

        async it "complains if none are found and raise_on_none", V:
            s3 = mock.Mock(name="s3", spec=["close"])
            s3.close = pytest.helpers.AsyncMock(name="close")

            found = V.communication.found
            found["d073d5000003"] = {"UDP": s3}

            async def _do_search(serials, timeout, **kwargs):
                return set()

            _do_search = pytest.helpers.AsyncMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            timeout = mock.Mock(name="timeout")

            with assertRaises(FoundNoDevices):
                with mock.patch.object(V.communication, "_do_search", _do_search):
                    await V.communication._find_specific_serials(
                        None, timeout=timeout, raise_on_none=True, a=a
                    )

            _do_search.assert_called_once_with(None, timeout, a=a)

            assert not found
            s3.close.assert_called_once_with()

        async it "does not complain if none are found and raise_on_none but non None serials", V:
            s3 = mock.Mock(name="s3", spec=[])
            found = V.communication.found
            found["d073d5000003"] = {"UDP": s3}

            async def _do_search(serials, timeout, **kwargs):
                return set()

            _do_search = pytest.helpers.AsyncMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(V.communication, "_do_search", _do_search):
                assert (
                    await V.communication._find_specific_serials(
                        serials, raise_on_none=True, timeout=timeout, a=a
                    )
                ) is found

            _do_search.assert_called_once_with(serials, timeout, a=a)

        async it "does not complain if none are found if not raise_on_none", V:
            s3 = mock.Mock(name="s3", spec=[])
            found = V.communication.found
            found["d073d5000003"] = {"UDP": s3}

            async def _do_search(serials, timeout, **kwargs):
                return set()

            _do_search = pytest.helpers.AsyncMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(V.communication, "_do_search", _do_search):
                assert (
                    await V.communication._find_specific_serials(
                        None, ignore_lost=True, timeout=timeout, a=a
                    )
                ) is found

            _do_search.assert_called_once_with(None, timeout, a=a)

            assert "d073d5000003" in found

    describe "broadcast":
        async it "is a send with a broadcast transport", V:
            a = mock.Mock(name="a")
            res = mock.Mock(name="res")
            packet = mock.Mock(name="packet")
            broadcast = mock.Mock(name="broadcast")

            transport = mock.Mock(name="transport")

            send_single = pytest.helpers.AsyncMock(name="send_single", return_value=res)
            make_broadcast_transport = pytest.helpers.AsyncMock(
                name="make_broadcast_transport", return_value=transport
            )

            mod = {"send_single": send_single, "make_broadcast_transport": make_broadcast_transport}
            with mock.patch.multiple(V.communication, **mod):
                assert await V.communication.broadcast(packet, broadcast, a=a) is res

            make_broadcast_transport.assert_awaited_once_with(broadcast)
            send_single.assert_awaited_once_with(
                packet, is_broadcast=True, transport=transport, a=a
            )

    describe "send_single":

        async it "sends", V:
            transport_in = mock.Mock(name="transport_in")
            transport_out = mock.Mock(name="transport_out")

            broadcast = mock.Mock(name="broadcast")
            is_broadcast = mock.Mock(name="broadcast")

            limit = mock.Mock(name="limit")
            packet = mock.Mock(name="packet")
            timeout = mock.Mock(name="timeout")
            no_retry = mock.Mock(name="no_retry")
            original = mock.Mock(name="original")
            connect_timeout = mock.Mock(name="connect_timeout")

            _transport_for_send = pytest.helpers.AsyncMock(name="_transport_for_send")
            _transport_for_send.return_value = (transport_out, is_broadcast)

            retry_options = mock.Mock(name="retry_options")
            retry_options_for = mock.Mock(name="retry_options_for", return_value=retry_options)

            writer = mock.Mock(name="writer")
            FakeWriter = mock.Mock(name="Writer", return_value=writer)

            class Waiter:
                def __init__(s):
                    s.reset()

                def reset(s):
                    s.cancelled = False

                def cancel(s):
                    s.cancelled = True

            waiter = Waiter()
            FakeWaiter = mock.Mock(name="Waiter", return_value=waiter)

            res = mock.Mock(name="res")

            async def ret():
                return res

            get_response_info = {"ret": ret}

            async def _get_response(*args, **kwargs):
                assert not waiter.cancelled
                return await get_response_info["ret"]()

            _get_response = pytest.helpers.AsyncMock(
                name="_get_response", side_effect=_get_response
            )

            mod = {
                "retry_options_for": retry_options_for,
                "_get_response": _get_response,
                "_transport_for_send": _transport_for_send,
            }
            patch_comms = mock.patch.multiple(V.communication, **mod)
            patch_writer = mock.patch("photons_transport.comms.base.Writer", FakeWriter)
            patch_waiter = mock.patch("photons_transport.comms.base.Waiter", FakeWaiter)

            with patch_comms, patch_writer, patch_waiter:
                kwargs = {
                    "timeout": timeout,
                    "limit": limit,
                    "no_retry": no_retry,
                    "transport": transport_in,
                    "broadcast": broadcast,
                    "connect_timeout": connect_timeout,
                }
                assert await V.communication.send_single(original, packet, **kwargs) is res

                _transport_for_send.assert_called_once_with(
                    transport_in, packet, original, broadcast, connect_timeout
                )
                retry_options_for.assert_called_once_with(original, transport_out)
                FakeWriter.assert_called_once_with(
                    V.communication,
                    transport_out,
                    V.communication.receiver,
                    original,
                    packet,
                    retry_options,
                    did_broadcast=is_broadcast,
                    connect_timeout=connect_timeout,
                )
                FakeWaiter.assert_called_once_with(
                    V.communication.stop_fut, writer, retry_options, no_retry=no_retry
                )
                _get_response.assert_awaited_once_with(packet, timeout, waiter, limit=limit)
                assert waiter.cancelled

                # Make sure waiter is cancelled if _get_response raises an exception
                waiter.reset()

                async def raise_error():
                    raise ValueError("NOPE")

                get_response_info["ret"] = raise_error
                assert not waiter.cancelled
                with assertRaises(ValueError, "NOPE"):
                    await V.communication.send_single(original, packet, **kwargs)
                assert waiter.cancelled

                # Make sure waiter is cancelled if _get_response gets cancelled
                waiter.reset()

                async def cancel():
                    fut = asyncio.Future()
                    fut.cancel()
                    await fut

                get_response_info["ret"] = cancel
                assert not waiter.cancelled
                with assertRaises(asyncio.CancelledError):
                    await V.communication.send_single(original, packet, **kwargs)
                assert waiter.cancelled

        async it "works without so much mocks", V:
            called = []

            class T(Transport):
                async def is_transport_active(s, packet, transport):
                    return True

                async def close_transport(s, transport):
                    pass

                def __eq__(s, other):
                    called.append("__eq__")
                    assert other is None
                    return False

                async def spawn_transport(s, timeout):
                    called.append("spawn_transport")
                    return s

                async def write(s, transport, bts, original_message):
                    called.append("write")

                    pkt = Messages.unpack(bts, protocol_register=protocol_register)

                    res = DeviceMessages.EchoResponse(
                        source=pkt.source, sequence=pkt.sequence, target=pkt.target, echoing=b"pong"
                    )

                    loop = asyncio.get_event_loop()
                    bts = res.pack().tobytes()
                    addr = ("fake://device", 56700)
                    loop.call_soon(s.session.sync_received_data, bts, addr)

            class C(Communication):
                def retry_options_for(s, original, transport_out):
                    called.append("retry_options_for")
                    return RetryOptions()

                async def choose_transport(s, original, services):
                    called.append("choose_transport")
                    return services["SERV"]

                async def make_transport(s, serial, service, kwargs):
                    called.append("make_transport")
                    assert service == "SERV"
                    return T(s)

            comms = C(V.transport_target)
            serial = "d073d5000001"
            await comms.add_service(serial, "SERV")
            assert called == ["make_transport", "__eq__"]

            original = DeviceMessages.EchoRequest(echoing=b"ping")
            packet = original.clone()
            packet.update(source=1, sequence=1, target=serial)

            res = await comms.send_single(original, packet, timeout=2)
            assert len(res) == 1
            pkt, addr, orig = res[0]
            assert pkt | DeviceMessages.EchoResponse
            assert pkt.echoing[: pkt.echoing.find(b"\x00")] == b"pong"

            assert addr == ("fake://device", 56700)
            assert orig is original

            assert called == [
                "make_transport",
                "__eq__",
                "choose_transport",
                "spawn_transport",
                "retry_options_for",
                "write",
            ]

    describe "private transport_for_send":

        @pytest.fixture()
        def V(self, V):
            class V(V.__class__):
                packet = mock.Mock(name="packet")
                original = mock.Mock(name="original")
                connect_timeout = mock.Mock(name="connect_timeout")

                @hp.memoized_property
                def transport(s):
                    transport = mock.Mock(name="transport")
                    transport.spawn = pytest.helpers.AsyncMock(name="spawn")
                    return transport

                @contextmanager
                def maker_mocks(s):
                    make_broadcast_transport = pytest.helpers.AsyncMock(
                        name="make_broadcast_transport", return_value=s.transport
                    )
                    choose_transport = pytest.helpers.AsyncMock(
                        name="choose_transport", return_value=s.transport
                    )

                    mbt_patch = mock.patch.object(
                        s.communication, "make_broadcast_transport", make_broadcast_transport
                    )
                    ct_patch = mock.patch.object(
                        s.communication, "choose_transport", choose_transport
                    )

                    with mbt_patch, ct_patch:
                        yield (make_broadcast_transport, choose_transport)

            return V()

        async it "uses make_broadcast_transport if broadcast", V:
            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(
                    None, V.packet, V.original, True, V.connect_timeout
                )
                assert res == (V.transport, True)

            make_broadcast_transport.assert_called_once_with(True)
            assert len(choose_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

        async it "uses make_broadcast_transport if broadcast is an address", V:
            broadcast = "192.168.0.255"

            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(
                    None, V.packet, V.original, broadcast, V.connect_timeout
                )
                assert res == (V.transport, True)

            make_broadcast_transport.assert_called_once_with(broadcast)
            assert len(choose_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

        async it "uses make_broadcast_transport if packet target is None", V:
            V.packet.target = None

            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(
                    None, V.packet, V.original, False, V.connect_timeout
                )
                assert res == (V.transport, True)

            make_broadcast_transport.assert_called_once_with(True)
            assert len(choose_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

        async it "uses choose_transport if not for broadcasting", V:
            V.packet.target = binascii.unhexlify("d073d5")
            V.packet.serial = "d073d5"

            services = mock.Mock(name="services")
            V.communication.found["d073d5"] = services

            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(
                    None, V.packet, V.original, False, V.connect_timeout
                )
                assert res == (V.transport, False)

            choose_transport.assert_called_once_with(V.original, services)
            assert len(make_broadcast_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

        async it "complains if the serial doesn't exist", V:
            V.packet.target = binascii.unhexlify("d073d5")
            V.packet.serial = "d073d5"

            with assertRaises(FailedToFindDevice, serial="d073d5"):
                with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                    await V.communication._transport_for_send(
                        None, V.packet, V.original, False, V.connect_timeout
                    )

            assert len(make_broadcast_transport.mock_calls) == 0
            assert len(choose_transport.mock_calls) == 0
            assert len(V.transport.spawn.mock_calls) == 0

        async it "just spawns transport if one is provided", V:
            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(
                    V.transport, V.packet, V.original, False, V.connect_timeout
                )
                assert res == (V.transport, False)

            assert len(make_broadcast_transport.mock_calls) == 0
            assert len(choose_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

    describe "received_data":
        async it "unpacks bytes and sends to the receiver", V:
            allow_zero = mock.Mock(name="allow_zero")
            addr = mock.Mock(name="addr")

            def recv(pkt, addr, *, allow_zero):
                assert pkt | DeviceMessages.StatePower
                assert pkt.level == 100

            recv = pytest.helpers.AsyncMock(name="recv", side_effect=recv)

            with mock.patch.object(V.communication.receiver, "recv", recv):
                pkt = DeviceMessages.StatePower(level=100, source=1, sequence=1, target=None)
                data = pkt.pack().tobytes()
                await V.communication.received_data(data, addr, allow_zero=allow_zero)

            recv.assert_called_once_with(mock.ANY, addr, allow_zero=allow_zero)

        async it "unpacks unknown packets", V:
            allow_zero = mock.Mock(name="allow_zero")
            addr = mock.Mock(name="addr")

            def recv(pkt, addr, *, allow_zero):
                assert isinstance(pkt, LIFXPacket)
                assert pkt.pkt_type == 9001
                assert pkt.payload == b"things"

            recv = pytest.helpers.AsyncMock(name="recv", side_effect=recv)

            with mock.patch.object(V.communication.receiver, "recv", recv):
                pkt = LIFXPacket(
                    payload=b"things", pkt_type=9001, source=1, sequence=1, target=None
                )
                data = pkt.pack().tobytes()
                await V.communication.received_data(data, addr, allow_zero=allow_zero)

            recv.assert_called_once_with(mock.ANY, addr, allow_zero=allow_zero)

        async it "ignores invalid data", V:
            allow_zero = mock.Mock(name="allow_zero")
            addr = mock.Mock(name="addr")

            recv = pytest.helpers.AsyncMock(name="recv")

            with mock.patch.object(V.communication.receiver, "recv", recv):
                data = "NOPE"
                await V.communication.received_data(data, addr, allow_zero=allow_zero)

            assert len(recv.mock_calls) == 0

    describe "private get_response":

        @pytest.fixture()
        def serial(self):
            return "d073d5001337"

        @pytest.fixture()
        def packet(self, serial):
            return mock.Mock(name="packet", serial=serial)

        async it "can successfully return results", V, packet:
            a = mock.Mock(name="a")
            b = mock.Mock(name="b")

            waiter = asyncio.Future()

            t = hp.async_as_background(V.communication._get_response(packet, 0.1, waiter))
            asyncio.get_event_loop().call_later(0.05, waiter.set_result, [a, b])

            assert await t == [a, b]
            assert not waiter.cancelled()

        async it "can timeout a task", V, packet, serial:
            waiter = asyncio.Future()

            t = hp.async_as_background(V.communication._get_response(packet, 0.05, waiter))

            with assertRaises(TimedOut, "Waiting for reply to a packet", serial=serial):
                await t

            assert waiter.cancelled()

        async it "understands when waiter is cancelled", V, serial, packet:
            waiter = asyncio.Future()

            t = hp.async_as_background(V.communication._get_response(packet, 0.05, waiter))
            asyncio.get_event_loop().call_later(0.01, waiter.cancel)

            with assertRaises(TimedOut, "Message was cancelled", serial=serial):
                await t

            assert waiter.cancelled()

        async it "passes on error from waiter", V, packet:
            waiter = asyncio.Future()

            t = hp.async_as_background(V.communication._get_response(packet, 0.05, waiter))
            asyncio.get_event_loop().call_later(0.01, waiter.set_exception, ValueError("NOPE"))

            with assertRaises(ValueError, "NOPE"):
                await t
