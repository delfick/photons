"""
Test helpers for creating fake devices that talk over the lan

Usage looks like:

.. code-block:: python

    from photons_socket.fake import FakeDevice, MemorySocketTarget
    from photons_messages import protocol_register, DeviceMessages

    import asyncio

    class MyDevice(FakeDevice):
        def make_response(self, pkt, protocol):
            if pkt | DeviceMessages.GetGroup:
                return DeviceMessages.StateGroup(group="123", label="one", updated_at=1)

    final_future = asyncio.Future()
    options = {
          "final_future": final_future
        , "protocol_register": protocol_register
        }
    target = MemorySocketTarget.create(options)

    device1 = MyDevice("d073d5000001", protocol_register)
    await device1.start()
    target.add_device(device1)

    try:
        async for pkt, _, _ in target.script(DeviceMessages.GetGroup()).run_with("d073d5000001"):
            # pkt should be that StateGroup
            print(pkt)
    finally:
        for device in target.devices.values():
            await device.finish()

Note that if you want to either not have the cost of talking over udp sockets
or want to do something async in the response to a message you can do the same
but the following differences:

.. code-block:: python

    # Tell the device you don't want to start a udp socket
    device1 = MyDevice("d073d5000001", protocol_register, use_sockets=False)

    # Use MemoryTarget instead of MemorySocketTarget
    target = MemoryTarget.create(options)

In this scenario you can override async_got_messages to do something when you
get a message, like:

.. code-block:: python

    class MyDevice(FakeDevice):
        async def async_got_message(pkt):
            await asyncio.sleep(some_delay)

            async for msg in super().async_got_message(pkt):
                yield msg

If you want a device to not appear when the target finds devices then
set ``device.online = False``.
"""
from photons_socket.target import SocketTarget, SocketBridge

from photons_app.errors import FoundNoDevices
from photons_app import helpers as hp

from photons_messages import Services, CoreMessages
from photons_protocol.messages import Messages
from photons_transport import RetryOptions

from contextlib import contextmanager
import binascii
import logging
import asyncio
import socket

log = logging.getLogger("photons_socket.fake")

class Done:
    pass

class MemorySocketBridge(SocketBridge):
    class RetryOptions(RetryOptions):
        timeouts = [(0.2, 0.2)]

    async def _find_specific_serials(self, serials, ignore_lost=False, raise_on_none=False, timeout=60, broadcast=True, **kwargs):
        res = {}

        broadcast_address = self.transport_target.default_broadcast
        if broadcast and broadcast is not True:
            broadcast_address = broadcast

        for target, device in self.transport_target.devices.items():
            if device.is_reachable(broadcast_address):
                res[target[:6]] = device.services

        if not ignore_lost:
            for target in list(self.found):
                if target not in res:
                    del self.found[target]

        if raise_on_none and not res:
            raise FoundNoDevices()

        self.found.update(res)
        return self.found

class WithDevices(object):
    def __init__(self, target, devices):
        self.target = target
        self.devices = devices

    async def __aenter__(self):
        for device in self.devices:
            self.target.add_device(device)
            await device.start()

    async def __aexit__(self, exc_type, exc, tb):
        for device in self.devices:
            await device.finish()

class MemorySocketTarget(SocketTarget):
    bridge_kls = lambda s: MemorySocketBridge

    def setup(self, *args, **kwargs):
        super(MemorySocketTarget, self).setup(*args, **kwargs)
        self.devices = {}

    def add_device(self, device):
        target = binascii.unhexlify(device.serial)
        self.devices[target] = device

    def with_devices(self, *devices):
        return WithDevices(self, devices)

class MemoryTarget(MemorySocketTarget):
    bridge_kls = lambda s: MemoryBridge

class MemoryBridge(MemorySocketBridge):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.receivers = {}
        self.connections = {}

    def is_sock_active(self, sock):
        if isinstance(sock, tuple):
            return True
        return super().is_sock_active(sock)

    async def finish(self):
        await super().finish()
        for target, task in self.receivers.items():
            task.cancel()

    async def create_receiver(self, conn, packet, addr):
        if packet.target not in self.receivers:
            async def receive():
                while not self.stop_fut.finished():
                    if conn is True:
                        await asyncio.sleep(0.1)
                    else:
                        nxt = await conn[0].get()
                        self.received_data(nxt, addr, conn)
            self.receivers[packet.target] = hp.async_as_background(receive())

    async def spawn_conn(self, address, backoff=0.05, target=None, timeout=10):
        if address[0] == "255.255.255.255":
            return True
        device = self.transport_target.devices[target]
        if target not in self.connections:
            self.connections[target] = device.connect()
        return self.connections[target]

    async def write_to_conn(self, conn, addr, packet, bts):
        if conn is not True:
            await conn[1].put(bts)

