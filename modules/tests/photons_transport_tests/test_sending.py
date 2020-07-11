# coding: spec

from photons_transport.targets import MemoryTarget
from photons_transport.fake import FakeDevice

from photons_app import helpers as hp

from photons_messages import DeviceMessages, protocol_register
from photons_control import test_helpers as chp
from photons_products import Products

from collections import defaultdict
import pytest


@pytest.fixture()
async def _setup():
    device = FakeDevice("d073d5001337", chp.default_responders(Products.LCM2_A19), use_sockets=True)
    async with device:
        options = {"final_future": hp.create_future(), "protocol_register": protocol_register}
        target = MemoryTarget.create(options, {"devices": device})
        yield target, device


describe "Sending messages":

    @pytest.fixture
    def V(self, _setup):
        class V:
            target = _setup[0]
            device = _setup[1]
            device_port = device.services[0].state_service.port

        return V()

    describe "send api":
        async it "works with the sender as sender api", V:
            async with V.target.session() as sender:
                original = DeviceMessages.EchoRequest(echoing=b"hi")

                got = defaultdict(list)
                async for pkt in sender(original, V.device.serial):
                    assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                    assert pkt.Information.sender_message is original
                    got[pkt.serial].append(pkt.payload.as_dict())

                assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async it "works with target.send api", V:
            original = DeviceMessages.EchoRequest(echoing=b"hi")

            got = defaultdict(list)
            async for pkt in V.target.send(original, V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async it "sender also works as a synchronous api", V:
            async with V.target.session() as sender:
                original = DeviceMessages.EchoRequest(echoing=b"hi")

                got = defaultdict(list)
                for pkt in await sender(original, V.device.serial):
                    assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                    assert pkt.Information.sender_message is original
                    got[pkt.serial].append(pkt.payload.as_dict())

                assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async it "target.send also works as a synchronous api", V:
            original = DeviceMessages.EchoRequest(echoing=b"hi")

            got = defaultdict(list)
            for pkt in await V.target.send(original, V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

    describe "run_with api":
        async it "works with the run_with api with sender", V:
            async with V.target.session() as sender:
                original = DeviceMessages.EchoRequest(echoing=b"hi")
                script = V.target.script(original)

                got = defaultdict(list)
                async for pkt in script.run_with(V.device.serial, sender):
                    assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                    assert pkt.Information.sender_message is original
                    got[pkt.serial].append(pkt.payload.as_dict())

                assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

            async with V.target.session() as sender:
                original = DeviceMessages.EchoRequest(echoing=b"hi")
                script = V.target.script(original)

                got = defaultdict(list)
                async for pkt, remote_addr, sender_message in script.run_with(
                    V.device.serial, sender
                ):
                    assert pkt.Information.remote_addr == remote_addr
                    assert pkt.Information.sender_message is sender_message
                    assert sender_message is original
                    got[pkt.serial].append(pkt.payload.as_dict())

                assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async it "works with run_with api without sender", V:
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            script = V.target.script(original)

            got = defaultdict(list)
            async for pkt in script.run_with(V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

            got = defaultdict(list)
            async for pkt, remote_addr, sender_message in script.run_with(V.device.serial):
                assert pkt.Information.remote_addr == remote_addr
                assert pkt.Information.sender_message is sender_message
                assert sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async it "works with the run_with_all api with sender", V:
            async with V.target.session() as sender:
                original = DeviceMessages.EchoRequest(echoing=b"hi")
                script = V.target.script(original)

                got = defaultdict(list)
                for pkt in await script.run_with_all(V.device.serial, sender):
                    assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                    assert pkt.Information.sender_message is original
                    got[pkt.serial].append(pkt.payload.as_dict())

                assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

            async with V.target.session() as sender:
                original = DeviceMessages.EchoRequest(echoing=b"hi")
                script = V.target.script(original)

                got = defaultdict(list)
                for pkt, remote_addr, sender_message in await script.run_with_all(
                    V.device.serial, sender
                ):
                    assert pkt.Information.remote_addr == remote_addr
                    assert pkt.Information.sender_message is sender_message
                    assert sender_message is original
                    got[pkt.serial].append(pkt.payload.as_dict())

                assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

        async it "works with run_with_all api without sender", V:
            original = DeviceMessages.EchoRequest(echoing=b"hi")
            script = V.target.script(original)

            got = defaultdict(list)
            for pkt in await script.run_with_all(V.device.serial):
                assert pkt.Information.remote_addr == ("127.0.0.1", V.device_port)
                assert pkt.Information.sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}

            got = defaultdict(list)
            for pkt, remote_addr, sender_message in await script.run_with_all(V.device.serial):
                assert pkt.Information.remote_addr == remote_addr
                assert pkt.Information.sender_message is sender_message
                assert sender_message is original
                got[pkt.serial].append(pkt.payload.as_dict())
            assert dict(got) == {V.device.serial: [{"echoing": b"hi" + b"\x00" * 62}]}
