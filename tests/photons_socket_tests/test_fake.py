# coding: spec

from photons_socket.messages import DiscoveryMessages, Services
from photons_socket.fake import MemorySocketTarget, FakeDevice

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.registers import ProtocolRegister
from photons_app.test_helpers import AsyncTestCase

from photons_protocol.frame import LIFXPacket
from photons_script.script import ATarget

from input_algorithms.meta import Meta
import asyncio

class Device(FakeDevice):
    def make_response(self, pkt, protocol):
        if pkt | DiscoveryMessages.GetService:
            msgs = []
            for service, (_, port) in self.services[0]:
                msgs.append(DiscoveryMessages.StateService(service=service, port=port))
            return msgs

describe AsyncTestCase, "Memory target":
    async it "works":
        protocol_register = ProtocolRegister()
        protocol_register.add(1024, LIFXPacket)
        protocol_register.message_register(1024).add(DiscoveryMessages)

        final_future = asyncio.Future()
        everything = {
              "final_future": final_future
            , "protocol_register": protocol_register
            }
        meta = Meta(everything, []).at("target")
        target = MemorySocketTarget.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, {})

        device1 = Device("d073d5000001", protocol_register)

        async def doit():
            async with ATarget(target) as afr:
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