class FakeDevice:
    def __init__(self, serial, protocol_register, port=None, use_sockets=True):
        self.serial = serial
        self.online = False
        self.chosen_port = port
        self.use_sockets = use_sockets
        self.protocol_register = protocol_register

        # Used if we use MemoryTarget instead of MemorySocketTarget
        self.memory_repliers = []
        self.memory_connections = []

    async def start(self):
        await self.start_services()
        self.online = True

    async def finish(self):
        if hasattr(self, "udp_remote"):
            self.udp_remote.close()

        for f in self.memory_repliers:
            f.cancel()

        for stop_fut, queue, conn in self.memory_connections:
            stop_fut.cancel()
            await queue.put(Done)
            await asyncio.wait([conn], timeout=1)
            conn.cancel()

    async def async_got_message(self, pkt):
        for msg in self.got_message(pkt):
            yield msg

    def got_message(self, pkt):
        ack = self.ack_for(pkt, "udp")
        if ack:
            ack.sequence = pkt.sequence
            ack.source = pkt.source
            ack.target = self.serial
            yield ack

        for res in self.response_for(pkt, "udp"):
            res.sequence = pkt.sequence
            res.source = pkt.source
            res.target = self.serial
            yield res

    async def start_services(self):
        if self.use_sockets:
            await self.start_udp()
        else:
            self.port = self.make_port()

        self.services = (
              set(
                [ (Services.UDP, ("127.0.0.1", self.port))
                ]
              )
            , "255.255.255.255"
            )

    async def start_udp(self):
        class ServerProtocol(asyncio.Protocol):
            def connection_made(sp, transport):
                self.udp_transport = transport

            def datagram_received(sp, data, addr):
                if not self.online:
                    return

                log.debug(hp.lc("RECV", bts=binascii.hexlify(data).decode(), protocol="udp", serial=self.serial))

                pkt = Messages.unpack(data, self.protocol_register, unknown_ok=True)
                if pkt.serial not in ("000000000000", self.serial):
                    return

                for msg in self.got_message(pkt):
                    self.udp_transport.sendto(msg.tobytes(serial=self.serial), addr)
        remote = None

        for i in range(3):
            port = self.make_port()

            try:
                remote, _ = await asyncio.get_event_loop().create_datagram_endpoint(ServerProtocol, local_addr=("0.0.0.0", port))
                break
            except OSError:
                if i == 2:
                    raise
                await asyncio.sleep(0.1)

        if remote is None:
            raise Exception("Failed to bind to a udp socket for fake device")

        self.udp_remote = remote
        self.port = port

    def connect(self):
        """Used if MemoryTarget is used instead of MemorySocketTarget"""
        stop_fut = asyncio.Future()
        recv_queue = asyncio.Queue()
        res_queue = asyncio.Queue()

        async def receive():
            while True:
                data = await recv_queue.get()
                if stop_fut.done():
                    return
                if not self.online:
                    continue

                pkt = Messages.unpack(data, self.protocol_register, unknown_ok=True)
                if pkt.serial not in ("000000000000", self.serial):
                    continue

                log.debug(hp.lc("RECV", bts=binascii.hexlify(data).decode(), protocol="udp", serial=self.serial))

                async def reply(pkt):
                    async for response in self.async_got_message(pkt):
                        await res_queue.put(response.tobytes(serial=self.serial))

                if not hasattr(self, "memory_repliers"):
                    self.memory_repliers = []
                self.memory_repliers.append(hp.async_as_background(reply(pkt)))

        if not hasattr(self, "memory_connections"):
            self.memory_connections = []
        self.memory_connections.append((stop_fut, recv_queue, hp.async_as_background(receive())))

        return res_queue, recv_queue

    def ack_for(self, pkt, protocol):
        if pkt.ack_required:
            return CoreMessages.Acknowledgement()

    def do_send_response(self, pkt):
        return pkt.res_required

    def response_for(self, pkt, protocol):
        res = self.make_response(pkt, protocol)
        if res is None or not self.do_send_response(pkt):
            return

        if type(res) is list:
            for r in res:
                yield r
        else:
            yield res

    def make_port(self):
        """Return the port to listen to"""
        if self.chosen_port is not None:
            return self.chosen_port

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 0))
            return s.getsockname()[1]

    def make_response(self, pkt, protocol):
        raise NotImplementedError()

    def is_reachable(self, broadcast_address):
        return self.online

    @contextmanager
    def offline(self):
        try:
            self.online = False
            yield
        finally:
            self.online = True
