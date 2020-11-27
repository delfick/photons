from photons_app import helpers as hp


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
            self.transport = hp.create_future(
                name=f"Transport::{self.session.__class__.__name__}::spawn[transport]"
            )
            t = hp.async_as_background(self.spawn_transport(timeout))
            t.add_done_callback(hp.transfer_result(self.transport))

        return await self.transport

    async def close(self):
        if self.transport:
            await hp.wait_for_all_futures(
                self.transport, name=f"Transport::{self.session.__class__.__name__}::close"
            )

            t = self.transport
            self.transport = None

            if t.cancelled() or t.exception():
                return

            await self.close_transport(t.result())

    async def close_transport(self, transport):
        pass

    async def is_transport_active(self, packet, transport):
        return True

    async def spawn_transport(self, timeout):
        raise NotImplementedError()

    async def write(self, transport, bts, original_message):
        raise NotImplementedError()
