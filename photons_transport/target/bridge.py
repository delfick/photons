"""
.. autoclass:: photons_transport.target.bridge.TransportBridge
"""
from photons_transport.target.receiver import Receiver
from photons_transport.target.writer import Writer
from photons_transport.target.waiter import Waiter

from photons_app.errors import TimedOut
from photons_app import helpers as hp

from input_algorithms import spec_base as sb
import binascii
import asyncio
import logging
import random
import time

log = logging.getLogger("photons_transport.target.bridge")

class TransportBridge(object):
    """
    The core of the transport!

    This is responsible for writing to, and reading from some connection(s).

    Usage is something like:

    .. code-block:: python

        class MyBridge(Transportbridge):
            Messages = KnownMessages
            default_desired_services = [Services.UDP]

        bridge = MyBridge(....)
        await bridge.start()

        # Interact with bridge

        bridge.finish()

    Writing to the bridge and waiting for a reply looks like:

    .. code-block:: python

        packet = Messages.GetService()
        writer = await bridge.make_writer(packet)
        reply = await bridge.make_waiter(writer)

    .. automethod:: photons_transport.target.bridge.TransportBridge.start

    .. automethod:: photons_transport.target.bridge.TransportBridge.finish

    Useful
        .. automethod:: photons_transport.target.bridge.TransportBridge.source

        .. automethod:: photons_transport.target.bridge.TransportBridge.seq

        .. automethod:: photons_transport.target.bridge.TransportBridge.forget

        .. automethod:: photons_transport.target.bridge.TransportBridge.target_is_at

        .. automethod:: photons_transport.target.bridge.TransportBridge.find

        .. automethod:: photons_transport.target.bridge.TransportBridge.make_writer

        .. automethod:: photons_transport.target.bridge.TransportBridge.make_waiter

    Hooks
        .. automethod:: photons_transport.target.bridge.TransportBridge.write_to_sock

        .. automethod:: photons_transport.target.bridge.TransportBridge.create_receiver

        .. automethod:: photons_transport.target.bridge.TransportBridge.spawn_conn

        .. automethod:: photons_transport.target.bridge.TransportBridge.find_devices
    """
    Waiter = Waiter
    Writer = Writer
    Receiver = Receiver
    Messages = NotImplemented
    default_desired_services = None

    def __init__(self, stop_fut, transport_target, protocol_register, found=None, default_broadcast="255.255.255.255"):
        self.transport_target = transport_target
        self.found = {} if found is None else found
        self.stop_fut = hp.ChildOfFuture(stop_fut)
        self.device_source = self.generate_source()
        self.broadcast_source = self.generate_source()
        self.protocol_register = protocol_register
        self.default_broadcast = default_broadcast

    async def start(self):
        """Hook for logic that happens when the bridge starts"""

    def finish(self):
        if hasattr(self, "stop_fut"):
            self.stop_fut.cancel()
    __del__ = finish

    # Following method is only used if it is defined
    # async def write_to_conn(self, conn, addr, packet, bts):
    #     # LAN connnections are written to in the write method
    #     pass

    def write_to_sock(self, sock, addr, packet, bts):
        """Hook for writing to a socket"""
        raise NotImplementedError()

    async def create_receiver(self, conn, packet, addr):
        """Hook for creating a receiver"""
        raise NotImplementedError()

    async def spawn_conn(self, address, backoff=0.05, target=None, timeout=10):
        """Hook for spawning a connection for a particular address"""
        raise NotImplementedError()

    async def find_devices(self, broadcast, ignore_lost=False, raise_on_none=False, **kwargs):
        """Hook for finding devices"""
        raise NotImplementedError()

    def is_sock_active(self, sock):
        """Hook for saying whether a socket is no longer active"""
        return True

    def generate_source(self):
        """Return us a randomly generated source"""
        return random.randrange(1, 1<<32)

    def source(self, is_broadcast):
        """Return us a source to use for our packet"""
        if is_broadcast is sb.NotSpecified or not is_broadcast:
            return self.device_source
        else:
            return self.broadcast_source

    def seq(self, target):
        """Create the next sequence for this target"""
        if not hasattr(self, "_seq"):
            self._seq = {}
        if target not in self._seq:
            self._seq[target] = 0
        self._seq[target] = (self._seq[target] + 1) % pow(2, 8)
        return self._seq[target]

    async def forget(self, serial):
        """Forget the location of a device"""
        target = binascii.unhexlify(serial)[:6]
        if target in self.found:
            self.found.pop(target)

    def target_is_at(self, serial, address, port, service):
        """Hard code the location of a device"""
        target = binascii.unhexlify(serial)
        self.found[target] = (set([(service, (address, port))]), address)

    async def find(self, target, broadcast=sb.NotSpecified, **kwargs):
        """Find all the devices we can"""
        if type(target) is str:
            target = binascii.unhexlify(target)
        target = target[:6]

        if target in self.found:
            return self.found[target]

        log.debug("Finding address for {0}, broadcasting on {1}".format(target, broadcast))

        kw = dict(kwargs)
        kw["broadcast"] = broadcast if broadcast is not sb.NotSpecified else self.default_broadcast

        start = time.time()
        end = start + kwargs.get("timeout", 20)

        while target not in self.found:
            left = end - time.time()
            if left < 0:
                raise TimedOut("Waiting for state messages", serial=binascii.hexlify(target[:6]).decode())

            kw["timeout"] = left
            fut = asyncio.ensure_future(self.find_devices(**kw))
            d, _ = await asyncio.wait([asyncio.sleep(left), fut], return_when=asyncio.FIRST_COMPLETED)

            if fut not in d:
                fut.cancel()
            else:
                self.found = await fut

            if target in self.found:
                break

        return self.found[target]

    def received_data(self, data, addr, address):
        """What to do when we get some data"""
        if type(data) is bytes:
            log.debug("RECEIVED: {0}".format(binascii.hexlify(data).decode()))

        try:
            pkt = self.Messages.unpack(data, self.protocol_register, unknown_ok=True)
        except Exception as error:
            # with open("/tmp/session", 'a') as fle:
            #     fle.write("RECEIVING\n")
            #     fle.write("\t{0}\n".format(binascii.hexlify(data).decode()))
            log.exception(error)
        else:
            # with open("/tmp/session", 'a') as fle:
            #     fle.write("RECEIVING - {0}\n".format(pkt.Payload.__name__))
            #     fle.write("\t{0}\n".format(binascii.hexlify(data).decode()))
            #     fle.write("\t{0}\n".format(repr(pkt)))
            return self.receiver((pkt, addr, address))

    @hp.memoized_property
    def receiver(self):
        """Make a class for receiving and distributing the messages"""
        return self.Receiver()

    def make_waiter(self, writer, **kwargs):
        """Make a future for waiting on a writer to get a reply"""
        return self.Waiter(self.stop_fut, writer, **kwargs)

    async def make_writer(self, packet, **kwargs):
        """Make an object for writing to this bridge"""
        writer = self.Writer(self, packet, **kwargs)
        return await writer.make()
