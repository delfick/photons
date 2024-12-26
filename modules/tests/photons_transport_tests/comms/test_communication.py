import binascii
from contextlib import contextmanager
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta, dictobj, sb
from photons_app import helpers as hp
from photons_app.errors import FoundNoDevices
from photons_app.formatter import MergedOptionStringFormatter
from photons_messages import CoreMessages, DeviceMessages, LIFXPacket, protocol_register
from photons_transport.comms.base import Communication, FakeAck, Found
from photons_transport.comms.receiver import Receiver
from photons_transport.errors import FailedToFindDevice


@pytest.fixture()
def VBase():
    class V:
        final_future = hp.create_future()

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


@pytest.fixture()
def V(VBase):
    return VBase


@pytest.fixture(autouse=True)
async def cleanup(V):
    try:
        yield
    finally:
        V.final_future.cancel()
        await V.communication.finish()


class TestFakeAck:
    def test_it_behaves_like_an_Acknowledgement(self):
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


class TestCommunication:
    async def test_it_is_formattable(self, V):
        class Other:
            pass

        other = Other()
        options = {"comms": V.communication, "other": other}

        class Thing(dictobj.Spec):
            other = dictobj.Field(sb.overridden("{other}"), formatted=True)
            comms = dictobj.Field(sb.overridden("{comms}"), formatted=True)

        thing = Thing.FieldSpec(formatter=MergedOptionStringFormatter).normalise(Meta(options, []).at("thing"), {})

        assert thing.comms is V.communication
        assert thing.other == str(other)

    async def test_it_takes_in_a_transport_target(self, V):
        assert V.communication.transport_target is V.transport_target
        assert V.communication.found == Found()
        assert isinstance(V.communication.receiver, Receiver)

    async def test_it_has_a_stop_fut(self, V):
        assert not V.communication.stop_fut.done()
        V.communication.stop_fut.cancel()
        assert not V.final_future.cancelled()

        comm2 = Communication(V.transport_target)
        assert not comm2.stop_fut.done()
        V.final_future.set_result(1)
        assert comm2.stop_fut.cancelled()

    async def test_it_calls_setup(self, V):
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

    class TestFinish:
        async def test_it_can_finish(self, V):
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

        async def test_it_can_finish_even_if_forget_raise_errors(self, V):
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

    class TestSource:
        async def test_it_generates_a_source(self, V):
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

    class TestSeq:
        async def test_it_records_where_were_at_with_the_target(self, V):
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

        async def test_it_wraps_around_at_255(self, V):
            target = mock.Mock(name="target2")
            assert V.communication.seq(target) == 1
            assert V.communication._seq == {target: 1}

            V.communication._seq[target] = 254
            assert V.communication.seq(target) == 255
            assert V.communication._seq == {target: 255}

            assert V.communication.seq(target) == 0
            assert V.communication._seq == {target: 0}

    class TestForget:
        async def test_it_does_nothing_if_serial_not_in_found(self, V):
            serial = "d073d5000001"
            assert serial not in V.communication.found
            await V.communication.forget(serial)

        async def test_it_closes_services_and_removes_from_found(self, V):
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

    class TestAddService:
        async def test_it_can_make_a_new_transport_when_serial_not_already_in_found(self, V):
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

        async def test_it_can_make_a_new_transport_when_serial_already_in_found(self, V):
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

        async def test_it_can_replace_a_transport(self, V):
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

        async def test_it_can_replace_a_transport_when_closing_it_fails(self, V):
            serial = "d073d5000001"
            service = mock.Mock(name="service")
            othertransport = mock.Mock(name="othertransport")
            othertransport.close = pytest.helpers.AsyncMock(name="close", side_effect=Exception("NOPE"))

            V.communication.found[serial] = {service: othertransport}

            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = pytest.helpers.AsyncMock(name="make_transport", return_value=t)

            with mock.patch.object(V.communication, "make_transport", make_transport):
                await V.communication.add_service(serial, service, a=a)

            assert V.communication.found[serial] == {service: t}
            make_transport.assert_called_once_with(serial, service, {"a": a})
            othertransport.close.assert_called_once_with()

        async def test_it_does_not_replace_if_the_transport_is_equal(self, V):
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

    class TestFindDevices:
        async def test_it_uses_find_specific_serials(self, V):
            a = mock.Mock(name="a")
            broadcast = mock.Mock(name="broadcast")
            ignore_lost = mock.Mock(name="ignore_lost")
            raise_on_none = mock.Mock(name="raise_on_none")

            found = mock.Mock(name="found")
            missing = mock.Mock(name="missing")
            find_specific_serials = pytest.helpers.AsyncMock(name="find_specific_serials")
            find_specific_serials.return_value = (found, missing)

            with mock.patch.object(V.communication, "find_specific_serials", find_specific_serials):
                f = await V.communication.find_devices(ignore_lost=ignore_lost, raise_on_none=raise_on_none, broadcast=broadcast, a=a)

            assert f is found
            find_specific_serials.assert_called_once_with(None, ignore_lost=ignore_lost, raise_on_none=raise_on_none, broadcast=broadcast, a=a)

        async def test_it_has_defaults_for_ignore_lost_and_raise_on_none(self, V):
            a = mock.Mock(name="a")

            found = mock.Mock(name="found")
            missing = mock.Mock(name="missing")
            find_specific_serials = pytest.helpers.AsyncMock(name="find_specific_serials")
            find_specific_serials.return_value = (found, missing)

            with mock.patch.object(V.communication, "find_specific_serials", find_specific_serials):
                f = await V.communication.find_devices(a=a)

            assert f is found
            find_specific_serials.assert_called_once_with(None, ignore_lost=False, raise_on_none=False, a=a)

    class TestFindSpecificSerials:
        @pytest.fixture()
        def V(self, VBase):
            V = VBase

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

                    with mock.patch.object(s.communication, "_find_specific_serials", _find_specific_serials):
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
                    with mock.patch.object(s.communication, "_find_specific_serials", _find_specific_serials):
                        f3, m = await s.communication.find_specific_serials(serials, broadcast=broadcast, a=a)

                    assert f3 is f
                    assert m == missing
                    _find_specific_serials.assert_called_once_with(serials, ignore_lost=False, raise_on_none=False, broadcast=broadcast, a=a)

            return V()

        async def test_it_No_missing_if_no_found_and_no_serials(self, V):
            serials = None
            found = {}
            missing = []
            await V.assertSpecificSerials(serials, found, missing)

        async def test_it_No_missing_if_found_has_all_the_serials(self, V):
            serials = [V.serial1, V.serial2]

            found = {V.target1: V.info1, V.target2: V.info2}
            missing = []
            await V.assertSpecificSerials(serials, found, missing)

        async def test_it_No_missing_if_more_found_than_serials(self, V):
            serials = [V.serial1]

            found = {V.target1: V.info1, V.target2: V.info2}
            missing = []
            await V.assertSpecificSerials(serials, found, missing)

        async def test_it_has_missing_if_less_found_than_serials(self, V):
            serials = [V.serial1, V.serial2]

            found = {V.target1: V.info1}
            missing = [V.serial2]
            await V.assertSpecificSerials(serials, found, missing)

        async def test_it_has_missing_if_no_found(self, V):
            serials = [V.serial1, V.serial2]

            found = {}
            missing = [V.serial1, V.serial2]
            await V.assertSpecificSerials(serials, found, missing)

        async def test_it_no_missing_if_found_and_no_serials(self, V):
            serials = None
            found = {V.target1: V.info1, V.target2: V.info2}
            missing = []
            await V.assertSpecificSerials(serials, found, missing)

    class TestPrivateFindSpecificSerials:
        async def test_it_uses_do_search(self, V):
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
                assert await V.communication._find_specific_serials(serials, timeout=timeout, a=a) is found

            _do_search.assert_called_once_with(serials, timeout, a=a)

        async def test_it_can_remove_lost(self, V):
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
                assert await V.communication._find_specific_serials(serials, timeout=timeout, a=a) is found

            _do_search.assert_called_once_with(serials, timeout, a=a)

            assert "d073d5000003" not in found
            s3.close.assert_called_once_with()

        async def test_it_does_not_remove_lost_if_ignore_lost(self, V):
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
                assert (await V.communication._find_specific_serials(serials, timeout=timeout, ignore_lost=True, a=a)) is found

            _do_search.assert_called_once_with(serials, timeout, a=a)

            assert "d073d5000003" in found

        async def test_it_complains_if_none_are_found_and_raise_on_none(self, V):
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
                    await V.communication._find_specific_serials(None, timeout=timeout, raise_on_none=True, a=a)

            _do_search.assert_called_once_with(None, timeout, a=a)

            assert not found
            s3.close.assert_called_once_with()

        async def test_it_does_not_complain_if_none_are_found_and_raise_on_none_but_non_None_serials(self, V):
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
                assert (await V.communication._find_specific_serials(serials, raise_on_none=True, timeout=timeout, a=a)) is found

            _do_search.assert_called_once_with(serials, timeout, a=a)

        async def test_it_does_not_complain_if_none_are_found_if_not_raise_on_none(self, V):
            s3 = mock.Mock(name="s3", spec=[])
            found = V.communication.found
            found["d073d5000003"] = {"UDP": s3}

            async def _do_search(serials, timeout, **kwargs):
                return set()

            _do_search = pytest.helpers.AsyncMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(V.communication, "_do_search", _do_search):
                assert (await V.communication._find_specific_serials(None, ignore_lost=True, timeout=timeout, a=a)) is found

            _do_search.assert_called_once_with(None, timeout, a=a)

            assert "d073d5000003" in found

    class TestBroadcast:
        async def test_it_is_a_send_with_a_broadcast_transport(self, V):
            a = mock.Mock(name="a")
            res = mock.Mock(name="res")
            packet = mock.Mock(name="packet")
            broadcast = mock.Mock(name="broadcast")

            transport = mock.Mock(name="transport")

            send_single = pytest.helpers.AsyncMock(name="send_single", return_value=res)
            make_broadcast_transport = pytest.helpers.AsyncMock(name="make_broadcast_transport", return_value=transport)

            mod = {"send_single": send_single, "make_broadcast_transport": make_broadcast_transport}
            with mock.patch.multiple(V.communication, **mod):
                assert await V.communication.broadcast(packet, broadcast, a=a) is res

            make_broadcast_transport.assert_awaited_once_with(broadcast)
            send_single.assert_awaited_once_with(packet, is_broadcast=True, transport=transport, a=a)

    class TestPrivateTransportForSend:
        @pytest.fixture()
        def V(self, VBase):
            V = VBase

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
                    make_broadcast_transport = pytest.helpers.AsyncMock(name="make_broadcast_transport", return_value=s.transport)
                    choose_transport = pytest.helpers.AsyncMock(name="choose_transport", return_value=s.transport)

                    mbt_patch = mock.patch.object(s.communication, "make_broadcast_transport", make_broadcast_transport)
                    ct_patch = mock.patch.object(s.communication, "choose_transport", choose_transport)

                    with mbt_patch, ct_patch:
                        yield (make_broadcast_transport, choose_transport)

            return V()

        async def test_it_uses_make_broadcast_transport_if_broadcast(self, V):
            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(None, V.packet, V.original, True, V.connect_timeout)
                assert res == (V.transport, True)

            make_broadcast_transport.assert_called_once_with(True)
            assert len(choose_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

        async def test_it_uses_make_broadcast_transport_if_broadcast_is_an_address(self, V):
            broadcast = "192.168.0.255"

            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(None, V.packet, V.original, broadcast, V.connect_timeout)
                assert res == (V.transport, True)

            make_broadcast_transport.assert_called_once_with(broadcast)
            assert len(choose_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

        async def test_it_uses_make_broadcast_transport_if_packet_target_is_None(self, V):
            V.packet.target = None

            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(None, V.packet, V.original, False, V.connect_timeout)
                assert res == (V.transport, True)

            make_broadcast_transport.assert_called_once_with(True)
            assert len(choose_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

        async def test_it_uses_choose_transport_if_not_for_broadcasting(self, V):
            V.packet.target = binascii.unhexlify("d073d5")
            V.packet.serial = "d073d5"

            services = mock.Mock(name="services")
            V.communication.found["d073d5"] = services

            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(None, V.packet, V.original, False, V.connect_timeout)
                assert res == (V.transport, False)

            choose_transport.assert_called_once_with(V.original, services)
            assert len(make_broadcast_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

        async def test_it_complains_if_the_serial_doesnt_exist(self, V):
            V.packet.target = binascii.unhexlify("d073d5")
            V.packet.serial = "d073d5"

            with assertRaises(FailedToFindDevice, serial="d073d5"):
                with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                    await V.communication._transport_for_send(None, V.packet, V.original, False, V.connect_timeout)

            assert len(make_broadcast_transport.mock_calls) == 0
            assert len(choose_transport.mock_calls) == 0
            assert len(V.transport.spawn.mock_calls) == 0

        async def test_it_just_spawns_transport_if_one_is_provided(self, V):
            with V.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await V.communication._transport_for_send(V.transport, V.packet, V.original, False, V.connect_timeout)
                assert res == (V.transport, False)

            assert len(make_broadcast_transport.mock_calls) == 0
            assert len(choose_transport.mock_calls) == 0
            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)

    class TestReceivedData:
        async def test_it_unpacks_bytes_and_sends_to_the_receiver(self, V):
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

        async def test_it_unpacks_unknown_packets(self, V):
            allow_zero = mock.Mock(name="allow_zero")
            addr = mock.Mock(name="addr")

            def recv(pkt, addr, *, allow_zero):
                assert isinstance(pkt, LIFXPacket)
                assert pkt.pkt_type == 9001
                assert pkt.payload == b"things"

            recv = pytest.helpers.AsyncMock(name="recv", side_effect=recv)

            with mock.patch.object(V.communication.receiver, "recv", recv):
                pkt = LIFXPacket(payload=b"things", pkt_type=9001, source=1, sequence=1, target=None)
                data = pkt.pack().tobytes()
                await V.communication.received_data(data, addr, allow_zero=allow_zero)

            recv.assert_called_once_with(mock.ANY, addr, allow_zero=allow_zero)

        async def test_it_ignores_invalid_data(self, V):
            allow_zero = mock.Mock(name="allow_zero")
            addr = mock.Mock(name="addr")

            recv = pytest.helpers.AsyncMock(name="recv")

            with mock.patch.object(V.communication.receiver, "recv", recv):
                data = "NOPE"
                await V.communication.received_data(data, addr, allow_zero=allow_zero)

            assert len(recv.mock_calls) == 0
