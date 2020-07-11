# coding: spec

from photons_transport.comms.receiver import Receiver

from photons_app import helpers as hp

from photons_messages import LIFXPacket

from unittest import mock
import binascii
import asyncio
import random
import pytest

describe "Receiver":
    async it "inits some variables":
        receiver = Receiver()
        assert receiver.loop is asyncio.get_event_loop()
        assert receiver.results == {}
        assert receiver.blank_target == b"\x00\x00\x00\x00\x00\x00\x00\x00"

    describe "Usage":

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

        describe "register":
            async it "puts the result under a key of source, sequence, target", V:
                assert V.receiver.results == {}
                key = V.register(V.source, V.sequence, V.target)

                loop = mock.Mock(name="loop")
                fut = hp.create_future()
                other = mock.Mock(name="other")
                called = []

                def call_later(t, cb):
                    called.append("call_later")

                    assert t == 0.5
                    assert V.receiver.results == {key: (V.original, V.result)}

                    V.receiver.results["other"] = other
                    cb()
                    fut.set_result(True)

                loop.call_later.side_effect = call_later

                with mock.patch.object(Receiver, "loop", loop):
                    assert called == []

                    V.result.set_result([])
                    await fut

                    assert called == ["call_later"]
                    assert V.receiver.results == {"other": other}

        describe "recv":
            async it "finds result based on source, sequence, target", V:
                V.register(V.source, V.sequence, V.target)
                await V.receiver.recv(V.packet, V.addr)
                V.result.add_packet.assert_called_once_with(V.packet)

                assert V.packet.Information.remote_addr is V.addr
                assert V.packet.Information.sender_message is V.original

            async it "finds result based on broadcast key if that was used", V:
                V.register(V.source, V.sequence, V.receiver.blank_target)
                await V.receiver.recv(V.packet, V.addr)
                V.result.add_packet.assert_called_once_with(V.packet)

                assert V.packet.Information.remote_addr is V.addr
                assert V.packet.Information.sender_message is V.original

            async it "does nothing if it can't find the key", V:
                V.register(1, 2, binascii.unhexlify("d073d5000001"))
                await V.receiver.recv(V.packet, V.addr)
                assert len(V.result.add_packet.mock_calls) == 0

                assert V.packet.Information.remote_addr is None
                assert V.packet.Information.sender_message is None

            async it "uses message_catcher if can't find the key and that's defined", V:
                message_catcher = pytest.helpers.AsyncMock(name="message_catcher")
                V.receiver.message_catcher = message_catcher
                await V.receiver.recv(V.packet, V.addr)
                message_catcher.assert_called_once_with(V.packet)

                assert V.packet.Information.remote_addr is None
                assert V.packet.Information.sender_message is None

            async it "does not use message_catcher if can find the key and that's defined", V:
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
