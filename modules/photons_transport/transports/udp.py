from photons_app import helpers as hp

from photons_transport.transports.socket import Socket

import platform
import logging
import socket

log = logging.getLogger("photons_transport.transports.udp")


class UDP(Socket):
    """Knows how to send and receive over udp"""

    async def spawn_transport(self, timeout):
        sock = self.make_socket()
        fut, Protocol = self.make_socket_protocol()

        loop = hp.get_event_loop()

        def canceler():
            if not fut.done():
                fut.cancel()

        handle = loop.call_later(timeout, canceler)

        log.info(self.lc("Creating datagram endpoint", address=self.address))
        await loop.create_datagram_endpoint(Protocol, sock=sock)

        try:
            return await fut
        finally:
            handle.cancel()

    async def write(self, transport, bts, original_message):
        transport.sendto(bts, self.address)

    def make_socket_protocol(self):
        fut, Protocol = super().make_socket_protocol()

        class Protocol(Protocol):
            def datagram_received(sp, data, addr):
                self.session.sync_received_data(data, addr)

        return fut, Protocol

    def make_socket(self):
        """Create the raw socket itself"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(5)
        if platform.system() == "Windows":
            sock.bind(("", 0))
        return sock
