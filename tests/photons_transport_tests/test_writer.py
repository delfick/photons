# coding: spec

from photons_transport.target.writer import Writer, NoDesiredService, CouldntMakeConnection

from photons_app.errors import ProgrammerError, PhotonsAppError
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from input_algorithms import spec_base as sb
import asynctest
import binascii
import asyncio
import mock

describe AsyncTestCase, "Writer":
    async before_each:
        self.a = mock.Mock(name="a")
        self.b = mock.Mock(name="b")

        self.conn = mock.Mock(name="conn")
        self.addr = mock.Mock(name="addr")
        self.found = mock.Mock(name="found")
        self.bridge = mock.Mock(name="bridge"
            , spec=["receiver", "write_to_sock", "default_desired_services", "default_broadcast", "found"]
            )
        self.packet = mock.Mock(name="packet")
        self.broadcast = mock.Mock(name="broadcast")
        self.connect_timeout = mock.Mock(name="connect_timeout")
        self.desired_services = mock.Mock(name="desired_services")
        self.multiple_replies = mock.Mock(name="multiple_replies")

    async it "takes in much":
        writer = Writer(self.bridge, self.packet
            , conn=self.conn, addr=self.addr, multiple_replies=self.multiple_replies, broadcast=self.broadcast
            , desired_services=self.desired_services, found=self.found, connect_timeout=self.connect_timeout
            , a=self.a, b=self.b
            )

        self.assertIs(writer.conn, self.conn)
        self.assertIs(writer.addr, self.addr)
        self.assertIs(writer.found, self.found)
        self.assertIs(writer.packet, self.packet)
        self.assertEqual(writer.kwargs, {"a": self.a, "b": self.b})
        self.assertIs(writer.bridge, self.bridge)
        self.assertIs(writer.broadcast, self.broadcast)
        self.assertIs(writer.connect_timeout, self.connect_timeout)
        self.assertIs(writer.desired_services, self.desired_services)
        self.assertIs(writer.multiple_replies, self.multiple_replies)

    async it "defaults much":
        writer = Writer(self.bridge, self.packet)

        self.assertIs(writer.bridge, self.bridge)
        self.assertIs(writer.packet, self.packet)

        self.assertIs(writer.conn, None)
        self.assertIs(writer.addr, None)
        self.assertIs(writer.found, self.bridge.found)
        self.assertEqual(writer.kwargs, {})
        self.assertIs(writer.broadcast, False)
        self.assertIs(writer.connect_timeout, 10)
        self.assertIs(writer.desired_services, self.bridge.default_desired_services)
        self.assertIs(writer.multiple_replies, False)

    async it "complains if we have broadcast but no addr":
        with self.fuzzyAssertRaisesError(ProgrammerError, "If broadcast is specified, so must multiple_replies be True"):
            writer = Writer(self.bridge, self.packet, broadcast=True, multiple_replies=False)

    async it "does not complain if we have broadcast and multiple_replies is not False":
        Writer(self.bridge, self.packet, broadcast=True, multiple_replies=True)
        assert True, "no exception was raised"

    describe "Usage":
        async before_each:
            self.expect_zero = mock.Mock(name="expect_zero")
            self.writer = Writer(self.bridge, self.packet
                , conn=self.conn, addr=self.addr, multiple_replies=self.multiple_replies, broadcast=self.broadcast
                , desired_services=self.desired_services, found=self.found, connect_timeout=self.connect_timeout
                , a=self.a, b=self.b
                , expect_zero = self.expect_zero
                )

        describe "make":
            async it "prepares an executor and creates a receiver if we need to":
                executor = mock.Mock(name="executor", spec=["requires_response", "create_receiver"])
                executor.requires_response = True
                executor.create_receiver = asynctest.mock.CoroutineMock(name="create_receiver")

                prepare = asynctest.mock.CoroutineMock(name="prepare", return_value=executor)

                with mock.patch.object(self.writer, "prepare", prepare):
                    self.assertIs(await self.writer.make(), executor)

                executor.create_receiver.assert_called_once_with(self.bridge)

            async it "does not create a receiver if it's not needed":
                executor = mock.Mock(name="executor", spec=["requires_response", "create_receiver"])
                executor.requires_response = False
                executor.create_receiver = asynctest.mock.CoroutineMock(name="create_receiver")

                prepare = asynctest.mock.CoroutineMock(name="prepare", return_value=executor)

                with mock.patch.object(self.writer, "prepare", prepare):
                    self.assertIs(await self.writer.make(), executor)

                self.assertEqual(executor.create_receiver.mock_calls, [])

        describe "prepare":
            async it "normalises the target, creates an addr, creates a conn and creates an executor":
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
                    with mock.patch("photons_transport.target.writer.Executor", FakeExecutor):
                        self.assertIs(await self.writer.prepare(), executor)

                normalise_target.assert_called_once_with(self.packet)
                determine_addr.assert_called_once_with(target, serial)
                determine_conn.assert_called_once_with(addr, target)
                FakeExecutor.assert_called_once_with(self.writer, self.packet, conn, serial, addr, target, self.expect_zero)

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
                self.target = mock.Mock(name="target")
                self.serial = mock.Mock(name="serial")
                self.service = mock.Mock(name="service")

                self.ip = mock.Mock(name="ip")
                self.port = mock.Mock(name="port")
                self.addr = [self.ip, self.port]

            async it "uses default broadcast if broadcast is True":
                self.writer.broadcast = True

                default_broadcast = mock.Mock(name="default_broadcast")
                self.bridge.default_broadcast = default_broadcast

                self.assertEqual(await self.writer.determine_addr(self.target, self.serial), (default_broadcast, 56700))

            async it "uses broadcast if truthy but not True":
                broadcast = mock.Mock(name="broadcast")
                self.writer.broadcast = broadcast

                self.assertEqual(await self.writer.determine_addr(self.target, self.serial), (broadcast, 56700))

            async it "gets services from found if target is in it":
                self.writer.broadcast = sb.NotSpecified
                services = mock.Mock(name="services")
                self.writer.found = {self.target: (services, mock.ANY)}

                match_address = mock.Mock(name="match_address", return_value=(self.service, self.addr))
                with mock.patch.object(self.writer, "match_address", match_address):
                    self.assertIs(await self.writer.determine_addr(self.target, self.serial), self.addr)

                match_address.assert_called_once_with(self.serial, services)

            async it "gets services from asking the bridge if not in found":
                self.writer.broadcast = sb.NotSpecified
                self.writer.found = {}

                services = mock.Mock(name="services")
                find = asynctest.mock.CoroutineMock(name="find", return_value=(services, mock.ANY))
                self.bridge.find = find

                match_address = mock.Mock(name="match_address", return_value=(self.service, self.addr))
                with mock.patch.object(self.writer, "match_address", match_address):
                    self.assertIs(await self.writer.determine_addr(self.target, self.serial), self.addr)

                match_address.assert_called_once_with(self.serial, services)

            async it "complains if we have no addr":
                self.writer.broadcast = sb.NotSpecified

                services = mock.Mock(name="services")
                self.writer.found = {self.target: (services, mock.ANY)}

                match_address = mock.Mock(name="match_address", return_value=(self.service, None))
                with mock.patch.object(self.writer, "match_address", match_address):
                    with self.fuzzyAssertRaisesError(NoDesiredService, wanted=self.desired_services, serial=self.serial, available=self.service):
                        await self.writer.determine_addr(self.target, self.serial)

            async it "fills in the ip to the default broadcast if it's gotten as notspecified":
                self.writer.broadcast = sb.NotSpecified

                services = mock.Mock(name="services")
                self.writer.found = {self.target: (services, mock.ANY)}

                match_address = mock.Mock(name="match_address", return_value=(self.service, (sb.NotSpecified, self.port)))
                with mock.patch.object(self.writer, "match_address", match_address):
                    self.assertEqual(await self.writer.determine_addr(self.target, self.serial), (self.bridge.default_broadcast, self.port))

        describe "determining conn":
            async before_each:
                self.timeout = mock.Mock(name="timeout")
                self.target = mock.Mock(name="target")
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
                self.clone = mock.Mock(name="clone")
                self.made_futures = []

                self.source = 666
                self.packet.source = self.source

                self.register_ack = mock.Mock(name="register_ack")
                self.register_res = mock.Mock(name="register_res")
                self.receiver = mock.Mock(name="receiver"
                    , register_ack = self.register_ack
                    , register_res = self.register_res
                    )
                self.bridge.receiver = self.receiver

                self.display_written = mock.Mock(name="display_written")
                self.writer.display_written = self.display_written

            async it "creates futures, writes to the sock and returns our futures":
                called = []
                def caller(num, ret=None):
                    def call(*args, **kwargs):
                        called.append(num)
                        return ret
                    return call

                self.register_ack.side_effect = caller(1)
                self.register_res.side_effect = caller(2)

                bts = mock.Mock(name="bts")
                self.clone.tobytes.side_effect = caller(3, bts)

                self.bridge.write_to_sock.side_effect = caller(4)
                self.display_written.side_effect = caller(5)

                assert isinstance(self.clone.source,  mock.Mock)
                af, rf = await self.writer.write(self.serial, self.packet, self.clone, self.conn, self.addr, self.made_futures, False)
                self.assertEqual(self.clone.source, 666)
                self.assertEqual(self.made_futures, [af, rf])

                self.register_ack.assert_called_once_with(self.clone, af, self.broadcast)
                self.register_res.assert_called_once_with(self.clone, rf, self.multiple_replies, False)
                self.clone.tobytes.assert_called_once_with(self.serial)
                self.bridge.write_to_sock.assert_called_once_with(self.conn, self.addr, self.clone, bts)
                self.display_written.assert_called_once_with(bts, self.serial)

                self.assertEqual(called, [1, 2, 3, 4, 5])
                assert not af.done()
                assert not rf.done()

            async it "creates futures, writes to the conn if write_to_conn is defined and returns our futures":
                called = []
                def caller(num, ret=None):
                    def call(*args, **kwargs):
                        called.append(num)
                        return ret
                    return call

                self.register_ack.side_effect = caller(1)
                self.register_res.side_effect = caller(2)

                bts = mock.Mock(name="bts")
                self.clone.tobytes.side_effect = caller(3, bts)

                write_to_conn = asynctest.mock.CoroutineMock(name="write_to_conn")
                self.bridge.write_to_conn = write_to_conn
                write_to_conn.side_effect = caller(4)
                self.bridge.write_to_sock.side_effect = caller("shouldnotbecalled")

                self.display_written.side_effect = caller(5)

                assert isinstance(self.clone.source,  mock.Mock)
                af, rf = await self.writer.write(self.serial, self.packet, self.clone, self.conn, self.addr, self.made_futures, True)
                self.assertEqual(self.clone.source, 666)
                self.assertEqual(self.made_futures, [af, rf])

                self.register_ack.assert_called_once_with(self.clone, af, self.broadcast)
                self.register_res.assert_called_once_with(self.clone, rf, self.multiple_replies, True)
                self.clone.tobytes.assert_called_once_with(self.serial)
                self.assertEqual(self.bridge.write_to_sock.mock_calls, [])
                write_to_conn.assert_called_once_with(self.conn, self.addr, self.clone, bts)
                self.display_written.assert_called_once_with(bts, self.serial)

                self.assertEqual(called, [1, 2, 3, 4, 5])
                assert not af.done()
                assert not rf.done()

            async it "sets source on the clone to the source plus number of things in made_futures":
                self.made_futures.extend(range(5))

                assert isinstance(self.clone.source,  mock.Mock)
                af, rf = await self.writer.write(self.serial, self.packet, self.clone, self.conn, self.addr, self.made_futures)
                self.assertEqual(self.clone.source, 666 + 5)
                assert not af.done()
                assert not rf.done()

            async it "doesn't register ack if doesn't need to":
                called = []
                def caller(num, ret=None):
                    def call(*args, **kwargs):
                        called.append(num)
                        return ret
                    return call

                self.register_ack.side_effect = caller(1)
                self.register_res.side_effect = caller(2)

                bts = mock.Mock(name="bts")
                self.clone.tobytes.side_effect = caller(3, bts)

                self.bridge.write_to_sock.side_effect = caller(4)
                self.display_written.side_effect = caller(5)

                assert isinstance(self.clone.source,  mock.Mock)
                self.packet.ack_required = False
                af, rf = await self.writer.write(self.serial, self.packet, self.clone, self.conn, self.addr, self.made_futures, True)
                self.assertEqual(self.clone.source, 666)
                self.assertEqual(self.made_futures, [af, rf])

                self.assertEqual(self.register_ack.mock_calls, [])
                self.register_res.assert_called_once_with(self.clone, rf, self.multiple_replies, True)
                self.clone.tobytes.assert_called_once_with(self.serial)
                self.bridge.write_to_sock.assert_called_once_with(self.conn, self.addr, self.clone, bts)
                self.display_written.assert_called_once_with(bts, self.serial)

                self.assertEqual(called, [2, 3, 4, 5])
                self.assertEqual(af.result(), False)
                assert not rf.done()

            async it "doesn't register res if it doesn't need to":
                called = []
                def caller(num, ret=None):
                    def call(*args, **kwargs):
                        called.append(num)
                        return ret
                    return call

                self.register_ack.side_effect = caller(1)
                self.register_res.side_effect = caller(2)

                bts = mock.Mock(name="bts")
                self.clone.tobytes.side_effect = caller(3, bts)

                self.bridge.write_to_sock.side_effect = caller(4)
                self.display_written.side_effect = caller(5)

                assert isinstance(self.clone.source,  mock.Mock)
                self.packet.res_required = False
                af, rf = await self.writer.write(self.serial, self.packet, self.clone, self.conn, self.addr, self.made_futures)
                self.assertEqual(self.clone.source, 666)
                self.assertEqual(self.made_futures, [af, rf])

                self.register_ack.assert_called_once_with(self.clone, af, self.broadcast)
                self.assertEqual(self.register_res.mock_calls, [])
                self.clone.tobytes.assert_called_once_with(self.serial)
                self.bridge.write_to_sock.assert_called_once_with(self.conn, self.addr, self.clone, bts)
                self.display_written.assert_called_once_with(bts, self.serial)

                self.assertEqual(called, [1, 3, 4, 5])
                assert not af.done()
                self.assertEqual(rf.result(), [])

            async it "doesn't register anything if it doesn't need to":
                called = []
                def caller(num, ret=None):
                    def call(*args, **kwargs):
                        called.append(num)
                        return ret
                    return call

                self.register_ack.side_effect = caller(1)
                self.register_res.side_effect = caller(2)

                bts = mock.Mock(name="bts")
                self.clone.tobytes.side_effect = caller(3, bts)

                self.bridge.write_to_sock.side_effect = caller(4)
                self.display_written.side_effect = caller(5)

                assert isinstance(self.clone.source,  mock.Mock)
                self.packet.ack_required = False
                self.packet.res_required = False
                af, rf = await self.writer.write(self.serial, self.packet, self.clone, self.conn, self.addr, self.made_futures)
                self.assertEqual(self.clone.source, 666)
                self.assertEqual(self.made_futures, [af, rf])

                self.assertEqual(self.register_ack.mock_calls, [])
                self.assertEqual(self.register_res.mock_calls, [])
                self.clone.tobytes.assert_called_once_with(self.serial)
                self.bridge.write_to_sock.assert_called_once_with(self.conn, self.addr, self.clone, bts)
                self.display_written.assert_called_once_with(bts, self.serial)

                self.assertEqual(called, [3, 4, 5])
                self.assertEqual(af.result(), False)
                self.assertEqual(rf.result(), [])
