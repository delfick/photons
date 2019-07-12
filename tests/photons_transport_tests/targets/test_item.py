# coding: spec

from photons_transport.comms.waiter import Waiter
from photons_transport.targets.item import Item
from photons_transport.comms.base import Found

from photons_app.errors import PhotonsAppError, TimedOut, BadRunWithResults, DevicesNotFound, RunErrors
from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app.special import SpecialReference
from photons_app import helpers as hp

from photons_messages import DeviceMessages

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from input_algorithms import spec_base as sb
from unittest import mock
import asynctest
import binascii
import asyncio

describe AsyncTestCase, "Item":
    async it "takes in parts":
        part = mock.Mock(name="part")
        part2 = mock.Mock(name="part2")

        item = Item(part)
        self.assertEqual(item.parts, [part])

        item = Item([part, part2])
        self.assertEqual(item.parts, [part, part2])

    describe "Functionality":
        async before_each:
            self.part1 = mock.Mock(name="part1")
            self.part2 = mock.Mock(name="part2")
            self.item = Item([self.part1, self.part2])

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

                simplified = Item([part1_dynamic, part2_static, part3_static, part4_dynamic]).simplify_parts()
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
                afr.source = source

                seqs = {s1: 0, s2: 0, target: 0}

                def seq_maker(t):
                    seqs[t] += 1
                    return seqs[t]
                afr.seq.side_effect = seq_maker

                item = Item([part1, part2, part3])
                simplify_parts = mock.Mock(name="simplify_parts"
                    , return_value= [(original1, part1), (original2, part2), (original3, part3)]
                    )

                with mock.patch.object(item, "simplify_parts", simplify_parts):
                    packets = item.make_packets(afr, serials)

                self.assertEqual(packets
                    , [ (original1, c1)
                      , (original1, c2)
                      , (original2, c3)
                      , (original2, c4)
                      , (original3, c5)
                      ]
                    )

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
                return await self.item.search(self.afr
                    , found
                    , accept_found
                    , self.packets
                    , self.broadcast_address
                    , find_timeout
                    , self.kwargs
                    )

            @with_timeout
            async it "returns without looking if we have all the targets":
                found = Found()
                found[self.target1] = self.found_info1
                found[self.target2] = self.found_info2

                f, missing = await self.search(found, False)
                self.assertIs(f, found)
                self.assertEqual(missing, [])
                self.assertEqual(len(self.find_specific_serials.mock_calls), 0)

            @with_timeout
            async it "returns without looking if accept_found is True":
                found = Found()
                found[self.target1] = self.found_info1
                found[self.target2] = self.found_info2

                f, missing = await self.search(found, True)
                self.assertEqual(len(self.find_specific_serials.mock_calls), 0)
                self.assertIs(f, found)
                self.assertEqual(missing, [])

                found = Found()
                found[self.target1] = self.found_info1
                f, missing = await self.search(found, True)
                self.assertEqual(len(self.find_specific_serials.mock_calls), 0)
                self.assertIs(f, found)
                self.assertEqual(missing, [self.serial2])

            @with_timeout
            async it "uses find_specific_serials if found is None":
                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                self.find_specific_serials.return_value = (found, missing)

                f, missing = await self.search(None, False, find_timeout=20)
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

            @with_timeout
            async it "uses find_specific_serials if found is None and accept_found is True":
                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                self.find_specific_serials.return_value = (found, missing)

                f, missing = await self.search(None, True, find_timeout=20)
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

            @with_timeout
            async it "uses find_specific_serials if found is not None and don't have all serials":
                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                self.find_specific_serials.return_value = (found, missing)

                fin = Found()
                fin[self.target1] = self.found_info1

                f, missing = await self.search(fin, False, find_timeout=20)
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

                self.results = [mock.Mock(name=f"res{i}") for i in range(10)]

                self.afr = mock.Mock(name="afr", spec=["send"])
                self.send = asynctest.mock.CoroutineMock(name="send")

                self.error_catcher = []
                self.kwargs = {"error_catcher": self.error_catcher}

            @with_timeout
            async it "sends the packets and gets the replies":
                async def send(original, packet, **kwargs):
                    self.assertIs(dict(self.packets)[original], packet)
                    if original is self.o1:
                        await asyncio.sleep(0.01)
                        return [self.results[5], self.results[6]]
                    elif original is self.o2:
                        await asyncio.sleep(0.02)
                        return [self.results[3], self.results[4]]
                    elif original is self.o3:
                        return [self.results[1], self.results[2]]
                    elif original is self.o4:
                        return [self.results[7]]
                    else:
                        assert False, f"Unknown packet {original}"
                self.afr.send.side_effect = send

                res = []
                async for r in self.item.write_messages(self.afr, self.packets, self.kwargs):
                    res.append(r)
                self.assertEqual(self.error_catcher, [])

                self.assertEqual(res, [self.results[i] for i in (1, 2, 7, 5, 6, 3, 4)])

                self.assertEqual(self.afr.send.mock_calls
                    , [ mock.call(self.o1, self.p1
                        , timeout=10, limit=None, no_retry=False, is_broadcast=False, connect_timeout=10
                        )
                      ,  mock.call(self.o2, self.p2
                        , timeout=10, limit=None, no_retry=False, is_broadcast=False, connect_timeout=10
                        )
                      ,  mock.call(self.o3, self.p3
                        , timeout=10, limit=None, no_retry=False, is_broadcast=False, connect_timeout=10
                        )
                      ,  mock.call(self.o4, self.p4
                        , timeout=10, limit=None, no_retry=False, is_broadcast=False, connect_timeout=10
                        )
                      ]
                    )

            @with_timeout
            async it "gets arguments for send from kwargs":
                async def send(original, packet, **kwargs):
                    self.assertIs(dict(self.packets)[original], packet)
                    if original is self.o1:
                        return [self.results[1], self.results[2]]
                    elif original is self.o2:
                        return [self.results[3], self.results[4]]
                    elif original is self.o3:
                        return [self.results[5]]
                    elif original is self.o4:
                        return [self.results[6]]
                    else:
                        assert False, f"Unknown packet {original}"
                self.afr.send.side_effect = send

                mt = mock.Mock(name="message_timeout")
                limit = mock.Mock(name="limit")
                nr = mock.Mock(name="no_retry")
                broadcast = mock.Mock(name="broadcast")
                ct = mock.Mock(nme="connect_timeout")

                kwargs = {
                      "error_catcher": self.error_catcher
                    , "message_timeout": mt
                    , "limit": limit
                    , "no_retry": nr
                    , "broadcast": broadcast
                    , "connect_timeout": ct
                    }

                res = []
                async for r in self.item.write_messages(self.afr, self.packets, kwargs):
                    res.append(r)
                self.assertEqual(self.error_catcher, [])

                self.assertEqual(res, [self.results[i] for i in (1, 2, 3, 4, 5, 6)])

                self.assertEqual(self.afr.send.mock_calls
                    , [ mock.call(self.o1, self.p1
                        , timeout=mt, limit=limit, no_retry=nr, is_broadcast=True, connect_timeout=ct
                        )
                      ,  mock.call(self.o2, self.p2
                        , timeout=mt, limit=limit, no_retry=nr, is_broadcast=True, connect_timeout=ct
                        )
                      ,  mock.call(self.o3, self.p3
                        , timeout=mt, limit=limit, no_retry=nr, is_broadcast=True, connect_timeout=ct
                        )
                      ,  mock.call(self.o4, self.p4
                        , timeout=mt, limit=limit, no_retry=nr, is_broadcast=True, connect_timeout=ct
                        )
                      ]
                    )

            @with_timeout
            async it "records errors":
                async def send(original, packet, **kwargs):
                    self.assertIs(dict(self.packets)[original], packet)
                    if original is self.o1:
                        return [self.results[0]]
                    elif original is self.o2:
                        raise asyncio.CancelledError()
                    elif original is self.o3:
                        raise ValueError("NOPE")
                    elif original is self.o4:
                        return [self.results[6]]
                    else:
                        assert False, f"Unknown packet {original}"
                self.afr.send.side_effect = send

                class IS:
                    def __init__(s, want):
                        s.want = want

                    def __eq__(s, other):
                        return isinstance(other, type(s.want)) and repr(s.want) == repr(other)

                res = []
                async for r in self.item.write_messages(self.afr, self.packets, self.kwargs):
                    res.append(r)
                self.assertEqual(self.error_catcher
                    , [ TimedOut("Message was cancelled", serial=self.p1.serial)
                      , IS(ValueError("NOPE"))
                      ]
                    )

                self.assertEqual(res, [self.results[i] for i in (0, 6)])

        describe "private find":
            async before_each:
                self.found = mock.Mock(name="found")
                self.afr = mock.Mock(name="afr", found=self.found, spec=["found"])
                self.broadcast = mock.Mock(name="broadcast")
                self.timeout = mock.Mock(name="timeout")

            async it "returns serials as a list":
                f, s, m = await self.item._find(None, "d073d5000000", self.afr, self.broadcast, self.timeout)
                self.assertIs(f, self.found)
                self.assertEqual(s, ["d073d5000000"])
                self.assertIs(m, None)

                f, s, m = await self.item._find(None, ["d073d5000000"], self.afr, self.broadcast, self.timeout)
                self.assertIs(f, self.found)
                self.assertEqual(s, ["d073d5000000"])
                self.assertIs(m, None)

                f, s, m = await self.item._find(None, ["d073d5000000", "d073d5000001"], self.afr, self.broadcast, self.timeout)
                self.assertIs(f, self.found)
                self.assertEqual(s, ["d073d5000000", "d073d5000001"])
                self.assertIs(m, None)

            async it "returns the provided found if one was given":
                found = mock.Mock(name="found")
                f, s, m = await self.item._find(found, ["d073d5000000", "d073d5000001"], self.afr, self.broadcast, self.timeout)
                self.assertIs(f, found)
                self.assertEqual(s, ["d073d5000000", "d073d5000001"])
                self.assertIs(m, None)

            async it "resolves the reference if it's a SpecialReference":
                ss = ["d073d5000000", "d073d5000001"]
                found = mock.Mock(name="found")
                called = []

                class Ref(SpecialReference):
                    async def find(s, *args, **kwargs):
                        called.append(("find", args, kwargs))
                        return found, ss

                    def missing(s, f):
                        called.append(("missing", f))
                        return []

                f, s, m = await self.item._find(None, Ref(), self.afr, self.broadcast, self.timeout)
                self.assertIs(f, found)
                self.assertEqual(s, ss)
                self.assertEqual(m, [])

                self.assertEqual(called
                    , [ ("find", (self.afr, ), {"broadcast": self.broadcast, "timeout": self.timeout})
                      , ("missing", found)
                      ]
                    )

            async it "gives missing to serials":
                ss = ["d073d5000000"]
                found = mock.Mock(name="found")
                called = []

                class Ref(SpecialReference):
                    async def find(s, *args, **kwargs):
                        called.append(("find", args, kwargs))
                        return found, ss

                    def missing(s, f):
                        called.append(("missing", f))
                        return ["d073d5000001"]

                f, s, m = await self.item._find(None, Ref(), self.afr, self.broadcast, self.timeout)
                self.assertIs(f, found)
                self.assertEqual(s, ["d073d5000000", "d073d5000001"])
                self.assertEqual(m, ["d073d5000001"])

                self.assertEqual(called
                    , [ ("find", (self.afr, ), {"broadcast": self.broadcast, "timeout": self.timeout})
                      , ("missing", found)
                      ]
                    )

        describe "run_with":
            async before_each:
                self.source = 9001
                self.found = Found()
                self.afr = mock.Mock(name="afr", source=self.source, found=self.found, spec=["source", "seq", "found"])
                self.afr.seq.return_value = 1

                self.item.parts = [DeviceMessages.GetPower(), DeviceMessages.GetLabel()]

            @with_timeout
            async it "finds, prepares, searches, writes":
                found = mock.Mock(name="found")
                serials = ["d073d5000000", "d073d5000001"]
                missing = None
                _find = asynctest.mock.CoroutineMock(name="_find", return_value=(found, serials, missing))

                packets = mock.Mock(name="packets")
                make_packets = mock.Mock(name="make_packets", return_value=packets)

                found2 = mock.Mock(name="found2")
                missing2 = mock.Mock(name="missing2")
                search = asynctest.mock.CoroutineMock(name="search", return_value=(found2, missing2))

                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name="res2")

                async def write_messages(*args, **kwargs):
                    yield res1
                    yield res2
                write_messages = asynctest.MagicMock(name='write_messages', side_effect=write_messages)

                mod = {
                      "_find": _find
                    , "make_packets": make_packets
                    , "search": search
                    , "write_messages": write_messages
                    }

                a = mock.Mock(name="a")
                reference = mock.Mock(name="reference")

                res = []
                with mock.patch.multiple(self.item, **mod):
                    async for r in self.item.run_with(reference, self.afr, a=a):
                        res.append(r)

                self.assertEqual(res, [res1, res2])

                _find.assert_called_once_with(None, reference, self.afr, False, 20)
                make_packets.assert_called_once_with(self.afr, serials)
                search.assert_called_once_with(self.afr, found, False, packets, False, 20, {"a": a, "error_catcher": mock.ANY})
                write_messages.assert_called_once_with(self.afr, packets, {"a": a, "error_catcher": mock.ANY})

            @with_timeout
            async it "shortcuts if no packets to send":
                found = mock.Mock(name="found")
                serials = ["d073d5000000", "d073d5000001"]
                missing = None
                _find = asynctest.mock.CoroutineMock(name="_find", return_value=(found, serials, missing))

                make_packets = mock.Mock(name="make_packets", return_value=[])

                search = asynctest.mock.CoroutineMock(name="search")
                write_messages = asynctest.MagicMock(name='write_messages')

                mod = {
                      "_find": _find
                    , "make_packets": make_packets
                    , "search": search
                    , "write_messages": write_messages
                    }

                a = mock.Mock(name="a")
                reference = mock.Mock(name="reference")

                res = []
                with mock.patch.multiple(self.item, **mod):
                    async for r in self.item.run_with(reference, self.afr, a=a):
                        res.append(r)

                self.assertEqual(res, [])

                _find.assert_called_once_with(None, reference, self.afr, False, 20)
                make_packets.assert_called_once_with(self.afr, serials)
                self.assertEqual(len(search.mock_calls), 0)
                self.assertEqual(len(write_messages.mock_calls), 0)

            @with_timeout
            async it "doesn't search if broadcasting":
                search = asynctest.mock.CoroutineMock(name="search")
                write_messages = asynctest.MagicMock(name='write_messages')

                mod = {
                      "search": search
                    , "write_messages": write_messages
                    }

                a = mock.Mock(name="a")
                reference = mock.Mock(name="reference")

                res = []
                with mock.patch.multiple(self.item, **mod):
                    async for r in self.item.run_with(None, self.afr, broadcast=True):
                        res.append(r)

                self.assertEqual(res, [])

                packets = []
                for part in self.item.parts:
                    clone = part.simplify()
                    clone.update(source=9001, sequence=1, target=None)
                    packets.append((part, clone))

                self.assertEqual(len(search.mock_calls), 0)
                write_messages.assert_called_once_with(self.afr, packets, {"broadcast": True, "error_catcher": mock.ANY})

            async it "complains if we haven't found all our serials":
                class Ref(SpecialReference):
                    async def find(s, *args, **kwargs):
                        found = Found()
                        found["d073d5000000"] = mock.Mock(name='service')
                        return found, ["d073d5000000"]

                    def missing(s, f):
                        return ["d073d5000001"]

                with self.fuzzyAssertRaisesError(DevicesNotFound, missing=["d073d5000001"]):
                    async for _ in self.item.run_with(Ref(), self.afr, require_all_devices=True):
                        pass

                es = []
                async for _ in self.item.run_with(Ref(), self.afr, require_all_devices=True, error_catcher=es):
                    pass
                self.assertEqual(es, [DevicesNotFound(missing=["d073d5000001"])])

                es = mock.Mock(name='es')
                async for _ in self.item.run_with(Ref(), self.afr, require_all_devices=True, error_catcher=es):
                    pass
                es.assert_called_once_with(DevicesNotFound(missing=["d073d5000001"]))

            async it "raises errors from write_messages":
                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name='res2')
                error = PhotonsAppError("wat")

                async def write_messages(afr, packets, kwargs):
                    yield res1
                    hp.add_error(kwargs["error_catcher"], error)
                    yield res2
                write_messages = asynctest.MagicMock(name="write_messages", side_effect=write_messages)

                with mock.patch.object(self.item, "write_messages", write_messages):
                    res = []
                    with self.fuzzyAssertRaisesError(PhotonsAppError, "wat"):
                        async for r in self.item.run_with(None, self.afr, broadcast=True):
                            res.append(r)

                self.assertEqual(res, [res1, res2])

                res = []
                es = []
                with mock.patch.object(self.item, "write_messages", write_messages):
                    async for r in self.item.run_with(None, self.afr, broadcast=True, error_catcher=es):
                        res.append(r)

                self.assertEqual(es, [error])
                self.assertEqual(res, [res1, res2])

                res = []
                es = mock.Mock(name="es")
                with mock.patch.object(self.item, "write_messages", write_messages):
                    async for r in self.item.run_with(None, self.afr, broadcast=True, error_catcher=es):
                        res.append(r)

                es.assert_called_once_with(error)
                self.assertEqual(res, [res1, res2])

            async it "raises multiple errors from write_messages":
                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name='res2')
                error1 = PhotonsAppError("wat")
                error2 = PhotonsAppError("nup")

                async def write_messages(afr, packets, kwargs):
                    yield res1
                    hp.add_error(kwargs["error_catcher"], error1)
                    yield res2
                    hp.add_error(kwargs["error_catcher"], error2)
                write_messages = asynctest.MagicMock(name="write_messages", side_effect=write_messages)

                with mock.patch.object(self.item, "write_messages", write_messages):
                    res = []
                    with self.fuzzyAssertRaisesError(RunErrors, _errors=[error1, error2]):
                        async for r in self.item.run_with(None, self.afr, broadcast=True):
                            res.append(r)

                self.assertEqual(res, [res1, res2])

                res = []
                es = []
                with mock.patch.object(self.item, "write_messages", write_messages):
                    async for r in self.item.run_with(None, self.afr, broadcast=True, error_catcher=es):
                        res.append(r)

                self.assertEqual(es, [error1, error2])
                self.assertEqual(res, [res1, res2])

                res = []
                es = mock.Mock(name="es")
                with mock.patch.object(self.item, "write_messages", write_messages):
                    async for r in self.item.run_with(None, self.afr, broadcast=True, error_catcher=es):
                        res.append(r)

                self.assertEqual(es.mock_calls, [mock.call(error1), mock.call(error2)])
                self.assertEqual(res, [res1, res2])
