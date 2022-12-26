import time

from delfick_project.norms import dictobj, sb
from photons_app.errors import PhotonsAppError
from photons_messages import protocol_register
from photons_protocol.messages import Messages
from photons_transport.retry_options import Gaps
from photons_transport.session.network import NetworkSession
from photons_transport.targets import LanTarget
from photons_transport.transports.base import Transport


def make_message(bts):
    return Messages.create(bts, protocol_register=protocol_register)


class MemoryServiceMeta(type):
    def __repr__(self):
        return "<Service.MEMORY>"


class MemoryService(metaclass=MemoryServiceMeta):
    name = "MEMORY"


class MemoryTransport(Transport):
    """Knows how to send and receive messages with an in memory Fake device"""

    def setup(self, record, received, serial=None):
        self.serial = serial
        self.record = record
        self.received = received

    def clone_for(self, session):
        return self.__class__(session, self.record, self.received)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.record is self.record

    async def is_transport_active(self, packet, transport):
        return True

    async def close_transport(self, transport):
        pass

    async def spawn_transport(self, timeout):
        return self

    async def write(self, transport, bts, original_message):
        async def receive(bts, addr, replying_to, *, reply):
            await self.session.received_data(reply, addr)

        await self.received(bts, receive, (f"fake://{self.serial}/memory", 56700))


def makeMemorySession(basedon):
    class MemorySession(basedon):
        def setup(self):
            super().setup()
            self.received = []

        def record(self, serial, received_data):
            try:
                msg = make_message(received_data)
                Payload = msg.Payload.__name__
                if msg.pkt_type != msg.Payload.message_type:
                    Payload = msg.pkt_type
                self.received.append((time.time(), serial, Payload, msg.payload))
            except Exception as error:
                self.received.append((time.time(), serial, error))

        async def make_transport(self, serial, service, kwargs):
            device = None
            for d in self.transport_target.devices:
                if d.serial == serial:
                    device = d
                    break

            if device is None:
                raise PhotonsAppError("No such device", want=serial)

            async def writer(bts, give_reply, addr):
                self.record(serial, bts)
                io_name = self.transport_target.io_service.name
                return device.io[io_name].received(bts, give_reply, addr)

            return self.transport_target.transport_kls(self, self.record, writer, serial=serial)

        async def make_broadcast_transport(self, broadcast):
            if broadcast is True:
                broadcast = self.transport_target.default_broadcast

            if broadcast not in self.broadcast_transports:

                io_service = self.transport_target.io_service

                async def writer(bts, received_data, addr):
                    for device in self.transport_target.devices:
                        self.record(device.serial, bts)
                        if io_service.name in device.io and await device.discoverable(
                            io_service, broadcast
                        ):
                            device.io[io_service.name].received(bts, received_data, addr)

                self.broadcast_transports[broadcast] = self.transport_target.transport_kls(
                    self, self.record, writer
                )
            return self.broadcast_transports[broadcast]

    return MemorySession


class MemoryTarget(LanTarget):
    """
    Knows how to talk to fake devices as if they were on the network.
    """

    gaps = dictobj.Field(
        Gaps(gap_between_results=0.05, gap_between_ack_and_res=0.05, timeouts=[(0.2, 0.2)])
    )
    io_service = dictobj.Field(sb.any_spec, default=MemoryService)
    transport_kls = dictobj.Field(sb.any_spec, default=MemoryTransport)

    devices = dictobj.Field(sb.listof(sb.any_spec()), wrapper=sb.required)
    default_broadcast = dictobj.Field(sb.defaulted(sb.string_spec(), "255.255.255.255"))

    session_kls = makeMemorySession(NetworkSession)
