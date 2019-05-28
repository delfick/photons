"""
.. autoclass:: photons_socket.target.SocketTarget

.. autoclass:: photons_socket.target.SocketItem

.. autoclass:: photons_socket.target.SocketBridge
"""
from photons_socket.connection import Sockets

from photons_app.errors import FoundNoDevices
from photons_app import helpers as hp

from photons_transport.base import TransportItem, TransportBridge, TransportTarget
from photons_messages import DiscoveryMessages, Services
from photons_protocol.messages import Messages

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import binascii
import logging

log = logging.getLogger("photons_socket.target")

def serials_to_targets(serials):
    if serials is not None:
        for serial in serials:
            target = serial
            if isinstance(serial, str):
                target = binascii.unhexlify(serial)
            yield target[:6]

class SocketItem(TransportItem):
    """Just a subclass of ``photons_protocol.target.item.TransportItem``"""
    pass

class SocketTarget(TransportTarget):
    """
    A subclass of ``photons_protocol.target.traget.TransportTarget``
    using our ``SocketItem`` and ``SocketBridge``
    """
    item_kls = lambda s: SocketItem
    bridge_kls = lambda s: SocketBridge
    description = dictobj.Field(sb.string_spec, default="Understands how to talk to a device over a TCP socket")

class SocketBridge(TransportBridge):
    """
    Knows how to speak with sockets, using our handy Sockets class

    .. automethod:: photons_socket.target.SocketBridge.spawn_conn

    .. automethod:: photons_socket.target.SocketBridge.write_to_sock
    """
    Sockets = Sockets
    Messages = Messages
    default_desired_services = [Services.UDP]

    def __init__(self, *args, **kwargs):
        super(SocketBridge, self).__init__(*args, **kwargs)
        self.sockets = self.Sockets(self.stop_fut, self.received_data)

    async def finish(self):
        self.sockets.finish()
        await super(SocketBridge, self).finish()

    # Following methods is only used if it is defined
    # async def write_to_connection(self, conn, addr, packet, bts):
    #     # LAN connections are written to in the write method
    #     pass

    async def destroy_receiver(self, conn, found, address):
        """LAN connections get destroyed with a different mechanism for now"""

    async def create_receiver(self, conn, packet, addr):
        """LAN connections do receiving with a different mechanism for now"""

    def is_sock_active(self, sock):
        """Determine if this sock (which is actually a transport) is still open"""
        return self.sockets.is_transport_active(sock)

    async def spawn_conn(self, address, backoff=0.05, target=None, timeout=10):
        """
        Spawn a connection for this address, or the default_broadcast if we
        don't have an address
        """
        # Use default broadcast if we have no address
        if address is sb.NotSpecified:
            address = self.default_broadcast
        return await self.sockets.spawn(address, backoff, timeout)

    def write_to_sock(self, sock, addr, packet, bts):
        """
        Write to the result from spawn_conn
        """
        log.debug("SENDING {0}:{1} TO {2} {3}".format(packet.source, packet.sequence, addr[0], addr[1]))
        sock.sendto(bts, (addr[0], addr[1]))

    async def _find_specific_serials(self, serials, ignore_lost=False, raise_on_none=False, timeout=60, **kwargs):
        """
        Broadcast a Discovery Packet (GetService) and interpret the return
        StateService messages.
        """
        found_now = await self._do_search(serials, self.found, timeout, **kwargs)

        if not ignore_lost:
            for target in list(self.found):
                if target not in found_now:
                    del self.found[target]

        if serials is None and not found_now:
            if raise_on_none:
                raise FoundNoDevices()
            else:
                log.error(hp.lc("Didn't find any devices"))

        return self.found

    async def _do_search(self, serials, found, timeout, **kwargs):
        found_now = set()
        wanted_targets = list(serials_to_targets(serials))

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

            async for pkt, addr, broadcast in script.run_with(None, self, **kwargs):
                target = pkt.target[:6]
                found_now.add(target)
                if target not in found:
                    found[target] = (set(), broadcast)

                if pkt.protocol == 1024 and pkt.pkt_type == 3:
                    found[target][0].add((pkt.service, (addr[0], pkt.port)))

            if serials is None:
                if found_now:
                    break
            elif all(target in found_now for target in wanted_targets):
                break

        return list(found_now)

    async def _search_retry_iterator(self, end_after):
        timeouts = [(0.6, 1.8), (1, 4)]
        retrier = self.make_retry_options(timeouts=timeouts)

        async for info in retrier.iterator(end_after=end_after):
            yield info
