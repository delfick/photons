from photons_app.mimic.transport import MemoryService
from photons_app.mimic.operator import operator, IO
from photons_app.mimic.event import Events

from photons_messages import DiscoveryMessages, Services
from photons_app import helpers as hp

from delfick_project.norms import dictobj, sb
import asyncio
import logging
import socket


def make_port():
    """Return the port to listen to"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


@operator
class MemoryIO(IO):
    Source = "MEMORY"

    class Options(dictobj.Spec):
        port = dictobj.Field(sb.overridden(56700))
        service = dictobj.Field(sb.overridden(MemoryService))

    def setup(self):
        super().setup()
        self.active = False
        self.io_source = self.Source

    @classmethod
    def select(kls, device):
        if device.value_store.get("no_memory_io"):
            return
        return kls(device)

    async def apply(self):
        self.device.io[self.options.service.name] = self

    async def _start_session(self):
        self.active = True

    async def _finish_session(self):
        self.active = False

    async def _send_reply(self, reply, give_reply, addr, replying_to):
        if self.active:
            bts = reply.pack().tobytes()
            await self.device.event(
                Events.OUTGOING,
                self,
                pkt=reply,
                bts=bts,
                addr=addr,
                replying_to=replying_to,
            )
            await give_reply(bts, addr, replying_to, reply=reply)

    async def respond(self, event):
        if event | DiscoveryMessages.GetService and event.io is self:
            port = 0 if self.options.port is None else self.options.port
            event.add_replies(DiscoveryMessages.StateService(service=Services.UDP, port=port))


@operator
class UDPIO(MemoryIO):
    Source = "UDP"

    class Options(dictobj.Spec):
        port = dictobj.NullableField(sb.integer_spec())
        service = dictobj.Field(sb.overridden(Services.UDP))

    def setup(self):
        super().setup()
        self.active = False
        self.io_source = self.Source

    @classmethod
    def select(kls, device):
        if device.value_store.get("no_udp_io"):
            return
        return kls(device, {"port": device.value_store.get("port", None)})

    async def _start_session(self):
        await self._finish_session()
        await super()._start_session()

        class ServerProtocol(asyncio.Protocol):
            def connection_made(sp, transport):
                sp.udp_transport = transport

            def datagram_received(sp, data, addr):
                if not self.device.has_power:
                    return

                async def give_reply(bts, addr, replying_to, *, reply):
                    sp.udp_transport.sendto(bts, addr)

                self.received(data, give_reply, addr)

        remote = None
        async with hp.tick(0.1, max_iterations=3) as ticker:
            async for _ in ticker:
                port = self.options.port
                if port is None:
                    port = make_port()

                try:
                    remote, _ = await asyncio.get_event_loop().create_datagram_endpoint(
                        ServerProtocol, local_addr=("0.0.0.0", port)
                    )
                    self.remote = remote
                except OSError:
                    pass
                else:
                    await self.device.annotate(
                        logging.INFO,
                        "Creating UDP port",
                        serial=self.device.serial,
                        port=port,
                        service="UDP",
                    )
                    self.options.port = port
                    break

        if remote is None:
            raise Exception("Failed to bind to a udp socket")

    async def _finish_session(self):
        await super()._finish_session()
        if hasattr(self, "remote"):
            self.remote.close()
