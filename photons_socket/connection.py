from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

import platform
import logging
import asyncio
import socket

log = logging.getLogger("photons_socket.connection")

class Sockets(object):
    """Knows how to create and manage sockets!!!"""
    def __init__(self, stop_fut, data_receiver):
        self.stop_fut = hp.ChildOfFuture(stop_fut)
        self.data_receiver = data_receiver

        self.sockets = {}

    def finish(self):
        """Make sure our sockets are closed"""
        for fut in self.sockets.values():
            if not fut.done():
                fut.cancel()
            elif not fut.cancelled() and not fut.exception():
                conn = fut.result()
                try:
                    conn.close()
                except OSError:
                    pass
        self.stop_fut.cancel()

    def spawn(self, address, backoff=0.05, timeout=10):
        """Spawn a socket for this address"""

        # Don't care about port, only care about host
        if type(address) is tuple:
            address = address[0]

        if address in self.sockets:
            fut = self.sockets[address]
            if not fut.done() or (not fut.cancelled() and not fut.exception()):
                return self.sockets[address]
            else:
                del self.sockets[address]

        if self.stop_fut.cancelled():
            raise PhotonsAppError("The target has been cancelled")

        # Initialize a spot for this address
        if address not in self.sockets:
            self.sockets[address] = hp.ChildOfFuture(self.stop_fut)

        # Ok, let's do this!
        self._spawn(address, self.sockets[address], backoff, timeout)

        # And return our future
        return self.sockets[address]

    def _spawn(self, address, fut, backoff, timeout):
        """Spawn the actual connection"""
        sock = self.make_socket(address)
        hp.async_as_background(self.connect_socket(sock, address, fut, backoff, timeout))

    async def connect_socket(self, sock, address, fut, backoff, timeout):
        """Connect our socket to the address"""
        log.info("Creating datagram endpoint to %s", address)

        loop = asyncio.get_event_loop()
        Protocol = self.make_socket_protocol(address, fut)
        connection, _ = await loop.create_datagram_endpoint(Protocol, sock=sock)

        def canceller():
            if not fut.done():
                fut.cancel()
        loop.call_later(timeout, canceller)

    def make_socket_protocol(self, address, fut):
        """Make a socket protocol to read data from"""

        def onerror(exc):
            if address in self.sockets:
                del self.sockets[address]

            if not fut.done() and not fut.cancelled():
                if exc:
                    fut.set_exception(exc)
                else:
                    fut.cancel()

        class SocketProtocol:
            def datagram_received(sp, data, addr):
                self.data_receiver(data, addr, address)

            def error_received(sp, exc):
                log.error("Socket for {0} got an error\terror={1}".format(address, exc))
                onerror(exc)

            def connection_made(sp, transport):
                log.debug("Connected socket for {0}".format(address))
                if fut.done():
                    transport.close()
                else:
                    fut.set_result(transport)

            def connection_lost(sp, exc):
                log.debug("Connected socket for {0} lost connection".format(address))
                onerror(exc)

            def eof_received(self):
                log.error("Socket for {0} got an eof".format(address))
                onerror(None)

        return SocketProtocol

    def make_socket(self, address):
        """Create the raw socket itself"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(5)
        if platform.system() == "Windows":
            sock.bind(("", 0))
        return sock
