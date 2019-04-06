# coding: spec

from photons_socket.fake import MemorySocketTarget, MemoryTarget, FakeDevice

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app.formatter import MergedOptionStringFormatter

from photons_messages import DiscoveryMessages, Services, protocol_register, DeviceMessages

import asyncio
import time

class Device(FakeDevice):
    def make_response(self, pkt, protocol):
        if pkt | DiscoveryMessages.GetService:
            msgs = []
            for service, (_, port) in self.services[0]:
                msgs.append(DiscoveryMessages.StateService(service=service, port=port))
            return msgs
        elif pkt | DeviceMessages.SetPower:
            return DeviceMessages.StatePower(level=0)
        elif pkt | DeviceMessages.SetLabel:
            return DeviceMessages.StateLabel(label=pkt.label)

describe AsyncTestCase, "Memory targets":
    async it "works with sockets":
        final_future = asyncio.Future()
        options = {
              "final_future": final_future
            , "protocol_register": protocol_register
            }
        target = MemorySocketTarget.create(options)

        device1 = Device("d073d5000001", protocol_register)

        async def doit():
            async with target.session() as afr:
                async with target.with_devices(device1):
                    script = target.script(DiscoveryMessages.GetService())

                    got = []
                    async for pkt, _, _ in script.run_with(device1.serial, afr):
                        got.append((pkt.service.value, pkt.port))

                    self.assertEqual(sorted(got)
                        , [ (Services.UDP.value, device1.port)
                          ]
                        )
        await self.wait_for(doit())

    async it "works without sockets":
        final_future = asyncio.Future()
        options = {
              "final_future": final_future
            , "protocol_register": protocol_register
            }
        target = MemoryTarget.create(options)

        device1 = Device("d073d5000001", protocol_register, use_sockets=False)

        async def doit():
            async with target.session() as afr:
                async with target.with_devices(device1):
                    script = target.script(DiscoveryMessages.GetService())

                    got = []
                    async for pkt, _, _ in script.run_with(device1.serial, afr):
                        got.append((pkt.service.value, pkt.port))

                    self.assertEqual(sorted(got)
                        , [ (Services.UDP.value, device1.port)
                          ]
                        )
        await self.wait_for(doit())

    @with_timeout
    async it "the non socket version isn't slow":
        final_future = asyncio.Future()
        options = {
              "final_future": final_future
            , "protocol_register": protocol_register
            }
        target = MemoryTarget.create(options)

        device1 = Device("d073d5000001", protocol_register, use_sockets=False)

        async with target.session() as afr:
            async with target.with_devices(device1):
                msgs = [
                      DeviceMessages.SetPower(level=0)
                    , DeviceMessages.SetLabel(label="thing")
                    ]

                got = []
                start = time.time()
                async for pkt, _, _ in target.script(msgs).run_with(device1.serial, afr):
                    got.append(pkt)
                self.assertLess(time.time() - start, 0.1)

                self.assertEqual(len(got), 2)
