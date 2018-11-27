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

    def is_transport_active(self, transport):
        """Say whether this transport is closed or not"""
        return getattr(transport, "_sock", None) is not None and not getattr(transport._sock, "_closed", False)

    def spawn(self, address, backoff=0.05, timeout=10):
        """Spawn a socket for this address"""

        if self.stop_fut.cancelled():
            raise PhotonsAppError("The target has been cancelled")

        # Don't care about port, only care about host
        if type(address) is tuple:
            address = address[0]

        if address in self.sockets:
            fut = self.sockets[address]
            if not fut.done():
                return fut

            if not fut.cancelled() and not fut.exception():
                transport = fut.result()
                if self.is_transport_active(transport):
                    return fut

            del self.sockets[address]

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
        t = hp.async_as_background(self.connect_socket(sock, address, fut, backoff, timeout))

        def pass_failure(res):
            if fut.done():
                return

            if res.cancelled():
                fut.cancel()
                return

            exc = res.exception()
            if exc is not None:
                fut.set_exception(exc)
        t.add_done_callback(pass_failure)

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
            if fut.done() and not fut.exception() and not fut.cancelled():
                transport = fut.result()
                if hasattr(transport, "close"):
                    transport.close()

            if not fut.done() and not fut.cancelled():
                if exc:
                    fut.set_exception(exc)
                else:
                    fut.cancel()

            if address in self.sockets and self.sockets[address] is fut:
                del self.sockets[address]

        class SocketProtocol:
            def datagram_received(sp, data, addr):
                self.data_receiver(data, addr, address)

            def error_received(sp, exc):
                log.error("Socket for {0} got an error\terror={1}".format(address, exc))
                # errno 51 is network unreachable
                # Once the network is back, the socket will start working again
                if isinstance(exc, OSError) and exc.errno == 51:
                    return
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
