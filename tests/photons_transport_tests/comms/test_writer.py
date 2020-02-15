# coding: spec

from photons_transport.comms.writer import Writer

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import asynctest

describe AsyncTestCase, "Writer":
    async before_each:
        self.session = mock.Mock(name="session")
        self.transport = mock.Mock(name="transport")
        self.receiver = mock.Mock(name="receiver")
        self.original = mock.Mock(name="original")
        self.packet = mock.Mock(name="packet")
        self.retry_options = mock.Mock(name="retry_options")
        self.did_broadcast = mock.Mock(name="did_broadcast")
        self.connect_timeout = mock.Mock(name="connect_timeout")

        self.writer = Writer(
            self.session,
            self.transport,
            self.receiver,
            self.original,
            self.packet,
            self.retry_options,
            did_broadcast=self.did_broadcast,
            connect_timeout=self.connect_timeout,
        )

    async it "takes in a bunch of things":
        assert self.writer.sent == 0
        assert self.writer.clone == self.packet.clone()
        assert self.writer.session == self.session
        assert self.writer.original == self.original
        assert self.writer.receiver == self.receiver
        assert self.writer.transport == self.transport
        assert self.writer.retry_options == self.retry_options
        assert self.writer.did_broadcast == self.did_broadcast
        assert self.writer.connect_timeout == self.connect_timeout

    @with_timeout
    async it "sends when we call it":
        result = mock.Mock(name="result")

        called = []

        def caller(name, ret=None):
            def call(*args, **kwargs):
                called.append(name)
                return ret

            return call

        modify_sequence = mock.Mock(name="modify_sequence", side_effect=caller("modify_sequence"))
        register = mock.Mock(name="register", side_effect=caller("register", result))
        write = asynctest.mock.CoroutineMock(name="write", side_effect=caller("write", b"asdf"))

        mods = {"modify_sequence": modify_sequence, "register": register, "write": write}

        with mock.patch.multiple(self.writer, **mods):
            assert await self.writer() is result

        assert called == ["modify_sequence", "register", "write"]

        modify_sequence.assert_called_once_with()
        register.assert_called_once_with()
        write.assert_called_once_with()

    describe "modify_sequence":
        async it "modifies sequence after first modify_sequence":
            sequence = mock.Mock(name="sequence")
            seq = mock.Mock(name="seq", return_value=sequence)
            self.session.seq = seq

            original_sequence = mock.Mock(name="original_sequence")
            self.writer.clone.sequence = original_sequence

            self.writer.modify_sequence()
            assert self.writer.clone.sequence is original_sequence
            assert len(seq.mock_calls) == 0

            self.writer.modify_sequence()
            assert self.writer.clone.sequence is sequence
            seq.assert_called_once_with(self.original.serial)

            seq.reset_mock()
            other_sequence = mock.Mock(name="other_sequence")
            seq.return_value = other_sequence
            self.writer.modify_sequence()
            assert self.writer.clone.sequence is other_sequence
            seq.assert_called_once_with(self.original.serial)

    describe "register":
        async it "does not register if the Result is already done":
            result = mock.Mock(name="result", spec=["done"])
            result.done.return_value = True
            FakeResult = mock.Mock(name="FakeResult", return_value=result)

            with mock.patch("photons_transport.comms.writer.Result", FakeResult):
                assert self.writer.register() is result

            result.done.assert_called_once_with()
            FakeResult.assert_called_once_with(
                self.original, self.did_broadcast, self.retry_options
            )
            assert len(self.receiver.register.mock_calls) == 0

        async it "registers if the Result is not already done":
            result = mock.Mock(name="result", spec=["done", "add_done_callback"])
            result.done.return_value = False
            FakeResult = mock.Mock(name="FakeResult", return_value=result)

            with mock.patch("photons_transport.comms.writer.Result", FakeResult):
                assert self.writer.register() is result

            result.done.assert_called_once_with()
            FakeResult.assert_called_once_with(
                self.original, self.did_broadcast, self.retry_options
            )
            self.receiver.register.assert_called_once_with(self.writer.clone, result, self.original)
            result.add_done_callback.assert_called_once_with(hp.silent_reporter)

    describe "write":
        async it "spawns a transport and writes to it":
            bts = mock.Mock(name="bts")
            self.writer.clone.tobytes.return_value = bts

            t = mock.Mock(name="t")

            self.transport.spawn = asynctest.mock.CoroutineMock(name="spawn", return_value=t)
            self.transport.write = asynctest.mock.CoroutineMock(name="write")

            assert await self.writer.write() is bts

            self.transport.spawn.assert_called_once_with(
                self.original, timeout=self.connect_timeout
            )
            self.transport.write.assert_called_once_with(t, bts, self.original)
