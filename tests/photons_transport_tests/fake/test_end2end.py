# coding: spec

from photons_transport.targets import MemoryTarget, LanTarget
from photons_transport.fake import FakeDevice

from photons_app.test_helpers import AsyncTestCase, with_timeout

from photons_messages import DiscoveryMessages, Services, DeviceMessages, protocol_register

from collections import defaultdict
import asyncio

describe AsyncTestCase, "Fake device":

    @with_timeout
    async it "works with sockets":
        device = FakeDevice("d073d5000001", [], use_sockets=True)

        options = {"final_future": asyncio.Future(), "protocol_register": protocol_register}
        target = MemoryTarget.create(options, {"devices": device})

        await device.start()
        self.assertEqual(len(device.services), 1)
        device_port = device.services[0].state_service.port

        async with target.session() as afr:
            script = target.script(DiscoveryMessages.GetService())

            got = defaultdict(list)
            async for pkt, _, _ in script.run_with(device.serial, afr):
                got[pkt.serial].append(pkt.payload.as_dict())

            self.assertEqual(
                dict(got), {"d073d5000001": [{"service": Services.UDP, "port": device_port}]}
            )

        lantarget = LanTarget.create(options)
        async with lantarget.session() as afr:
            await afr.add_service(device.serial, Services.UDP, host="127.0.0.1", port=device_port)

            script = lantarget.script(DeviceMessages.EchoRequest(echoing=b"hi"))

            got = defaultdict(list)
            async for pkt, _, _ in script.run_with(device.serial, afr):
                got[pkt.serial].append(pkt.payload.as_dict())

            self.assertEqual(dict(got), {"d073d5000001": [{"echoing": b"hi" + b"\x00" * 62}]})

    @with_timeout
    async it "works without sockets":
        device = FakeDevice("d073d5000001", [], use_sockets=False)

        options = {"final_future": asyncio.Future(), "protocol_register": protocol_register}
        target = MemoryTarget.create(options, {"devices": device})

        await device.start()

        async with target.session() as afr:
            script = target.script(DeviceMessages.EchoRequest(echoing=b"hi"))

            got = defaultdict(list)
            async for pkt, _, _ in script.run_with(device.serial, afr):
                got[pkt.serial].append(pkt.payload.as_dict())

            self.assertEqual(dict(got), {"d073d5000001": [{"echoing": b"hi" + b"\x00" * 62}]})
