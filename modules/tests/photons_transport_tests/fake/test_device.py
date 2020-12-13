# coding: spec

from photons_transport.fake import (
    FakeDevice,
    EchoResponder,
    ServicesResponder,
    Attrs,
    Responder,
    IgnoreMessage,
)
from photons_transport.session.network import NetworkSession
from photons_transport.session.memory import MemoryService
from photons_transport.targets import MemoryTarget
from photons_transport.transports.udp import UDP

from photons_app.errors import TimedOut
from photons_app import helpers as hp

from photons_messages import (
    protocol_register,
    Services,
    DiscoveryMessages,
    DeviceMessages,
    CoreMessages,
)
from photons_products import Products

from delfick_project.errors_pytest import assertRaises, assertSameError
from unittest import mock
import asyncio
import pytest

describe "FakeDevice":
    it "has a repr":
        device = FakeDevice("d073d5001337", [])
        assert repr(device) == "<FakeDevice d073d5001337>"

        device.attrs.vendor_id = 1
        device.attrs.product_id = 55
        device.attrs.product = Products[1, 55]
        assert repr(device) == "<FakeDevice d073d5001337: LIFX Tile>"

    describe "init":
        async it "takes in serial and responders":
            serial = mock.Mock(name="serial")
            responders = [mock.Mock(name="responders")]
            device = FakeDevice(serial, responders)

            assert device.serial is serial
            assert device.responders is responders

            assert device.port is None
            assert device.use_sockets is False
            assert device.protocol_register is protocol_register

            assert isinstance(device.echo_responder, EchoResponder)
            assert isinstance(device.service_responder, ServicesResponder)

            assert isinstance(device.attrs, Attrs)
            assert device.attrs._device is device
            assert device.attrs.online is False

            assert device.reboots == []
            assert device.services == []
            assert device.pre_reboot is None
            assert device.time_rebooting == 1

        async it "can be given different values for protocol_register, port and use_sockets":
            pr = mock.Mock(name="protocol_register")
            port = mock.Mock(name="port")
            device = FakeDevice(
                "d073d5001337", [], protocol_register=pr, port=port, use_sockets=True
            )

            assert device.port is port
            assert device.protocol_register is pr
            assert device.use_sockets is True

        async it "calls setup":
            called = []

            class Device(FakeDevice):
                def setup(s):
                    called.append(("setup", s.attrs.online))

            Device("d073d5001337", [])
            assert called == [("setup", False)]

    describe "Usage":

        @pytest.fixture()
        def serial(self):
            return "d073d5001337"

        @pytest.fixture()
        def device(self, serial):
            return FakeDevice(serial, [])

        async it "is an asynchronous context manager", device:
            start = pytest.helpers.AsyncMock(name="start")
            finish = pytest.helpers.AsyncMock(name="finish")

            with mock.patch.multiple(device, start=start, finish=finish):
                async with device:
                    start.assert_called_once_with()
                    assert len(finish.mock_calls) == 0
                finish.assert_called_once_with(None, None, None)

        async it "can get all responders", device:
            responder1 = mock.Mock(name="responder1")
            responder2 = mock.Mock(name="responder2")
            device.responders = [responder1, responder2]

            got = []
            for r in device.all_responders:
                got.append(r)

            assert got == [
                responder1,
                responder2,
                device.service_responder,
                device.echo_responder,
            ]

        async it "can validate an attribute", device:
            r1 = mock.NonCallableMock(name="responder1", spec=["validate_attr"])
            r2 = mock.NonCallableMock(name="responder2", spec=["validate_attr"])

            key = mock.Mock(name="key")
            value = mock.Mock(name="value")

            with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                device.validate_attr(key, value)

            r1.validate_attr.assert_called_once_with(device, key, value)
            r2.validate_attr.assert_called_once_with(device, key, value)

            r1.validate_attr.reset_mock()
            r2.validate_attr.reset_mock()
            r1.validate_attr.side_effect = ValueError("NOPE")

            with assertRaises(ValueError, "NOPE"):
                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    device.validate_attr(key, value)

            r1.validate_attr.assert_called_once_with(device, key, value)
            assert len(r2.validate_attr.mock_calls) == 0

        async it "has a contextmanger for reboot options", device:
            tr = mock.Mock(name="time_rebooting")
            pr = mock.Mock(name="pre_reboot")

            device.time_rebooting = tr
            device.pre_reboot = pr

            ntr = mock.Mock(name="new_time_rebooting")
            with device.reboot_options(ntr):
                assert device.time_rebooting is ntr
                assert device.pre_reboot is None

            assert device.time_rebooting is tr
            assert device.pre_reboot is pr

            npr = mock.Mock(name="new_pre_reboot")
            with device.reboot_options(ntr, pre_reboot=npr):
                assert device.time_rebooting is ntr
                assert device.pre_reboot is npr

            assert device.time_rebooting is tr
            assert device.pre_reboot is pr

            with assertRaises(ValueError, "NOPE"):
                with device.reboot_options(ntr, pre_reboot=npr):
                    assert device.time_rebooting is ntr
                    assert device.pre_reboot is npr
                    raise ValueError("NOPE")

            assert device.time_rebooting is tr
            assert device.pre_reboot is pr

        async it "can be turned back on", device:
            r1 = mock.NonCallableMock(name="responder1", spec=[])
            r2 = mock.NonCallableMock(name="responder2", spec=["restart"])

            r2.restart = pytest.helpers.AsyncMock(name="restart")
            device.attrs.online = False

            with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                await device.power_on()

            assert device.attrs.online is True

            r2.restart.assert_called_once_with(device)

        async it "can set intercept_got_message", device:
            interceptor = mock.Mock(name="interceptor")
            device.set_intercept_got_message(interceptor)
            assert device.intercept_got_message is interceptor

        async it "can set replies", device:
            await device.reset()

            kls = mock.Mock(name="kls")
            msg1 = mock.Mock(name="msg1")
            msg2 = mock.Mock(name="msg2")

            device.set_reply(kls, msg1)
            assert device.set_replies == {kls: [msg1]}

            device.set_reply(kls, msg2)
            assert device.set_replies == {kls: [msg1, msg2]}

        async it "can reset received", device:
            device.received = mock.Mock(name="received")
            device.reset_received()
            assert device.received == []

        async it "says a device is reachable if it's online", device:
            broadcast_address = mock.NonCallableMock(name="broadcast_address", spec=[])

            device.attrs.online = False
            assert not await device.is_reachable(broadcast_address)

            device.attrs.online = True
            assert await device.is_reachable(broadcast_address)

        async it "has a decorator for making a device offline", device:
            device.attrs.online = True
            with device.offline():
                assert not device.attrs.online
            assert device.attrs.online

        async it "has a helper for recording what no to give acks for", device:
            kls = DeviceMessages.SetPower
            await device.reset()

            def assertValues(*vals):
                assert device.no_res == {}
                assert list(device.no_acks.values()) == list(vals)

            assertValues()
            with device.no_acks_for(kls):
                assertValues(kls)
                with device.no_acks_for(kls):
                    assertValues(kls, kls)
                assertValues(kls)
            assertValues()

        async it "has a helper for recording what no to give replies for", device:
            kls = DeviceMessages.SetPower
            await device.reset()

            def assertValues(*vals):
                assert device.no_acks == {}
                assert list(device.no_res.values()) == list(vals)

            assertValues()
            with device.no_replies_for(kls):
                assertValues(kls)
                with device.no_replies_for(kls):
                    assertValues(kls, kls)
                assertValues(kls)
            assertValues()

        async it "has a helper for recording what no to give responses for", device:
            kls = DeviceMessages.SetPower
            await device.reset()

            def assertValues(*vals):
                assert list(device.no_acks.values()) == list(vals)
                assert list(device.no_res.values()) == list(vals)

            assertValues()
            with device.no_responses_for(kls):
                assertValues(kls)
                with device.no_responses_for(kls):
                    assertValues(kls, kls)
                assertValues(kls)
            assertValues()

        async it "can create an ack", device:
            pkt = DeviceMessages.SetPower(level=0)
            source = mock.Mock(name="source")
            await device.reset()

            assert await device.ack_for(pkt, source) | CoreMessages.Acknowledgement

            with device.no_acks_for(DeviceMessages.SetPower):
                assert await device.ack_for(pkt, source) is None

            pkt = DeviceMessages.SetPower(level=0, ack_required=False)
            assert await device.ack_for(pkt, source) is None

        async it "can determine if we send a response", device:
            pkt = DeviceMessages.SetPower(level=0)
            source = mock.Mock(name="source")
            await device.reset()

            assert await device.do_send_response(pkt, source)

            with device.no_replies_for(DeviceMessages.SetPower):
                assert not await device.do_send_response(pkt, source)

            pkt = DeviceMessages.SetPower(level=0, res_required=False)
            assert not await device.do_send_response(pkt, source)

            # Get messages return response anyways
            pkt = DeviceMessages.GetPower(res_required=False)
            assert await device.do_send_response(pkt, source)

            with device.no_replies_for(DeviceMessages.GetPower):
                pkt = DeviceMessages.GetPower(res_required=False)
                assert not await device.do_send_response(pkt, source)

        async it "can make responses", device:
            pkt = mock.Mock(name="pkt")
            res = mock.Mock(name="res")
            res2 = mock.Mock(name="res2")
            source = mock.Mock(name="source")
            make_response = pytest.helpers.AsyncMock(name="make_response")
            do_send_response = pytest.helpers.AsyncMock(name="do_send_response")

            await device.reset()

            async def collect():
                got = []
                make_response.reset_mock()
                do_send_response.reset_mock()
                with mock.patch.multiple(
                    device, make_response=make_response, do_send_response=do_send_response
                ):
                    async for r in device.response_for(pkt, source):
                        got.append(r)
                return got

            make_response.return_value = res
            do_send_response.return_value = True
            got = await collect()
            assert got == [res]
            make_response.assert_called_once_with(pkt, source)
            do_send_response.assert_called_once_with(pkt, source)

            make_response.return_value = [res, res2]
            do_send_response.return_value = True
            got = await collect()
            assert got == [res, res2]
            make_response.assert_called_once_with(pkt, source)
            do_send_response.assert_called_once_with(pkt, source)

            make_response.return_value = [res, res2]
            do_send_response.return_value = False
            got = await collect()
            assert got == []
            make_response.assert_called_once_with(pkt, source)
            do_send_response.assert_called_once_with(pkt, source)

        async it "can make a port", device:
            port = device.make_port()
            assert port > 0

            port2 = device.make_port()
            assert port != port2

        async it "has empty hook for extra response", device:
            pkt = mock.NonCallableMock(name="pkt", spec=[])
            source = mock.NonCallableMock(name="source", spec=[])

            got = []
            async for r in device.extra_make_response(pkt, source):
                got.apend(r)
            assert got == []

        describe "discoverable":
            async it "is discoverable if we are reachable and no responders have undiscoverable", device:
                r1 = mock.Mock(name="r1", spec=[])
                r2 = mock.Mock(name="r2", spec=[])
                broadcast = mock.Mock(name="broadcast")
                is_reachable = pytest.helpers.AsyncMock(name="is_reachable", return_value=True)
                with mock.patch.multiple(
                    FakeDevice, all_responders=[r1, r2], is_reachable=is_reachable
                ):
                    assert await device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)

            async it "is not discoverable if we are not reachable", device:
                r1 = mock.Mock(name="r1", spec=[])
                r2 = mock.Mock(name="r2", spec=[])
                broadcast = mock.Mock(name="broadcast")
                is_reachable = pytest.helpers.AsyncMock(name="is_reachable", return_value=False)
                with mock.patch.multiple(
                    FakeDevice, all_responders=[r1, r2], is_reachable=is_reachable
                ):
                    assert not await device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)

            async it "is not discoverable if we are reachable but a responder is undiscoverable", device:
                r1 = mock.Mock(name="r1", spec=["undiscoverable"])
                r1.undiscoverable = pytest.helpers.AsyncMock(
                    name="undiscoverable", return_value=True
                )

                r2 = mock.Mock(name="r2", spec=[])
                broadcast = mock.Mock(name="broadcast")
                is_reachable = pytest.helpers.AsyncMock(name="is_reachable", return_value=True)
                with mock.patch.multiple(
                    FakeDevice, all_responders=[r1, r2], is_reachable=is_reachable
                ):
                    assert not await device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)
                r1.undiscoverable.assert_called_once_with(device)

            async it "is not discoverable if we are reachable but a responder is undiscoverable even if others are", device:
                r1 = mock.Mock(name="r1", spec=["undiscoverable"])
                r1.undiscoverable = pytest.helpers.AsyncMock(
                    name="undiscoverable", return_value=False
                )

                r2 = mock.Mock(name="r2", spec=["undiscoverable"])
                r2.undiscoverable = pytest.helpers.AsyncMock(
                    name="undiscoverable", return_value=True
                )

                r3 = mock.Mock(name="r3", spec=[])

                r4 = mock.Mock(name="r4", spec=["undiscoverable"])
                r4.undiscoverable = pytest.helpers.AsyncMock(
                    name="undiscoverable", return_value=None
                )

                broadcast = mock.Mock(name="broadcast")
                is_reachable = pytest.helpers.AsyncMock(name="is_reachable", return_value=True)
                with mock.patch.multiple(
                    FakeDevice, all_responders=[r1, r2, r3, r4], is_reachable=is_reachable
                ):
                    assert not await device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)
                r1.undiscoverable.assert_called_once_with(device)
                r2.undiscoverable.assert_called_once_with(device)

                # We shortcut after r2 returns True
                assert len(r4.undiscoverable.mock_calls) == 0

            async it "is discoverable if we are reachable but responder say False to undiscoverable", device:
                r1 = mock.Mock(name="r1", spec=["undiscoverable"])
                r1.undiscoverable = pytest.helpers.AsyncMock(
                    name="undiscoverable", return_value=False
                )

                r2 = mock.Mock(name="r2", spec=["undiscoverable"])
                r2.undiscoverable = pytest.helpers.AsyncMock(
                    name="undiscoverable", return_value=False
                )

                r3 = mock.Mock(name="r3", spec=[])

                r4 = mock.Mock(name="r4", spec=["undiscoverable"])
                r4.undiscoverable = pytest.helpers.AsyncMock(
                    name="undiscoverable", return_value=None
                )

                broadcast = mock.Mock(name="broadcast")
                is_reachable = pytest.helpers.AsyncMock(name="is_reachable", return_value=True)
                with mock.patch.multiple(
                    FakeDevice, all_responders=[r1, r2, r3, r4], is_reachable=is_reachable
                ):
                    assert await device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)
                r1.undiscoverable.assert_called_once_with(device)
                r2.undiscoverable.assert_called_once_with(device)
                r4.undiscoverable.assert_called_once_with(device)

        describe "reset":
            async it "resets the device", device:
                r1 = mock.NonCallableMock(name="responder1", spec=["reset"])
                r2 = mock.NonCallableMock(name="responder2", spec=["reset"])

                r1.reset = pytest.helpers.AsyncMock(name="reset")
                r2.reset = pytest.helpers.AsyncMock(name="reset")

                device.no_res = mock.Mock(name="no_res")
                device.no_acks = mock.Mock(name="no_acks")
                device.reboots = mock.Mock(name="reboots")
                device.waiters = mock.Mock(name="waiters")
                device.received = mock.Mock(name="received")
                device.set_replies = mock.Mock(name="set_replies")
                device.intercept_got_message = mock.Mock(name="intercept_got_message")
                device.attrs.online = False

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    await device.reset()

                assert device.no_res == {}
                assert device.no_acks == {}
                assert device.reboots == []
                assert device.waiters == {}

                assert device.set_replies == {}
                device.set_replies[1].append(2)
                assert device.set_replies == {1: [2]}

                assert device.intercept_got_message is None
                assert device.received == []

                r1.reset.assert_called_once_with(device, zero=False)
                r2.reset.assert_called_once_with(device, zero=False)

                assert device.attrs.online is True

            async it "can reset to zero", device:
                r1 = mock.NonCallableMock(name="responder1", spec=["reset"])
                r2 = mock.NonCallableMock(name="responder2", spec=["reset"])

                r1.reset = pytest.helpers.AsyncMock(name="reset")
                r2.reset = pytest.helpers.AsyncMock(name="reset")

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    await device.reset(zero=True)

                r1.reset.assert_called_once_with(device, zero=True)
                r2.reset.assert_called_once_with(device, zero=True)

        describe "reboot":

            async it "can be rebooted", device:
                fut = hp.create_future()

                called = []

                async def power_on():
                    called.append("power_on")
                    fut.set_result(None)

                power_on = pytest.helpers.AsyncMock(name="power_on", side_effect=power_on)

                r1 = mock.NonCallableMock(name="responder1", spec=[])
                r2 = mock.NonCallableMock(name="responder2", spec=["shutdown"])

                async def shut(d):
                    assert d is device
                    called.append("shutdown")

                r2.shutdown = pytest.helpers.AsyncMock(name="shutdown", side_effect=shut)

                async def pre_reboot(d):
                    assert d is device
                    called.append("pre_reboot")

                pre_reboot = pytest.helpers.AsyncMock(name="pre_reboot", side_effect=pre_reboot)

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    with mock.patch.object(FakeDevice, "power_on", power_on):
                        with device.reboot_options(0.01, pre_reboot):
                            await device.reboot()

                assert len(power_on.mock_calls) == 0
                assert device.attrs.online is False
                pre_reboot.assert_awaited_once_with(device)
                r2.shutdown.assert_called_once_with(device)

                await fut

                power_on.assert_called_once_with()
                assert called == ["pre_reboot", "shutdown", "power_on"]

            async it "can be told not to come back online", device:
                called = []

                async def power_on():
                    called.append("power_on")
                    assert False, "Shouldn't be called"

                power_on = pytest.helpers.AsyncMock(name="power_on", side_effect=power_on)

                r1 = mock.NonCallableMock(name="responder1", spec=[])
                r2 = mock.NonCallableMock(name="responder2", spec=[])

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    with mock.patch.object(FakeDevice, "power_on", power_on):
                        with device.reboot_options(-1):
                            await device.reboot()

                await asyncio.sleep(0.1)

                assert len(power_on.mock_calls) == 0
                assert device.attrs.online is False
                assert called == []

        describe "start":
            async it "can start udp service", device:
                called = []

                def call(name):
                    async def func(*args, **kwargs):
                        called.append(name)

                    return func

                finish = pytest.helpers.AsyncMock(name="finish", side_effect=call("finish"))
                reset = pytest.helpers.AsyncMock(name="reset", side_effect=call("reset"))
                ensure_udp_service = pytest.helpers.AsyncMock(
                    name="ensure_udp_service", side_effect=call("ensure_udp_service")
                )
                ensure_memory_service = pytest.helpers.AsyncMock(
                    name="ensure_memory_service", side_effect=call("ensure_memory_service")
                )

                mod = {
                    "finish": finish,
                    "reset": reset,
                    "ensure_udp_service": ensure_udp_service,
                    "ensure_memory_service": ensure_memory_service,
                }

                with mock.patch.multiple(device, **mod):
                    device.use_sockets = True
                    await device.start()

                assert called == ["finish", "reset", "ensure_udp_service"]

            async it "can start memory service", device:
                called = []

                def call(name):
                    async def func(*args, **kwargs):
                        called.append(name)

                    return func

                finish = pytest.helpers.AsyncMock(name="finish", side_effect=call("finish"))
                reset = pytest.helpers.AsyncMock(name="reset", side_effect=call("reset"))
                ensure_udp_service = pytest.helpers.AsyncMock(
                    name="ensure_udp_service", side_effect=call("ensure_udp_service")
                )
                ensure_memory_service = pytest.helpers.AsyncMock(
                    name="ensure_memory_service", side_effect=call("ensure_memory_service")
                )

                mod = {
                    "finish": finish,
                    "reset": reset,
                    "ensure_udp_service": ensure_udp_service,
                    "ensure_memory_service": ensure_memory_service,
                }

                with mock.patch.multiple(device, **mod):
                    device.use_sockets = False
                    await device.start()

                assert called == ["finish", "reset", "ensure_memory_service"]

            async it "works without mocks", device:
                device.use_sockets = False

                await device.start()
                assert [s.service for s in device.services] == [MemoryService]
                await device.start()
                assert [s.service for s in device.services] == [MemoryService]

                device.use_sockets = True
                await device.start()
                assert [s.service for s in device.services] == [Services.UDP]

        describe "finish":
            async it "closes services and resets services to []", device:
                s1 = mock.Mock(name="service1", spec=["closer"])
                s2 = mock.Mock(name="service1", spec=["closer"])

                s1.closer = pytest.helpers.AsyncMock(name="closer")
                s2.closer = pytest.helpers.AsyncMock(name="closer")

                device.services = [s1, s2]
                await device.finish()
                assert device.services == []

                s1.closer.assert_called_once_with()
                s2.closer.assert_called_once_with()

        describe "add_services":
            async it "can add services", device:
                adder = mock.Mock(name="adder")

                s1 = mock.Mock(name="s1", spec=["add_service"])
                s2 = mock.Mock(name="s1", spec=["add_service"])

                s1.add_service = pytest.helpers.AsyncMock(name="add_service")
                s2.add_service = pytest.helpers.AsyncMock(name="add_service")

                filtered_services = mock.Mock(name="filtered_services", return_value=[s1, s2])

                with mock.patch.object(ServicesResponder, "filtered_services", filtered_services):
                    await device.add_services(adder)

                s1.add_service.assert_called_once_with(adder)
                s2.add_service.assert_called_once_with(adder)

            async it "works", serial, device:
                final_future = hp.create_future()
                target = MemoryTarget.create(
                    {"final_future": final_future, "protocol_register": protocol_register},
                    {"devices": [device]},
                )
                session = NetworkSession(target)
                assert not session.found

                device.use_sockets = True
                await device.start()
                await device.add_services(session.add_service)

                transport = UDP(
                    session, host="127.0.0.1", port=device.services[0].state_service.port
                )

                assert session.found.serials == [serial]
                assert session.found[serial] == {Services.UDP: transport}

        describe "write":
            async it "does nothing if none of the services recognise the source", serial, device:
                device.attrs.online = True

                pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target=serial)

                s1 = mock.Mock(name="s1", spec=["address"])
                s2 = mock.Mock(name="s2", spec=["address"])

                s1.address.return_value = None
                s2.address.return_value = None

                device.services = [s1, s2]

                source = mock.Mock(name="source")
                got_message = mock.NonCallableMock(name="got_message")
                received_data = mock.NonCallableMock(name="received_data")

                with mock.patch.object(device, "got_message", got_message):
                    await device.write(source, received_data, pkt.tobytes(serial=serial))

                s1.address.assert_called_once_with(source)
                s2.address.assert_called_once_with(source)

            async it "sends results from got_message to received_data", serial, device:
                device.use_sockets = False
                await device.start()

                pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target=serial)

                m1 = mock.Mock(name="m1")
                m1b = mock.Mock(name="m1 bytes")

                m2 = mock.Mock(name="m2")
                m2b = mock.Mock(name="m2 bytes")

                m1.tobytes.return_value = m1b
                m2.tobytes.return_value = m2b

                async def got_message(*args):
                    yield m1
                    yield m2

                got_message = pytest.helpers.MagicAsyncMock(
                    name="got_message", side_effect=got_message
                )
                received_data = pytest.helpers.AsyncMock(name="received_data")

                with mock.patch.object(device, "got_message", got_message):
                    await device.write("memory", received_data, pkt.tobytes(serial=serial))

                assert received_data.mock_calls == [
                    mock.call(m1b, (f"fake://{serial}/memory", 56700)),
                    mock.call(m2b, (f"fake://{serial}/memory", 56700)),
                ]

            async it "chooses address based on the services", device:
                device.use_sockets = True
                await device.start()

                port = device.services[0].state_service.port

                pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target=None)

                m1 = mock.Mock(name="m1")
                m1b = mock.Mock(name="m1 bytes")
                m1.tobytes.return_value = m1b

                async def got_message(*args):
                    yield m1

                got_message = pytest.helpers.MagicAsyncMock(
                    name="got_message", side_effect=got_message
                )
                received_data = pytest.helpers.AsyncMock(name="received_data")

                with mock.patch.object(device, "got_message", got_message):
                    await device.write("udp", received_data, pkt.tobytes(serial=None))

                assert received_data.mock_calls == [mock.call(m1b, ("127.0.0.1", port))]

            async it "does nothing if the serial is incorrect", serial, device:
                device.use_sockets = False
                await device.start()

                pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target="d073d5000001")

                got_message = mock.NonCallableMock(name="got_message")
                received_data = mock.NonCallableMock(name="received_data")

                with mock.patch.object(device, "got_message", got_message):
                    await device.write("memory", received_data, pkt.tobytes(serial=serial))

            async it "does nothing if the device is offline", serial, device:
                device.use_sockets = False
                await device.start()

                with device.offline():
                    pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target=serial)

                    got_message = mock.NonCallableMock(name="got_message")
                    received_data = mock.NonCallableMock(name="received_data")

                    with mock.patch.object(device, "got_message", got_message):
                        await device.write("memory", received_data, pkt.tobytes(serial=serial))

        describe "got_message":
            async it "yields ack and results", serial, device:
                await device.reset()

                process_reply = pytest.helpers.AsyncMock(name="process_reply")

                source = mock.Mock(name="source")
                sequence = mock.Mock(name="sequence")

                pkt = mock.Mock(name="pkt", source=source, sequence=sequence, serial=serial)

                ack = mock.Mock(name="ack")
                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name="res2")

                ack_for = pytest.helpers.AsyncMock(name="ack_for", return_value=ack)

                async def response_for(*args):
                    yield res1
                    yield res2

                response_for = pytest.helpers.MagicAsyncMock(
                    name="response_for", side_effect=response_for
                )

                got = []
                message_source = mock.Mock(name="message_source")

                with mock.patch.multiple(
                    device, ack_for=ack_for, response_for=response_for, process_reply=process_reply
                ):
                    async for m in device.got_message(pkt, message_source):
                        got.append(m)

                assert got == [ack, res1, res2]
                for g in got:
                    assert g.source is source
                    assert g.sequence is sequence
                    assert g.target == serial

                ack_for.assert_called_once_with(pkt, message_source)
                response_for.assert_called_once_with(pkt, message_source)
                assert process_reply.mock_calls == [
                    mock.call(ack, message_source, pkt),
                    mock.call(res1, message_source, pkt),
                    mock.call(res2, message_source, pkt),
                ]

            async it "yields nothing if intercept_got_message returns False", device:
                await device.reset()

                source = mock.Mock(name="source")
                sequence = mock.Mock(name="sequence")
                serial = mock.Mock(name="serial")

                pkt = mock.Mock(name="pkt", source=source, sequence=sequence, serial=serial)
                ack_for = mock.NonCallableMock(name="ack_for")
                response_for = mock.NonCallableMock(name="response_for ")

                igm = pytest.helpers.AsyncMock(name="intercept_got_message", return_value=False)

                got = []
                message_source = mock.Mock(name="message_source")

                with mock.patch.multiple(device, ack_for=ack_for, response_for=response_for):
                    device.set_intercept_got_message(igm)
                    async for m in device.got_message(pkt, message_source):
                        got.append(m)

                assert got == []
                igm.assert_called_once_with(pkt, message_source)

            async it "works", serial, device:

                class R(Responder):
                    async def respond(s, device, pkt, source):
                        if pkt | DeviceMessages.SetLabel:
                            yield DeviceMessages.StateLabel(label=pkt.label)

                device.responders = [R()]
                await device.start()

                msg = DeviceMessages.SetLabel(label="hello", source=1, sequence=2, target=serial)
                msg_zero_target = DeviceMessages.SetLabel(
                    label="hello", source=1, sequence=2, target=None
                )

                for msg in (msg, msg_zero_target):
                    got = []

                    async for m in device.got_message(msg, "memory"):
                        got.append(m)

                    assert len(got) == 2
                    assert got[0] | CoreMessages.Acknowledgement
                    assert got[1] | DeviceMessages.StateLabel

                    for g in got:
                        assert g.source == 1
                        assert g.sequence == 2
                        assert g.serial == serial

            async it "resolves waiters", serial, device:

                class R(Responder):
                    async def respond(s, device, pkt, source):
                        if pkt | DeviceMessages.SetLabel:
                            yield DeviceMessages.StateLabel(label=pkt.label)
                        if pkt | DeviceMessages.SetPower:
                            yield DeviceMessages.StatePower(level=pkt.level)

                device.responders = [R()]
                await device.start()

                fut = device.wait_for("udp", DeviceMessages.SetLabel)
                device.wait_for("udp", DeviceMessages.SetGroup)
                assert device.waiters == {
                    ("udp", DeviceMessages.SetGroup): mock.ANY,
                    ("udp", DeviceMessages.SetLabel): mock.ANY,
                }

                label_msg = DeviceMessages.SetLabel(
                    label="hello", source=1, sequence=2, target=serial
                )
                power_msg = DeviceMessages.SetPower(level=0, source=1, sequence=2, target=serial)

                assert not fut.done()

                got = []
                async for m in device.got_message(power_msg, "memory"):
                    got.append(m)
                assert len(got) == 2, [g.__class__.__name__ for g in got]
                assert not fut.done()

                got = []
                async for m in device.got_message(label_msg, "memory"):
                    got.append(m)
                assert len(got) == 2, [g.__class__.__name__ for g in got]
                assert not fut.done()

                assert device.waiters == {
                    ("udp", DeviceMessages.SetGroup): mock.ANY,
                    ("udp", DeviceMessages.SetLabel): mock.ANY,
                }

                got = []
                async for m in device.got_message(label_msg, "udp"):
                    got.append(m)
                assert len(got) == 2, [g.__class__.__name__ for g in got]
                assert await fut == label_msg
                assert device.waiters == {("udp", DeviceMessages.SetGroup): mock.ANY}

        describe "process_reply":
            async it "gives every responder a chance to do something with the packet", device:
                r1 = mock.Mock(name="r1", spec=[])
                r2 = mock.Mock(name="r2", spec=["process_reply"])
                r3 = mock.Mock(name="r3", spec=[])
                r4 = mock.Mock(name="r4", spec=["process_reply"])

                r2.process_reply = pytest.helpers.AsyncMock(name="process_reply")
                r4.process_reply = pytest.helpers.AsyncMock(name="process_reply")

                pkt = mock.Mock(name="pkt")
                request = mock.Mock(name="request")
                message_source = mock.Mock(name="message_source")

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2, r3, r4]):
                    await device.process_reply(pkt, message_source, request)

                r2.process_reply.assert_called_once_with(device, pkt, message_source, request)
                r4.process_reply.assert_called_once_with(device, pkt, message_source, request)

        describe "stop_service":
            async it "does nothing if no such service already", device:
                device.services = []
                await device.stop_service(Services.UDP)

                await device.start()
                assert len(device.services) == 1
                assert device.services[0].service is MemoryService

                await device.stop_service(Services.UDP)
                assert len(device.services) == 1
                assert device.services[0].service is MemoryService

            async it "closes and removes services if it finds one", device:
                s1 = mock.Mock(name="service1", service=MemoryService)
                s2 = mock.Mock(name="service2", service=Services.UDP)

                s1.closer = mock.NonCallableMock(name="closer")
                s2.closer = pytest.helpers.AsyncMock(name="closer")

                device.services = [s1, s2]
                await device.stop_service(Services.UDP)
                assert len(device.services) == 1
                assert device.services[0].service is MemoryService

                s2.closer.assert_called_once_with()

        describe "ensure_memory_service":
            async it "Creates a MemoryService", serial, device:
                info = {}

                async def adder(serial, service, *, writer):
                    assert serial == serial
                    assert service is MemoryService
                    info["writer"] = writer

                write = pytest.helpers.AsyncMock(name="write")

                assert len(device.services) == 0
                await device.ensure_memory_service()
                assert len(device.services) == 1
                await device.ensure_memory_service()
                assert len(device.services) == 1

                service = device.services[0]
                assert service.service is MemoryService
                await service.closer()

                assert info == {}
                with mock.patch.object(device, "write", write):
                    await service.add_service(adder)
                assert "writer" in info
                assert len(write.mock_calls) == 0
                a = mock.Mock(name="a")
                b = mock.Mock(name="b")
                await info["writer"](a, b)
                write.assert_called_once_with("memory", a, b)

                state_service = service.state_service
                assert state_service | DiscoveryMessages.StateService
                assert state_service.service == Services.UDP
                assert state_service.port == 56700

                assert service.address("memory") == (f"fake://{serial}/memory", 56700)
                assert service.address("udp") is None

        describe "ensure_udp_service":

            async it "works", serial, device:
                assert len(device.services) == 0

                await device.ensure_udp_service()
                assert len(device.services) == 1
                first_service = device.services[0]
                port1 = first_service.state_service.port

                await device.ensure_udp_service()
                assert len(device.services) == 1
                second_service = device.services[0]
                port2 = second_service.state_service.port

                assert port1 != port2

                final_future = hp.create_future()
                target = MemoryTarget.create(
                    {"final_future": final_future, "protocol_register": protocol_register},
                    {"devices": [device]},
                )

                echo = DeviceMessages.EchoRequest(echoing=b"hello")
                await device.reset()

                async with target.session() as sender:
                    await first_service.add_service(sender.add_service)
                    got = []
                    es = []
                    async for pkt in sender(echo, serial, message_timeout=0.05, error_catcher=es):
                        got.append(pkt)
                    assert len(got) == 0
                    assert len(es) == 1
                    echo_type = DeviceMessages.EchoRequest.Payload.message_type
                    assertSameError(
                        es[0],
                        TimedOut,
                        "Waiting for reply to a packet",
                        dict(serial=serial, sent_pkt_type=echo_type),
                        [],
                    )

                    await sender.forget(serial)
                    await second_service.add_service(sender.add_service)
                    got = []
                    es = []
                    async for pkt in sender(echo, serial, message_timeout=0.05, error_catcher=es):
                        assert pkt.Information.remote_addr == ("127.0.0.1", port2)
                        got.append(pkt)
                    assert es == []
                    assert len(got) == 1

        describe "make_response":
            async it "can use set_replies", serial, device:
                await device.start()
                assert device.received == []

                pkt = DeviceMessages.EchoRequest(
                    echoing=b"hello", source=1, sequence=2, target=serial
                )

                shortcut = DeviceMessages.EchoResponse(echoing=b"REPSONDING")
                device.set_reply(DeviceMessages.EchoRequest, shortcut)
                res = await device.make_response(pkt, "memory")
                assert device.received == [pkt]
                assert res | DeviceMessages.EchoResponse
                assert res.echoing == shortcut.echoing

                res = await device.make_response(pkt, "memory")
                assert device.received == [pkt, pkt]
                assert len(res) == 1
                res = res[0]
                assert res | DeviceMessages.EchoResponse
                assert res.echoing == pkt.echoing

                device.set_reply(DeviceMessages.SetLabel, DeviceMessages.StateLabel(label="wat"))
                res = await device.make_response(pkt, "memory")
                assert device.received == [pkt, pkt, pkt]
                assert len(res) == 1
                res = res[0]
                assert res | DeviceMessages.EchoResponse
                assert res.echoing == pkt.echoing

            async it "does nothing if it doesn't find a responder", device:
                await device.start()
                pkt = DeviceMessages.SetLabel(label="hi")
                res = await device.make_response(pkt, "memory")
                assert res is None

            async it "uses extra_make_response if we didn't find a responder", device:
                await device.start()

                pkt = DeviceMessages.SetLabel(label="hi")
                extra_make_response = pytest.helpers.MagicAsyncMock(name="extra_make_response")

                def yld(*r, fail=False):
                    async def func(*args):
                        for thing in r:
                            yield thing
                        if fail:
                            raise IgnoreMessage()

                    return func

                with mock.patch.object(device, "extra_make_response", extra_make_response):
                    extra_make_response.side_effect = yld()
                    res = await device.make_response(pkt, "memory")
                    assert res is None
                    extra_make_response.assert_called_once_with(pkt, "memory")
                    extra_make_response.reset_mock()

                    r1 = mock.Mock(name="r1")
                    r2 = mock.Mock(name="r2")
                    extra_make_response.side_effect = yld(r1, r2)
                    res = await device.make_response(pkt, "memory")
                    assert res == [r1, r2]
                    extra_make_response.assert_called_once_with(pkt, "memory")
                    extra_make_response.reset_mock()

                    extra_make_response.side_effect = yld(fail=True)
                    with assertRaises(IgnoreMessage):
                        await device.make_response(pkt, "memory")
                    extra_make_response.assert_called_once_with(pkt, "memory")

            async it "uses the first responder that works", device:
                res = mock.Mock(name="res")
                r1 = mock.Mock(name="responder1", spec=["respond", "reset"])
                r2 = mock.Mock(name="responder2", spec=["respond", "reset"])
                r3 = mock.Mock(name="responder3", spec=["respond", "reset"])

                def yld(*r, fail=False):
                    async def func(*args):
                        for thing in r:
                            yield thing
                        if fail:
                            raise IgnoreMessage()

                    return func

                r1.respond = pytest.helpers.MagicAsyncMock(name="respond", side_effect=yld())
                r1.reset = pytest.helpers.AsyncMock(name="reset")

                r2.respond = pytest.helpers.MagicAsyncMock(name="respond", side_effect=yld(res))
                r2.reset = pytest.helpers.AsyncMock(name="reset")

                r3.respond = mock.NonCallableMock(name="respond", spec=[])
                r3.reset = pytest.helpers.AsyncMock(name="reset")

                device.responders = [r1, r2, r3]
                await device.start()

                pkt = DeviceMessages.SetLabel(label="hi")
                assert await device.make_response(pkt, "memory") == [res]
                r1.respond.assert_called_once_with(device, pkt, "memory")
                r2.respond.assert_called_once_with(device, pkt, "memory")
                assert len(r3.respond.mock_calls) == 0

                r1.respond.side_effect = yld(fail=True)
                with assertRaises(IgnoreMessage):
                    await device.make_response(pkt, "memory")

        describe "compare_received":
            async it "is fine if no messages either way", device:
                device.received = []
                device.compare_received([])

            async it "complains if we have a different number of messages", device:
                device.received = []

                p1 = DeviceMessages.SetLabel(label="hi")

                with assertRaises(
                    AssertionError, "Expected a different number of messages to what we got"
                ):
                    device.compare_received([p1])

            async it "complains if the messages are different", device:
                p1 = DeviceMessages.GetPower()
                p2 = DeviceMessages.SetLabel(label="hi")
                p3 = DeviceMessages.SetLabel(label="other")

                device.received = [p1, p2]

                with assertRaises(AssertionError, "Expected messages to be the same"):
                    device.compare_received([p2, p1])

                with assertRaises(AssertionError, "Expected messages to be the same"):
                    device.compare_received([p1, p3])

                with assertRaises(AssertionError, "Expected messages to be the same"):
                    device.compare_received([p3, p2])

                device.compare_received([p1, p2])

            async it "is not effected by source and sequence or duplicates", serial, device:
                p1 = DeviceMessages.GetPower(source=1, sequence=2, target=serial)
                p2 = DeviceMessages.SetLabel(label="hi", source=3, sequence=4, target=serial)
                device.received = [p1, p2]

                p3 = DeviceMessages.GetPower()
                p4 = DeviceMessages.SetLabel(label="hi")
                device.compare_received([p3, p4, p3])

                device.received = [p1, p2, p2]
                device.compare_received([p3, p4, p3])

            async it "can be told to not remove duplicates", serial, device:
                p1 = DeviceMessages.GetPower(source=1, sequence=2, target=serial)
                p2 = DeviceMessages.SetLabel(label="hi", source=3, sequence=4, target=serial)
                device.received = [p1, p2]

                p3 = DeviceMessages.GetPower()
                p4 = DeviceMessages.SetLabel(label="hi")

                with assertRaises(
                    AssertionError, "Expected a different number of messages to what we got"
                ):
                    device.compare_received([p3, p4, p3], keep_duplicates=True)

            async it "cares about same payload, but different packet", serial, device:
                p1 = DeviceMessages.GetPower(source=1, sequence=2, target=serial)
                p2 = DeviceMessages.GetLabel(source=1, sequence=2, target=serial)
                device.received = [p1, p2]

                p3 = DeviceMessages.GetPower()
                p4 = DeviceMessages.GetLabel()

                with assertRaises(AssertionError, "Expected messages to be the same"):
                    device.compare_received([p4, p3])

        describe "compare_received klses":
            async it "is fine if no messages either way", device:
                device.received = []
                device.compare_received_klses([])

            async it "complains if we have a different number of messages", device:
                device.received = []

                p1 = DeviceMessages.SetLabel

                with assertRaises(
                    AssertionError, "Expected a different number of messages to what we got"
                ):
                    device.compare_received_klses([p1])

            async it "complains if the messages are different", device:
                p1 = DeviceMessages.GetPower()
                p2 = DeviceMessages.SetLabel(label="hi")

                device.received = [p1, p2]

                k1 = DeviceMessages.GetPower
                k2 = DeviceMessages.SetLabel
                k3 = DeviceMessages.GetLabel

                with assertRaises(AssertionError, "Expected messages to be the same"):
                    device.compare_received_klses([k2, k1])

                with assertRaises(AssertionError, "Expected messages to be the same"):
                    device.compare_received_klses([k1, k3])

                with assertRaises(AssertionError, "Expected messages to be the same"):
                    device.compare_received_klses([k3, k2])

                device.compare_received_klses([k1, k2])

            async it "is effected by duplicates", serial, device:
                p1 = DeviceMessages.GetPower(source=1, sequence=2, target=serial)
                p2 = DeviceMessages.SetLabel(label="hi", source=3, sequence=4, target=serial)

                k1 = DeviceMessages.GetPower
                k2 = DeviceMessages.SetLabel

                device.received = [p1, p2, p2]
                with assertRaises(
                    AssertionError, "Expected a different number of messages to what we got"
                ):
                    device.compare_received_klses([k1, k2])
