# coding: spec

from photons_transport.target.writer import Executor

from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import asynctest

describe AsyncTestCase, "Executor":
    async it "takes in a few things":
        writer = mock.Mock(name='writer')

        original = mock.Mock(name="original")

        clone = mock.Mock(name="clone")
        packet = mock.Mock(name='packet')
        packet.clone.return_value = clone

        conn = mock.Mock(name='conn')
        serial = mock.Mock(name='serial')
        target = mock.Mock(name='target')
        addr = mock.Mock(name='addr')
        expect_zero = mock.Mock(name="expect_zero")

        executor = Executor(writer, original, packet, conn, serial, addr, target, expect_zero)

        self.assertIs(executor.writer, writer)
        self.assertIs(executor.original, original)
        self.assertIs(executor.packet, packet)
        self.assertIs(executor.conn, conn)
        self.assertIs(executor.serial, serial)
        self.assertIs(executor.addr, addr)
        self.assertIs(executor.target, target)
        self.assertIs(executor.clone, clone)
        self.assertIs(executor.expect_zero, expect_zero)

        self.assertEqual(executor.requests, [])

    describe "Usage":
        async before_each:
            self.writer = mock.Mock(name='writer')

            self.clone = mock.Mock(name="clone")
            self.packet = mock.Mock(name='packet')
            self.packet.clone.return_value = self.clone
            self.original = mock.Mock(name="original")

            self.conn = mock.Mock(name='conn')
            self.serial = mock.Mock(name='serial')
            self.target = mock.Mock(name='target')
            self.addr = mock.Mock(name='addr')
            self.expect_zero = mock.Mock(name='expect_zero')

            self.executor = Executor(self.writer, self.original, self.packet, self.conn, self.serial, self.addr, self.target, self.expect_zero)

        describe "requires response":
            async it "says yes if the packet only needs a res":
                self.packet.res_required = True
                self.packet.ack_required = False
                assert self.executor.requires_response

            async it "says yes if the packet only needs an ack":
                self.packet.res_required = False
                self.packet.ack_required = True
                assert self.executor.requires_response

            async it "says yes if the packet needs both ack and res":
                self.packet.res_required = True
                self.packet.ack_required = True
                assert self.executor.requires_response

            async it "says no if the packet needs neither ack or res":
                self.packet.res_required = False
                self.packet.ack_required = False
                assert not self.executor.requires_response

        describe "creating a receiver":
            async it "uses the bridge that was passed in":
                bridge = mock.Mock(name="bridge")
                bridge.create_receiver = asynctest.mock.CoroutineMock(name="create_receiver")
                await self.executor.create_receiver(bridge)
                bridge.create_receiver.assert_called_once_with(self.conn, self.packet, self.addr)

        describe "ensuring connection":
            async it "recreates the conn if it's no longer active":
                bridge = mock.Mock(name="bridge")
                bridge.is_sock_active.return_value = False

                conn2 = mock.Mock(name='conn2')
                self.writer.determine_conn = asynctest.mock.CoroutineMock(name="determine_conn", return_value=conn2)
                self.writer.write = asynctest.mock.CoroutineMock(name="write")
                self.writer.bridge = bridge

                await self.executor.ensure_conn()
                self.assertIs(self.executor.conn, conn2)
                bridge.is_sock_active.assert_called_once_with(self.conn)
                self.writer.determine_conn.assert_called_once_with(self.addr, self.target)

            async it "does nothing if socket is active":
                bridge = mock.Mock(name="bridge")
                bridge.is_sock_active.return_value = True

                conn2 = mock.Mock(name='conn2')
                self.writer.determine_conn = asynctest.mock.CoroutineMock(name="determine_conn", return_value=conn2)
                self.writer.write = asynctest.mock.CoroutineMock(name="write")
                self.writer.bridge = bridge

                await self.executor.ensure_conn()
                self.assertIs(self.executor.conn, self.conn)
                bridge.is_sock_active.assert_called_once_with(self.conn)
                self.assertEqual(len(self.writer.determine_conn.mock_calls), 0)

        describe "calling":
            async it "calls the writer.write when it gets called":
                self.writer.write = asynctest.mock.CoroutineMock(name="write")
                await self.executor()
                self.writer.write.assert_called_once_with(
                      self.serial
                    , self.original, self.clone, self.packet.source
                    , self.conn, self.addr
                    , self.executor.requests
                    , self.expect_zero
                    )
