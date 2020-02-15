# coding: spec

from photons_transport.transports.memory import Memory

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from unittest import mock
import asynctest
import asyncio

describe AsyncTestCase, "Memory":
    async before_each:
        self.writer = asynctest.mock.Mock(name="writer")
        self.session = mock.Mock(name="session")
        self.transport = Memory(self.session, self.writer)
        self.original_message = mock.Mock(name="original_message")

    async after_each:
        await self.transport.close()

    async it "has equality checks":
        writer1 = asynctest.mock.CoroutineMock(name="writer1")
        writer2 = asynctest.mock.CoroutineMock(name="writer2")

        transport1 = Memory(self.session, writer1)
        transport2 = Memory(self.session, writer1)
        transport3 = Memory(mock.Mock(name="othersession"), writer1)
        transport4 = Memory(self.session, writer2)

        assert transport1 == transport1
        assert transport1 == transport2
        assert transport1 == transport3

        assert transport1 != transport4

    async it "takes in the writer":
        assert self.transport.writer is self.writer

    async it "can be cloned":
        transport = Memory(self.session, self.writer)
        transport.transport = mock.Mock(name="transport")

        new_session = mock.Mock(name="new_session")
        clone = transport.clone_for(new_session)
        assert clone.session is new_session
        assert clone.writer == self.writer
        assert clone.transport is None

    @with_timeout
    async it "writes to writer":
        called = []
        received = []

        reply1 = mock.Mock(name="reply1")
        reply2 = mock.Mock(name="reply2")
        reply3 = mock.Mock(name="reply3")

        request1 = mock.Mock(name="request1")
        request2 = mock.Mock(name="request2")

        first_receive = asyncio.Future()
        second_receive = asyncio.Future()

        async def writer(receiver, bts):
            called.append("writer")
            if bts is request1:
                receiver(reply1, "fake")
                receiver(reply2, "fake")
            elif bts is request2:
                receiver(reply3, "fake")
            else:
                assert False, f"unexpected request: {request}"

        def receive(message, addr):
            received.append(message)

            if message is reply2:
                first_receive.set_result(True)
            elif message is reply3:
                second_receive.set_result(True)

        self.session.received_data.side_effect = receive

        transport = Memory(self.session, writer)
        assert await transport.spawn(self.original_message, timeout=1) is writer

        await transport.write(transport, request1, self.original_message)
        await first_receive
        assert received == [reply1, reply2]

        await transport.write(transport, request2, self.original_message)
        await second_receive
        assert received == [reply1, reply2, reply3]

        assert called == ["writer", "writer"]
