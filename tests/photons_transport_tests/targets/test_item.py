# coding: spec

from photons_transport.comms.waiter import Waiter
from photons_transport.targets.item import Item
from photons_transport.comms.base import Found

from photons_app.errors import (
    PhotonsAppError,
    TimedOut,
    BadRunWithResults,
    DevicesNotFound,
    RunErrors,
)
from photons_app.special import SpecialReference
from photons_app import helpers as hp

from photons_messages import DeviceMessages

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from unittest import mock
import binascii
import asyncio
import pytest


@pytest.fixture()
def item():
    return Item([DeviceMessages.GetPower(), DeviceMessages.GetLabel()])


describe "Item":
    async it "takes in parts":
        part = mock.Mock(name="part")
        part2 = mock.Mock(name="part2")

        item = Item(part)
        assert item.parts == [part]

        item = Item([part, part2])
        assert item.parts == [part, part2]

    describe "Functionality":

        describe "simplify_parts":
            async it "returns originals with packets as they are if they are dynamic, else we simplify them":
                part1_dynamic = mock.Mock(
                    name="part1_dynamic", is_dynamic=True, spec=["is_dynamic"]
                )

                part2_static = mock.Mock(name="part2_static", is_dynamic=False)
                part2_simple = mock.Mock(name="part2_simple")
                part2_static.simplify.return_value = part2_simple

                part3_static = mock.Mock(name="part3_static", is_dynamic=False)
                part3_simple = mock.Mock(name="part3_simple")
                part3_static.simplify.return_value = part3_simple

                part4_dynamic = mock.Mock(
                    name="part4_dynamic", is_dynamic=True, spec=["is_dynamic"]
                )

                simplified = Item(
                    [part1_dynamic, part2_static, part3_static, part4_dynamic]
                ).simplify_parts()
                assert simplified == [
                    (part1_dynamic, part1_dynamic),
                    (part2_static, part2_simple),
                    (part3_static, part3_simple),
                    (part4_dynamic, part4_dynamic),
                ]

        describe "making packets":
            async it "duplicates parts for each serial and only clones those already with targets":
                original1 = mock.Mock(name="original1")
                original2 = mock.Mock(name="original2")
                original3 = mock.Mock(name="original3")

                s1 = mock.Mock(name="s1")
                s2 = mock.Mock(name="s2")
                serials = [s1, s2]

                c1 = mock.Mock(name="clone1")
                c1.actual.return_value = sb.NotSpecified
                c2 = mock.Mock(name="clone2")
                c2.actual.return_value = sb.NotSpecified
                p1clones = [c1, c2]

                c3 = mock.Mock(name="clone3")
                c3.actual.return_value = sb.NotSpecified
                c4 = mock.Mock(name="clone4")
                c4.actual.return_value = sb.NotSpecified
                p2clones = [c3, c4]

                def part1clone():
                    return p1clones.pop(0)

                part1 = mock.Mock(name="part1", target=sb.NotSpecified)
                part1.clone.side_effect = part1clone

                def part2clone():
                    return p2clones.pop(0)

                part2 = mock.Mock(name="part2", target=sb.NotSpecified)
                part2.clone.side_effect = part2clone

                c5source = mock.Mock(name="c5source")
                c5 = mock.Mock(name="clone5", source=c5source)
                c5.actual.return_value = 123
                serial = mock.Mock(name="serial")
                part3 = mock.Mock(name="part3", serial=serial)
                part3.clone.return_value = c5

                sender = mock.Mock(name="sender")
                source = mock.Mock(name="source")
                sender.source = source

                seqs = {s1: 0, s2: 0, serial: 0}

                def seq_maker(t):
                    seqs[t] += 1
                    return seqs[t]

                sender.seq.side_effect = seq_maker

                item = Item([part1, part2, part3])
                simplify_parts = mock.Mock(
                    name="simplify_parts",
                    return_value=[(original1, part1), (original2, part2), (original3, part3)],
                )

                with mock.patch.object(item, "simplify_parts", simplify_parts):
                    packets = item.make_packets(sender, serials)

                assert packets == [
                    (original1, c1),
                    (original1, c2),
                    (original2, c3),
                    (original2, c4),
                    (original3, c5),
                ]

                c1.update.assert_called_once_with(dict(source=source, sequence=1, target=s1))
                c2.update.assert_called_once_with(dict(source=source, sequence=1, target=s2))

                c3.update.assert_called_once_with(dict(source=source, sequence=2, target=s1))
                c4.update.assert_called_once_with(dict(source=source, sequence=2, target=s2))

                # c5 had an overridden source
                c5.update.assert_called_once_with(dict(source=c5source, sequence=1))
                c5.actual.assert_called_once_with("source")

        describe "search":

            @pytest.fixture()
            def V(self, item):
                class V:
                    find_specific_serials = pytest.helpers.AsyncMock(name="find_specific_serials")
                    serial1 = "d073d5000000"
                    serial2 = "d073d5000001"

                    broadcast_address = mock.Mock(name="broadcast_address")

                    found_info1 = mock.Mock(name="found_info1")
                    found_info2 = mock.Mock(name="found_info2")

                    @hp.memoized_property
                    def target1(s):
                        return binascii.unhexlify(s.serial1)[:6]

                    @hp.memoized_property
                    def target2(s):
                        return binascii.unhexlify(s.serial2)[:6]

                    @hp.memoized_property
                    def sender(s):
                        sender = mock.Mock(name="sender")
                        sender.find_specific_serials = s.find_specific_serials
                        return sender

                    @hp.memoized_property
                    def packets(s):
                        return [
                            (s.o1, s.p1),
                            (s.o2, s.p2),
                            (s.o3, s.p3),
                            (s.o4, s.p4),
                        ]

                    def __init__(s):
                        s.o1, s.p1 = (
                            mock.Mock(name="original1"),
                            mock.Mock(name="packet1", serial=s.serial1),
                        )
                        s.o2, s.p2 = (
                            mock.Mock(name="original2"),
                            mock.Mock(name="packet2", serial=s.serial1),
                        )
                        s.o3, s.p3 = (
                            mock.Mock(name="original3"),
                            mock.Mock(name="packet3", serial=s.serial2),
                        )
                        s.o4, s.p4 = (
                            mock.Mock(name="original4"),
                            mock.Mock(name="packet4", serial=s.serial2),
                        )

                        s.a = mock.Mock(name="a")
                        s.kwargs = {"a": s.a}

                    async def search(s, found, accept_found, find_timeout=1):
                        return await item.search(
                            s.sender,
                            found,
                            accept_found,
                            s.packets,
                            s.broadcast_address,
                            find_timeout,
                            s.kwargs,
                        )

                return V()

            async it "returns without looking if we have all the targets", V:
                found = Found()
                found[V.target1] = V.found_info1
                found[V.target2] = V.found_info2

                f, missing = await V.search(found, False)
                assert f is found
                assert missing == []
                assert len(V.find_specific_serials.mock_calls) == 0

            async it "returns without looking if accept_found is True", V:
                found = Found()
                found[V.target1] = V.found_info1
                found[V.target2] = V.found_info2

                f, missing = await V.search(found, True)
                assert len(V.find_specific_serials.mock_calls) == 0
                assert f is found
                assert missing == []

                found = Found()
                found[V.target1] = V.found_info1
                f, missing = await V.search(found, True)
                assert len(V.find_specific_serials.mock_calls) == 0
                assert f is found
                assert missing == [V.serial2]

            async it "uses find_specific_serials if found is None", V:
                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                V.find_specific_serials.return_value = (found, missing)

                f, missing = await V.search(None, False, find_timeout=20)
                assert f is found
                assert missing is missing

                class L:
                    def __init__(s, want):
                        s.want = want

                    def __eq__(s, other):
                        return sorted(other) == sorted(s.want)

                V.find_specific_serials.assert_called_once_with(
                    L([V.serial1, V.serial2]),
                    broadcast=V.broadcast_address,
                    raise_on_none=False,
                    timeout=20,
                    a=V.a,
                )

            async it "uses find_specific_serials if found is None and accept_found is True", V:
                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                V.find_specific_serials.return_value = (found, missing)

                f, missing = await V.search(None, True, find_timeout=20)
                assert f is found
                assert missing is missing

                class L:
                    def __init__(s, want):
                        s.want = want

                    def __eq__(s, other):
                        return sorted(other) == sorted(s.want)

                V.find_specific_serials.assert_called_once_with(
                    L([V.serial1, V.serial2]),
                    broadcast=V.broadcast_address,
                    raise_on_none=False,
                    timeout=20,
                    a=V.a,
                )

            async it "uses find_specific_serials if found is not None and don't have all serials", V:
                found = mock.Mock(name="found")
                missing = mock.Mock(name="missing")
                V.find_specific_serials.return_value = (found, missing)

                fin = Found()
                fin[V.target1] = V.found_info1

                f, missing = await V.search(fin, False, find_timeout=20)
                assert f is found
                assert missing is missing

                class L:
                    def __init__(s, want):
                        s.want = want

                    def __eq__(s, other):
                        return sorted(other) == sorted(s.want)

                V.find_specific_serials.assert_called_once_with(
                    L([V.serial1, V.serial2]),
                    broadcast=V.broadcast_address,
                    raise_on_none=False,
                    timeout=20,
                    a=V.a,
                )

        describe "write_messages":

            @pytest.fixture()
            def V(self):
                class V:
                    serial1 = "d073d5000000"
                    serial2 = "d073d5000001"

                    results = [mock.Mock(name=f"res{i}") for i in range(10)]

                    sender = mock.Mock(name="sender", spec=["send_single"])

                    error_catcher = []

                    @hp.memoized_property
                    def kwargs(s):
                        return {"error_catcher": s.error_catcher}

                    @hp.memoized_property
                    def packets(s):
                        return [
                            (s.o1, s.p1),
                            (s.o2, s.p2),
                            (s.o3, s.p3),
                            (s.o4, s.p4),
                        ]

                    def __init__(s):
                        s.o1, s.p1 = (
                            mock.Mock(name="original1"),
                            mock.Mock(name="packet1", serial=s.serial1),
                        )
                        s.o2, s.p2 = (
                            mock.Mock(name="original2"),
                            mock.Mock(name="packet2", serial=s.serial1),
                        )
                        s.o3, s.p3 = (
                            mock.Mock(name="original3"),
                            mock.Mock(name="packet3", serial=s.serial2),
                        )
                        s.o4, s.p4 = (
                            mock.Mock(name="original4"),
                            mock.Mock(name="packet4", serial=s.serial2),
                        )

                return V()

            async it "sends the packets and gets the replies", item, V:

                async def send_single(original, packet, **kwargs):
                    assert dict(V.packets)[original] is packet
                    if original is V.o1:
                        await asyncio.sleep(0.01)
                        return [V.results[5], V.results[6]]
                    elif original is V.o2:
                        await asyncio.sleep(0.02)
                        return [V.results[3], V.results[4]]
                    elif original is V.o3:
                        return [V.results[1], V.results[2]]
                    elif original is V.o4:
                        return [V.results[7]]
                    else:
                        assert False, f"Unknown packet {original}"

                V.sender.send_single.side_effect = send_single

                res = []
                async for r in item.write_messages(V.sender, V.packets, V.kwargs):
                    res.append(r)
                assert V.error_catcher == []

                assert res == [V.results[i] for i in (1, 2, 7, 5, 6, 3, 4)]

                assert V.sender.send_single.mock_calls == [
                    mock.call(
                        V.o1,
                        V.p1,
                        timeout=10,
                        limit=None,
                        no_retry=False,
                        broadcast=None,
                        connect_timeout=10,
                    ),
                    mock.call(
                        V.o2,
                        V.p2,
                        timeout=10,
                        limit=None,
                        no_retry=False,
                        broadcast=None,
                        connect_timeout=10,
                    ),
                    mock.call(
                        V.o3,
                        V.p3,
                        timeout=10,
                        limit=None,
                        no_retry=False,
                        broadcast=None,
                        connect_timeout=10,
                    ),
                    mock.call(
                        V.o4,
                        V.p4,
                        timeout=10,
                        limit=None,
                        no_retry=False,
                        broadcast=None,
                        connect_timeout=10,
                    ),
                ]

            async it "gets arguments for send from kwargs", item, V:

                async def send_single(original, packet, **kwargs):
                    assert dict(V.packets)[original] is packet
                    if original is V.o1:
                        return [V.results[1], V.results[2]]
                    elif original is V.o2:
                        return [V.results[3], V.results[4]]
                    elif original is V.o3:
                        return [V.results[5]]
                    elif original is V.o4:
                        return [V.results[6]]
                    else:
                        assert False, f"Unknown packet {original}"

                V.sender.send_single.side_effect = send_single

                mt = mock.Mock(name="message_timeout")
                limit = mock.Mock(name="limit")
                nr = mock.Mock(name="no_retry")
                broadcast = mock.Mock(name="broadcast")
                ct = mock.Mock(nme="connect_timeout")

                kwargs = {
                    "error_catcher": V.error_catcher,
                    "message_timeout": mt,
                    "limit": limit,
                    "no_retry": nr,
                    "broadcast": broadcast,
                    "connect_timeout": ct,
                }

                res = []
                async for r in item.write_messages(V.sender, V.packets, kwargs):
                    res.append(r)
                assert V.error_catcher == []

                assert res == [V.results[i] for i in (1, 2, 3, 4, 5, 6)]

                assert V.sender.send_single.mock_calls == [
                    mock.call(
                        V.o1,
                        V.p1,
                        timeout=mt,
                        limit=limit,
                        no_retry=nr,
                        broadcast=broadcast,
                        connect_timeout=ct,
                    ),
                    mock.call(
                        V.o2,
                        V.p2,
                        timeout=mt,
                        limit=limit,
                        no_retry=nr,
                        broadcast=broadcast,
                        connect_timeout=ct,
                    ),
                    mock.call(
                        V.o3,
                        V.p3,
                        timeout=mt,
                        limit=limit,
                        no_retry=nr,
                        broadcast=broadcast,
                        connect_timeout=ct,
                    ),
                    mock.call(
                        V.o4,
                        V.p4,
                        timeout=mt,
                        limit=limit,
                        no_retry=nr,
                        broadcast=broadcast,
                        connect_timeout=ct,
                    ),
                ]

            async it "records errors", item, V:

                async def send_single(original, packet, **kwargs):
                    assert dict(V.packets)[original] is packet
                    if original is V.o1:
                        return [V.results[0]]
                    elif original is V.o2:
                        raise asyncio.CancelledError()
                    elif original is V.o3:
                        raise ValueError("NOPE")
                    elif original is V.o4:
                        return [V.results[6]]
                    else:
                        assert False, f"Unknown packet {original}"

                V.sender.send_single.side_effect = send_single

                class IS:
                    def __init__(s, want):
                        s.want = want

                    def __eq__(s, other):
                        return isinstance(other, type(s.want)) and repr(s.want) == repr(other)

                res = []
                async for r in item.write_messages(V.sender, V.packets, V.kwargs):
                    res.append(r)
                assert V.error_catcher == [
                    TimedOut("Message was cancelled", serial=V.p1.serial),
                    IS(ValueError("NOPE")),
                ]

                assert res == [V.results[i] for i in (0, 6)]

        describe "private find":

            @pytest.fixture()
            def V(self):
                class V:
                    found = mock.Mock(name="found")
                    broadcast = mock.Mock(name="broadcast")
                    timeout = mock.Mock(name="timeout")

                    @hp.memoized_property
                    def sender(s):
                        return mock.Mock(name="sender", found=s.found, spec=["found"])

                return V()

            async it "returns serials as a list", item, V:
                f, s, m = await item._find(None, "d073d5000000", V.sender, V.broadcast, V.timeout)
                assert f is V.found
                assert s == ["d073d5000000"]
                assert m is None

                f, s, m = await item._find(None, ["d073d5000000"], V.sender, V.broadcast, V.timeout)
                assert f is V.found
                assert s == ["d073d5000000"]
                assert m is None

                f, s, m = await item._find(
                    None, ["d073d5000000", "d073d5000001"], V.sender, V.broadcast, V.timeout
                )
                assert f is V.found
                assert s == ["d073d5000000", "d073d5000001"]
                assert m is None

            async it "returns the provided found if one was given", item, V:
                found = mock.Mock(name="found")
                f, s, m = await item._find(
                    found, ["d073d5000000", "d073d5000001"], V.sender, V.broadcast, V.timeout
                )
                assert f is found
                assert s == ["d073d5000000", "d073d5000001"]
                assert m is None

            async it "resolves the reference if it's a SpecialReference", item, V:
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

                f, s, m = await item._find(None, Ref(), V.sender, V.broadcast, V.timeout)
                assert f is found
                assert s == ss
                assert m == []

                assert called == [
                    ("find", (V.sender,), {"broadcast": V.broadcast, "timeout": V.timeout},),
                    ("missing", found),
                ]

            async it "gives missing to serials", item, V:
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

                f, s, m = await item._find(None, Ref(), V.sender, V.broadcast, V.timeout)
                assert f is found
                assert s == ["d073d5000000", "d073d5000001"]
                assert m == ["d073d5000001"]

                assert called == [
                    ("find", (V.sender,), {"broadcast": V.broadcast, "timeout": V.timeout},),
                    ("missing", found),
                ]

        describe "run_with":

            @pytest.fixture()
            def V(self):
                class V:
                    source = 9001
                    found = Found()

                    @hp.memoized_property
                    def sender(s):
                        sender = mock.Mock(
                            name="sender",
                            source=s.source,
                            found=s.found,
                            spec=["source", "seq", "found"],
                        )
                        sender.seq.return_value = 1
                        return sender

                return V()

            async it "finds, prepares, searches, writes", item, V:
                found = mock.Mock(name="found")
                serials = ["d073d5000000", "d073d5000001"]
                missing = None
                _find = pytest.helpers.AsyncMock(
                    name="_find", return_value=(found, serials, missing)
                )

                packets = mock.Mock(name="packets")
                make_packets = mock.Mock(name="make_packets", return_value=packets)

                found2 = mock.Mock(name="found2")
                missing2 = mock.Mock(name="missing2")
                search = pytest.helpers.AsyncMock(name="search", return_value=(found2, missing2))

                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name="res2")

                async def write_messages(*args, **kwargs):
                    yield res1
                    yield res2

                write_messages = pytest.helpers.MagicAsyncMock(
                    name="write_messages", side_effect=write_messages
                )

                mod = {
                    "_find": _find,
                    "make_packets": make_packets,
                    "search": search,
                    "write_messages": write_messages,
                }

                a = mock.Mock(name="a")
                reference = mock.Mock(name="reference")

                res = []
                with mock.patch.multiple(item, **mod):
                    async for r in item.run_with(reference, V.sender, a=a):
                        res.append(r)

                assert res == [res1, res2]

                _find.assert_called_once_with(None, reference, V.sender, False, 20)
                make_packets.assert_called_once_with(V.sender, serials)
                search.assert_called_once_with(
                    V.sender, found, False, packets, False, 20, {"a": a, "error_catcher": mock.ANY}
                )
                write_messages.assert_called_once_with(
                    V.sender, packets, {"a": a, "error_catcher": mock.ANY}
                )

            async it "shortcuts if no packets to send", item, V:
                found = mock.Mock(name="found")
                serials = ["d073d5000000", "d073d5000001"]
                missing = None
                _find = pytest.helpers.AsyncMock(
                    name="_find", return_value=(found, serials, missing)
                )

                make_packets = mock.Mock(name="make_packets", return_value=[])

                search = pytest.helpers.AsyncMock(name="search")
                write_messages = pytest.helpers.MagicAsyncMock(name="write_messages")

                mod = {
                    "_find": _find,
                    "make_packets": make_packets,
                    "search": search,
                    "write_messages": write_messages,
                }

                a = mock.Mock(name="a")
                reference = mock.Mock(name="reference")

                res = []
                with mock.patch.multiple(item, **mod):
                    async for r in item.run_with(reference, V.sender, a=a):
                        res.append(r)

                assert res == []

                _find.assert_called_once_with(None, reference, V.sender, False, 20)
                make_packets.assert_called_once_with(V.sender, serials)
                assert len(search.mock_calls) == 0
                assert len(write_messages.mock_calls) == 0

            async it "doesn't search if broadcasting", item, V:
                search = pytest.helpers.AsyncMock(name="search")
                write_messages = pytest.helpers.MagicAsyncMock(name="write_messages")

                mod = {"search": search, "write_messages": write_messages}

                a = mock.Mock(name="a")
                reference = mock.Mock(name="reference")

                res = []
                with mock.patch.multiple(item, **mod):
                    async for r in item.run_with(None, V.sender, broadcast=True):
                        res.append(r)

                assert res == []

                packets = []
                for part in item.parts:
                    clone = part.simplify()
                    clone.update(source=9001, sequence=1, target=None)
                    packets.append((part, clone))

                assert len(search.mock_calls) == 0
                write_messages.assert_called_once_with(
                    V.sender, packets, {"broadcast": True, "error_catcher": mock.ANY}
                )

            async it "complains if we haven't found all our serials", item, V:

                class Ref(SpecialReference):
                    async def find(s, *args, **kwargs):
                        found = Found()
                        found["d073d5000000"] = mock.Mock(name="service")
                        return found, ["d073d5000000"]

                    def missing(s, f):
                        return ["d073d5000001"]

                with assertRaises(DevicesNotFound, missing=["d073d5000001"]):
                    async for _ in item.run_with(Ref(), V.sender, require_all_devices=True):
                        pass

                es = []
                async for _ in item.run_with(
                    Ref(), V.sender, require_all_devices=True, error_catcher=es
                ):
                    pass
                assert es == [DevicesNotFound(missing=["d073d5000001"])]

                es = mock.Mock(name="es")
                async for _ in item.run_with(
                    Ref(), V.sender, require_all_devices=True, error_catcher=es
                ):
                    pass
                es.assert_called_once_with(DevicesNotFound(missing=["d073d5000001"]))

            async it "raises errors from write_messages", item, V:
                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name="res2")
                error = PhotonsAppError("wat")

                async def write_messages(sender, packets, kwargs):
                    yield res1
                    hp.add_error(kwargs["error_catcher"], error)
                    yield res2

                write_messages = pytest.helpers.MagicAsyncMock(
                    name="write_messages", side_effect=write_messages
                )

                with mock.patch.object(item, "write_messages", write_messages):
                    res = []
                    with assertRaises(PhotonsAppError, "wat"):
                        async for r in item.run_with(None, V.sender, broadcast=True):
                            res.append(r)

                assert res == [res1, res2]

                res = []
                es = []
                with mock.patch.object(item, "write_messages", write_messages):
                    async for r in item.run_with(None, V.sender, broadcast=True, error_catcher=es):
                        res.append(r)

                assert es == [error]
                assert res == [res1, res2]

                res = []
                es = mock.Mock(name="es")
                with mock.patch.object(item, "write_messages", write_messages):
                    async for r in item.run_with(None, V.sender, broadcast=True, error_catcher=es):
                        res.append(r)

                es.assert_called_once_with(error)
                assert res == [res1, res2]

            async it "raises multiple errors from write_messages", item, V:
                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name="res2")
                error1 = PhotonsAppError("wat")
                error2 = PhotonsAppError("nup")

                async def write_messages(sender, packets, kwargs):
                    yield res1
                    hp.add_error(kwargs["error_catcher"], error1)
                    yield res2
                    hp.add_error(kwargs["error_catcher"], error2)

                write_messages = pytest.helpers.MagicAsyncMock(
                    name="write_messages", side_effect=write_messages
                )

                with mock.patch.object(item, "write_messages", write_messages):
                    res = []
                    with assertRaises(RunErrors, _errors=[error1, error2]):
                        async for r in item.run_with(None, V.sender, broadcast=True):
                            res.append(r)

                assert res == [res1, res2]

                res = []
                es = []
                with mock.patch.object(item, "write_messages", write_messages):
                    async for r in item.run_with(None, V.sender, broadcast=True, error_catcher=es):
                        res.append(r)

                assert es == [error1, error2]
                assert res == [res1, res2]

                res = []
                es = mock.Mock(name="es")
                with mock.patch.object(item, "write_messages", write_messages):
                    async for r in item.run_with(None, V.sender, broadcast=True, error_catcher=es):
                        res.append(r)

                assert es.mock_calls == [mock.call(error1), mock.call(error2)]
                assert res == [res1, res2]
