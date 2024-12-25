
from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_transport.comms.writer import Writer

class TestWriter:

    @pytest.fixture()
    def V(self):
        class V:
            session = mock.Mock(name="session")
            transport = mock.Mock(name="transport")
            receiver = mock.Mock(name="receiver")
            original = mock.Mock(name="original")
            packet = mock.Mock(name="packet")
            retry_gaps = mock.Mock(name="retry_gaps")
            did_broadcast = mock.Mock(name="did_broadcast")
            connect_timeout = mock.Mock(name="connect_timeout")

            @hp.memoized_property
            def writer(s):
                return Writer(
                    s.session,
                    s.transport,
                    s.receiver,
                    s.original,
                    s.packet,
                    s.retry_gaps,
                    did_broadcast=s.did_broadcast,
                    connect_timeout=s.connect_timeout,
                )

        return V()

    async def test_it_takes_in_a_bunch_of_things(self, V):
        assert V.writer.sent == 0
        assert V.writer.clone == V.packet.clone()
        assert V.writer.session == V.session
        assert V.writer.original == V.original
        assert V.writer.receiver == V.receiver
        assert V.writer.transport == V.transport
        assert V.writer.retry_gaps == V.retry_gaps
        assert V.writer.did_broadcast == V.did_broadcast
        assert V.writer.connect_timeout == V.connect_timeout

    async def test_it_sends_when_we_call_it(self, V):
        result = mock.Mock(name="result")

        called = []

        def caller(name, ret=None):
            def call(*args, **kwargs):
                called.append(name)
                return ret

            return call

        modify_sequence = mock.Mock(name="modify_sequence", side_effect=caller("modify_sequence"))
        register = mock.Mock(name="register", side_effect=caller("register", result))
        write = pytest.helpers.AsyncMock(name="write", side_effect=caller("write", b"asdf"))

        mods = {"modify_sequence": modify_sequence, "register": register, "write": write}

        with mock.patch.multiple(V.writer, **mods):
            assert await V.writer() is result

        assert called == ["modify_sequence", "register", "write"]

        modify_sequence.assert_called_once_with()
        register.assert_called_once_with()
        write.assert_called_once_with()

    class TestModifySequence:
        async def test_it_modifies_sequence_after_first_modify_sequence(self, V):
            sequence = mock.Mock(name="sequence")
            seq = mock.Mock(name="seq", return_value=sequence)
            V.session.seq = seq

            original_sequence = mock.Mock(name="original_sequence")
            V.writer.clone.sequence = original_sequence

            V.writer.modify_sequence()
            assert V.writer.clone.sequence is original_sequence
            assert len(seq.mock_calls) == 0

            V.writer.modify_sequence()
            assert V.writer.clone.sequence is sequence
            seq.assert_called_once_with(V.original.serial)

            seq.reset_mock()
            other_sequence = mock.Mock(name="other_sequence")
            seq.return_value = other_sequence
            V.writer.modify_sequence()
            assert V.writer.clone.sequence is other_sequence
            seq.assert_called_once_with(V.original.serial)

    class TestRegister:
        async def test_it_does_not_register_if_the_Result_is_already_done(self, V):
            result = mock.Mock(name="result", spec=["done"])
            result.done.return_value = True
            FakeResult = mock.Mock(name="FakeResult", return_value=result)

            with mock.patch("photons_transport.comms.writer.Result", FakeResult):
                assert V.writer.register() is result

            result.done.assert_called_once_with()
            FakeResult.assert_called_once_with(V.original, V.did_broadcast, V.retry_gaps)
            assert len(V.receiver.register.mock_calls) == 0

        async def test_it_registers_if_the_Result_is_not_already_done(self, V):
            result = mock.Mock(name="result", spec=["done", "add_done_callback"])
            result.done.return_value = False
            FakeResult = mock.Mock(name="FakeResult", return_value=result)

            with mock.patch("photons_transport.comms.writer.Result", FakeResult):
                assert V.writer.register() is result

            result.done.assert_called_once_with()
            FakeResult.assert_called_once_with(V.original, V.did_broadcast, V.retry_gaps)
            V.receiver.register.assert_called_once_with(V.writer.clone, result, V.original)
            result.add_done_callback.assert_called_once_with(hp.silent_reporter)

    class TestWrite:
        async def test_it_spawns_a_transport_and_writes_to_it(self, V):
            bts = mock.Mock(name="bts")
            V.writer.clone.tobytes.return_value = bts

            t = mock.Mock(name="t")

            V.transport.spawn = pytest.helpers.AsyncMock(name="spawn", return_value=t)
            V.transport.write = pytest.helpers.AsyncMock(name="write")

            assert await V.writer.write() is bts

            V.transport.spawn.assert_called_once_with(V.original, timeout=V.connect_timeout)
            V.transport.write.assert_called_once_with(t, bts, V.original)
