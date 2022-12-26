import asyncio
import logging
import socket

from delfick_project.norms import dictobj, sb
from photons_app import helpers as hp
from photons_app.mimic.event import Events
from photons_app.mimic.operator import IO, operator
from photons_app.mimic.transport import MemoryService
from photons_messages import DiscoveryMessages, Services


def make_port():
    """Return the port to listen to"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


@operator
class MemoryIO(IO):
    io_source = MemoryService.name

    class Options(dictobj.Spec):
        port = dictobj.Field(sb.overridden(56700))
        service = dictobj.Field(sb.overridden(MemoryService))
        state_service = dictobj.Field(sb.overridden(Services.UDP))

    @classmethod
    def select(kls, device):
        if device.value_store.get("no_memory_io"):
            return
        return kls(device)

    async def apply(self):
        self.device.io[self.options.service.name] = self

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
            port = self.options.get("state_service_port", self.options.port)
            state_service_port = 0 if port is None else port
            event.add_replies(
                DiscoveryMessages.StateService(
                    service=self.options.state_service, port=state_service_port
                )
            )


@operator
class UDPIO(MemoryIO):
    io_source = Services.UDP.name

    class Options(dictobj.Spec):
        port = dictobj.NullableField(sb.integer_spec())
        service = dictobj.Field(sb.overridden(Services.UDP))
        state_service = dictobj.Field(sb.overridden(Services.UDP))

    @classmethod
    def select(kls, device):
        if device.value_store.get("no_udp_io"):
            return
        return kls(device, {"port": device.value_store.get("port", None)})

    async def power_on(self, event):
        await super().power_on(event)

        class ServerProtocol(asyncio.Protocol):
            def connection_made(sp, transport):
                sp.udp_transport = transport

            def datagram_received(sp, data, addr):
                if not self.device.has_power:
                    return

                async def give_reply(bts, addr, replying_to, *, reply):
                    if sp.udp_transport and not sp.udp_transport.is_closing():
                        sp.udp_transport.sendto(bts, addr)

                self.received(data, give_reply, addr)

        port = None
        error = None
        remote = None
        async with hp.tick(0.1, max_iterations=3) as ticker:
            async for _ in ticker:
                port = self.options.port
                if port is None:
                    port = make_port()

                try:
                    remote, _ = await hp.get_event_loop().create_datagram_endpoint(
                        ServerProtocol, local_addr=("0.0.0.0", port)
                    )
                    self.remote = remote
                except OSError as e:
                    error = e
                else:
                    await self.device.annotate(
                        logging.INFO,
                        f"Creating {self.io_source} port",
                        serial=self.device.serial,
                        port=port,
                        service=self.io_source,
                    )
                    self.options.port = port
                    break

        if remote is None:
            raise Exception(
                "%" * 80
                + f"%%% Failed to bind to a udp socket: {port} ({error})\n"
                + "You should stop whatever is using that port!"
            )

    async def shutting_down(self, event):
        if hasattr(self, "remote"):
            await self.device.annotate(
                logging.INFO,
                f"Closing {self.io_source} port",
                serial=self.device.serial,
                port=self.options.port,
                service=self.io_source,
            )
            self.remote.close()
        await super().shutting_down(event)
