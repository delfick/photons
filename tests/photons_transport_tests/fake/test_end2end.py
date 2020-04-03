# coding: spec

from photons_transport.targets import MemoryTarget, LanTarget
from photons_transport.fake import FakeDevice

from photons_messages import DiscoveryMessages, Services, DeviceMessages, protocol_register

from collections import defaultdict
import asyncio

describe "Fake device":

    async it "works with sockets":
        device = FakeDevice("d073d5000001", [], use_sockets=True)

        options = {"final_future": asyncio.Future(), "protocol_register": protocol_register}
        target = MemoryTarget.create(options, {"devices": device})

        await device.start()
        assert len(device.services) == 1
        device_port = device.services[0].state_service.port

        async with target.session() as afr:
            script = target.script(DiscoveryMessages.GetService())

            got = defaultdict(list)
            async for pkt in script.run_with(device.serial, afr):
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {"d073d5000001": [{"service": Services.UDP, "port": device_port}]}

        lantarget = LanTarget.create(options)
        async with lantarget.session() as afr:
            await afr.add_service(device.serial, Services.UDP, host="127.0.0.1", port=device_port)

            script = lantarget.script(DeviceMessages.EchoRequest(echoing=b"hi"))

            got = defaultdict(list)
            async for pkt in script.run_with(device.serial, afr):
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {"d073d5000001": [{"echoing": b"hi" + b"\x00" * 62}]}

    async it "works without sockets":
        device = FakeDevice("d073d5000001", [], use_sockets=False)

        options = {"final_future": asyncio.Future(), "protocol_register": protocol_register}
        target = MemoryTarget.create(options, {"devices": device})

        await device.start()

        async with target.session() as afr:
            script = target.script(DeviceMessages.EchoRequest(echoing=b"hi"))

            got = defaultdict(list)
            async for pkt in script.run_with(device.serial, afr):
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {"d073d5000001": [{"echoing": b"hi" + b"\x00" * 62}]}

    async it "run_with_works with old api":
        device = FakeDevice("d073d5000001", [], use_sockets=False)

        options = {"final_future": asyncio.Future(), "protocol_register": protocol_register}
        target = MemoryTarget.create(options, {"devices": device})

        await device.start()

        async with target.session() as afr:
            script = target.script(DeviceMessages.EchoRequest(echoing=b"hi"))

            got = defaultdict(list)
            async for pkt, remote_addr, original in script.run_with(device.serial, afr):
                assert pkt.Information.remote_addr == remote_addr
                assert pkt.Information.sender_message == original
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {"d073d5000001": [{"echoing": b"hi" + b"\x00" * 62}]}

            got = defaultdict(list)
            for pkt, remote_addr, original in await script.run_with_all(device.serial, afr):
                assert pkt.Information.remote_addr == remote_addr
                assert pkt.Information.sender_message == original
                got[pkt.serial].append(pkt.payload.as_dict())

            assert dict(got) == {"d073d5000001": [{"echoing": b"hi" + b"\x00" * 62}]}
