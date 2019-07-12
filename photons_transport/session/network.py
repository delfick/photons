from photons_transport.errors import (
      InvalidBroadcast, UnknownService, NoDesiredService
    )
from photons_transport.retry_options import RetryOptions
from photons_transport.comms.base import Communication
from photons_transport.transports.udp import UDP

from photons_app import helpers as hp

from photons_messages import DiscoveryMessages, Services

import binascii
import logging
import asyncio
import time

log = logging.getLogger("photons_transport.session.network")

class UDPRetryOptions(RetryOptions):
    pass

udp_retry_options = UDPRetryOptions()

class NetworkSession(Communication):
    """
    Knows how to discover by broadcasting GetService. It then knows per packet
    which service to use for sending messages.
    """
    UDPTransport = UDP

    def setup(self):
        self.broadcast_transports = {}

    async def finish(self):
        await super().finish()
        for t in self.broadcast_transports.values():
            try:
                await t.close()
            except asyncio.CancelledError:
                pass
            except Exception as error:
                log.error(hp.lc("Failed to close broadcast transport", error=error))

    def retry_options_for(self, packet, transport):
        return udp_retry_options

    async def determine_needed_transport(self, packet, services):
        return [Services.UDP]

    async def choose_transport(self, packet, services):
        need = await self.determine_needed_transport(packet, services)

        if not need:
            raise NoDesiredService("Unable to determine what service to send packet to"
                , protocol = packet.protocol
                , pkt_type = packet.pkt_type
                )

        for n in need:
            if n in services:
                return services[n]

        raise NoDesiredService("Don't have a desired service", need=need, have=list(services))

    async def _do_search(self, serials, timeout, **kwargs):
        found_now = set()

        get_service = DiscoveryMessages.GetService(
              target = None
            , tagged = True
            , addressable = True
            , res_required = True
            , ack_required = False
            )

        script = self.transport_target.script(get_service)

        kwargs["no_retry"] = True
        kwargs["broadcast"] = kwargs.get("broadcast", True) or True
        kwargs["accept_found"] = True
        kwargs["error_catcher"] = []

        async for time_left, time_till_next in self._search_retry_iterator(timeout):
            kwargs["message_timeout"] = time_till_next

            async for pkt, addr, _ in script.run_with(None, self, **kwargs):
                found_now.add(pkt.target[:6])
                await self.add_service(pkt.serial, pkt.service, host=addr[0], port=pkt.port)

            if serials is None:
                if found_now:
                    break
            elif all(binascii.unhexlify(serial)[:6] in found_now for serial in serials):
                break

        return list(found_now)

    async def _search_retry_iterator(self, end_after, get_now=time.time):
        timeouts = [(0.6, 1.8), (1, 4)]
        retrier = RetryOptions(timeouts=timeouts)

        async for info in retrier.iterator(end_after=end_after, get_now=get_now):
            yield info

    async def make_transport(self, serial, service, kwargs):
        if hasattr(service, "name") and service.name.startswith("RESERVED"):
            return None

        if service != Services.UDP:
            raise UnknownService(service=service)

        return self.UDPTransport(self, kwargs["host"], kwargs["port"], serial=serial)

    async def make_broadcast_transport(self, broadcast):
        if broadcast is True:
            broadcast = self.transport_target.default_broadcast

        if isinstance(broadcast, str):
            broadcast = (broadcast, 56700)

        if type(broadcast) is not str and not (isinstance(broadcast, tuple) and len(broadcast) == 2):
            raise InvalidBroadcast("Expect a string or (host, port) tuple", got=broadcast)

        if broadcast in self.broadcast_transports:
            return self.broadcast_transports[broadcast]

        transport = UDP(self, *broadcast)
        self.broadcast_transports[broadcast] = transport
        return transport
