
import asyncio
import binascii
import random
from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_messages import LIFXPacket
from photons_transport.comms.receiver import Receiver

class TestReceiver:
    async def test_it_inits_some_variables(self):
        receiver = Receiver()
        assert receiver.loop is hp.get_event_loop()
        assert receiver.results == {}
        assert receiver.blank_target == b"\x00\x00\x00\x00\x00\x00\x00\x00"

    class TestUsage:

        @pytest.fixture()
        def V(self):
            class V:
                addr = mock.Mock(name="addr")
                source = random.randrange(0, 100)
                target = binascii.unhexlify("d073d50000000000")
                sequence = random.randrange(0, 100)
                receiver = Receiver()

                @hp.memoized_property
                def packet(s):
                    return LIFXPacket(
                        source=s.source, pkt_type=20, sequence=s.sequence, target=s.target
                    )

                @hp.memoized_property
                def original(s):
                    return s.packet.clone()

                @hp.memoized_property
                def result(s):
                    result = hp.create_future()
                    result.add_packet = mock.Mock(name="add_packet")
                    return result

                def register(s, source, sequence, target):
                    packet = LIFXPacket(source=source, sequence=sequence, target=target)

                    s.receiver.register(packet, s.result, s.original)
                    return (source, sequence, target)

            return V()

        class TestRegister:
            async def test_it_puts_the_result_under_a_key_of_source_sequence_target(self, V):
                assert V.receiver.results == {}
                key = V.register(V.source, V.sequence, V.target)
                assert key == (V.source, V.sequence, V.target)
                assert V.receiver.results == {key: (V.original, V.result)}

                r = mock.Mock(name="r")
                V.result.set_result([r])
                assert await V.result == [r]
                await asyncio.sleep(0)
                assert V.receiver.results == {}

        class TestRecv:
            async def test_it_finds_result_based_on_source_sequence_target(self, V):
                V.register(V.source, V.sequence, V.target)
                await V.receiver.recv(V.packet, V.addr)
                V.result.add_packet.assert_called_once_with(V.packet)

                assert V.packet.Information.remote_addr is V.addr
                assert V.packet.Information.sender_message is V.original

            async def test_it_finds_result_based_on_broadcast_key_if_that_was_used(self, V):
                V.register(V.source, V.sequence, V.receiver.blank_target)
                await V.receiver.recv(V.packet, V.addr)
                V.result.add_packet.assert_called_once_with(V.packet)

                assert V.packet.Information.remote_addr is V.addr
                assert V.packet.Information.sender_message is V.original

            async def test_it_does_nothing_if_it_cant_find_the_key(self, V):
                V.register(1, 2, binascii.unhexlify("d073d5000001"))
                await V.receiver.recv(V.packet, V.addr)
                assert len(V.result.add_packet.mock_calls) == 0

                assert V.packet.Information.remote_addr is None
                assert V.packet.Information.sender_message is None

            async def test_it_uses_message_catcher_if_cant_find_the_key_and_thats_defined(self, V):
                message_catcher = pytest.helpers.AsyncMock(name="message_catcher")
                V.receiver.message_catcher = message_catcher
                await V.receiver.recv(V.packet, V.addr)
                message_catcher.assert_called_once_with(V.packet)

                assert V.packet.Information.remote_addr is None
                assert V.packet.Information.sender_message is None

            async def test_it_does_not_use_message_catcher_if_can_find_the_key_and_thats_defined(self, V):
                V.register(V.source, V.sequence, V.target)

                message_catcher = pytest.helpers.AsyncMock(name="message_catcher")
                V.receiver.message_catcher = message_catcher
                await V.receiver.recv(V.packet, V.addr)

                V.result.add_packet.assert_called_once_with(V.packet)
                assert len(message_catcher.mock_calls) == 0

                V.result.add_packet.reset_mock()
                V.register(V.source, V.sequence, V.receiver.blank_target)

                message_catcher = pytest.helpers.AsyncMock(name="message_catcher")
                V.receiver.message_catcher = message_catcher
                await V.receiver.recv(V.packet, V.addr)

                V.result.add_packet.assert_called_once_with(V.packet)
                assert len(message_catcher.mock_calls) == 0

                assert V.packet.Information.remote_addr is V.addr
                assert V.packet.Information.sender_message is V.original
