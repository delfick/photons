from photons_transport.transports.base import Transport

from photons_app import helpers as hp

import logging

log = logging.getLogger("photons_transport.transports.socket")


def close_socket(socket):
    try:
        socket.close()
    except OSError:
        pass


def close_existing(fut):
    if fut.done() and not fut.cancelled() and not fut.exception():
        close_socket(fut.result())
    fut.reset()


def onerror(fut, exc):
    close_existing(fut)
    if exc:
        fut.set_exception(exc)
    else:
        fut.cancel()


class Socket(Transport):
    def setup(self, host, port, serial=None):
        self.host = host
        self.port = port
        self.serial = serial
        self.address = (self.host, self.port)
        self.lc = hp.lc.using(serial=serial)
        self.socket_futs = []

    def clone_for(self, session):
        return self.__class__(session, self.host, self.port, serial=self.serial)

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and other.host == self.host
            and other.port == self.port
        )

    async def close(self):
        await super().close()

        for fut in self.socket_futs:
            close_existing(fut)

        await hp.cancel_futures_and_wait(
            *self.socket_futs, name=f"{type(self).__name__}::close[wait_for_sockets]"
        )

    async def close_transport(self, transport):
        close_socket(transport)

    async def is_transport_active(self, packet, transport):
        if hasattr(transport, "_sock") and transport._sock is None:
            return False
        return not transport.is_closing()

    def make_socket_protocol(self):
        fut = hp.ResettableFuture(name="Socket::make_socket_protocol[fut]")
        fut.add_done_callback(hp.reporter)
        self.socket_futs.append(fut)
        self.socket_futs = [t for t in self.socket_futs if not t.done()]

        class SocketProtocol:
            def error_received(sp, exc):
                log.error(self.lc("Socket got an error", address=self.address, error=exc))
                # errno 51 is network unreachable
                # Once the network is back, the socket will start working again
                if isinstance(exc, OSError) and exc.errno == 51:
                    return
                onerror(fut, exc)

            def connection_made(sp, transport):
                log.debug(self.lc("Connected socket", address=self.address))
                close_existing(fut)
                fut.set_result(transport)

            def connection_lost(sp, exc):
                log.debug(self.lc("Connected socket lost connection", address=self.address))
                onerror(fut, exc)

            def eof_received(sp):
                log.error(self.lc("Socket got an eof", address=self.address))
                onerror(fut, EOFError())

        return fut, SocketProtocol
