# coding: spec

from photons_transport.fake import Responder, Attrs, ServicesResponder, EchoResponder, FakeDevice
from photons_transport.session.memory import MemoryService

from photons_app.test_helpers import AsyncTestCase

from photons_messages import Services, DiscoveryMessages, DeviceMessages

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import asynctest

describe AsyncTestCase, "Responder":
    async it "holds onto defaults and provided values":

        class R(Responder):
            _fields = ["one", ("two", lambda: 3), ("three", lambda: 4)]

        r = R(one="things", three=5)

        self.assertEqual(r._attr_default_one, "things")
        self.assertEqual(r._attr_default_two, 3)
        self.assertEqual(r._attr_default_three, 5)

    async it "complains if missing a value without a default":

        class R(Responder):
            _fields = ["one", ("two", lambda: 3), ("three", lambda: 4)]

        with self.fuzzyAssertRaisesError(TypeError, "Missing argument one"):
            R(three=5)

    async it "complains about invalid fields":
        for invalid in ((), (1, 2, 3)):

            class R(Responder):
                _fields = [invalid]

            with self.fuzzyAssertRaisesError(
                TypeError, "tuple field should be \(name, default\), got .+"
            ):
                R()

    describe "reset":
        async it "sets the fields on the device based on defaults given at init time and calling default functions again":
            info = {"i": 0, "j": 10}
            dflts = {}

            def make_dflt_func(l):
                def dflt():
                    info[l] += 1
                    return info[l]

                dflt = mock.Mock(name="dflt", side_effect=dflt)
                dflts[l] = dflt
                return dflt

            dflt1 = make_dflt_func("i")
            dflt2 = make_dflt_func("j")

            class R(Responder):
                _fields = ["one", ("two", dflt1), ("three", dflt2)]

            r = R(one=2, three=True)

            dflt1.assert_called_once_with()
            self.assertEqual(len(dflt2.mock_calls), 0)

            device = mock.Mock(name="device")
            device.attrs = Attrs(device)

            dflt1.reset_mock()

            await r.reset(device)
            self.assertEqual(device.attrs._attrs, {"one": 2, "two": 1, "three": True})
            self.assertEqual(len(dflt1.mock_calls), 0)
            self.assertEqual(len(dflt2.mock_calls), 0)

            device.attrs.one = 20
            device.attrs.two = 21
            device.attrs.three = 22
            self.assertEqual(device.attrs._attrs, {"one": 20, "two": 21, "three": 22})

            await r.reset(device)
            self.assertEqual(device.attrs._attrs, {"one": 2, "two": 1, "three": True})
            self.assertEqual(len(dflt1.mock_calls), 0)
            self.assertEqual(len(dflt2.mock_calls), 0)

            device.attrs.one = 20
            device.attrs.two = 21
            device.attrs.three = 22

            # And zero will use default func regardless of passed in values
            await r.reset(device, zero=True)
            self.assertEqual(device.attrs._attrs, {"one": 2, "two": 2, "three": 11})
            dflt1.assert_called_once_with()
            dflt2.assert_called_once_with()

    describe "respond":
        async it "does nothing by default":
            device = mock.NonCallableMock(name="device", spec=[])
            pkt = mock.NonCallableMock(name="pkt", spec=[])
            source = mock.NonCallableMock(name="source", spec=[])

            class R(Responder):
                pass

            got = []
            async for m in R().respond(device, pkt, source):
                got.append(m)
            self.assertEqual(got, [])

describe AsyncTestCase, "default responders":
    async before_each:
        self.device = FakeDevice("d073d5001337", [])
        self.assertEqual(self.device.attrs._attrs, {"online": False})

    describe "ServicesResponder":
        async before_each:
            self.responder = self.device.service_responder

        async it "puts limited_services on the device":
            await self.responder.reset(self.device)
            self.assertEqual(self.device.attrs.limited_services, None)

        async it "has a contextmanager for changing limited services":
            await self.responder.reset(self.device)

            ls = mock.Mock(name="ls")
            self.device.attrs.limited_services = ls

            with ServicesResponder.limited_services(self.device, Services.UDP, MemoryService):
                self.assertEqual(self.device.attrs.limited_services, (Services.UDP, MemoryService))
            self.assertIs(self.device.attrs.limited_services, ls)

        async it "can yield State service messages":
            await self.responder.reset(self.device)

            class AnotherService:
                pass

            state_service1 = mock.NonCallableMock(name="state_service1", spec=[])
            service1 = mock.Mock(name="service", service=Services.UDP, state_service=state_service1)

            state_service2 = mock.NonCallableMock(name="state_service2", spec=[])
            service2 = mock.Mock(
                name="service", service=AnotherService, state_service=state_service2
            )

            state_service3 = mock.NonCallableMock(name="state_service3", spec=[])
            service3 = mock.Mock(
                name="service", service=MemoryService, state_service=state_service3
            )

            self.device.services = [service1, service2, service3]

            got = []
            get_service = DiscoveryMessages.GetService()
            async for m in self.responder.respond(self.device, get_service, "UDP"):
                got.append(m)

            self.assertEqual(got, [state_service1, state_service2, state_service3])

            got = []
            with ServicesResponder.limited_services(self.device, Services.UDP, AnotherService):
                async for m in self.responder.respond(self.device, get_service, "UDP"):
                    got.append(m)
            self.assertEqual(got, [state_service1, state_service2])

            got = []
            with ServicesResponder.limited_services(self.device, MemoryService):
                async for m in self.responder.respond(self.device, get_service, "UDP"):
                    got.append(m)
            self.assertEqual(got, [state_service3])

            got = []
            with ServicesResponder.limited_services(self.device, mock.Mock(name="Service")):
                async for m in self.responder.respond(self.device, get_service, "UDP"):
                    got.append(m)
            self.assertEqual(got, [])

    describe "EchoResponder":
        async before_each:
            self.responder = self.device.echo_responder

        async it "returns an EchoResponse":
            pkt = DeviceMessages.EchoRequest(echoing=b"hello")
            got = []
            async for m in self.responder.respond(self.device, pkt, "memory"):
                got.append(m)

            self.assertEqual(got, [DeviceMessages.EchoResponse(echoing=pkt.echoing)])
