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

If you want a device to not appear when the target finds devices then
set ``device.online = False``.
"""
from photons_socket.target import SocketTarget, SocketBridge

from photons_app import helpers as hp

from photons_transport.target.retry_options import RetryOptions
from photons_messages import Services, CoreMessages
from photons_protocol.messages import Messages

from contextlib import contextmanager
import binascii
import logging
import asyncio
import socket

log = logging.getLogger("photons_socket.fake")

class MemorySocketBridge(SocketBridge):
    class RetryOptions(RetryOptions):
        timeouts = [(0.2, 0.2)]

    async def find_devices(self, broadcast, ignore_lost=False, raise_on_none=False, timeout=60, **kwargs):
        res = {}

        broadcast_address = (
              self.default_broadcast if broadcast is True else broadcast
            ) or self.default_broadcast

        for target, device in self.transport_target.devices.items():
            if device.is_reachable(broadcast_address):
                res[target[:6]] = device.services

        return res

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

class FakeDevice(object):
    def __init__(self, serial, protocol_register, port=None):
        self.serial = serial
        self.online = False
        self.chosen_port = port
        self.protocol_register = protocol_register

    async def start(self):
        await self.start_services()
        self.online = True

    async def start_services(self):
        await self.start_udp()
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

                ack = self.ack_for(pkt, "udp")
                if ack:
                    ack.sequence = pkt.sequence
                    ack.source = pkt.source
                    ack.target = self.serial
                    self.udp_transport.sendto(ack.tobytes(serial=self.serial), addr)

                for res in self.response_for(pkt, "udp"):
                    res.sequence = pkt.sequence
                    res.source = pkt.source
                    res.target = self.serial
                    self.udp_transport.sendto(res.tobytes(serial=self.serial), addr)

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

    async def finish(self):
        if hasattr(self, "udp_remote"):
            self.udp_remote.close()

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
