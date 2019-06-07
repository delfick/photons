from photons_transport.errors import NoDesiredService, CouldntMakeConnection
from photons_transport.base.result import Result

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from input_algorithms import spec_base as sb
import binascii
import logging
import asyncio

log = logging.getLogger("photons_transport.base.writer")

class Executor(object):
    """
    Container of information necessary for writing to a device.

    Ultimately it uses the Writer that's passed in to do the actual writing
    """
    def __init__(self, writer, original, packet, conn, serial, addr, target, expect_zero):
        self.writer = writer
        self.conn = conn
        self.addr = addr
        self.packet = packet
        self.serial = serial
        self.target = target
        self.original = original
        self.expect_zero = expect_zero

        self.clone = packet.clone()
        self.requests = []

        self.conn_fut = hp.ResettableFuture()
        self.conn_fut.set_result(self.conn)

    @property
    def requires_response(self):
        return self.packet.res_required or self.packet.ack_required

    async def create_receiver(self, bridge):
        await bridge.create_receiver(self.conn, self.packet, self.addr)

    async def ensure_conn(self):
        if not self.writer.bridge.is_sock_active(self.conn):
            log.info(hp.lc("Connection is no longer active, making a new one", serial=self.serial))
            self.conn = await self.writer.determine_conn(self.addr, self.target)

    async def __call__(self):
        return await self.writer.write(self.serial, self.original, self.clone, self.packet.source, self.conn, self.addr, self.requests, self.expect_zero)

class Writer(object):
    """
    Does what it says on the tin! This writes to a device using the bridge that
    is passed in.

    Usage is via the bridge.

    .. code-block:: python

        writer = await bridge.make_writer(packet, **kwargs)
        result = await writer()
        print(await result)
    """
    def __init__(self, bridge, original, packet, retry_options
        , conn=None, addr=None, broadcast=False
        , desired_services=None, found=None, connect_timeout=10, expect_zero=False
        , **kwargs
        ):
        self.conn = conn
        self.addr = addr
        self.found = found
        self.packet = packet
        self.kwargs = kwargs
        self.bridge = bridge
        self.original = original
        self.broadcast = broadcast
        self.expect_zero = expect_zero
        self.retry_options = retry_options
        self.connect_timeout = connect_timeout
        self.desired_services = desired_services

        if self.desired_services is None:
            self.desired_services = self.bridge.default_desired_services

        if self.found is None:
            self.found = self.bridge.found

    async def make(self, services):
        """
        Return an asynchronous callable that when called and awaited returns a pair of futures
        representing the acknowledgement and result from sending this packet
        to the device

        This function also ensures that the bridge has a receiver setup.
        """
        executor = await self.prepare(services)

        if executor.requires_response:
            await executor.create_receiver(self.bridge)

        return executor

    async def prepare(self, services):
        """
        Used by ``make`` to get us the ``Executor`` instance that'll be used to
        do the writing
        """
        packet = self.packet
        target, serial = self.normalise_target(packet)
        addr = await self.determine_addr(serial, services)
        conn = await self.determine_conn(addr, target)
        return Executor(self, self.original, packet, conn, serial, addr, target, self.expect_zero)

    def normalise_target(self, packet):
        """
        Make sure our target is 6 bytes and our serial is a hex string
        """
        target = packet.target

        if target is None:
            return None, None

        if type(target) is bytes:
            target = target[:6]
            serial = binascii.hexlify(target).decode()
        else:
            serial = target
            target = binascii.unhexlify(target)[:6]

        return target, serial

    async def determine_addr(self, serial, services):
        """Use ``self.bridge.find`` to find the address of our target"""
        if type(self.broadcast) is tuple:
            return self.broadcast

        if self.broadcast not in (sb.NotSpecified, False):
            broadcast_addr = self.bridge.transport_target.default_broadcast if self.broadcast in (True, None) else self.broadcast
            return (broadcast_addr, 56700)

        service, addr = self.match_address(serial, services)

        if addr is None:
            raise NoDesiredService(wanted=self.desired_services, serial=serial, available=service)

        if addr and addr[0] is sb.NotSpecified:
            addr = (self.bridge.transport_target.default_broadcast, addr[1])

        return addr

    async def determine_conn(self, addr, target):
        conn = self.conn
        if conn is None:
            conn_future = asyncio.ensure_future(self.bridge.spawn_conn(addr, target=target, timeout=self.connect_timeout))

            try:
                conn = await conn_future
            except asyncio.CancelledError:
                raise CouldntMakeConnection("Timedout waiting for a connection")

        if conn is None:
            raise PhotonsAppError("Failed to spawn a connection!", bridge=repr(self.bridge), addr=addr)

        return conn

    def match_address(self, serial, services):
        addr = None
        service = [s for s, _ in services]
        addresses = [a for _, a in services]

        if len(set(addresses)) > 1:
            log.debug("Found separate addresses\tserial=%s\tfound=%s", serial, services)

        if self.desired_services is None:
            a = addresses[0] if len(addresses) > 0 else None
            return service, a

        for s, a in services:
            if s in self.desired_services:
                addr = a
                service = [s2 for s2, a2 in services if a == a2]
                break

        return service, addr

    async def write(self, serial, original, clone, original_source, conn, addr, requests, expect_zero=False):
        """
        Return the result object representing the results we get from the device

        We allow this result to be resolved by telling the bridge to expect
        results for this ``(source, sequence, target)`` combination.

        Finally, we use ``bridge.write_to_conn`` if it is defined, otherwise
        we use ``bridge.write_to_sock``. The difference between them is
        ``write_to_sock`` does not require awaiting, whereas ``write_to_conn``
        does.

        We also create a clone of the packet and set it's source to be different
        depending on how many times we have retried this packet.
        """
        # Set new source on the clone
        if len(requests) > 0:
            clone.sequence = self.bridge.seq(clone.serial)

        result = Result(original, self.broadcast, self.retry_options)
        if not result.done():
            result.add_done_callback(hp.silent_reporter)
            requests.append(result)
            self.bridge.receiver.register(clone, result, expect_zero)

        # Pack the clone to bytes for transferral
        bts = clone.tobytes(serial)

        # from photons_protocol.messages import Messages
        # with open("/tmp/session", 'a') as fle:
        #     pkt = Messages.unpack(bts, self.bridge.protocol_register)
        #     fle.write("SENDING - {0}\n".format(pkt.Payload.__name__))
        #     fle.write("\t{0}\n".format(binascii.hexlify(bts).decode()))
        #     fle.write("\t{0}\n".format(repr(pkt)))

        if hasattr(self.bridge, "write_to_conn"):
            await self.bridge.write_to_conn(conn, addr, clone, bts)
        else:
            self.bridge.write_to_sock(conn, addr, clone, bts)

        self.display_written(bts, serial)

        # from photons_protocol.messages import Messages
        # unpackd = Messages.unpack(bts, self.bridge.protocol_register, unknown_ok=True)
        # log.info("SENDING %s", unpackd.__class__.__name__)
        # if unpackd:
        #     as_dct = unpackd.payload.as_dict()
        #     for k in sorted(unpackd.payload.keys()):
        #         actual = ""
        #         if as_dct[k] != unpackd.__getitem__(k, do_spec=False):
        #             actual = " ({0})".format(as_dct[k])
        #         log.info("------- %-30s: %-20s%s", k, unpackd.__getitem__(k, do_spec=False), actual)

        return result

    def display_written(self, bts, serial):
        """Log out what we just wrote to the connection"""
        if len(bts) < 256:
            log.debug("SENT: {0} {1}".format(serial, binascii.hexlify(bts).decode()))
