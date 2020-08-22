from photons_transport.transports.base import Transport

from photons_app import helpers as hp

import logging

log = logging.getLogger("photons_transport.transports.memory")


class Memory(Transport):
    """Knows how to send and receive messages with an in memory Fake device"""

    def setup(self, writer):
        self.writer = writer
        self.ts_fut = hp.ChildOfFuture(self.session.stop_fut)
        self.ts = hp.TaskHolder(self.ts_fut)

    def clone_for(self, session):
        return self.__class__(session, self.writer)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.writer is self.writer

    async def is_transport_active(self, packet, transport):
        return True

    async def close_transport(self, transport):
        self.ts_fut.cancel()
        await self.ts.finish()

    async def spawn_transport(self, timeout):
        return self.writer

    async def write(self, transport, bts, original_message):
        self.ts.add(self.writer(self.session.received_data, bts))
