# coding: spec

from photons_transport.transports.udp import UDP

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from unittest import mock
import asyncio
import socket


def free_port():
    """
    Return an unused port number
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


class FakeDevice:
    def __init__(self, port, received):
        self.port = port
        self.received = received

    async def start(self):
        class ServerProtocol(asyncio.Protocol):
            def connection_made(sp, transport):
                self.udp_transport = transport

            def datagram_received(sp, data, addr):
                for msg in self.received(data, addr):
                    self.udp_transport.sendto(msg, addr)

        self.remote, _ = await asyncio.get_event_loop().create_datagram_endpoint(
            ServerProtocol, local_addr=("0.0.0.0", self.port)
        )

    async def finish(self):
        self.remote.close()


describe AsyncTestCase, "UDP":
    async before_each:
        self.host = "127.0.0.1"
        self.port = free_port()

        self.session = mock.Mock(name="session")
        self.original_message = mock.Mock(name="original_message")

        self.serial = "d073d5000001"
        self.transport = UDP(self.session, self.host, self.port, serial=self.serial)

    async it "has equality checks":
        transport1 = UDP(self.session, "one", 1)
        transport2 = UDP(self.session, "one", 1)
        transport3 = UDP(lambda: 1, "one", 1)
        transport4 = UDP(self.session, "two", 1)
        transport5 = UDP(self.session, "two", 2)

        self.assertEqual(transport1, transport1)
        self.assertEqual(transport1, transport2)
        self.assertEqual(transport1, transport3)

        self.assertNotEqual(transport1, transport4)
        self.assertNotEqual(transport1, transport5)

    async it "takes in address":
        self.assertEqual(self.transport.host, self.host)
        self.assertEqual(self.transport.port, self.port)
        self.assertEqual(self.transport.address, (self.host, self.port))
        self.assertEqual(self.transport.serial, self.serial)
        self.assertEqual(self.transport.lc.context, {"serial": self.serial})

        transport = UDP(self.session, self.host, self.port)
        self.assertEqual(transport.serial, None)

    async it "can be cloned":
        transport = UDP(self.session, self.host, self.port, serial=self.serial)
        transport.transport = mock.Mock(name="transport")

        new_session = mock.Mock(name="new_session")
        clone = transport.clone_for(new_session)
        self.assertIs(clone.session, new_session)
        self.assertEqual(clone.host, self.host)
        self.assertEqual(clone.port, self.port)
        self.assertEqual(clone.serial, self.serial)
        self.assertIs(clone.transport, None)

    @with_timeout
    async it "can send and receive bytes":
        reply1 = b"reply1"
        reply2 = b"reply2"
        reply3 = b"reply3"

        request1 = b"request1"
        request2 = b"request2"

        received = []

        first_receive = asyncio.Future()
        second_receive = asyncio.Future()

        def receive(message, addr):
            self.assertEqual(addr, (self.host, self.port))
            received.append(message)

            if message == reply2:
                first_receive.set_result(True)
            elif message == reply3:
                second_receive.set_result(True)

        self.session.received_data.side_effect = receive

        def translate(bts, addr):
            if bts == request1:
                yield reply1
                yield reply2
            elif bts == request2:
                yield reply3
            else:
                assert False, "Unknown message"

        device = FakeDevice(self.port, translate)
        await device.start()

        transport = await self.transport.spawn(self.original_message, timeout=1)

        try:
            await self.transport.write(transport, request1, self.original_message)
            await first_receive
            self.assertEqual(received, [reply1, reply2])

            await self.transport.write(transport, request2, self.original_message)
            await second_receive
            self.assertEqual(received, [reply1, reply2, reply3])
        finally:
            await device.finish()

    @with_timeout
    async it "can close the transport":
        device = FakeDevice(self.port, lambda b, a: [])
        await device.start()

        try:
            transport = await self.transport.spawn(self.original_message, timeout=1)
            assert await self.transport.is_transport_active(self.original_message, transport)

            await self.transport.close()
            assert not await self.transport.is_transport_active(self.original_message, transport)
        finally:
            await device.finish()
