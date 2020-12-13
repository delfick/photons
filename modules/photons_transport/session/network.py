from photons_transport.errors import InvalidBroadcast, UnknownService, NoDesiredService
from photons_transport.retry_options import RetryTicker
from photons_transport.comms.base import Communication
from photons_transport.transports.udp import UDP

from photons_app import helpers as hp

from photons_messages import DiscoveryMessages, Services

import binascii
import logging

log = logging.getLogger("photons_transport.session.network")


class NetworkSession(Communication):
    """
    Knows how to discover by broadcasting GetService. It then knows per packet
    which service to use for sending messages.
    """

    UDPTransport = UDP

    def setup(self):
        self.broadcast_transports = {}

    async def finish(self, exc_typ=None, exc=None, tb=None):
        await super().finish(exc_typ, exc, tb)

        ts = [hp.async_as_background(t.close()) for t in self.broadcast_transports.values()]
        await hp.cancel_futures_and_wait(
            *ts, name=f"{type(self).__name__}::finish[wait_for_broadcast_transports]"
        )

        for t in ts:
            if not t.cancelled():
                exc = t.exception()
                if exc:
                    log.error(hp.lc("Failed to close broadcast transport", error=exc))

    def retry_gaps(self, packet, transport):
        return self.transport_target.gaps

    async def determine_needed_transport(self, packet, services):
        return [Services.UDP]

    async def choose_transport(self, packet, services):
        need = await self.determine_needed_transport(packet, services)

        if not need:
            raise NoDesiredService(
                "Unable to determine what service to send packet to",
                protocol=packet.protocol,
                pkt_type=packet.pkt_type,
            )

        for n in need:
            if n in services:
                return services[n]

        raise NoDesiredService("Don't have a desired service", need=need, have=list(services))

    async def _do_search(self, serials, timeout, **kwargs):
        found_now = set()
        discovery_options = self.transport_target.discovery_options

        if discovery_options.has_hardcoded_discovery:
            log.debug("Using hard coded discovery information")
            return await discovery_options.discover(self.add_service)

        get_service = DiscoveryMessages.GetService(
            target=None, tagged=True, addressable=True, res_required=True, ack_required=False
        )

        kwargs["no_retry"] = True
        kwargs["broadcast"] = kwargs.get("broadcast", True) or True
        kwargs["accept_found"] = True
        kwargs["error_catcher"] = []

        async for time_left, time_till_next in self._search_retry_iterator(timeout):
            kwargs["message_timeout"] = time_till_next

            async for pkt in self(get_service, **kwargs):
                if pkt | DiscoveryMessages.StateService:
                    if discovery_options.want(pkt.serial):
                        addr = pkt.Information.remote_addr
                        found_now.add(pkt.target[:6])
                        await self.add_service(pkt.serial, pkt.service, host=addr[0], port=pkt.port)

            if serials is None:
                if found_now:
                    break
            elif all(binascii.unhexlify(serial)[:6] in found_now for serial in serials):
                break

        return list(found_now)

    async def _search_retry_iterator(self, end_after):
        timeouts = [(0.6, 1.8), (1, 2), (2, 6), (4, 10), (5, 20)]
        async for info in RetryTicker(
            timeouts=timeouts, name=f"{type(self).__name__}::_search_retry_iterator[retry_ticker]"
        ).tick(self.stop_fut, end_after):
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

        if type(broadcast) is not str and not (
            isinstance(broadcast, tuple) and len(broadcast) == 2
        ):
            raise InvalidBroadcast("Expect a string or (host, port) tuple", got=broadcast)

        if broadcast in self.broadcast_transports:
            return self.broadcast_transports[broadcast]

        transport = UDP(self, *broadcast)
        self.broadcast_transports[broadcast] = transport
        return transport
