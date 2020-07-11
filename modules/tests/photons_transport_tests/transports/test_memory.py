# coding: spec

from photons_transport.transports.memory import Memory

from photons_app import helpers as hp

from unittest import mock
import pytest

describe "Memory":

    @pytest.fixture()
    def V(self):
        class V:
            writer = mock.Mock(name="writer")
            session = mock.Mock(name="session")
            original_message = mock.Mock(name="original_message")

            @hp.memoized_property
            def transport(s):
                return Memory(s.session, s.writer)

        return V()

    @pytest.fixture(autouse=True)
    async def close_transport(self, V):
        try:
            yield
        finally:
            await V.transport.close()

    async it "has equality checks", V:
        writer1 = pytest.helpers.AsyncMock(name="writer1")
        writer2 = pytest.helpers.AsyncMock(name="writer2")

        transport1 = Memory(V.session, writer1)
        transport2 = Memory(V.session, writer1)
        transport3 = Memory(mock.Mock(name="othersession"), writer1)
        transport4 = Memory(V.session, writer2)

        assert transport1 == transport1
        assert transport1 == transport2
        assert transport1 == transport3

        assert transport1 != transport4

    async it "takes in the writer", V:
        assert V.transport.writer is V.writer

    async it "can be cloned", V:
        transport = Memory(V.session, V.writer)
        transport.transport = mock.Mock(name="transport")

        new_session = mock.Mock(name="new_session")
        clone = transport.clone_for(new_session)
        assert clone.session is new_session
        assert clone.writer == V.writer
        assert clone.transport is None

    async it "writes to writer", V:
        called = []
        received = []

        reply1 = mock.Mock(name="reply1")
        reply2 = mock.Mock(name="reply2")
        reply3 = mock.Mock(name="reply3")

        request1 = mock.Mock(name="request1")
        request2 = mock.Mock(name="request2")

        first_receive = hp.create_future()
        second_receive = hp.create_future()

        async def writer(receiver, bts):
            called.append("writer")
            if bts is request1:
                receiver(reply1, "fake")
                receiver(reply2, "fake")
            elif bts is request2:
                receiver(reply3, "fake")
            else:
                assert False, f"unexpected request: {bts}"

        def receive(message, addr):
            received.append(message)

            if message is reply2:
                first_receive.set_result(True)
            elif message is reply3:
                second_receive.set_result(True)

        V.session.received_data.side_effect = receive

        transport = Memory(V.session, writer)
        assert await transport.spawn(V.original_message, timeout=1) is writer

        await transport.write(transport, request1, V.original_message)
        await first_receive
        assert received == [reply1, reply2]

        await transport.write(transport, request2, V.original_message)
        await second_receive
        assert received == [reply1, reply2, reply3]

        assert called == ["writer", "writer"]
