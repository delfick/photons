# coding: spec

from photons_transport.comms.base import Communication, Found
from photons_transport.errors import FailedToFindDevice
from photons_transport.transports.base import Transport
from photons_transport.comms.receiver import Receiver
from photons_transport import RetryOptions

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import FoundNoDevices, TimedOut
from photons_app import helpers as hp

from photons_messages import DeviceMessages, protocol_register, LIFXPacket
from photons_protocol.messages import Messages

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from delfick_project.norms import dictobj, sb, Meta
from contextlib import contextmanager
from unittest import mock
import asynctest
import binascii
import asyncio

describe AsyncTestCase, "Communication":
    async before_each:
        self.final_future = asyncio.Future()
        self.protocol_register = protocol_register

        self.transport_target = mock.Mock(
            name="transport_target",
            final_future=self.final_future,
            protocol_register=self.protocol_register,
            spec=["final_future", "protocol_register"],
        )

        self.communication = Communication(self.transport_target)

    async after_each:
        self.final_future.cancel()
        await self.communication.finish()

    async it "is formattable":

        class Other:
            pass

        other = Other()
        options = {"comms": self.communication, "other": other}

        class Thing(dictobj.Spec):
            other = dictobj.Field(sb.overridden("{other}"), formatted=True)
            comms = dictobj.Field(sb.overridden("{comms}"), formatted=True)

        thing = Thing.FieldSpec(formatter=MergedOptionStringFormatter).normalise(
            Meta(options, []).at("thing"), {}
        )

        self.assertIs(thing.comms, self.communication)
        self.assertEqual(thing.other, str(other))

    async it "takes in a transport_target":
        self.assertIs(self.communication.transport_target, self.transport_target)
        self.assertEqual(self.communication.found, Found())
        self.assertIsInstance(self.communication.receiver, Receiver)

    async it "has a stop fut":
        assert not self.communication.stop_fut.done()
        self.communication.stop_fut.cancel()
        assert not self.final_future.cancelled()

        comm2 = Communication(self.transport_target)
        assert not comm2.stop_fut.done()
        self.final_future.set_result(1)
        assert comm2.stop_fut.cancelled()

    async it "calls setup":
        called = []

        class C(Communication):
            def setup(self):
                for n in ("transport_target", "stop_fut", "receiver", "found"):
                    assert hasattr(self, n)
                called.append("setup")
                self.wat = 2

        c = C(self.transport_target)
        self.assertEqual(c.wat, 2)

        self.assertEqual(called, ["setup"])

    describe "finish":
        async it "can finish":
            t1 = mock.Mock(name="t1")
            t1.close = asynctest.mock.CoroutineMock(name="close")

            t2 = mock.Mock(name="t2")
            t2.close = asynctest.mock.CoroutineMock(name="close")

            t3 = mock.Mock(name="t3")
            t3.close = asynctest.mock.CoroutineMock(name="close")

            found = self.communication.found
            found["d073d5000001"] = {"UDP": t1, "OTH": t2}
            found["d073d5000002"] = {"MEM": t3}
            assert found

            assert not self.communication.stop_fut.done()
            await self.communication.finish()
            assert self.communication.stop_fut.done()
            assert not self.final_future.done()

            assert not found

            t1.close.assert_called_once_with()
            t2.close.assert_called_once_with()
            t3.close.assert_called_once_with()

        async it "can finish even if forget raise errors":
            called = []

            async def forget(serial):
                called.append(serial)
                raise Exception("NOPE")

            found = self.communication.found
            found["d073d5000001"] = {"UDP": mock.Mock(name="UDP"), "OTH": mock.Mock(name="OTH")}
            found["d073d5000002"] = {"MEM": mock.Mock(name="MEM")}

            assert not self.communication.stop_fut.done()

            with mock.patch.object(self.communication, "forget", forget):
                await self.communication.finish()

            assert self.communication.stop_fut.done()
            assert not self.final_future.done()

            self.assertEqual(called, ["d073d5000001", "d073d5000002"])

    describe "source":
        async it "generates a source":
            source = self.communication.source
            assert source > 0 and source < 1 << 32, source

            s2 = self.communication.source
            self.assertEqual(s2, source)

            del self.communication.source
            s3 = self.communication.source
            self.assertNotEqual(s3, source)

            for _ in range(1000):
                del self.communication.source
                s = self.communication.source
                assert s > 0 and s < 1 << 32, s

    describe "seq":
        async it "records where we're at with the target":
            target = mock.Mock(name="target")
            assert not hasattr(self.communication, "_seq")
            self.assertEqual(self.communication.seq(target), 1)
            self.assertEqual(self.communication._seq, {target: 1})

            self.assertEqual(self.communication.seq(target), 2)
            self.assertEqual(self.communication._seq, {target: 2})

            target2 = mock.Mock(name="target2")
            self.assertEqual(self.communication.seq(target2), 1)
            self.assertEqual(self.communication._seq, {target: 2, target2: 1})

            self.assertEqual(self.communication.seq(target), 3)
            self.assertEqual(self.communication._seq, {target: 3, target2: 1})

        async it "wraps around at 255":
            target = mock.Mock(name="target2")
            self.assertEqual(self.communication.seq(target), 1)
            self.assertEqual(self.communication._seq, {target: 1})

            self.communication._seq[target] = 254
            self.assertEqual(self.communication.seq(target), 255)
            self.assertEqual(self.communication._seq, {target: 255})

            self.assertEqual(self.communication.seq(target), 0)
            self.assertEqual(self.communication._seq, {target: 0})

    describe "forget":
        async it "does nothing if serial not in found":
            serial = "d073d5000001"
            assert serial not in self.communication.found
            await self.communication.forget(serial)

        async it "closes services and removes from found":
            t1 = mock.Mock(name="t1")
            t1.close = asynctest.mock.CoroutineMock(name="close", side_effect=Exception("NOPE"))

            t2 = mock.Mock(name="t2")
            t2.close = asynctest.mock.CoroutineMock(name="close")

            serial = "d073d5000001"

            found = self.communication.found
            found[serial] = {"UDP": t1, "OTH": t2}

            await self.communication.forget(serial)

            t1.close.assert_called_once_with()
            t2.close.assert_called_once_with()

            assert serial not in found

    describe "add_service":
        async it "can make a new transport when serial not already in found":
            assert not self.communication.found

            serial = "d073d5000001"
            service = mock.Mock(name="service")
            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = asynctest.mock.CoroutineMock(name="make_transport", return_value=t)

            with mock.patch.object(self.communication, "make_transport", make_transport):
                await self.communication.add_service(serial, service, a=a)

            self.assertEqual(self.communication.found[serial], {service: t})
            make_transport.assert_called_once_with(serial, service, {"a": a})

        async it "can make a new transport when serial already in found":
            serial = "d073d5000001"
            othertransport = mock.Mock(name="othertransport")
            self.communication.found[serial] = {"OTH": othertransport}

            service = mock.Mock(name="service")
            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = asynctest.mock.CoroutineMock(name="make_transport", return_value=t)

            with mock.patch.object(self.communication, "make_transport", make_transport):
                await self.communication.add_service(serial, service, a=a)

            self.assertEqual(self.communication.found[serial], {"OTH": othertransport, service: t})
            make_transport.assert_called_once_with(serial, service, {"a": a})

        async it "can replace a transport":
            serial = "d073d5000001"
            service = mock.Mock(name="service")
            othertransport = mock.Mock(name="othertransport")
            othertransport.close = asynctest.mock.CoroutineMock(name="close")

            self.communication.found[serial] = {service: othertransport}

            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = asynctest.mock.CoroutineMock(name="make_transport", return_value=t)

            with mock.patch.object(self.communication, "make_transport", make_transport):
                await self.communication.add_service(serial, service, a=a)

            self.assertEqual(self.communication.found[serial], {service: t})
            make_transport.assert_called_once_with(serial, service, {"a": a})
            othertransport.close.assert_called_once_with()

        async it "can replace a transport when closing it fails":
            serial = "d073d5000001"
            service = mock.Mock(name="service")
            othertransport = mock.Mock(name="othertransport")
            othertransport.close = asynctest.mock.CoroutineMock(
                name="close", side_effect=Exception("NOPE")
            )

            self.communication.found[serial] = {service: othertransport}

            a = mock.Mock(name="a")

            t = mock.Mock(name="transport")
            make_transport = asynctest.mock.CoroutineMock(name="make_transport", return_value=t)

            with mock.patch.object(self.communication, "make_transport", make_transport):
                await self.communication.add_service(serial, service, a=a)

            self.assertEqual(self.communication.found[serial], {service: t})
            make_transport.assert_called_once_with(serial, service, {"a": a})
            othertransport.close.assert_called_once_with()

        async it "does not replace if the transport is equal":

            class T:
                def __eq__(self, other):
                    return True

            t1 = T()
            t2 = T()

            serial = "d073d5000001"
            service = mock.Mock(name="service")

            self.communication.found[serial] = {service: t1}

            a = mock.Mock(name="a")

            make_transport = asynctest.mock.CoroutineMock(name="make_transport", return_value=t2)

            with mock.patch.object(self.communication, "make_transport", make_transport):
                await self.communication.add_service(serial, service, a=a)

            self.assertEqual(self.communication.found[serial], {service: t1})
            make_transport.assert_called_once_with(serial, service, {"a": a})

    describe "find_devices":
        async it "uses find_specific_serials":
            a = mock.Mock(name="a")
            broadcast = mock.Mock(name="broadcast")
            ignore_lost = mock.Mock(name="ignore_lost")
            raise_on_none = mock.Mock(name="raise_on_none")

            found = mock.Mock(name="found")
            missing = mock.Mock(name="missing")
            find_specific_serials = asynctest.mock.CoroutineMock(name="find_specific_serials")
            find_specific_serials.return_value = (found, missing)

            with mock.patch.object(
                self.communication, "find_specific_serials", find_specific_serials
            ):
                f = await self.communication.find_devices(
                    ignore_lost=ignore_lost, raise_on_none=raise_on_none, broadcast=broadcast, a=a
                )

            self.assertIs(f, found)
            find_specific_serials.assert_called_once_with(
                None, ignore_lost=ignore_lost, raise_on_none=raise_on_none, broadcast=broadcast, a=a
            )

        async it "has defaults for ignore_lost and raise_on_none":
            a = mock.Mock(name="a")
            broadcast = mock.Mock(name="broadcast")

            found = mock.Mock(name="found")
            missing = mock.Mock(name="missing")
            find_specific_serials = asynctest.mock.CoroutineMock(name="find_specific_serials")
            find_specific_serials.return_value = (found, missing)

            with mock.patch.object(
                self.communication, "find_specific_serials", find_specific_serials
            ):
                f = await self.communication.find_devices(a=a)

            self.assertIs(f, found)
            find_specific_serials.assert_called_once_with(
                None, ignore_lost=False, raise_on_none=False, a=a
            )

    describe "find_specific_serials":
        async before_each:
            self.serial1 = "d073d5000001"
            self.serial2 = "d073d5000002"

            self.target1 = binascii.unhexlify(self.serial1)[:6]
            self.target2 = binascii.unhexlify(self.serial2)[:6]

            self.info1 = mock.Mock(name="info1")
            self.info2 = mock.Mock(name="info2")

        async def assertSpecificSerials(self, serials, found, missing):
            a = mock.Mock(name="a")
            broadcast = mock.Mock(name="broadcast")
            ignore_lost = mock.Mock(name="ignore_lost")
            raise_on_none = mock.Mock(name="raise_on_none")

            f = Found()
            for target, info in found.items():
                f[target] = info

            _find_specific_serials = asynctest.mock.CoroutineMock(name="_find_specific_serials")
            _find_specific_serials.return_value = f

            with mock.patch.object(
                self.communication, "_find_specific_serials", _find_specific_serials
            ):
                f2, m = await self.communication.find_specific_serials(
                    serials,
                    ignore_lost=ignore_lost,
                    raise_on_none=raise_on_none,
                    broadcast=broadcast,
                    a=a,
                )

            self.assertIs(f2, f)
            self.assertEqual(m, missing)
            _find_specific_serials.assert_called_once_with(
                serials,
                ignore_lost=ignore_lost,
                raise_on_none=raise_on_none,
                broadcast=broadcast,
                a=a,
            )

            _find_specific_serials.reset_mock()
            with mock.patch.object(
                self.communication, "_find_specific_serials", _find_specific_serials
            ):
                f3, m = await self.communication.find_specific_serials(
                    serials, broadcast=broadcast, a=a
                )

            self.assertIs(f3, f)
            self.assertEqual(m, missing)
            _find_specific_serials.assert_called_once_with(
                serials, ignore_lost=False, raise_on_none=False, broadcast=broadcast, a=a
            )

        async it "No missing if no found and no serials":
            serials = None
            found = {}
            missing = []
            await self.assertSpecificSerials(serials, found, missing)

        async it "No missing if found has all the serials":
            serials = [self.serial1, self.serial2]

            found = {self.target1: self.info1, self.target2: self.info2}
            missing = []
            await self.assertSpecificSerials(serials, found, missing)

        async it "No missing if more found than serials":
            serials = [self.serial1]

            found = {self.target1: self.info1, self.target2: self.info2}
            missing = []
            await self.assertSpecificSerials(serials, found, missing)

        async it "has missing if less found than serials":
            serials = [self.serial1, self.serial2]

            found = {self.target1: self.info1}
            missing = [self.serial2]
            await self.assertSpecificSerials(serials, found, missing)

        async it "has missing if no found":
            serials = [self.serial1, self.serial2]

            found = {}
            missing = [self.serial1, self.serial2]
            await self.assertSpecificSerials(serials, found, missing)

        async it "no missing if found and no serials":
            serials = None
            found = {self.target1: self.info1, self.target2: self.info2}
            missing = []
            await self.assertSpecificSerials(serials, found, missing)

    describe "private find_specific_serials":
        async it "uses _do_search":
            found = self.communication.found

            s1 = mock.Mock(name="s1")
            s2 = mock.Mock(name="s2")

            services = {"d073d5000001": s1, "d073d5000002": s2}

            async def _do_search(serials, timeout, **kwargs):
                for serial in serials:
                    self.communication.found[serial] = services[serial]
                return set(serials)

            _do_search = asynctest.mock.CoroutineMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(self.communication, "_do_search", _do_search):
                self.assertIs(
                    await self.communication._find_specific_serials(serials, timeout=timeout, a=a),
                    found,
                )

            _do_search.assert_called_once_with(serials, timeout, a=a)

        async it "can remove lost":
            s1 = mock.Mock(name="s1", spec=[])
            s2 = mock.Mock(name="s2", spec=[])
            s3 = mock.Mock(name="s3", spec=["close"])
            s3.close = asynctest.mock.CoroutineMock(name="s3")

            found = self.communication.found
            found["d073d5000003"] = {"UDP": s3}

            services = {"d073d5000001": s1, "d073d5000002": s2}

            async def _do_search(serials, timeout, **kwargs):
                for serial in serials:
                    self.communication.found[serial] = services[serial]
                return set(serials)

            _do_search = asynctest.mock.CoroutineMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(self.communication, "_do_search", _do_search):
                self.assertIs(
                    await self.communication._find_specific_serials(serials, timeout=timeout, a=a),
                    found,
                )

            _do_search.assert_called_once_with(serials, timeout, a=a)

            assert "d073d5000003" not in found
            s3.close.assert_called_once_with()

        async it "does not remove lost if ignore_lost":
            s1 = mock.Mock(name="s1", spec=[])
            s2 = mock.Mock(name="s2", spec=[])
            s3 = mock.Mock(name="s3", spec=[])

            found = self.communication.found
            found["d073d5000003"] = {"UDP": s3}

            services = {"d073d5000001": s1, "d073d5000002": s2}

            async def _do_search(serials, timeout, **kwargs):
                for serial in serials:
                    self.communication.found[serial] = services[serial]
                return set(serials)

            _do_search = asynctest.mock.CoroutineMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(self.communication, "_do_search", _do_search):
                self.assertIs(
                    await self.communication._find_specific_serials(
                        serials, timeout=timeout, ignore_lost=True, a=a
                    ),
                    found,
                )

            _do_search.assert_called_once_with(serials, timeout, a=a)

            assert "d073d5000003" in found

        async it "complains if none are found and raise_on_none":
            s3 = mock.Mock(name="s3", spec=["close"])
            s3.close = asynctest.mock.CoroutineMock(name="close")

            found = self.communication.found
            found["d073d5000003"] = {"UDP": s3}

            async def _do_search(serials, timeout, **kwargs):
                return set()

            _do_search = asynctest.mock.CoroutineMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with self.fuzzyAssertRaisesError(FoundNoDevices):
                with mock.patch.object(self.communication, "_do_search", _do_search):
                    await self.communication._find_specific_serials(
                        None, timeout=timeout, raise_on_none=True, a=a
                    )

            _do_search.assert_called_once_with(None, timeout, a=a)

            assert not found
            s3.close.assert_called_once_with()

        async it "does not complain if none are found and raise_on_none but non None serials":
            s3 = mock.Mock(name="s3", spec=[])
            found = self.communication.found
            found["d073d5000003"] = {"UDP": s3}

            async def _do_search(serials, timeout, **kwargs):
                return set()

            _do_search = asynctest.mock.CoroutineMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(self.communication, "_do_search", _do_search):
                self.assertIs(
                    await self.communication._find_specific_serials(
                        serials, raise_on_none=True, timeout=timeout, a=a
                    ),
                    found,
                )

            _do_search.assert_called_once_with(serials, timeout, a=a)

        async it "does not complain if none are found if not raise_on_none":
            s3 = mock.Mock(name="s3", spec=[])
            found = self.communication.found
            found["d073d5000003"] = {"UDP": s3}

            async def _do_search(serials, timeout, **kwargs):
                return set()

            _do_search = asynctest.mock.CoroutineMock(name="_do_search", side_effect=_do_search)

            a = mock.Mock(name="a")
            serials = ["d073d5000001", "d073d5000002"]
            timeout = mock.Mock(name="timeout")

            with mock.patch.object(self.communication, "_do_search", _do_search):
                self.assertIs(
                    await self.communication._find_specific_serials(
                        None, ignore_lost=True, timeout=timeout, a=a
                    ),
                    found,
                )

            _do_search.assert_called_once_with(None, timeout, a=a)

            assert "d073d5000003" in found

    describe "broadcast":
        async it "is a send with a broadcast transport":
            a = mock.Mock(name="a")
            res = mock.Mock(name="res")
            packet = mock.Mock(name="packet")
            broadcast = mock.Mock(name="broadcast")

            transport = mock.Mock(name="transport")

            send = asynctest.mock.CoroutineMock(name="send", return_value=res)
            make_broadcast_transport = asynctest.mock.CoroutineMock(
                name="make_broadcast_transport", return_value=transport
            )

            mod = {"send": send, "make_broadcast_transport": make_broadcast_transport}
            with mock.patch.multiple(self.communication, **mod):
                self.assertIs(await self.communication.broadcast(packet, broadcast, a=a), res)

            make_broadcast_transport.assert_awaited_once_with(broadcast)
            send.assert_awaited_once_with(packet, is_broadcast=True, transport=transport, a=a)

    describe "send":

        @with_timeout
        async it "sends":
            transport_in = mock.Mock(name="transport_in")
            transport_out = mock.Mock(name="transport_out")

            broadcast = mock.Mock(name="broadcast")
            is_broadcast = mock.Mock(name="broadcast")

            limit = mock.Mock(name="limit")
            packet = mock.Mock(name="packet")
            timeout = mock.Mock(name="timeout")
            no_retry = mock.Mock(name="no_retry")
            original = mock.Mock(name="original")
            connect_timeout = mock.Mock(name="connect_timeout")

            _transport_for_send = asynctest.mock.CoroutineMock(name="_transport_for_send")
            _transport_for_send.return_value = (transport_out, is_broadcast)

            retry_options = mock.Mock(name="retry_options")
            retry_options_for = mock.Mock(name="retry_options_for", return_value=retry_options)

            writer = mock.Mock(name="writer")
            FakeWriter = mock.Mock(name="Writer", return_value=writer)

            class Waiter:
                def __init__(self):
                    self.reset()

                def reset(self):
                    self.cancelled = False

                def cancel(self):
                    self.cancelled = True

            waiter = Waiter()
            FakeWaiter = mock.Mock(name="Waiter", return_value=waiter)

            res = mock.Mock(name="res")

            async def ret():
                return res

            get_response_info = {"ret": ret}

            async def _get_response(*args, **kwargs):
                assert not waiter.cancelled
                return await get_response_info["ret"]()

            _get_response = asynctest.mock.CoroutineMock(
                name="_get_response", side_effect=_get_response
            )

            mod = {
                "retry_options_for": retry_options_for,
                "_get_response": _get_response,
                "_transport_for_send": _transport_for_send,
            }
            patch_comms = mock.patch.multiple(self.communication, **mod)
            patch_writer = mock.patch("photons_transport.comms.base.Writer", FakeWriter)
            patch_waiter = mock.patch("photons_transport.comms.base.Waiter", FakeWaiter)

            with patch_comms, patch_writer, patch_waiter:
                kwargs = {
                    "timeout": timeout,
                    "limit": limit,
                    "no_retry": no_retry,
                    "transport": transport_in,
                    "broadcast": broadcast,
                    "connect_timeout": connect_timeout,
                }
                self.assertIs(await self.communication.send(original, packet, **kwargs), res)

                _transport_for_send.assert_called_once_with(
                    transport_in, packet, original, broadcast, connect_timeout
                )
                retry_options_for.assert_called_once_with(original, transport_out)
                FakeWriter.assert_called_once_with(
                    self.communication,
                    transport_out,
                    self.communication.receiver,
                    original,
                    packet,
                    retry_options,
                    did_broadcast=is_broadcast,
                    connect_timeout=connect_timeout,
                )
                FakeWaiter.assert_called_once_with(
                    self.communication.stop_fut, writer, retry_options, no_retry=no_retry
                )
                _get_response.assert_awaited_once_with(packet, timeout, waiter, limit=limit)
                assert waiter.cancelled

                # Make sure waiter is cancelled if _get_response raises an exception
                waiter.reset()

                async def raise_error():
                    raise ValueError("NOPE")

                get_response_info["ret"] = raise_error
                assert not waiter.cancelled
                with self.fuzzyAssertRaisesError(ValueError, "NOPE"):
                    await self.communication.send(original, packet, **kwargs)
                assert waiter.cancelled

                # Make sure waiter is cancelled if _get_response gets cancelled
                waiter.reset()

                async def cancel():
                    fut = asyncio.Future()
                    fut.cancel()
                    await fut

                get_response_info["ret"] = cancel
                assert not waiter.cancelled
                with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                    await self.communication.send(original, packet, **kwargs)
                assert waiter.cancelled

        @with_timeout
        async it "works without so much mocks":
            called = []

            class T(Transport):
                async def is_transport_active(s, packet, transport):
                    return True

                async def close_transport(s, transport):
                    pass

                def __eq__(s, other):
                    called.append("__eq__")
                    assert other is None
                    return False

                async def spawn_transport(s, timeout):
                    called.append("spawn_transport")
                    return s

                async def write(s, transport, bts, original_message):
                    called.append("write")

                    pkt = Messages.unpack(bts, protocol_register=protocol_register)

                    res = DeviceMessages.EchoResponse(
                        source=pkt.source, sequence=pkt.sequence, target=pkt.target, echoing=b"pong"
                    )

                    loop = asyncio.get_event_loop()
                    bts = res.pack().tobytes()
                    addr = ("fake://device", 56700)
                    loop.call_soon(s.session.sync_received_data, bts, addr)

            class C(Communication):
                def retry_options_for(s, original, transport_out):
                    called.append("retry_options_for")
                    return RetryOptions()

                async def choose_transport(s, original, services):
                    called.append("choose_transport")
                    return services["SERV"]

                async def make_transport(s, serial, service, kwargs):
                    called.append("make_transport")
                    self.assertEqual(service, "SERV")
                    return T(s)

            comms = C(self.transport_target)
            serial = "d073d5000001"
            await comms.add_service(serial, "SERV")
            self.assertEqual(called, ["make_transport", "__eq__"])

            original = DeviceMessages.EchoRequest(echoing=b"ping")
            packet = original.clone()
            packet.update(source=1, sequence=1, target=serial)

            res = await comms.send(original, packet, timeout=2)
            self.assertEqual(len(res), 1)
            pkt, addr, orig = res[0]
            assert pkt | DeviceMessages.EchoResponse
            self.assertEqual(pkt.echoing[: pkt.echoing.find(b"\x00")], b"pong")

            self.assertEqual(addr, ("fake://device", 56700))
            self.assertIs(orig, original)

            self.assertEqual(
                called,
                [
                    "make_transport",
                    "__eq__",
                    "choose_transport",
                    "spawn_transport",
                    "retry_options_for",
                    "write",
                ],
            )

    describe "private transport_for_send":
        async before_each:
            self.transport = mock.Mock(name="transport")
            self.transport.spawn = asynctest.mock.CoroutineMock(name="spawn")

            self.packet = mock.Mock(name="packet")
            self.original = mock.Mock(name="original")
            self.connect_timeout = mock.Mock(name="connect_timeout")

        @contextmanager
        def maker_mocks(self):
            make_broadcast_transport = asynctest.mock.CoroutineMock(
                name="make_broadcast_transport", return_value=self.transport
            )
            choose_transport = asynctest.mock.CoroutineMock(
                name="choose_transport", return_value=self.transport
            )

            mbt_patch = mock.patch.object(
                self.communication, "make_broadcast_transport", make_broadcast_transport
            )
            ct_patch = mock.patch.object(self.communication, "choose_transport", choose_transport)

            with mbt_patch, ct_patch:
                yield (make_broadcast_transport, choose_transport)

        @with_timeout
        async it "uses make_broadcast_transport if broadcast":
            with self.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await self.communication._transport_for_send(
                    None, self.packet, self.original, True, self.connect_timeout
                )
                self.assertEqual(res, (self.transport, True))

            make_broadcast_transport.assert_called_once_with(True)
            self.assertEqual(len(choose_transport.mock_calls), 0)
            self.transport.spawn.assert_called_once_with(
                self.original, timeout=self.connect_timeout
            )

        @with_timeout
        async it "uses make_broadcast_transport if broadcast is an address":
            broadcast = "192.168.0.255"

            with self.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await self.communication._transport_for_send(
                    None, self.packet, self.original, broadcast, self.connect_timeout
                )
                self.assertEqual(res, (self.transport, True))

            make_broadcast_transport.assert_called_once_with(broadcast)
            self.assertEqual(len(choose_transport.mock_calls), 0)
            self.transport.spawn.assert_called_once_with(
                self.original, timeout=self.connect_timeout
            )

        @with_timeout
        async it "uses make_broadcast_transport if packet target is None":
            self.packet.target = None

            with self.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await self.communication._transport_for_send(
                    None, self.packet, self.original, False, self.connect_timeout
                )
                self.assertEqual(res, (self.transport, True))

            make_broadcast_transport.assert_called_once_with(True)
            self.assertEqual(len(choose_transport.mock_calls), 0)
            self.transport.spawn.assert_called_once_with(
                self.original, timeout=self.connect_timeout
            )

        @with_timeout
        async it "uses choose_transport if not for broadcasting":
            self.packet.target = binascii.unhexlify("d073d5")
            self.packet.serial = "d073d5"

            services = mock.Mock(name="services")
            self.communication.found["d073d5"] = services

            with self.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await self.communication._transport_for_send(
                    None, self.packet, self.original, False, self.connect_timeout
                )
                self.assertEqual(res, (self.transport, False))

            choose_transport.assert_called_once_with(self.original, services)
            self.assertEqual(len(make_broadcast_transport.mock_calls), 0)
            self.transport.spawn.assert_called_once_with(
                self.original, timeout=self.connect_timeout
            )

        @with_timeout
        async it "complains if the serial doesn't exist":
            self.packet.target = binascii.unhexlify("d073d5")
            self.packet.serial = "d073d5"

            with self.fuzzyAssertRaisesError(FailedToFindDevice, serial="d073d5"):
                with self.maker_mocks() as (make_broadcast_transport, choose_transport):
                    await self.communication._transport_for_send(
                        None, self.packet, self.original, False, self.connect_timeout
                    )

            self.assertEqual(len(make_broadcast_transport.mock_calls), 0)
            self.assertEqual(len(choose_transport.mock_calls), 0)
            self.assertEqual(len(self.transport.spawn.mock_calls), 0)

        @with_timeout
        async it "just spawns transport if one is provided":
            with self.maker_mocks() as (make_broadcast_transport, choose_transport):
                res = await self.communication._transport_for_send(
                    self.transport, self.packet, self.original, False, self.connect_timeout
                )
                self.assertEqual(res, (self.transport, False))

            self.assertEqual(len(make_broadcast_transport.mock_calls), 0)
            self.assertEqual(len(choose_transport.mock_calls), 0)
            self.transport.spawn.assert_called_once_with(
                self.original, timeout=self.connect_timeout
            )

    describe "received_data":
        async it "unpacks bytes and sends to the receiver":
            allow_zero = mock.Mock(name="allow_zero")
            addr = mock.Mock(name="addr")

            def recv(pkt, addr, *, allow_zero):
                assert pkt | DeviceMessages.StatePower
                self.assertEqual(pkt.level, 100)

            recv = asynctest.mock.CoroutineMock(name="recv", side_effect=recv)

            with mock.patch.object(self.communication.receiver, "recv", recv):
                pkt = DeviceMessages.StatePower(level=100, source=1, sequence=1, target=None)
                data = pkt.pack().tobytes()
                await self.communication.received_data(data, addr, allow_zero=allow_zero)

            recv.assert_called_once_with(mock.ANY, addr, allow_zero=allow_zero)

        async it "unpacks unknown packets":
            allow_zero = mock.Mock(name="allow_zero")
            addr = mock.Mock(name="addr")

            def recv(pkt, addr, *, allow_zero):
                self.assertIsInstance(pkt, LIFXPacket)
                self.assertEqual(pkt.pkt_type, 9001)
                self.assertEqual(pkt.payload, b"things")

            recv = asynctest.mock.CoroutineMock(name="recv", side_effect=recv)

            with mock.patch.object(self.communication.receiver, "recv", recv):
                pkt = LIFXPacket(
                    payload=b"things", pkt_type=9001, source=1, sequence=1, target=None
                )
                data = pkt.pack().tobytes()
                await self.communication.received_data(data, addr, allow_zero=allow_zero)

            recv.assert_called_once_with(mock.ANY, addr, allow_zero=allow_zero)

        async it "ignores invalid data":
            allow_zero = mock.Mock(name="allow_zero")
            addr = mock.Mock(name="addr")

            recv = asynctest.mock.CoroutineMock(name="recv")

            with mock.patch.object(self.communication.receiver, "recv", recv):
                data = "NOPE"
                await self.communication.received_data(data, addr, allow_zero=allow_zero)

            self.assertEqual(len(recv.mock_calls), 0)

    describe "private get_response":
        async before_each:
            self.serial = "d073d5001337"
            self.packet = mock.Mock(name="packet", serial=self.serial)

        async it "can successfully return results":
            a = mock.Mock(name="a")
            b = mock.Mock(name="b")

            waiter = asyncio.Future()

            t = hp.async_as_background(self.communication._get_response(self.packet, 0.1, waiter))
            asyncio.get_event_loop().call_later(0.05, waiter.set_result, [a, b])

            self.assertEqual(await t, [a, b])
            assert not waiter.cancelled()

        async it "can timeout a task":
            waiter = asyncio.Future()

            t = hp.async_as_background(self.communication._get_response(self.packet, 0.05, waiter))

            with self.fuzzyAssertRaisesError(
                TimedOut, "Waiting for reply to a packet", serial=self.serial
            ):
                await t

            assert waiter.cancelled()

        async it "understands when waiter is cancelled":
            waiter = asyncio.Future()

            t = hp.async_as_background(self.communication._get_response(self.packet, 0.05, waiter))
            asyncio.get_event_loop().call_later(0.01, waiter.cancel)

            with self.fuzzyAssertRaisesError(TimedOut, "Message was cancelled", serial=self.serial):
                await t

            assert waiter.cancelled()

        async it "passes on error from waiter":
            waiter = asyncio.Future()

            t = hp.async_as_background(self.communication._get_response(self.packet, 0.05, waiter))
            asyncio.get_event_loop().call_later(0.01, waiter.set_exception, ValueError("NOPE"))

            with self.fuzzyAssertRaisesError(ValueError, "NOPE"):
                await t
