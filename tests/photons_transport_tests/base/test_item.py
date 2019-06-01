# coding: spec

from photons_transport.base.item import TransportItem
from photons_transport.base.waiter import Waiter
from photons_transport import RetryOptions

from photons_app.errors import PhotonsAppError, TimedOut, BadRunWithResults
from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from input_algorithms import spec_base as sb
from unittest import mock
import asynctest
import binascii
import asyncio

class LargeRetryOptions(RetryOptions):
    timeouts = [(1, 5)]

describe AsyncTestCase, "TransportItem":
    async it "takes in parts":
        part = mock.Mock(name="part")
        part2 = mock.Mock(name="part2")

        item = TransportItem(part)
        self.assertEqual(item.parts, [part])

        item = TransportItem([part, part2])
        self.assertEqual(item.parts, [part, part2])

    describe "Functionality":
        async before_each:
            self.part1 = mock.Mock(name="part1")
            self.part2 = mock.Mock(name="part2")
            self.item = TransportItem([self.part1, self.part2])

        describe "simplify_parts":
            async it "returns originals with packets as they are if they are dynamic, else we simplify them":
                part1_dynamic = mock.Mock(name="part1_dynamic", is_dynamic=True, spec=["is_dynamic"])

                part2_static = mock.Mock(name="part2_static", is_dynamic=False)
                part2_simple = mock.Mock(name="part2_simple")
                part2_static.simplify.return_value = part2_simple

                part3_static = mock.Mock(name="part3_static", is_dynamic=False)
                part3_simple = mock.Mock(name="part3_simple")
                part3_static.simplify.return_value = part3_simple

                part4_dynamic = mock.Mock(name="part4_dynamic", is_dynamic=True, spec=["is_dynamic"])

                simplified = TransportItem([part1_dynamic, part2_static, part3_static, part4_dynamic]).simplify_parts()
                self.assertEqual(simplified
                    , [ (part1_dynamic, part1_dynamic)
                      , (part2_static, part2_simple)
                      , (part3_static, part3_simple)
                      , (part4_dynamic, part4_dynamic)
                      ]
                    )

        describe "making packets":
            async it "duplicates parts for each serial and only clones those already with targets":
                original1 = mock.Mock(name="original1")
                original2 = mock.Mock(name="original2")
                original3 = mock.Mock(name="original3")

                s1 = mock.Mock(name='s1')
                s2 = mock.Mock(name='s2')
                serials = [s1, s2]

                c1 = mock.Mock(name="clone1")
                c2 = mock.Mock(name="clone2")
                p1clones = [c1, c2]

                c3 = mock.Mock(name="clone3")
                c4 = mock.Mock(name="clone4")
                p2clones = [c3, c4]

                def part1clone():
                    return p1clones.pop(0)
                part1 = mock.Mock(name="part1", target=sb.NotSpecified)
                part1.clone.side_effect = part1clone

                def part2clone():
                    return p2clones.pop(0)
                part2 = mock.Mock(name="part2", target=sb.NotSpecified)
                part2.clone.side_effect = part2clone

                c5 = mock.Mock(name="clone5")
                target = mock.Mock(name="target")
                part3 = mock.Mock(name="part3", target=target)
                part3.clone.return_value = c5

                afr = mock.Mock(name="afr")
                source = mock.Mock(name="source")
                afr.source.return_value = source

                seqs = {s1: 0, s2: 0, target: 0}

                def seq_maker(t):
                    seqs[t] += 1
                    return seqs[t]
                afr.seq.side_effect = seq_maker

                item = TransportItem([part1, part2, part3])
                simplify_parts = mock.Mock(name="simplify_parts"
                    , return_value= [(original1, part1), (original2, part2), (original3, part3)]
                    )

                broadcast_address = False

                with mock.patch.object(item, "simplify_parts", simplify_parts):
                    packets = item.make_packets(afr, serials, broadcast_address)

                self.assertEqual(packets, [(original1, c1), (original1, c2), (original2, c3), (original2, c4), (original3, c5)])

                c1.update.assert_called_once_with(dict(source=source, sequence=1, target=s1))
                c2.update.assert_called_once_with(dict(source=source, sequence=1, target=s2))

                c3.update.assert_called_once_with(dict(source=source, sequence=2, target=s1))
                c4.update.assert_called_once_with(dict(source=source, sequence=2, target=s2))

                c5.update.assert_called_once_with(dict(source=source, sequence=1))

        describe "search":
            async before_each:
                self.afr = mock.Mock(name="afr")
                self.find_specific_serials = asynctest.mock.CoroutineMock(name="find_specific_serials")
                self.afr.find_specific_serials = self.find_specific_serials

                self.serial1 = "d073d5000000"
                self.serial2 = "d073d5000001"
                self.target1 = binascii.unhexlify(self.serial1)[:6]
                self.target2 = binascii.unhexlify(self.serial2)[:6]

                self.o1, self.p1 = mock.Mock(name="original1"), mock.Mock(name="packet1", serial=self.serial1)
                self.o2, self.p2 = mock.Mock(name="original2"), mock.Mock(name="packet2", serial=self.serial1)
                self.o3, self.p3 = mock.Mock(name="original3"), mock.Mock(name="packet3", serial=self.serial2)
                self.o4, self.p4 = mock.Mock(name="original4"), mock.Mock(name="packet4", serial=self.serial2)

                self.packets = [
                      (self.o1, self.p1)
                    , (self.o2, self.p2)
                    , (self.o3, self.p3)
                    , (self.o4, self.p4)
                    ]

                self.broadcast_address = mock.Mock(name="broadcast_address")

                self.a = mock.Mock(name="a")
                self.kwargs = {"a": self.a}

                self.found_info1 = mock.Mock(name="found_info1")
                self.found_info2 = mock.Mock(name="found_info2")

            async def search(self, found, accept_found, find_timeout=1):
                return await self.item.search(self.afr, found, accept_found, self.packets, self.broadcast_address, find_timeout, self.kwargs)

            @with_timeout
            async it "returns without looking if we have all the targets":
                found = {self.target1: self.found_info1, self.target2: self.found_info2}
                looked, f, missing = await self.search(found, False)
                assert not looked
                self.assertEqual(f, found)
                self.assertEqual(missing, [])
                self.assertEqual(len(self.find_specific_serials.mock_calls), 0)

            @with_timeout
            async it "returns without looking if accept_found is True":
                found = {self.target1: self.found_info1, self.target2: self.found_info2}
                looked, f, missing = await self.search(found, True)
                self.assertEqual(len(self.find_specific_serials.mock_calls), 0)
                assert not looked
                self.assertEqual(f, found)
                self.assertEqual(missing, [])

                found = {self.target1: self.found_info1}
                looked, f, missing = await self.search(found, True)
                self.assertEqual(len(self.find_specific_serials.mock_calls), 0)
                assert not looked
                self.assertEqual(f, found)
                self.assertEqual(missing, [self.serial2])

            @with_timeout
            async it "otherwise uses find_specific_serials":
                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                self.find_specific_serials.return_value = (found, missing)

                looked, f, missing = await self.search(None, False, find_timeout=20)
                assert looked
                self.assertIs(f, found)
                self.assertIs(missing, missing)

                class L:
                    def __init__(self, want):
                        self.want = want

                    def __eq__(self, other):
                        return sorted(other) == sorted(self.want)

                self.find_specific_serials.assert_called_once_with(L([self.serial1, self.serial2])
                    , broadcast = self.broadcast_address
                    , raise_on_none = False
                    , timeout = 20
                    , a = self.a
                    )

        describe "write_messages":
            async before_each:
                self.serial1 = "d073d5000000"
                self.serial2 = "d073d5000001"

                self.o1, self.p1 = mock.Mock(name="original1"), mock.Mock(name="packet1", serial=self.serial1)
                self.o2, self.p2 = mock.Mock(name="original2"), mock.Mock(name="packet2", serial=self.serial1)
                self.o3, self.p3 = mock.Mock(name="original3"), mock.Mock(name="packet3", serial=self.serial2)
                self.o4, self.p4 = mock.Mock(name="original4"), mock.Mock(name="packet4", serial=self.serial2)

                self.packets = [
                      (self.o1, self.p1)
                    , (self.o2, self.p2)
                    , (self.o3, self.p3)
                    , (self.o4, self.p4)
                    ]

                self.make_waiter = mock.Mock(name="make_waiter")
                self.make_writer = asynctest.mock.CoroutineMock(name="make_writer")
                self.check_packet = mock.Mock(name="check_packet")

                self.stop_fut = asyncio.Future()

            async after_each:
                self.stop_fut.cancel()

            async it "collects errors from check_packet and from waiter and waits on the rest":
                err = PhotonsAppError("packet not found")
                err2 = PhotonsAppError("Failed to wait")

                def check_packet(p):
                    if p is self.p2:
                        return err
                self.check_packet.side_effect = check_packet

                w1 = asyncio.Future()
                w3 = asyncio.Future()
                w4 = asyncio.Future()

                async def make_writer(o, p):
                    self.assertIs({self.p1: self.o1, self.p2: self.o2, self.p3: self.o3, self.p4: self.o4}[p], o)
                    return {self.p1: w1, self.p3: w3, self.p4: w4}[p]
                self.make_writer.side_effect = make_writer

                f1 = asyncio.Future()
                f3 = asyncio.Future()
                f4 = asyncio.Future()

                r1 = mock.Mock(name="r1")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")

                def make_waiter(w):
                    f = {w1: f1, w3: f3, w4: f4}[w]
                    if w is w3:
                        f.set_exception(err2)
                        return f

                    f.set_result([{w1: r1, w4: r4}[w]])
                    return f
                self.make_waiter.side_effect = make_waiter

                results = []
                errors = []

                async def doit():
                    async for info in self.item.write_messages(self.packets
                        , self.check_packet, self.make_writer, self.make_waiter
                        , message_timeout=0.1, error_catcher=errors
                        ):
                        results.append(info)
                await self.wait_for(doit())

                self.assertEqual(sorted(errors), sorted([err, err2]))
                self.assertEqual(results, [r1, r4])

            async it "creates timeout error if it fails to wait":
                self.check_packet.return_value = None

                w1 = asyncio.Future()
                w2 = asyncio.Future()
                w3 = asyncio.Future()
                w4 = asyncio.Future()

                async def make_writer(o, p):
                    self.assertIs({self.p1: self.o1, self.p2: self.o2, self.p3: self.o3, self.p4: self.o4}[p], o)
                    return {self.p1: w1, self.p2: w2, self.p3: w3, self.p4: w4}[p]
                self.make_writer.side_effect = make_writer

                f1 = asyncio.Future()
                f2 = asyncio.Future()
                f3 = asyncio.Future()
                f4 = asyncio.Future()

                r1 = mock.Mock(name="r1")
                r4 = mock.Mock(name="r4")

                def make_waiter(w):
                    f = {w1: f1, w2: f2, w3: f3, w4: f4}[w]
                    if w in (w2, w3):
                        return f

                    f.set_result([{w1: r1, w4: r4}[w]])
                    return f
                self.make_waiter.side_effect = make_waiter

                errors = []
                results = []

                async def doit():
                    async for info in self.item.write_messages(self.packets
                        , self.check_packet, self.make_writer, self.make_waiter
                        , message_timeout=0.1, error_catcher=errors
                        ):
                        results.append(info)
                await self.wait_for(doit())

                self.assertEqual(sorted(errors), sorted(
                      [ TimedOut("Waiting for reply to a packet", serial=self.serial1)
                      , TimedOut("Waiting for reply to a packet", serial=self.serial2)
                      ]
                    ))
                self.assertEqual(results, [r1, r4])

            async it "creates message cancelled error if it gets cancelled":
                self.check_packet.return_value = None

                w1 = asyncio.Future()
                w2 = asyncio.Future()
                w3 = asyncio.Future()
                w4 = asyncio.Future()

                async def make_writer(o, p):
                    self.assertIs({self.p1: self.o1, self.p2: self.o2, self.p3: self.o3, self.p4: self.o4}[p], o)
                    return {self.p1: w1, self.p2: w2, self.p3: w3, self.p4: w4}[p]
                self.make_writer.side_effect = make_writer

                f1 = asyncio.Future()
                f2 = asyncio.Future()
                f3 = asyncio.Future()
                f4 = asyncio.Future()

                r1 = mock.Mock(name="r1")
                r4 = mock.Mock(name="r4")

                def make_waiter(w):
                    f = {w1: f1, w2: f2, w3: f3, w4: f4}[w]
                    if w in (w2, w3):
                        return f

                    f.set_result([{w1: r1, w4: r4}[w]])
                    return f
                self.make_waiter.side_effect = make_waiter

                errors = []
                results = []

                async def doit():
                    async for info in self.item.write_messages(self.packets
                        , self.check_packet, self.make_writer, self.make_waiter
                        , message_timeout=1, error_catcher=errors
                        ):
                        results.append(info)

                t = hp.async_as_background(doit())
                await self.wait_for(f1)
                await self.wait_for(f4)
                t.cancel()

                # Do a switch so that the cancellation happens and errors gets populated
                await asyncio.sleep(0.01)

                self.assertEqual(sorted(errors), sorted(
                      [ TimedOut("Message was cancelled", serial=self.serial1)
                      , TimedOut("Message was cancelled", serial=self.serial2)
                      ]
                    ))
                self.assertEqual(results, [r1, r4])

            async def assertLimits(self, results, waits, expectedResult, expectedMaxinflight, limit, timeout=1):
                self.check_packet.return_value = None

                info = {"inflight": 0, "maxinflight": 0}

                class Writer:
                    def __init__(s, timeout, result):
                        s.result = result
                        s.timeout = timeout

                    async def ensure_conn(s):
                        pass

                    async def __call__(s):
                        info["inflight"] += 1
                        info["maxinflight"] = max(info["maxinflight"], info["inflight"])
                        await asyncio.sleep(s.timeout)
                        info["inflight"] -= 1
                        f = asyncio.Future()
                        f.set_result([s.result])
                        return f

                async def make_writer(o, p):
                    self.assertIs({self.p1: self.o1, self.p2: self.o2, self.p3: self.o3, self.p4: self.o4}[p], o)
                    w = {self.p1: 1, self.p2: 2, self.p3: 3, self.p4: 4}[p]
                    return Writer(waits[w], results[w])
                self.make_writer.side_effect = make_writer

                def make_waiter(writer):
                    return Waiter(self.stop_fut, writer, LargeRetryOptions())
                self.make_waiter.side_effect = make_waiter

                def errors(e):
                    raise e

                res = []

                async def doit():
                    async for info in self.item.write_messages(self.packets
                        , self.check_packet, self.make_writer, self.make_waiter
                        , message_timeout = timeout, error_catcher=errors, limit = limit
                        ):
                        res.append(info)
                await self.wait_for(doit())

                self.assertEqual(res, expectedResult, res)
                self.assertEqual(info["maxinflight"], expectedMaxinflight)

            async it "defaults to no limit":
                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")

                results = {
                      1: r1
                    , 2: r2
                    , 3: r3
                    , 4: r4
                    }

                waits = {
                      1: 0.04
                    , 2: 0.02
                    , 3: 0.03
                    , 4: 0.05
                    }

                expected = [r2, r3, r1, r4]
                await self.assertLimits(results, waits, expected, 4, None)

            async it "can be given a limit":
                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")

                results = {
                      1: r1
                    , 2: r2
                    , 3: r3
                    , 4: r4
                    }

                waits = {
                      1: 0.04
                    , 2: 0.02
                    , 3: 0.03
                    , 4: 0.05
                    }

                expected = [r2, r1, r3, r4]
                await self.assertLimits(results, waits, expected, 2, asyncio.Semaphore(2))

            async it "can be given a limit of 1":
                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")

                results = {
                      1: r1
                    , 2: r2
                    , 3: r3
                    , 4: r4
                    }

                waits = {
                      1: 0.04
                    , 2: 0.02
                    , 3: 0.03
                    , 4: 0.05
                    }

                expected = [r1, r2, r3, r4]
                await self.assertLimits(results, waits, expected, 1, asyncio.Semaphore(1))

            async it "timeout is per message":
                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")

                results = {
                      1: r1
                    , 2: r2
                    , 3: r3
                    , 4: r4
                    }

                waits = {
                      1: 0.06
                    , 2: 0.06
                    , 3: 0.09
                    , 4: 0.05
                    }

                expected = [r1, r2, r3, r4]
                await self.assertLimits(results, waits, expected, 1, asyncio.Semaphore(1), timeout=0.2)
