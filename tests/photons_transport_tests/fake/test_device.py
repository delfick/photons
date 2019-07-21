# coding: spec

from photons_transport.fake import FakeDevice, EchoResponder, ServicesResponder, Attrs, Responder, IgnoreMessage
from photons_transport.session.network import NetworkSession
from photons_transport.session.memory import MemoryService
from photons_transport.targets import MemoryTarget
from photons_transport.transports.udp import UDP

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app.errors import TimedOut

from photons_messages import protocol_register, Services, DiscoveryMessages, DeviceMessages, CoreMessages

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import asynctest
import asyncio
import time

describe AsyncTestCase, "FakeDevice":
    describe "init":
        async it "takes in serial and responders":
            serial = mock.Mock(name="serial")
            responders = [mock.Mock(name="responders")]
            device = FakeDevice(serial, responders)

            self.assertIs(device.serial, serial)
            self.assertIs(device.responders, responders)

            self.assertIs(device.port, None)
            self.assertIs(device.use_sockets, False)
            self.assertIs(device.protocol_register, protocol_register)

            self.assertIsInstance(device.echo_responder, EchoResponder)
            self.assertIsInstance(device.service_responder, ServicesResponder)

            self.assertIsInstance(device.attrs, Attrs)
            self.assertIs(device.attrs._device, device)
            self.assertIs(device.attrs.online, False)

            self.assertEqual(device.reboots, [])
            self.assertEqual(device.services, [])
            self.assertEqual(device.pre_reboot, None)
            self.assertEqual(device.time_rebooting, 1)

        async it "can be given different values for protocol_register, port and use_sockets":
            pr = mock.Mock(name="protocol_register")
            port = mock.Mock(name="port")
            device = FakeDevice("d073d5001337", [], protocol_register=pr, port=port, use_sockets=True)
            
            self.assertIs(device.port, port)
            self.assertIs(device.protocol_register, pr)
            self.assertIs(device.use_sockets, True)

        async it "calls setup":
            called = []

            class Device(FakeDevice):
                def setup(self):
                    called.append(("setup", self.attrs.online))

            device = Device("d073d5001337", [])
            self.assertEqual(called, [("setup", False)])

    describe "Usage":
        async before_each:
            self.serial = "d073d5001337"
            self.device = FakeDevice(self.serial, [])

        async it "is an asynchronous context manager":
            start = asynctest.mock.CoroutineMock(name="start")
            finish = asynctest.mock.CoroutineMock(name="finish")

            with mock.patch.multiple(self.device, start=start, finish=finish):
                async with self.device:
                    start.assert_called_once_with()
                    self.assertEqual(len(finish.mock_calls), 0)
                finish.assert_called_once_with()

        async it "can get all responders":
            responder1 = mock.Mock(name="responder1")
            responder2 = mock.Mock(name="responder2")
            self.device.responders = [responder1, responder2]

            got = []
            for r in self.device.all_responders:
                got.append(r)

            self.assertEqual(got
                , [ responder1
                  , responder2
                  , self.device.service_responder
                  , self.device.echo_responder
                  ]
                )

        async it "can validate an attribute":
            r1 = mock.NonCallableMock(name="responder1", spec=["validate_attr"])
            r2 = mock.NonCallableMock(name="responder2", spec=["validate_attr"])

            key = mock.Mock(name="key")
            value = mock.Mock(name="value")

            with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                self.device.validate_attr(key, value)

            r1.validate_attr.assert_called_once_with(self.device, key, value)
            r2.validate_attr.assert_called_once_with(self.device, key, value)

            r1.validate_attr.reset_mock()
            r2.validate_attr.reset_mock()
            r1.validate_attr.side_effect = ValueError("NOPE")

            with self.fuzzyAssertRaisesError(ValueError, "NOPE"):
                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    self.device.validate_attr(key, value)

            r1.validate_attr.assert_called_once_with(self.device, key, value)
            self.assertEqual(len(r2.validate_attr.mock_calls), 0)

        async it "has a contextmanger for reboot options":
            tr = mock.Mock(name="time_rebooting")
            pr = mock.Mock(name="pre_reboot")

            self.device.time_rebooting = tr
            self.device.pre_reboot = pr

            ntr = mock.Mock(name="new_time_rebooting")
            with self.device.reboot_options(ntr):
                self.assertIs(self.device.time_rebooting, ntr)
                self.assertIs(self.device.pre_reboot, None)

            self.assertIs(self.device.time_rebooting, tr)
            self.assertIs(self.device.pre_reboot, pr)

            npr = mock.Mock(name="new_pre_reboot")
            with self.device.reboot_options(ntr, pre_reboot=npr):
                self.assertIs(self.device.time_rebooting, ntr)
                self.assertIs(self.device.pre_reboot, npr)

            self.assertIs(self.device.time_rebooting, tr)
            self.assertIs(self.device.pre_reboot, pr)

            with self.fuzzyAssertRaisesError(ValueError, "NOPE"):
                with self.device.reboot_options(ntr, pre_reboot=npr):
                    self.assertIs(self.device.time_rebooting, ntr)
                    self.assertIs(self.device.pre_reboot, npr)
                    raise ValueError("NOPE")

            self.assertIs(self.device.time_rebooting, tr)
            self.assertIs(self.device.pre_reboot, pr)

        async it "can be turned back on":
            r1 = mock.NonCallableMock(name="responder1", spec=[])
            r2 = mock.NonCallableMock(name="responder2", spec=["restart"])

            r2.restart = asynctest.mock.CoroutineMock(name="restart")
            self.device.attrs.online = False

            with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                await self.device.power_on()

            self.assertEqual(self.device.attrs.online, True)

            r2.restart.assert_called_once_with(self.device)

        async it "can set intercept_got_message":
            interceptor = mock.Mock(name="interceptor")
            self.device.set_intercept_got_message(interceptor)
            self.assertIs(self.device.intercept_got_message, interceptor)

        async it "can set replies":
            await self.device.reset()

            kls = mock.Mock(name="kls")
            msg1 = mock.Mock(name="msg1")
            msg2 = mock.Mock(name="msg2")

            self.device.set_reply(kls, msg1)
            self.assertEqual(self.device.set_replies, {kls: [msg1]})

            self.device.set_reply(kls, msg2)
            self.assertEqual(self.device.set_replies, {kls: [msg1, msg2]})

        async it "can reset received":
            self.device.received = mock.Mock(name='received')
            self.device.reset_received()
            self.assertEqual(self.device.received, [])

        async it "says a device is reachable if it's online":
            broadcast_address = mock.NonCallableMock(name="broadcast_address", spec=[])

            self.device.attrs.online = False
            assert not await self.device.is_reachable(broadcast_address)

            self.device.attrs.online = True
            assert await self.device.is_reachable(broadcast_address)

        async it "has a decorator for making a device offline":
            self.device.attrs.online = True
            with self.device.offline():
                assert not self.device.attrs.online
            assert self.device.attrs.online

        async it "has a helper for recording what no to give acks for":
            kls = DeviceMessages.SetPower
            await self.device.reset()

            def assertValues(*vals):
                self.assertEqual(self.device.no_res, {})
                self.assertEqual(list(self.device.no_acks.values()), list(vals))

            assertValues()
            with self.device.no_acks_for(kls):
                assertValues(kls)
                with self.device.no_acks_for(kls):
                    assertValues(kls, kls)
                assertValues(kls)
            assertValues()

        async it "has a helper for recording what no to give replies for":
            kls = DeviceMessages.SetPower
            await self.device.reset()

            def assertValues(*vals):
                self.assertEqual(self.device.no_acks, {})
                self.assertEqual(list(self.device.no_res.values()), list(vals))

            assertValues()
            with self.device.no_replies_for(kls):
                assertValues(kls)
                with self.device.no_replies_for(kls):
                    assertValues(kls, kls)
                assertValues(kls)
            assertValues()

        async it "has a helper for recording what no to give responses for":
            kls = DeviceMessages.SetPower
            await self.device.reset()

            def assertValues(*vals):
                self.assertEqual(list(self.device.no_acks.values()), list(vals))
                self.assertEqual(list(self.device.no_res.values()), list(vals))

            assertValues()
            with self.device.no_responses_for(kls):
                assertValues(kls)
                with self.device.no_responses_for(kls):
                    assertValues(kls, kls)
                assertValues(kls)
            assertValues()

        async it "can create an ack":
            pkt = DeviceMessages.SetPower(level=0)
            source = mock.Mock(name='source')
            await self.device.reset()

            assert await self.device.ack_for(pkt, source) | CoreMessages.Acknowledgement

            with self.device.no_acks_for(DeviceMessages.SetPower):
                self.assertIs(await self.device.ack_for(pkt, source), None)

            pkt = DeviceMessages.SetPower(level=0, ack_required=False)
            self.assertIs(await self.device.ack_for(pkt, source), None)

        async it "can determine if we send a response":
            pkt = DeviceMessages.SetPower(level=0)
            source = mock.Mock(name='source')
            await self.device.reset()

            assert await self.device.do_send_response(pkt, source)

            with self.device.no_replies_for(DeviceMessages.SetPower):
                assert not await self.device.do_send_response(pkt, source)

            pkt = DeviceMessages.SetPower(level=0, res_required=False)
            assert not await self.device.do_send_response(pkt, source)

            # Get messages return response anyways
            pkt = DeviceMessages.GetPower(res_required=False)
            assert await self.device.do_send_response(pkt, source)

            with self.device.no_replies_for(DeviceMessages.GetPower):
                pkt = DeviceMessages.GetPower(res_required=False)
                assert not await self.device.do_send_response(pkt, source)

        async it "can make responses":
            pkt = mock.Mock(name="pkt")
            res = mock.Mock(name="res")
            res2 = mock.Mock(name="res2")
            source = mock.Mock(name="source")
            make_response = asynctest.mock.CoroutineMock(name="make_response")
            do_send_response = asynctest.mock.CoroutineMock(name="do_send_response")

            await self.device.reset()

            async def collect():
                got = []
                make_response.reset_mock()
                do_send_response.reset_mock()
                with mock.patch.multiple(self.device, make_response=make_response, do_send_response=do_send_response):
                    async for r in self.device.response_for(pkt, source):
                        got.append(r)
                return got

            make_response.return_value = res
            do_send_response.return_value = True
            got = await collect()
            self.assertEqual(got, [res])
            make_response.assert_called_once_with(pkt, source)
            do_send_response.assert_called_once_with(pkt, source)

            make_response.return_value = [res, res2]
            do_send_response.return_value = True
            got = await collect()
            self.assertEqual(got, [res, res2])
            make_response.assert_called_once_with(pkt, source)
            do_send_response.assert_called_once_with(pkt, source)

            make_response.return_value = [res, res2]
            do_send_response.return_value = False
            got = await collect()
            self.assertEqual(got, [])
            make_response.assert_called_once_with(pkt, source)
            do_send_response.assert_called_once_with(pkt, source)

        async it "can make a port":
            port = self.device.make_port()
            self.assertGreater(port, 0)

            port2 = self.device.make_port()
            self.assertNotEqual(port, port2)

        async it "has empty hook for extra response":
            pkt = mock.NonCallableMock(name="pkt", spec=[])
            source = mock.NonCallableMock(name="source", spec=[])

            got = []
            async for r in self.device.extra_make_response(pkt, source):
                got.apend(r)
            self.assertEqual(got, [])

        describe "discoverable":
            async it "is discoverable if we are reachable and no responders have undiscoverable":
                r1 = mock.Mock(name="r1", spec=[])
                r2 = mock.Mock(name="r2", spec=[])
                broadcast = mock.Mock(name="broadcast")
                is_reachable = asynctest.mock.CoroutineMock(name="is_reachable", return_value=True)
                with mock.patch.multiple(FakeDevice, all_responders=[r1, r2], is_reachable=is_reachable):
                    assert await self.device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)

            async it "is not discoverable if we are not reachable":
                r1 = mock.Mock(name="r1", spec=[])
                r2 = mock.Mock(name="r2", spec=[])
                broadcast = mock.Mock(name="broadcast")
                is_reachable = asynctest.mock.CoroutineMock(name="is_reachable", return_value=False)
                with mock.patch.multiple(FakeDevice, all_responders=[r1, r2], is_reachable=is_reachable):
                    assert not await self.device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)

            async it "is not discoverable if we are reachable but a responder is undiscoverable":
                r1 = mock.Mock(name="r1", spec=["undiscoverable"])
                r1.undiscoverable = asynctest.mock.CoroutineMock(name="undiscoverable", return_value=True)

                r2 = mock.Mock(name="r2", spec=[])
                broadcast = mock.Mock(name="broadcast")
                is_reachable = asynctest.mock.CoroutineMock(name="is_reachable", return_value=True)
                with mock.patch.multiple(FakeDevice, all_responders=[r1, r2], is_reachable=is_reachable):
                    assert not await self.device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)
                r1.undiscoverable.assert_called_once_with(self.device)

            async it "is not discoverable if we are reachable but a responder is undiscoverable even if others are":
                r1 = mock.Mock(name="r1", spec=["undiscoverable"])
                r1.undiscoverable = asynctest.mock.CoroutineMock(name="undiscoverable", return_value=False)

                r2 = mock.Mock(name="r2", spec=["undiscoverable"])
                r2.undiscoverable = asynctest.mock.CoroutineMock(name="undiscoverable", return_value=True)

                r3 = mock.Mock(name="r3", spec=[])

                r4 = mock.Mock(name="r4", spec=["undiscoverable"])
                r4.undiscoverable = asynctest.mock.CoroutineMock(name="undiscoverable", return_value=None)

                broadcast = mock.Mock(name="broadcast")
                is_reachable = asynctest.mock.CoroutineMock(name="is_reachable", return_value=True)
                with mock.patch.multiple(FakeDevice, all_responders=[r1, r2, r3, r4], is_reachable=is_reachable):
                    assert not await self.device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)
                r1.undiscoverable.assert_called_once_with(self.device)
                r2.undiscoverable.assert_called_once_with(self.device)

                # We shortcut after r2 returns True
                self.assertEqual(len(r4.undiscoverable.mock_calls), 0)

            async it "is discoverable if we are reachable but responder say False to undiscoverable":
                r1 = mock.Mock(name="r1", spec=["undiscoverable"])
                r1.undiscoverable = asynctest.mock.CoroutineMock(name="undiscoverable", return_value=False)

                r2 = mock.Mock(name="r2", spec=["undiscoverable"])
                r2.undiscoverable = asynctest.mock.CoroutineMock(name="undiscoverable", return_value=False)

                r3 = mock.Mock(name="r3", spec=[])

                r4 = mock.Mock(name="r4", spec=["undiscoverable"])
                r4.undiscoverable = asynctest.mock.CoroutineMock(name="undiscoverable", return_value=None)

                broadcast = mock.Mock(name="broadcast")
                is_reachable = asynctest.mock.CoroutineMock(name="is_reachable", return_value=True)
                with mock.patch.multiple(FakeDevice, all_responders=[r1, r2, r3, r4], is_reachable=is_reachable):
                    assert await self.device.discoverable(broadcast)
                is_reachable.assert_called_once_with(broadcast)
                r1.undiscoverable.assert_called_once_with(self.device)
                r2.undiscoverable.assert_called_once_with(self.device)
                r4.undiscoverable.assert_called_once_with(self.device)

        describe "reset":
            async it "resets the device":
                r1 = mock.NonCallableMock(name="responder1", spec=["reset"])
                r2 = mock.NonCallableMock(name="responder2", spec=["reset"])

                r1.reset = asynctest.mock.CoroutineMock(name="reset")
                r2.reset = asynctest.mock.CoroutineMock(name="reset")

                self.device.no_res = mock.Mock(name="no_res")
                self.device.no_acks = mock.Mock(name="no_acks")
                self.device.reboots = mock.Mock(name="reboots")
                self.device.received = mock.Mock(name="received")
                self.device.set_replies = mock.Mock(name="set_replies")
                self.device.intercept_got_message = mock.Mock(name="intercept_got_message")
                self.device.attrs.online = False

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    await self.device.reset()

                self.assertEqual(self.device.no_res, {})
                self.assertEqual(self.device.no_acks, {})
                self.assertEqual(self.device.reboots, [])

                self.assertEqual(self.device.set_replies, {})
                self.device.set_replies[1].append(2)
                self.assertEqual(self.device.set_replies, {1: [2]})

                self.assertIs(self.device.intercept_got_message, None)
                self.assertEqual(self.device.received, [])

                r1.reset.assert_called_once_with(self.device, zero=False)
                r2.reset.assert_called_once_with(self.device, zero=False)

                self.assertEqual(self.device.attrs.online, True)

            async it "can reset to zero":
                r1 = mock.NonCallableMock(name="responder1", spec=["reset"])
                r2 = mock.NonCallableMock(name="responder2", spec=["reset"])

                r1.reset = asynctest.mock.CoroutineMock(name="reset")
                r2.reset = asynctest.mock.CoroutineMock(name="reset")

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    await self.device.reset(zero=True)

                r1.reset.assert_called_once_with(self.device, zero=True)
                r2.reset.assert_called_once_with(self.device, zero=True)

        describe "reboot":
            @with_timeout
            async it "can be rebooted":
                fut = asyncio.Future()
                
                called = []

                async def power_on():
                    called.append("power_on")
                    fut.set_result(None)
                power_on = asynctest.mock.CoroutineMock(name="power_on", side_effect=power_on)

                r1 = mock.NonCallableMock(name="responder1", spec=[])
                r2 = mock.NonCallableMock(name="responder2", spec=["shutdown"])

                async def shut(d):
                    self.assertIs(d, self.device)
                    called.append("shutdown")
                r2.shutdown = asynctest.mock.CoroutineMock(name="shutdown", side_effect=shut)

                async def pre_reboot(d):
                    self.assertIs(d, self.device)
                    called.append("pre_reboot")
                pre_reboot = asynctest.mock.CoroutineMock(name="pre_reboot", side_effect=pre_reboot)

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    with mock.patch.object(FakeDevice, "power_on", power_on):
                        with self.device.reboot_options(0.01, pre_reboot):
                            await self.device.reboot()

                self.assertEqual(len(power_on.mock_calls), 0)
                self.assertEqual(self.device.attrs.online, False)
                pre_reboot.assert_awaited_once_with(self.device)
                r2.shutdown.assert_called_once_with(self.device)

                await fut

                power_on.assert_called_once_with()
                self.assertEqual(called, ['pre_reboot', 'shutdown', 'power_on'])

            @with_timeout
            async it "can be told not to come back online":
                called = []

                async def power_on():
                    called.append("power_on")
                    assert False, "Shouldn't be called"
                power_on = asynctest.mock.CoroutineMock(name="power_on", side_effect=power_on)

                r1 = mock.NonCallableMock(name="responder1", spec=[])
                r2 = mock.NonCallableMock(name="responder2", spec=[])

                with mock.patch.object(FakeDevice, "all_responders", [r1, r2]):
                    with mock.patch.object(FakeDevice, "power_on", power_on):
                        with self.device.reboot_options(-1):
                            await self.device.reboot()

                await asyncio.sleep(0.1)

                self.assertEqual(len(power_on.mock_calls), 0)
                self.assertEqual(self.device.attrs.online, False)
                self.assertEqual(called, [])

        describe "start":
            async it "can start udp service":
                called = []

                def call(name):
                    async def func(*args, **kwargs):
                        called.append(name)

                    return func

                finish = asynctest.mock.CoroutineMock(name="finish", side_effect=call("finish"))
                reset = asynctest.mock.CoroutineMock(name="reset", side_effect=call("reset"))
                ensure_udp_service = asynctest.mock.CoroutineMock(name="ensure_udp_service", side_effect=call("ensure_udp_service"))
                ensure_memory_service = asynctest.mock.CoroutineMock(name="ensure_memory_service", side_effect=call("ensure_memory_service"))

                mod = {
                      "finish": finish
                    , "reset": reset
                    , "ensure_udp_service": ensure_udp_service
                    , "ensure_memory_service": ensure_memory_service
                    }

                with mock.patch.multiple(self.device, **mod):
                    self.device.use_sockets = True
                    await self.device.start()

                self.assertEqual(called, ["finish", "reset", "ensure_udp_service"])

            async it "can start memory service":
                called = []

                def call(name):
                    async def func(*args, **kwargs):
                        called.append(name)

                    return func

                finish = asynctest.mock.CoroutineMock(name="finish", side_effect=call("finish"))
                reset = asynctest.mock.CoroutineMock(name="reset", side_effect=call("reset"))
                ensure_udp_service = asynctest.mock.CoroutineMock(name="ensure_udp_service", side_effect=call("ensure_udp_service"))
                ensure_memory_service = asynctest.mock.CoroutineMock(name="ensure_memory_service", side_effect=call("ensure_memory_service"))

                mod = {
                      "finish": finish
                    , "reset": reset
                    , "ensure_udp_service": ensure_udp_service
                    , "ensure_memory_service": ensure_memory_service
                    }

                with mock.patch.multiple(self.device, **mod):
                    self.device.use_sockets = False
                    await self.device.start()

                self.assertEqual(called, ["finish", "reset", "ensure_memory_service"])

            async it "works without mocks":
                self.device.use_sockets = False

                await self.device.start()
                self.assertEqual([s.service for s in self.device.services], [MemoryService])
                await self.device.start()
                self.assertEqual([s.service for s in self.device.services], [MemoryService])

                self.device.use_sockets = True
                await self.device.start()
                self.assertEqual([s.service for s in self.device.services], [Services.UDP])

        describe "finish":
            async it "closes services and resets services to []":
                s1 = mock.Mock(name="service1", spec=["closer"])
                s2 = mock.Mock(name="service1", spec=["closer"])

                s1.closer = asynctest.mock.CoroutineMock(name="closer")
                s2.closer = asynctest.mock.CoroutineMock(name="closer")

                self.device.services = [s1, s2]
                await self.device.finish()
                self.assertEqual(self.device.services, [])

                s1.closer.assert_called_once_with()
                s2.closer.assert_called_once_with()

        describe "add_services":
            async it "can add services":
                adder = mock.Mock(name="adder")

                s1 = mock.Mock(name="s1", spec=["add_service"])
                s2 = mock.Mock(name="s1", spec=["add_service"])

                s1.add_service = asynctest.mock.CoroutineMock(name="add_service")
                s2.add_service = asynctest.mock.CoroutineMock(name="add_service")

                filtered_services = mock.Mock(name="filtered_services", return_value=[s1, s2])

                with mock.patch.object(ServicesResponder, "filtered_services", filtered_services):
                    await self.device.add_services(adder)

                s1.add_service.assert_called_once_with(adder)
                s2.add_service.assert_called_once_with(adder)

            async it "works":
                final_future = asyncio.Future()
                target = MemoryTarget.create(
                      {"final_future": final_future, "protocol_register": protocol_register}
                    , {"devices": [self.device]}
                    )
                session = NetworkSession(target)
                assert not session.found

                self.device.use_sockets = True
                await self.device.start()
                await self.device.add_services(session.add_service)

                transport = UDP(session, host="127.0.0.1", port=self.device.services[0].state_service.port)

                self.assertEqual(session.found.serials, [self.serial])
                self.assertEqual(session.found[self.serial], {Services.UDP: transport})

        describe "write":
            async it "does nothing if none of the services recognise the source":
                self.device.attrs.online = True

                pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target=self.serial)

                s1 = mock.Mock(name="s1", spec=["address"])
                s2 = mock.Mock(name="s2", spec=["address"])

                s1.address.return_value = None
                s2.address.return_value = None

                self.device.services = [s1, s2]

                source = mock.Mock(name="source")
                got_message = mock.NonCallableMock(name="got_message")
                received_data = mock.NonCallableMock(name="received_data")
                
                with mock.patch.object(self.device, "got_message", got_message):
                    await self.device.write(source, received_data, pkt.tobytes(serial=self.serial))

                s1.address.assert_called_once_with(source)
                s2.address.assert_called_once_with(source)

            async it "sends results from got_message to received_data":
                self.device.use_sockets = False
                await self.device.start()

                pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target=self.serial)

                m1 = mock.Mock(name="m1")
                m1b = mock.Mock(name="m1 bytes")

                m2 = mock.Mock(name="m2")
                m2b = mock.Mock(name="m2 bytes")

                m1.tobytes.return_value = m1b
                m2.tobytes.return_value = m2b

                async def got_message(*args):
                    yield m1
                    yield m2
                got_message = asynctest.MagicMock(name="got_message", side_effect=got_message)
                received_data = mock.Mock(name="received_data")
                
                with mock.patch.object(self.device, "got_message", got_message):
                    await self.device.write("memory", received_data, pkt.tobytes(serial=self.serial))

                self.assertEqual(received_data.mock_calls
                    , [ mock.call(m1b, (f"fake://{self.serial}/memory", 56700))
                      , mock.call(m2b, (f"fake://{self.serial}/memory", 56700))
                      ]
                    )

            async it "chooses address based on the services":
                self.device.use_sockets = True
                await self.device.start()

                port = self.device.services[0].state_service.port

                pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target=None)

                m1 = mock.Mock(name="m1")
                m1b = mock.Mock(name="m1 bytes")
                m1.tobytes.return_value = m1b

                async def got_message(*args):
                    yield m1
                got_message = asynctest.MagicMock(name="got_message", side_effect=got_message)
                received_data = mock.Mock(name="received_data")
                
                with mock.patch.object(self.device, "got_message", got_message):
                    await self.device.write("udp", received_data, pkt.tobytes(serial=None))

                self.assertEqual(received_data.mock_calls
                    , [ mock.call(m1b, (f"127.0.0.1", port))
                      ]
                    )

            async it "does nothing if the serial is incorrect":
                self.device.use_sockets = False
                await self.device.start()

                pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target="d073d5000001")

                got_message = mock.NonCallableMock(name="got_message")
                received_data = mock.NonCallableMock(name="received_data")
                
                with mock.patch.object(self.device, "got_message", got_message):
                    await self.device.write("memory", received_data, pkt.tobytes(serial=self.serial))

            async it "does nothing if the device is offline":
                self.device.use_sockets = False
                await self.device.start()

                with self.device.offline():
                    pkt = DeviceMessages.SetPower(level=0, source=1, sequence=1, target=self.serial)

                    got_message = mock.NonCallableMock(name="got_message")
                    received_data = mock.NonCallableMock(name="received_data")
                    
                    with mock.patch.object(self.device, "got_message", got_message):
                        await self.device.write("memory", received_data, pkt.tobytes(serial=self.serial))

        describe "got_message":
            async it "yields ack and results":
                await self.device.reset()

                source = mock.Mock(name="source")
                sequence = mock.Mock(name="sequence")
                serial = mock.Mock(name="serial")

                pkt = mock.Mock(name="pkt", source=source, sequence=sequence, serial=serial)

                ack = mock.Mock(name="ack")
                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name="res2")

                ack_for = asynctest.mock.CoroutineMock(name="ack_for", return_value=ack)

                async def response_for(*args):
                    yield res1
                    yield res2
                response_for = asynctest.MagicMock(name="response_for", side_effect=response_for)

                got = []
                message_source = mock.Mock(name="message_source")

                with mock.patch.multiple(self.device, ack_for=ack_for, response_for=response_for):
                    async for m in self.device.got_message(pkt, message_source):
                        got.append(m)

                self.assertEqual(got, [ack, res1, res2])
                for g in got:
                    self.assertIs(g.source, source)
                    self.assertIs(g.sequence, sequence)
                    self.assertEqual(g.target, self.serial)

                ack_for.assert_called_once_with(pkt, message_source)
                response_for.assert_called_once_with(pkt, message_source)

            async it "yields nothing if intercept_got_message returns False":
                await self.device.reset()

                source = mock.Mock(name="source")
                sequence = mock.Mock(name="sequence")
                serial = mock.Mock(name="serial")

                pkt = mock.Mock(name="pkt", source=source, sequence=sequence, serial=serial)
                ack_for = mock.NonCallableMock(name="ack_for")
                response_for = mock.NonCallableMock(name="response_for ")

                igm = asynctest.mock.CoroutineMock(name="intercept_got_message", return_value=False)

                got = []
                message_source = mock.Mock(name="message_source")

                with mock.patch.multiple(self.device, ack_for=ack_for, response_for=response_for):
                    self.device.set_intercept_got_message(igm)
                    async for m in self.device.got_message(pkt, message_source):
                        got.append(m)

                self.assertEqual(got, [])
                igm.assert_called_once_with(pkt, message_source)

            async it "works":
                class R(Responder):
                    async def respond(s, device, pkt, source):
                        if pkt | DeviceMessages.SetLabel:
                            yield DeviceMessages.StateLabel(label=pkt.label)

                self.device.responders = [R()]
                await self.device.start()

                msg = DeviceMessages.SetLabel(label="hello", source=1, sequence=2, target=self.serial)
                msg_zero_target = DeviceMessages.SetLabel(label="hello", source=1, sequence=2, target=None)

                for msg in (msg, msg_zero_target):
                    got = []

                    async for m in self.device.got_message(msg, "memory"):
                        got.append(m)

                    self.assertEqual(len(got), 2)
                    assert got[0] | CoreMessages.Acknowledgement
                    assert got[1] | DeviceMessages.StateLabel

                    for g in got:
                        self.assertEqual(g.source, 1)
                        self.assertEqual(g.sequence, 2)
                        self.assertEqual(g.serial, self.serial)

        describe "stop_service":
            async it "does nothing if no such service already":
                self.device.services = []
                await self.device.stop_service(Services.UDP)

                await self.device.start()
                self.assertEqual(len(self.device.services), 1)
                self.assertIs(self.device.services[0].service, MemoryService)

                await self.device.stop_service(Services.UDP)
                self.assertEqual(len(self.device.services), 1)
                self.assertIs(self.device.services[0].service, MemoryService)

            async it "closes and removes services if it finds one":
                s1 = mock.Mock(name="service1", service=MemoryService)
                s2 = mock.Mock(name="service2", service=Services.UDP)
                
                s1.closer = mock.NonCallableMock(name="closer")
                s2.closer = asynctest.mock.CoroutineMock(name="closer")

                self.device.services = [s1, s2]
                await self.device.stop_service(Services.UDP)
                self.assertEqual(len(self.device.services), 1)
                self.assertIs(self.device.services[0].service, MemoryService)

                s2.closer.assert_called_once_with()

        describe "ensure_memory_service":
            async it "Creates a MemoryService":
                info = {}

                async def adder(serial, service, *, writer):
                    self.assertEqual(serial, self.serial)
                    self.assertIs(service, MemoryService)
                    info["writer"] = writer

                write = asynctest.mock.CoroutineMock(name="write")

                self.assertEqual(len(self.device.services), 0)
                await self.device.ensure_memory_service()
                self.assertEqual(len(self.device.services), 1)
                await self.device.ensure_memory_service()
                self.assertEqual(len(self.device.services), 1)

                service = self.device.services[0]
                self.assertIs(service.service, MemoryService)
                await service.closer()

                self.assertEqual(info, {})
                with mock.patch.object(self.device, "write", write):
                    await service.add_service(adder)
                assert "writer" in info
                self.assertEqual(len(write.mock_calls), 0)
                a = mock.Mock(name="a")
                b = mock.Mock(name="b")
                await info['writer'](a, b)
                write.assert_called_once_with("memory", a, b)

                state_service = service.state_service
                assert state_service | DiscoveryMessages.StateService
                self.assertEqual(state_service.service, Services.UDP)
                self.assertEqual(state_service.port, 56700)

                self.assertEqual(service.address("memory"), (f"fake://{self.serial}/memory", 56700))
                self.assertEqual(service.address("udp"), None)

        describe "ensure_udp_service":
            @with_timeout
            async it "works":
                self.assertEqual(len(self.device.services), 0)

                await self.device.ensure_udp_service()
                self.assertEqual(len(self.device.services), 1)
                first_service = self.device.services[0]
                port1 = first_service.state_service.port

                await self.device.ensure_udp_service()
                self.assertEqual(len(self.device.services), 1)
                second_service = self.device.services[0]
                port2 = second_service.state_service.port

                self.assertNotEqual(port1, port2)

                final_future = asyncio.Future()
                target = MemoryTarget.create(
                      {"final_future": final_future, "protocol_register": protocol_register}
                    , {"devices": [self.device]}
                    )

                echo = DeviceMessages.EchoRequest(echoing=b"hello")
                await self.device.reset()

                async with target.session() as afr:
                    await first_service.add_service(afr.add_service)
                    got = []
                    es = []
                    async for pkt, _, _ in target.script(echo).run_with(self.serial, afr, message_timeout=0.05, error_catcher=es):
                        got.append(pkt)
                    self.assertEqual(len(got), 0)
                    self.assertEqual(es, [TimedOut("Waiting for reply to a packet", serial=self.serial)])

                    await afr.forget(self.serial)
                    await second_service.add_service(afr.add_service)
                    got = []
                    es = []
                    async for pkt, addr, _ in target.script(echo).run_with(self.serial, afr, message_timeout=0.05, error_catcher=es):
                        self.assertEqual(addr, ("127.0.0.1", port2))
                        got.append(pkt)
                    self.assertEqual(es, [])
                    self.assertEqual(len(got), 1)

        describe "make_response":
            async it "can use set_replies":
                await self.device.start()
                self.assertEqual(self.device.received, [])

                pkt = DeviceMessages.EchoRequest(echoing=b"hello", source=1, sequence=2, target=self.serial)

                shortcut = DeviceMessages.EchoResponse(echoing=b"REPSONDING")
                self.device.set_reply(DeviceMessages.EchoRequest, shortcut)
                res = await self.device.make_response(pkt, "memory")
                self.assertEqual(self.device.received, [pkt])
                assert res | DeviceMessages.EchoResponse
                self.assertEqual(res.echoing, shortcut.echoing)

                res = await self.device.make_response(pkt, "memory")
                self.assertEqual(self.device.received, [pkt, pkt])
                self.assertEqual(len(res), 1)
                res = res[0]
                assert res | DeviceMessages.EchoResponse
                self.assertEqual(res.echoing, pkt.echoing)

                self.device.set_reply(DeviceMessages.SetLabel, DeviceMessages.StateLabel(label="wat"))
                res = await self.device.make_response(pkt, "memory")
                self.assertEqual(self.device.received, [pkt, pkt, pkt])
                self.assertEqual(len(res), 1)
                res = res[0]
                assert res | DeviceMessages.EchoResponse
                self.assertEqual(res.echoing, pkt.echoing)

            async it "does nothing if it doesn't find a responder":
                await self.device.start()
                pkt = DeviceMessages.SetLabel(label="hi")
                res = await self.device.make_response(pkt, "memory")
                self.assertEqual(res, None)

            async it "uses extra_make_response if we didn't find a responder":
                await self.device.start()

                pkt = DeviceMessages.SetLabel(label="hi")
                extra_make_response = asynctest.MagicMock(name="extra_make_response")

                def yld(*r, fail=False):
                    async def func(*args):
                        for thing in r:
                            yield thing
                        if fail:
                            raise IgnoreMessage()
                    return func

                with mock.patch.object(self.device, "extra_make_response", extra_make_response):
                    extra_make_response.side_effect = yld()
                    res = await self.device.make_response(pkt, "memory")
                    self.assertEqual(res, None)
                    extra_make_response.assert_called_once_with(pkt, "memory")
                    extra_make_response.reset_mock()

                    r1 = mock.Mock(name="r1")
                    r2 = mock.Mock(name='r2')
                    extra_make_response.side_effect = yld(r1, r2)
                    res = await self.device.make_response(pkt, "memory")
                    self.assertEqual(res, [r1, r2])
                    extra_make_response.assert_called_once_with(pkt, "memory")
                    extra_make_response.reset_mock()

                    extra_make_response.side_effect = yld(fail=True)
                    res = await self.device.make_response(pkt, "memory")
                    self.assertEqual(res, None)
                    extra_make_response.assert_called_once_with(pkt, "memory")

            async it "uses the first responder that works":
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

                r1.respond = asynctest.MagicMock(name='respond', side_effect=yld())
                r1.reset = asynctest.mock.CoroutineMock(name='reset')

                r2.respond = asynctest.MagicMock(name='respond', side_effect=yld(res))
                r2.reset = asynctest.mock.CoroutineMock(name='reset')

                r3.respond = mock.NonCallableMock(name="respond", spec=[])
                r3.reset = asynctest.mock.CoroutineMock(name='reset')

                self.device.responders = [r1, r2, r3]
                await self.device.start()

                pkt = DeviceMessages.SetLabel(label="hi")
                self.assertEqual(await self.device.make_response(pkt, "memory"), [res])
                r1.respond.assert_called_once_with(self.device, pkt, "memory")
                r2.respond.assert_called_once_with(self.device, pkt, "memory")
                self.assertEqual(len(r3.respond.mock_calls), 0)

                r1.respond.side_effect = yld(fail=True)
                self.assertEqual(await self.device.make_response(pkt, "memory"), None)

        describe "compare_received":
            async it "is fine if no messages either way":
                self.device.received = []
                self.device.compare_received([])

            async it "complains if we have a different number of messages":
                self.device.received = []

                p1 = DeviceMessages.SetLabel(label="hi")

                with self.fuzzyAssertRaisesError(AssertionError, "Expected a different number of messages to what we got"):
                    self.device.compare_received([p1])

            async it "complains if the messages are different":
                p1 = DeviceMessages.GetPower()
                p2 = DeviceMessages.SetLabel(label="hi")
                p3 = DeviceMessages.SetLabel(label="other")

                self.device.received = [p1, p2]

                with self.fuzzyAssertRaisesError(AssertionError, "Expected messages to be the same"):
                    self.device.compare_received([p2, p1])

                with self.fuzzyAssertRaisesError(AssertionError, "Expected messages to be the same"):
                    self.device.compare_received([p1, p3])

                with self.fuzzyAssertRaisesError(AssertionError, "Expected messages to be the same"):
                    self.device.compare_received([p3, p2])

                self.device.compare_received([p1, p2])

            async it "is not effected by source and sequence or duplicates":
                p1 = DeviceMessages.GetPower(source=1, sequence=2, target=self.serial)
                p2 = DeviceMessages.SetLabel(label="hi", source=3, sequence=4, target=self.serial)
                self.device.received = [p1, p2]

                p3 = DeviceMessages.GetPower()
                p4 = DeviceMessages.SetLabel(label="hi")
                self.device.compare_received([p3, p4, p3])

                self.device.received = [p1, p2, p2]
                self.device.compare_received([p3, p4, p3])

            async it "can be told to not remove duplicates":
                p1 = DeviceMessages.GetPower(source=1, sequence=2, target=self.serial)
                p2 = DeviceMessages.SetLabel(label="hi", source=3, sequence=4, target=self.serial)
                self.device.received = [p1, p2]

                p3 = DeviceMessages.GetPower()
                p4 = DeviceMessages.SetLabel(label="hi")

                with self.fuzzyAssertRaisesError(AssertionError, "Expected a different number of messages to what we got"):
                    self.device.compare_received([p3, p4, p3], keep_duplicates=True)

            async it "cares about same payload, but different packet":
                p1 = DeviceMessages.GetPower(source=1, sequence=2, target=self.serial)
                p2 = DeviceMessages.GetLabel(source=1, sequence=2, target=self.serial)
                self.device.received = [p1, p2]

                p3 = DeviceMessages.GetPower()
                p4 = DeviceMessages.GetLabel()

                with self.fuzzyAssertRaisesError(AssertionError, "Expected messages to be the same"):
                    self.device.compare_received([p4, p3])

        describe "compare_received klses":
            async it "is fine if no messages either way":
                self.device.received = []
                self.device.compare_received_klses([])

            async it "complains if we have a different number of messages":
                self.device.received = []

                p1 = DeviceMessages.SetLabel

                with self.fuzzyAssertRaisesError(AssertionError, "Expected a different number of messages to what we got"):
                    self.device.compare_received_klses([p1])

            async it "complains if the messages are different":
                p1 = DeviceMessages.GetPower()
                p2 = DeviceMessages.SetLabel(label="hi")
                p3 = DeviceMessages.SetLabel(label="other")

                self.device.received = [p1, p2]

                k1 = DeviceMessages.GetPower
                k2 = DeviceMessages.SetLabel
                k3 = DeviceMessages.GetLabel

                with self.fuzzyAssertRaisesError(AssertionError, "Expected messages to be the same"):
                    self.device.compare_received_klses([k2, k1])

                with self.fuzzyAssertRaisesError(AssertionError, "Expected messages to be the same"):
                    self.device.compare_received_klses([k1, k3])

                with self.fuzzyAssertRaisesError(AssertionError, "Expected messages to be the same"):
                    self.device.compare_received_klses([k3, k2])

                self.device.compare_received_klses([k1, k2])

            async it "is effected by duplicates":
                p1 = DeviceMessages.GetPower(source=1, sequence=2, target=self.serial)
                p2 = DeviceMessages.SetLabel(label="hi", source=3, sequence=4, target=self.serial)

                k1 = DeviceMessages.GetPower
                k2 = DeviceMessages.SetLabel

                self.device.received = [p1, p2, p2]
                with self.fuzzyAssertRaisesError(AssertionError, "Expected a different number of messages to what we got"):
                    self.device.compare_received_klses([k1, k2])
