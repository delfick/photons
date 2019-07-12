from photons_transport.retry_options import RetryOptions
from photons_transport.transports.memory import Memory

class MemoryServiceMeta(type):
    def __repr__(self):
        return "<Service.MEMORY>"

class MemoryService(metaclass=MemoryServiceMeta):
    pass

class MemoryRetryOptions(RetryOptions):
    timeouts = [(0.2, 0.2)]
    finish_multi_gap = 0.1
memory_retry_options = MemoryRetryOptions()

def makeMemorySession(basedon):
    class MemorySession(basedon):
        def retry_options_for(self, packet, transport):
            return memory_retry_options

        async def determine_needed_transport(self, packet, services):
            if MemoryService in services:
                return [MemoryService]
            return await super().determine_needed_transport(packet, services)

        async def _do_search(self, serials, timeout, **kwargs):
            found_now = []
            for device in self.transport_target.devices:
                if device.is_reachable(self.transport_target.default_broadcast):
                    found_now.append(device.serial)
                    await device.add_services(self.add_service)
            return found_now

        async def make_transport(self, serial, service, kwargs):
            if service == MemoryService:
                return Memory(self, kwargs["writer"])
            return await super().make_transport(serial, service, kwargs)

        async def make_broadcast_transport(self, broadcast):
            if broadcast is True:
                broadcast = self.transport_target.default_broadcast

            if broadcast not in self.broadcast_transports:
                async def writer(received_data, bts):
                    for device in self.transport_target.devices:
                        if device.is_reachable(broadcast):
                            await device.write("udp", received_data, bts)

                self.broadcast_transports[broadcast] = Memory(self, writer)
            return self.broadcast_transports[broadcast]

    return MemorySession
