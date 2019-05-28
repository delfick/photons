"""
.. autoclass:: photons_transport.base.bridge.TransportBridge
"""
from photons_transport.base.receiver import Receiver
from photons_transport.base.writer import Writer
from photons_transport.base.waiter import Waiter
from photons_transport import RetryOptions

from photons_app import helpers as hp

from input_algorithms import spec_base as sb
import binascii
import logging
import random

log = logging.getLogger("photons_transport.base.bridge")

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

        await bridge.finish()

    Writing to the bridge and waiting for a reply looks like:

    .. code-block:: python

        packet = Messages.GetService()
        writer = await bridge.make_writer(packet)
        reply = await bridge.make_waiter(writer)

    .. automethod:: photons_transport.base.bridge.TransportBridge.start

    .. automethod:: photons_transport.base.bridge.TransportBridge.finish

    Useful
        .. automethod:: photons_transport.base.bridge.TransportBridge.source

        .. automethod:: photons_transport.base.bridge.TransportBridge.seq

        .. automethod:: photons_transport.base.bridge.TransportBridge.forget

        .. automethod:: photons_transport.base.bridge.TransportBridge.target_is_at

        .. automethod:: photons_transport.base.bridge.TransportBridge.find_devices

        .. automethod:: photons_transport.base.bridge.TransportBridge.find_specific_serials

        .. automethod:: photons_transport.base.bridge.TransportBridge.make_writer

        .. automethod:: photons_transport.base.bridge.TransportBridge.make_waiter

    Hooks
        .. automethod:: photons_transport.base.bridge.TransportBridge.write_to_sock

        .. automethod:: photons_transport.base.bridge.TransportBridge.create_receiver

        .. automethod:: photons_transport.base.bridge.TransportBridge.spawn_conn

        .. automethod:: photons_transport.base.bridge.TransportBridge._find_specific_serials
    """
    Waiter = Waiter
    Writer = Writer
    Receiver = Receiver
    Messages = NotImplemented
    RetryOptions = RetryOptions
    default_desired_services = None
    _merged_options_formattable = True

    def __init__(self, stop_fut, transport_target, protocol_register):
        self.transport_target = transport_target
        self.found = {}
        self.stop_fut = hp.ChildOfFuture(stop_fut)
        self.device_source = self.generate_source()
        self.broadcast_source = self.generate_source()
        self.protocol_register = protocol_register

    async def start(self):
        """Hook for logic that happens when the bridge starts"""

    async def finish(self):
        if hasattr(self, "stop_fut"):
            self.stop_fut.cancel()

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

    async def find_devices(self, *, ignore_lost=False, raise_on_none=False, **kwargs):
        """Hook for finding devices"""
        kwargs["ignore_lost"] = ignore_lost
        kwargs["raise_on_none"] = raise_on_none
        found, _ = await self.find_specific_serials(None, **kwargs)
        return found

    async def find_specific_serials(self, serials, ignore_lost=False, raise_on_none=False, **kwargs):
        kwargs["ignore_lost"] = ignore_lost
        kwargs["raise_on_none"] = raise_on_none
        found = await self._find_specific_serials(serials, **kwargs)
        missing = [] if serials is None else [serial for serial in serials if binascii.unhexlify(serial)[:6] not in found]

        if missing:
            log.error(hp.lc("Didn't find some devices", missing=missing))

        return found, missing

    async def _find_specific_serials(self, serials, ignore_lost=False, raise_on_none=False, **kwargs):
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
            self.receiver((pkt, addr, address))

    @hp.memoized_property
    def receiver(self):
        """Make a class for receiving and distributing the messages"""
        return self.Receiver()

    def make_waiter(self, writer, **kwargs):
        """Make a future for waiting on a writer to get a reply"""
        return self.Waiter(self.stop_fut, writer, **kwargs)

    async def make_writer(self, services, original, packet, **kwargs):
        """Make an object for writing to this bridge"""
        writer = self.Writer(self, original, packet, **kwargs)
        return await writer.make(services)

    def make_retry_options(self, **kwargs):
        """Return a new retry options object"""
        return self.RetryOptions(**kwargs)
