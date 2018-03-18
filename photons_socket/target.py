"""
.. autoclass:: photons_socket.target.SocketTarget

.. autoclass:: photons_socket.target.SocketItem

.. autoclass:: photons_socket.target.SocketBridge
"""
from photons_socket.messages import DiscoveryMessages, Services
from photons_socket.connection import Sockets

from photons_app.errors import TimedOut, FoundNoDevices

from photons_transport.target import TransportItem, TransportBridge, TransportTarget
from photons_protocol.messages import Messages

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import logging

log = logging.getLogger("photons_socket.target")

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

    .. automethod:: photons_socket.target.SocketBridge.find_devices
    """
    Sockets = Sockets
    Messages = Messages
    default_desired_services = [Services.UDP]

    def __init__(self, *args, **kwargs):
        super(SocketBridge, self).__init__(*args, **kwargs)
        self.sockets = self.Sockets(self.stop_fut, self.received_data)

    def finish(self):
        self.sockets.finish()
        super(SocketBridge, self).finish()

    # Following methods is only used if it is defined
    # async def write_to_connection(self, conn, addr, packet, bts):
    #     # LAN connections are written to in the write method
    #     pass

    async def destroy_receiver(self, conn, found, address):
        """LAN connections get destroyed with a different mechanism for now"""

    async def create_receiver(self, conn, packet, addr):
        """LAN connections do receiving with a different mechanism for now"""

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

    async def find_devices(self, broadcast, ignore_lost=False, raise_on_none=False, timeout=60, **kwargs):
        """
        Broadcast a Discovery Packet (GetService) and interpret the return
        StateService messages.
        """
        discovery = DiscoveryMessages.GetService(
              ack_required=False, res_required=True
            , target=None, addressable=True, tagged=True
            )

        script = self.transport_target.script(discovery)
        found_now = []
        try:
            kwargs["broadcast"] = broadcast
            kwargs["first_wait"] = 0.8
            kwargs["first_resend"] = 0.8
            kwargs["accept_found"] = True
            kwargs["multiple_replies"] = True
            kwargs["timeout"] = timeout
            async for pkt, addr, broadcast in script.run_with([], self, **kwargs):
                target = pkt.target[:6]
                found_now.append(target)
                if target not in self.found:
                    self.found[target] = (set(), broadcast)

                if pkt.protocol == 1024 and pkt.pkt_type == 3:
                    service = pkt.payload.service
                    self.found[target][0].add((service, addr))
        except TimedOut as error:
            if raise_on_none:
                raise FoundNoDevices()
            log.error("Didn't find any devices!\terror=%s", error)

        if not ignore_lost:
            for target in list(self.found):
                if target not in found_now:
                    del self.found[target]

        return self.found
