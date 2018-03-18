# coding: spec

from photons_socket.connection import Sockets

from photons_app.test_helpers import AsyncTestCase
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
import asynctest
import asyncio
import socket
import mock

describe AsyncTestCase, "Sockets":
    async before_each:
        self.stop_fut = asyncio.Future()
        self.data_receiver = mock.Mock(name="data_receiver")
        self.sockets = Sockets(self.stop_fut, self.data_receiver)

    async after_each:
        self.stop_fut.cancel()

    async it "takes in ome stuff":
        sockets = Sockets(self.stop_fut, self.data_receiver)

        assert not sockets.stop_fut.done()
        self.assertIsNot(sockets.stop_fut, self.stop_fut)
        self.stop_fut.cancel()
        assert sockets.stop_fut.done()
        assert sockets.stop_fut.cancelled()

        self.assertIs(sockets.data_receiver, self.data_receiver)

    describe "finish":
        async it "cancels what isn't already cancelled":
            fut1 = asyncio.Future()
            fut2 = asyncio.Future()
            fut3 = asyncio.Future()
            fut4 = asyncio.Future()

            fut1.set_result(mock.Mock(name="conn"))
            fut3.set_exception(Exception('wat'))

            self.sockets.sockets = {"one": fut1, "two": fut2, "three": fut3, "four": fut4}
            self.sockets.finish()

            assert fut2.cancelled()
            assert fut4.cancelled()

        async it "closes connections":
            fut1 = asyncio.Future()
            fut2 = asyncio.Future()
            fut3 = asyncio.Future()
            fut4 = asyncio.Future()

            conn1 = mock.Mock(name="conn1")
            conn2 = mock.Mock(name="conn2")

            fut1.set_result(conn1)
            fut2.cancel()
            fut3.set_result(conn2)
            fut4.set_exception(Exception("astw"))

            self.sockets.sockets = {"one": fut1, "two": fut2, "three": fut3, "four": fut4}
            self.sockets.finish()

            conn1.close.assert_called_once_with()
            conn2.close.assert_called_once_with()

        async it "ignores OSErors from calling close":
            fut1 = asyncio.Future()
            fut2 = asyncio.Future()
            fut3 = asyncio.Future()
            fut4 = asyncio.Future()

            conn1 = mock.Mock(name="conn1")
            conn1.close.side_effect = OSError("yeap")
            conn2 = mock.Mock(name="conn2")

            fut1.set_result(conn1)
            fut2.cancel()
            fut3.set_result(conn2)
            fut4.set_exception(Exception("astw"))

            self.sockets.sockets = {"one": fut1, "two": fut2, "three": fut3, "four": fut4}
            self.sockets.finish()

            conn1.close.assert_called_once_with()
            conn2.close.assert_called_once_with()

    describe "spawn":
        async it "returns the fut if it's not done":
            fut = asyncio.Future()
            self.sockets.sockets["address"] = fut

            _spawn = mock.NonCallableMock(name='_spawn')
            with mock.patch.object(self.sockets, "_spawn", _spawn):
                self.assertIs(self.sockets.spawn(("address", 1)), fut)

        async it "returns the fut if it's done without error":
            fut = asyncio.Future()
            fut.set_result(mock.Mock(name="conn"))
            self.sockets.sockets["address"] = fut

            _spawn = mock.NonCallableMock(name='_spawn')
            with mock.patch.object(self.sockets, "_spawn", _spawn):
                self.assertIs(self.sockets.spawn(("address", 1)), fut)

        async it "spawns a new connection if current future has an exception":
            backoff = mock.Mock(name="backoff")
            timeout = mock.Mock(name="timeout")

            fut = asyncio.Future()
            fut.set_exception(Exception("wat"))
            self.sockets.sockets["address"] = fut

            _spawn = mock.Mock(name='_spawn')
            with mock.patch.object(self.sockets, "_spawn", _spawn):
                made = self.sockets.spawn(("address", 1), backoff=backoff, timeout=timeout)
                self.assertIsNot(made, fut)
                self.assertEqual(self.sockets.sockets["address"], made)

            class IsFut:
                def __eq__(s, thing):
                    print(thing)
                    self.assertIs(type(thing), hp.ChildOfFuture)
                    self.assertIs(thing.original_fut, self.sockets.stop_fut)
                    return True

            _spawn.assert_called_once_with("address", IsFut(), backoff, timeout)

        async it "spawns a new connection if current future is cancelled":
            backoff = mock.Mock(name="backoff")
            timeout = mock.Mock(name="timeout")

            fut = asyncio.Future()
            fut.cancel()
            self.sockets.sockets["address"] = fut

            _spawn = mock.Mock(name='_spawn')
            with mock.patch.object(self.sockets, "_spawn", _spawn):
                made = self.sockets.spawn(("address", 1), backoff=backoff, timeout=timeout)
                self.assertIsNot(made, fut)
                self.assertEqual(self.sockets.sockets["address"], made)

            class IsFut:
                def __eq__(s, thing):
                    print(thing)
                    self.assertIs(type(thing), hp.ChildOfFuture)
                    self.assertIs(thing.original_fut, self.sockets.stop_fut)
                    return True

            _spawn.assert_called_once_with("address", IsFut(), backoff, timeout)

        async it "spawns a new connection if there is no current future":
            backoff = mock.Mock(name="backoff")
            timeout = mock.Mock(name="timeout")

            _spawn = mock.Mock(name='_spawn')
            with mock.patch.object(self.sockets, "_spawn", _spawn):
                made = self.sockets.spawn(("address", 1), backoff=backoff, timeout=timeout)
                self.assertEqual(self.sockets.sockets["address"], made)

            class IsFut:
                def __eq__(s, thing):
                    self.assertIs(type(thing), hp.ChildOfFuture)
                    self.assertIs(thing.original_fut, self.sockets.stop_fut)
                    return True

            _spawn.assert_called_once_with("address", IsFut(), backoff, timeout)

    describe "private _spawn":
        async it "works":
            conn = mock.Mock(name="conn")
            address = mock.Mock(name='address')
            backoff = mock.Mock(name="backoff")
            timeout = 2

            fut = asyncio.Future()

            sock = mock.Mock(name='sock')
            make_socket = mock.Mock(name="make_socket", return_value=sock)

            async def connector(s, a, f, b, t):
                self.assertIs(f, fut)
                fut.set_result(conn)
            connect_socket = asynctest.mock.CoroutineMock(name="connect_socket", side_effect=connector)

            with mock.patch.object(self.sockets, "make_socket", make_socket):
                with mock.patch.object(self.sockets, "connect_socket", connect_socket):
                    self.sockets._spawn(address, fut, backoff, timeout)

            assert not fut.done()
            c = await self.wait_for(fut, timeout=1)
            self.assertIs(c, conn)

            make_socket.assert_called_once_with(address)
            connect_socket.assert_called_once_with(sock, address, fut, backoff, timeout)

    describe "connect_socket":
        async it "works and ignores address and backoff":
            fut = asyncio.Future()
            sock = self.sockets.make_socket(None)
            await self.sockets.connect_socket(sock, None, fut, None, 1)
            result = await self.wait_for(fut, timeout=2)
            assert isinstance(result, asyncio.transports.Transport)

        async it "can be used to communicate":
            received = asyncio.Future()

            def receive(data, *args):
                received.set_result(data)
            self.data_receiver.side_effect = receive

            fut = asyncio.Future()
            sock = self.sockets.make_socket(None)
            await self.sockets.connect_socket(sock, None, fut, None, 1)
            conn = await self.wait_for(fut, timeout=2)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', 0))
                port = s.getsockname()[1]

            class ServerProtocol(asyncio.Protocol):
                def connection_made(sp, transport):
                    self.transport = transport

                def datagram_received(sp, data, addr):
                    self.transport.sendto(data + data, addr)

            remote, _ = await self.loop.create_datagram_endpoint(ServerProtocol, local_addr=("0.0.0.0", port))

            try:
                conn.sendto(b"wat", ("127.0.0.1", port))
                echoed = await self.wait_for(received, timeout=1)
                self.assertEqual(echoed, b"watwat")
            finally:
                remote.close()

    describe "make_socket_protocol":
        async before_each:
            self.address = mock.Mock(name="address")
            self.fut = hp.ChildOfFuture(self.sockets.stop_fut)
            self.sockets.sockets[self.address] = self.fut
            self.exc = Exception("wat")

        async it "passes on exception if connection_lost":
            protocol = self.sockets.make_socket_protocol(self.address, self.fut)()

            assert not self.fut.done()
            assert self.address in self.sockets.sockets

            protocol.connection_lost(self.exc)

            assert self.address not in self.sockets.sockets
            self.assertIs(self.fut.exception(), self.exc)

        async it "cancels the future if we get eof_received":
            protocol = self.sockets.make_socket_protocol(self.address, self.fut)()

            assert not self.fut.done()
            assert self.address in self.sockets.sockets

            protocol.eof_received()

            assert self.address not in self.sockets.sockets
            assert self.fut.cancelled()

        async it "passes on exception if error_received":
            protocol = self.sockets.make_socket_protocol(self.address, self.fut)()

            assert not self.fut.done()
            assert self.address in self.sockets.sockets

            protocol.error_received(self.exc)

            assert self.address not in self.sockets.sockets
            self.assertIs(self.fut.exception(), self.exc)

        async it "puts transport on the fut when connect_made":
            transport = mock.Mock(name="transport", spec=[])
            protocol = self.sockets.make_socket_protocol(self.address, self.fut)()

            assert not self.fut.done()
            assert self.address in self.sockets.sockets

            protocol.connection_made(transport)

            assert self.address in self.sockets.sockets
            self.assertIs(await self.wait_for(self.fut, timeout=1), transport)

        async it "closes the transport if the future is already done":
            transport = mock.Mock(name="transport")
            protocol = self.sockets.make_socket_protocol(self.address, self.fut)()

            self.fut.set_result(True)

            assert self.address in self.sockets.sockets

            protocol.connection_made(transport)

            assert self.address in self.sockets.sockets
            self.assertIs(await self.wait_for(self.fut, timeout=1), True)

            transport.close.assert_called_once_with()

        async it "calls the data_receiver on datagram_received":
            data = mock.Mock(name="data")
            addr = mock.Mock(name="addr")

            protocol = self.sockets.make_socket_protocol(self.address, self.fut)()
            protocol.datagram_received(data, addr)

            self.data_receiver.assert_called_once_with(data, addr, self.address)
