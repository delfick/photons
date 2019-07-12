from photons_transport.transports.socket import Socket

from photons_app import helpers as hp

import platform
import logging
import asyncio
import socket

log = logging.getLogger("photons_transport.transports.udp")

class UDP(Socket):
    """Knows how to send and receive over udp"""
    async def spawn_transport(self, timeout):
        sock = self.make_socket()
        fut, Protocol = self.make_socket_protocol()

        loop = asyncio.get_event_loop()
        loop.call_later(timeout, fut.cancel)

        log.info(self.lc("Creating datagram endpoint", address=self.address))
        await loop.create_datagram_endpoint(Protocol, sock=sock)

        return await fut

    async def write(self, transport, bts, original_message):
        transport.sendto(bts, self.address)

    def make_socket_protocol(self):
        fut, Protocol = super().make_socket_protocol()

        class Protocol(Protocol):
            def datagram_received(sp, data, addr):
                self.session.received_data(data, addr)

        return fut, Protocol

    def make_socket(self):
        """Create the raw socket itself"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(5)
        if platform.system() == "Windows":
            sock.bind(("", 0))
        return sock
