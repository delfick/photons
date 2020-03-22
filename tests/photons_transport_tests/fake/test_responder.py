# coding: spec

from photons_transport.fake import Responder, Attrs, ServicesResponder, EchoResponder, FakeDevice
from photons_transport.session.memory import MemoryService

from photons_messages import Services, DiscoveryMessages, DeviceMessages

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import pytest

describe "Responder":
    async it "holds onto defaults and provided values":

        class R(Responder):
            _fields = ["one", ("two", lambda: 3), ("three", lambda: 4)]

        r = R(one="things", three=5)

        assert r._attr_default_one == "things"
        assert r._attr_default_two == 3
        assert r._attr_default_three == 5

    async it "complains if missing a value without a default":

        class R(Responder):
            _fields = ["one", ("two", lambda: 3), ("three", lambda: 4)]

        with assertRaises(TypeError, "Missing argument one"):
            R(three=5)

    async it "complains about invalid fields":
        for invalid in ((), (1, 2, 3)):

            class R(Responder):
                _fields = [invalid]

            with assertRaises(TypeError, r"tuple field should be \(name, default\), got .+"):
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
            assert len(dflt2.mock_calls) == 0

            device = mock.Mock(name="device")
            device.attrs = Attrs(device)

            dflt1.reset_mock()

            await r.reset(device)
            assert device.attrs._attrs == {"one": 2, "two": 1, "three": True}
            assert len(dflt1.mock_calls) == 0
            assert len(dflt2.mock_calls) == 0

            device.attrs.one = 20
            device.attrs.two = 21
            device.attrs.three = 22
            assert device.attrs._attrs == {"one": 20, "two": 21, "three": 22}

            await r.reset(device)
            assert device.attrs._attrs == {"one": 2, "two": 1, "three": True}
            assert len(dflt1.mock_calls) == 0
            assert len(dflt2.mock_calls) == 0

            device.attrs.one = 20
            device.attrs.two = 21
            device.attrs.three = 22

            # And zero will use default func regardless of passed in values
            await r.reset(device, zero=True)
            assert device.attrs._attrs == {"one": 2, "two": 2, "three": 11}
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
            assert got == []

describe "default responders":

    @pytest.fixture()
    def device(self):
        device = FakeDevice("d073d5001337", [])
        assert device.attrs._attrs == {"online": False}
        return device

    describe "ServicesResponder":

        @pytest.fixture()
        def responder(self, device):
            return device.service_responder

        async it "puts limited_services on the device", device, responder:
            await responder.reset(device)
            assert device.attrs.limited_services == None

        async it "has a contextmanager for changing limited services", device, responder:
            await responder.reset(device)

            ls = mock.Mock(name="ls")
            device.attrs.limited_services = ls

            with ServicesResponder.limited_services(device, Services.UDP, MemoryService):
                assert device.attrs.limited_services == (Services.UDP, MemoryService)
            assert device.attrs.limited_services is ls

        async it "can yield State service messages", device, responder:
            await responder.reset(device)

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

            device.services = [service1, service2, service3]

            got = []
            get_service = DiscoveryMessages.GetService()
            async for m in responder.respond(device, get_service, "UDP"):
                got.append(m)

            assert got == [state_service1, state_service2, state_service3]

            got = []
            with ServicesResponder.limited_services(device, Services.UDP, AnotherService):
                async for m in responder.respond(device, get_service, "UDP"):
                    got.append(m)
            assert got == [state_service1, state_service2]

            got = []
            with ServicesResponder.limited_services(device, MemoryService):
                async for m in responder.respond(device, get_service, "UDP"):
                    got.append(m)
            assert got == [state_service3]

            got = []
            with ServicesResponder.limited_services(device, mock.Mock(name="Service")):
                async for m in responder.respond(device, get_service, "UDP"):
                    got.append(m)
            assert got == []

    describe "EchoResponder":

        @pytest.fixture()
        def responder(self, device):
            return device.echo_responder

        async it "returns an EchoResponse", device, responder:
            pkt = DeviceMessages.EchoRequest(echoing=b"hello")
            got = []
            async for m in responder.respond(device, pkt, "memory"):
                got.append(m)

            assert got == [DeviceMessages.EchoResponse(echoing=pkt.echoing)]
