from photons_app import helpers as hp

import asyncio

class Transport:
    def __init__(self, session, *args, **kwargs):
        self.session = session
        self.transport = None
        self.setup(*args, **kwargs)

    def setup(self, *args, **kwargs):
        pass

    def clone_for(self, session):
        raise NotImplementedError()

    def __eq__(self, other):
        raise NotImplementedError()

    async def spawn(self, packet, *, timeout=10, create=True):
        if self.transport is not None:
            if self.transport.done() and (self.transport.cancelled() or self.transport.exception()):
                self.transport = None

        if self.transport is not None and self.transport.done():
            if not await self.is_transport_active(packet, self.transport.result()):
                self.transport = None

        if not create and (self.transport is None or not self.transport.done()):
            return None

        if self.transport is None:
            self.transport = hp.async_as_background(self.spawn_transport(timeout))

        return await self.transport

    async def close(self):
        if self.transport:
            try:
                (f, ), _ = await asyncio.wait([self.transport])
            except asyncio.CancelledError:
                raise
            except:
                return
            else:
                if f.done() and not f.cancelled() and not f.exception():
                    await self.close_transport(f.result())
            self.transport = None

    async def close_transport(self, transport):
        pass

    async def is_transport_active(self, packet, transport):
        return True

    async def spawn_transport(self, timeout):
        raise NotImplementedError()

    async def write(self, transport, bts, original_message):
        raise NotImplementedError()
