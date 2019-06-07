# coding: spec

from photons_transport.base.writer import Writer, NoDesiredService, CouldntMakeConnection

from photons_app.errors import ProgrammerError, PhotonsAppError
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from input_algorithms import spec_base as sb
from unittest import mock
import asynctest
import binascii
import asyncio

describe AsyncTestCase, "Writer":
    async before_each:
        self.a = mock.Mock(name="a")
        self.b = mock.Mock(name="b")

        self.conn = mock.Mock(name="conn")
        self.addr = mock.Mock(name="addr")
        self.found = mock.Mock(name="found")

        self.default_broadcast = "192.168.0.255"
        self.target = mock.Mock(name="target", default_broadcast=self.default_broadcast)
        self.bridge = mock.Mock(name="bridge"
            , spec=["receiver", "write_to_sock", "default_desired_services", "found", "transport_target", "seq"]
            , transport_target = self.target
            )

        self.packet = mock.Mock(name="packet")
        self.original = mock.Mock(name="original")
        self.broadcast = mock.Mock(name="broadcast")
        self.retry_options = mock.Mock(name="retry_options", spec=[])
        self.connect_timeout = mock.Mock(name="connect_timeout")
        self.desired_services = mock.Mock(name="desired_services")

    async it "takes in much":
        writer = Writer(self.bridge, self.original, self.packet, self.retry_options
            , conn=self.conn, addr=self.addr, broadcast=self.broadcast
            , desired_services=self.desired_services, found=self.found, connect_timeout=self.connect_timeout
            , a=self.a, b=self.b
            )

        self.assertIs(writer.conn, self.conn)
        self.assertIs(writer.addr, self.addr)
        self.assertIs(writer.found, self.found)
        self.assertIs(writer.packet, self.packet)
        self.assertIs(writer.original, self.original)
        self.assertEqual(writer.kwargs, {"a": self.a, "b": self.b})
        self.assertIs(writer.bridge, self.bridge)
        self.assertIs(writer.broadcast, self.broadcast)
        self.assertIs(writer.connect_timeout, self.connect_timeout)
        self.assertIs(writer.desired_services, self.desired_services)

    async it "defaults much":
        writer = Writer(self.bridge, self.original, self.packet, self.retry_options)

        self.assertIs(writer.bridge, self.bridge)
        self.assertIs(writer.packet, self.packet)
        self.assertIs(writer.original, self.original)
        self.assertIs(writer.retry_options, self.retry_options)

        self.assertIs(writer.conn, None)
        self.assertIs(writer.addr, None)
        self.assertIs(writer.found, self.bridge.found)
        self.assertEqual(writer.kwargs, {})
        self.assertIs(writer.broadcast, False)
        self.assertIs(writer.connect_timeout, 10)
        self.assertIs(writer.desired_services, self.bridge.default_desired_services)

    describe "Usage":
        async before_each:
            self.expect_zero = mock.Mock(name="expect_zero")
            self.writer = Writer(self.bridge, self.original, self.packet, self.retry_options
                , conn=self.conn, addr=self.addr, broadcast=self.broadcast
                , desired_services=self.desired_services, found=self.found, connect_timeout=self.connect_timeout
                , a=self.a, b=self.b
                , expect_zero = self.expect_zero
                )

        describe "make":
            async it "prepares an executor and creates a receiver if we need to":
                services = mock.Mock(name="services")
                executor = mock.Mock(name="executor", spec=["requires_response", "create_receiver"])
                executor.requires_response = True
                executor.create_receiver = asynctest.mock.CoroutineMock(name="create_receiver")

                prepare = asynctest.mock.CoroutineMock(name="prepare", return_value=executor)

                with mock.patch.object(self.writer, "prepare", prepare):
                    self.assertIs(await self.writer.make(services), executor)

                prepare.assert_called_once_with(services)
                executor.create_receiver.assert_called_once_with(self.bridge)

            async it "does not create a receiver if it's not needed":
                services = mock.Mock(name="services")
                executor = mock.Mock(name="executor", spec=["requires_response", "create_receiver"])
                executor.requires_response = False
                executor.create_receiver = asynctest.mock.CoroutineMock(name="create_receiver")

                prepare = asynctest.mock.CoroutineMock(name="prepare", return_value=executor)

                with mock.patch.object(self.writer, "prepare", prepare):
                    self.assertIs(await self.writer.make(services), executor)

                prepare.assert_called_once_with(services)
                self.assertEqual(executor.create_receiver.mock_calls, [])

        describe "prepare":
            async it "normalises the target, creates an addr, creates a conn and creates an executor":
                services = mock.Mock(name="services")
                target = mock.Mock(name="target")
                serial = mock.Mock(name="serial")
                normalise_target = mock.Mock(name="normalise_target", return_value=(target, serial))

                addr = mock.Mock(name="addr")
                determine_addr = asynctest.mock.CoroutineMock(name="determine_addr", return_value=addr)

                conn = mock.Mock(name="conn")
                determine_conn = asynctest.mock.CoroutineMock(name="determine_conn", return_value=conn)

                executor = mock.Mock(name="executor")
                FakeExecutor = mock.Mock(name="Executor", return_value=executor)

                with mock.patch.multiple(self.writer
                    , normalise_target = normalise_target
                    , determine_addr = determine_addr
                    , determine_conn = determine_conn
                    ):
                    with mock.patch("photons_transport.base.writer.Executor", FakeExecutor):
                        self.assertIs(await self.writer.prepare(services), executor)

                normalise_target.assert_called_once_with(self.packet)
                determine_addr.assert_called_once_with(serial, services)
                determine_conn.assert_called_once_with(addr, target)
                FakeExecutor.assert_called_once_with(self.writer, self.original, self.packet, conn, serial, addr, target, self.expect_zero)

        describe "normalise_target":
            async it "gets serial from hexlifying target if target is bytes":
                self.packet.target = binascii.unhexlify("d073d50000010000")
                gtarget, gserial = self.writer.normalise_target(self.packet)

                self.assertEqual(gtarget, binascii.unhexlify("d073d5000001"))
                self.assertEqual(gserial, "d073d5000001")

            async it "gets target from unhexlifying target if target is str":
                self.packet.target = "d073d5000001"
                gtarget, gserial = self.writer.normalise_target(self.packet)

                self.assertEqual(gtarget, binascii.unhexlify("d073d5000001"))
                self.assertEqual(gserial, "d073d5000001")

        describe "determining addr":
            async before_each:
                self.serial = mock.Mock(name="serial")
                self.service = mock.Mock(name="service")

                self.ip = mock.Mock(name="ip")
                self.port = mock.Mock(name="port")
                self.addr = [self.ip, self.port]

            async it "uses default broadcast if broadcast is True":
                self.writer.broadcast = True
                self.assertEqual(await self.writer.determine_addr(self.target, self.serial), (self.default_broadcast, 56700))

            async it "uses broadcast if truthy but not True":
                broadcast = mock.Mock(name="broadcast")
                self.writer.broadcast = broadcast

                self.assertEqual(await self.writer.determine_addr(self.target, self.serial), (broadcast, 56700))

            async it "uses passed in services in match_address":
                self.writer.broadcast = sb.NotSpecified
                services = mock.Mock(name="services")
                self.writer.found = {self.target: (services, mock.ANY)}

                match_address = mock.Mock(name="match_address", return_value=(self.service, self.addr))
                with mock.patch.object(self.writer, "match_address", match_address):
                    self.assertIs(await self.writer.determine_addr(self.serial, services), self.addr)

                match_address.assert_called_once_with(self.serial, services)

            async it "complains if we have no addr":
                self.writer.broadcast = sb.NotSpecified

                services = mock.Mock(name="services")
                self.writer.found = {self.target: (services, mock.ANY)}

                match_address = mock.Mock(name="match_address", return_value=(self.service, None))
                with mock.patch.object(self.writer, "match_address", match_address):
                    with self.fuzzyAssertRaisesError(NoDesiredService, wanted=self.desired_services, serial=self.serial, available=self.service):
                        await self.writer.determine_addr(self.serial, services)

            async it "fills in the ip to the default broadcast if it's gotten as notspecified":
                self.writer.broadcast = sb.NotSpecified

                services = mock.Mock(name="services")
                self.writer.found = {self.target: (services, mock.ANY)}

                match_address = mock.Mock(name="match_address", return_value=(self.service, (sb.NotSpecified, self.port)))
                with mock.patch.object(self.writer, "match_address", match_address):
                    self.assertEqual(await self.writer.determine_addr(self.serial, services), (self.default_broadcast, self.port))

        describe "determining conn":
            async before_each:
                self.timeout = mock.Mock(name="timeout")
                self.addr = mock.Mock(name="addr")

            async it "returns the conn as is if it's not None":
                self.assertIs(self.writer.conn, self.conn)
                self.assertIs(await self.writer.determine_conn(self.addr, self.target), self.conn)

            async it "asks the bridge to spawn a conn if conn is None":
                self.writer.conn = None
                conn = mock.Mock(name="conn")
                spawn_conn = asynctest.mock.CoroutineMock(name="spawn_conn", return_value=conn)
                self.bridge.spawn_conn = spawn_conn
                self.assertIs(await self.writer.determine_conn(self.addr, self.target), conn)

                spawn_conn.assert_called_once_with(self.addr, target=self.target, timeout=self.connect_timeout)

            async it "complains if spawning a connection still returns None":
                self.writer.conn = None
                spawn_conn = asynctest.mock.CoroutineMock(name="spawn_conn", return_value=None)
                self.bridge.spawn_conn = spawn_conn

                with self.fuzzyAssertRaisesError(PhotonsAppError, "Failed to spawn a connection!", bridge=repr(self.bridge), addr=self.addr):
                    await self.writer.determine_conn(self.addr, self.target)

        describe "matching the address":
            async before_each:
                self.s1 = mock.Mock(name='s1')
                self.s2 = mock.Mock(name='s2')
                self.s3 = mock.Mock(name='s3')

                self.a1 = mock.Mock(name='a1')
                self.a2 = mock.Mock(name='a2')
                self.a3 = mock.Mock(name='a3')

                self.serial = mock.Mock(name="serial")

            async it "just chooses the first address if we have no desired_services":
                self.writer.desired_services = None
                services = [(self.s1, self.a1), (self.s2, self.a2)]

                s, a = self.writer.match_address(self.serial, services)
                self.assertEqual(s, [self.s1, self.s2])
                self.assertIs(a, self.a1)

            async it "just returns None if no desired_services or services":
                self.writer.desired_services = None
                services = []

                s, a = self.writer.match_address(self.serial, services)
                self.assertEqual(s, [])
                self.assertIs(a, None)

            async it "just returns None if desired_services but no services":
                self.writer.desired_services = [self.s1, self.s2]
                services = []

                s, a = self.writer.match_address(self.serial, services)
                self.assertEqual(s, [])
                self.assertIs(a, None)

            async it "returns the first address that has a matching desired_service":
                self.writer.desired_services = [self.s2]
                services = [(self.s1, self.a1), (self.s2, self.a2), (self.s3, self.a2)]

                s, a = self.writer.match_address(self.serial, services)
                self.assertEqual(s, [self.s2, self.s3])
                self.assertIs(a, self.a2)

            async it "returns nothing if no matching service":
                self.writer.desired_services = [self.s2]
                services = [(self.s1, self.a1), (self.s3, self.a2)]

                s, a = self.writer.match_address(self.serial, services)
                self.assertEqual(s, [self.s1, self.s3])
                self.assertIs(a, None)

        describe "write":
            async before_each:
                self.serial = mock.Mock(name="serial")
                self.source = 666

                self.clone = mock.Mock(name="clone", serial=self.serial, source=self.source)
                self.bts = mock.Mock(name="bts")
                self.clone.tobytes.return_value = self.bts
                self.requests = []


                self.register = mock.Mock(name="register")
                self.receiver = mock.Mock(name="receiver", register=self.register)

                self.bridge.receiver = self.receiver

                self.display_written = mock.Mock(name="display_written")
                self.writer.display_written = self.display_written

            async it "registers with the receiver if the result is not already done before sending":
                result = mock.Mock(name="result", spec=["done", "add_done_callback"])
                result.done.return_value = False
                FakeResult = mock.Mock(name="Result", return_value=result)

                requests = []

                with mock.patch("photons_transport.base.writer.Result", FakeResult):
                    r = await self.wait_for(self.writer.write(self.serial, self.original, self.clone, self.source
                        , self.conn, self.addr
                        , requests = requests
                        , expect_zero = self.expect_zero
                        ))

                    self.assertIs(r, result)

                FakeResult.assert_called_once_with(self.original, self.broadcast, self.retry_options)
                self.bridge.receiver.register.assert_called_once_with(self.clone, result, self.expect_zero)
                self.assertEqual(requests, [result])
                self.assertEqual(self.clone.source, self.source)

                self.bridge.write_to_sock.assert_called_once_with(self.conn, self.addr, self.clone, self.bts)
                self.display_written.assert_called_once_with(self.bts, self.serial)

            async it "does not register with the receiver if the result is already done before sending":
                result = mock.Mock(name="result", spec=["done", "add_done_callback"])
                result.done.return_value = True
                FakeResult = mock.Mock(name="Result", return_value=result)

                requests = []

                with mock.patch("photons_transport.base.writer.Result", FakeResult):
                    r = await self.wait_for(self.writer.write(self.serial, self.original, self.clone, self.source
                        , self.conn, self.addr
                        , requests = requests
                        , expect_zero = self.expect_zero
                        ))

                    self.assertIs(r, result)

                FakeResult.assert_called_once_with(self.original, self.broadcast, self.retry_options)
                self.assertEqual(len(self.bridge.receiver.register.mock_calls), 0)
                self.assertEqual(requests, [])
                self.assertEqual(self.clone.source, self.source)

                self.bridge.write_to_sock.assert_called_once_with(self.conn, self.addr, self.clone, self.bts)
                self.display_written.assert_called_once_with(self.bts, self.serial)

            async it "changes sequence for retries":
                result = mock.Mock(name="result", spec=["done", "add_done_callback"])
                result.done.return_value = False
                FakeResult = mock.Mock(name="Result", return_value=result)

                called = []

                newseq = mock.Mock(name="newseq")
                oldseq = mock.Mock(name="oldseq")
                self.clone.sequence = oldseq

                def seq(serial):
                    self.assertEqual(serial, self.serial)
                    return newseq
                self.bridge.seq.side_effect = seq

                def register(cl, *args):
                    called.append(("register", cl.source, cl.sequence))
                self.bridge.receiver.register.side_effect = register

                with mock.patch("photons_transport.base.writer.Result", FakeResult):
                    await self.wait_for(self.writer.write(self.serial, self.original, self.clone, self.source
                        , self.conn, self.addr
                        , requests = []
                        , expect_zero = self.expect_zero
                        ))
                    await self.wait_for(self.writer.write(self.serial, self.original, self.clone, self.source
                        , self.conn, self.addr
                        , requests = [1]
                        , expect_zero = self.expect_zero
                        ))

                self.bridge.seq.assert_called_once_with(self.serial)
                self.assertEqual(called
                    , [ ("register", self.source, oldseq)
                      , ("register", self.source, newseq)
                      ]
                    )

            async it "uses write_to_conn if that's available":
                result = mock.Mock(name="result", spec=["done", "add_done_callback"])
                result.done.return_value = False
                FakeResult = mock.Mock(name="Result", return_value=result)

                requests = []

                self.bridge.write_to_conn = asynctest.mock.CoroutineMock(name="write_to_conn")

                with mock.patch("photons_transport.base.writer.Result", FakeResult):
                    await self.wait_for(self.writer.write(self.serial, self.original, self.clone, self.source
                        , self.conn, self.addr
                        , requests = requests
                        , expect_zero = self.expect_zero
                        ))

                self.assertEqual(len(self.bridge.write_to_sock.mock_calls), 0)
                self.bridge.write_to_conn.assert_called_once_with(self.conn, self.addr, self.clone, self.bts)
