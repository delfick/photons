# coding: spec

import asyncio
from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_transport.transports.udp import UDP


class FakeIO:
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

        self.remote, _ = await hp.get_event_loop().create_datagram_endpoint(
            ServerProtocol, local_addr=("0.0.0.0", self.port)
        )

    async def finish(self, exc_type=None, exc=None, tb=None):
        self.remote.close()


describe "UDP":

    @pytest.fixture()
    def V(self):
        class V:
            host = "127.0.0.1"
            port = pytest.helpers.free_port()

            session = mock.Mock(name="session")
            original_message = mock.Mock(name="original_message")

            serial = "d073d5000001"

            @hp.memoized_property
            def transport(s):
                return UDP(s.session, s.host, s.port, serial=s.serial)

        return V()

    async it "has equality checks", V:
        transport1 = UDP(V.session, "one", 1)
        transport2 = UDP(V.session, "one", 1)
        transport3 = UDP(lambda: 1, "one", 1)
        transport4 = UDP(V.session, "two", 1)
        transport5 = UDP(V.session, "two", 2)

        assert transport1 == transport1
        assert transport1 == transport2
        assert transport1 == transport3

        assert transport1 != transport4
        assert transport1 != transport5

    async it "takes in address", V:
        assert V.transport.host == V.host
        assert V.transport.port == V.port
        assert V.transport.address == (V.host, V.port)
        assert V.transport.serial == V.serial
        assert V.transport.lc.context == {"serial": V.serial}

        transport = UDP(V.session, V.host, V.port)
        assert transport.serial is None

    async it "can be cloned", V:
        transport = UDP(V.session, V.host, V.port, serial=V.serial)
        transport.transport = mock.Mock(name="transport")

        new_session = mock.Mock(name="new_session")
        clone = transport.clone_for(new_session)
        assert clone.session is new_session
        assert clone.host == V.host
        assert clone.port == V.port
        assert clone.serial == V.serial
        assert clone.transport is None

    async it "can send and receive bytes", V:
        reply1 = b"reply1"
        reply2 = b"reply2"
        reply3 = b"reply3"

        request1 = b"request1"
        request2 = b"request2"

        received = []

        first_receive = hp.create_future()
        second_receive = hp.create_future()

        def receive(message, addr):
            assert addr == (V.host, V.port)
            received.append(message)

            if message == reply2:
                first_receive.set_result(True)
            elif message == reply3:
                second_receive.set_result(True)

        V.session.sync_received_data.side_effect = receive

        def translate(bts, addr):
            if bts == request1:
                yield reply1
                yield reply2
            elif bts == request2:
                yield reply3
            else:
                assert False, "Unknown message"

        device = FakeIO(V.port, translate)
        await device.start()

        transport = await V.transport.spawn(V.original_message, timeout=1)

        try:
            await V.transport.write(transport, request1, V.original_message)
            await first_receive
            assert received == [reply1, reply2]

            await V.transport.write(transport, request2, V.original_message)
            await second_receive
            assert received == [reply1, reply2, reply3]
        finally:
            await device.finish()

    async it "can close the transport", V:
        device = FakeIO(V.port, lambda b, a: [])
        await device.start()

        try:
            transport = await V.transport.spawn(V.original_message, timeout=1)
            assert await V.transport.is_transport_active(V.original_message, transport)

            await V.transport.close()
            assert not await V.transport.is_transport_active(V.original_message, transport)
        finally:
            await device.finish()
