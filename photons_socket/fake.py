"""
Test helpers for creating fake devices that talk over the lan

Usage looks like:

.. code-block:: python

    from photons_app.formatter import MergedOptionStringFormatter
    from photons_app.registers import ProtocolRegister

    from photons_socket.fake import FakeDevice, MemorySocketTarget
    from photons_socket.messages import DiscoveryMessages
    from photons_device_messages import DeviceMessages
    from photons_protocol.frame import LIFXPacket

    from input_algorithms.meta import Meta
    import asyncio

    # The protocol register is used to transform bytes into objects
    # Note that for acks to work, we must register DiscoveryMessages
    protocol_register = ProtocolRegister()
    protocol_register.add(1024, LIFXPacket)
    protocol_register.message_register(1024).add(DiscoveryMessages)
    protocol_register.message_register(1024).add(DeviceMessages)

    class MyDevice(FakeDevice):
        def make_response(self, pkt):
            if pkt | DeviceMessages.GetGroup:
                return DeviceMessages.StateGroup(group="123", label="one", updated_at=1)

    final_future = asyncio.Future()
    everything = {
          "final_future": lambda: final_future
        , "protocol_register": protocol_register
        }
    meta = Meta(everything, []).at("target")
    target = MemorySocketTarget.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, {})

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
from photons_socket.messages import Services, DiscoveryMessages
from photons_socket.target import SocketTarget, SocketBridge

from photons_protocol.messages import Messages

import binascii
import asyncio
import socket

class MemorySocketBridge(SocketBridge):
    async def find_devices(self, broadcast, ignore_lost=False, raise_on_none=False, timeout=60, **kwargs):
        res = {}
        for target, device in self.transport_target.devices.items():
            if device.online:
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
    def __init__(self, serial, protocol_register):
        self.serial = serial
        self.online = False
        self.protocol_register = protocol_register

    async def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 0))
            port = s.getsockname()[1]

        class ServerProtocol(asyncio.Protocol):
            def connection_made(sp, transport):
                self.transport = transport

            def datagram_received(sp, data, addr):
                if not self.online:
                    return

                pkt = Messages.unpack(data, self.protocol_register, unknown_ok=True)
                ack = self.ack_for(pkt)
                if ack:
                    ack.sequence = pkt.sequence
                    ack.source = pkt.source
                    ack.target = pkt.target
                    self.transport.sendto(ack.tobytes(serial=self.serial), addr)

                for res in self.response_for(pkt):
                    res.sequence = pkt.sequence
                    res.source = pkt.source
                    res.target = pkt.target
                    self.transport.sendto(res.tobytes(serial=self.serial), addr)

        remote, _ = await asyncio.get_event_loop().create_datagram_endpoint(ServerProtocol, local_addr=("0.0.0.0", port))
        self.remote = remote
        self.port = port
        self.services = (set([(Services.UDP, ("127.0.0.1", self.port))]), "255.255.255.255")
        self.online = True

    async def finish(self):
        if hasattr(self, "remote"):
            self.remote.close()

    def ack_for(self, pkt):
        if pkt.ack_required:
            return DiscoveryMessages.Acknowledgment()

    def response_for(self, pkt):
        res = self.make_response(pkt)
        if res is None or not pkt.res_required:
            return

        if type(res) is list:
            for r in res:
                yield r
        else:
            yield res

    def make_response(pkt):
        raise NotImplementedError()
