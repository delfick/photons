from photons_transport.transports.memory import Memory

from photons_protocol.messages import Messages
from photons_messages import protocol_register

import time


def make_message(bts):
    return Messages.create(bts, protocol_register=protocol_register)


class MemoryServiceMeta(type):
    def __repr__(self):
        return "<Service.MEMORY>"


class MemoryService(metaclass=MemoryServiceMeta):
    pass


def makeMemorySession(basedon):
    class MemorySession(basedon):
        def setup(self):
            super().setup()
            self.received = []

        def record(self, serial, received_data):
            try:
                msg = make_message(received_data)
                Payload = msg.Payload.__name__
                if msg.pkt_type != msg.Payload.message_type:
                    Payload = msg.pkt_type
                self.received.append((time.time(), serial, Payload, msg.payload))
            except Exception as error:
                self.received.append((time.time(), serial, error))

        async def determine_needed_transport(self, packet, services):
            if MemoryService in services:
                return [MemoryService]
            return await super().determine_needed_transport(packet, services)

        async def _do_search(self, serials, timeout, **kwargs):
            found_now = []
            for device in self.transport_target.devices:
                if await device.discoverable(self.transport_target.default_broadcast):
                    found_now.append(device.serial)
                    await device.add_services(self.add_service)
            return found_now

        async def make_transport(self, serial, service, kwargs):
            if service == MemoryService:

                async def writer(received_data, bts):
                    self.record(serial, bts)
                    return await kwargs["writer"](received_data, bts)

                return Memory(self, writer)
            return await super().make_transport(serial, service, kwargs)

        async def make_broadcast_transport(self, broadcast):
            if broadcast is True:
                broadcast = self.transport_target.default_broadcast

            if broadcast not in self.broadcast_transports:

                async def writer(received_data, bts):
                    for device in self.transport_target.devices:
                        self.record(device.serial, bts)
                        if await device.is_reachable(broadcast):
                            await device.write("udp", received_data, bts)

                self.broadcast_transports[broadcast] = Memory(self, writer)
            return self.broadcast_transports[broadcast]

    return MemorySession
