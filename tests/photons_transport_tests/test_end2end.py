# coding: spec

from photons_transport.target import TransportItem, TransportBridge, TransportTarget

from photons_app.errors import PhotonsAppError, TimedOut, RunErrors
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.test_helpers import AsyncTestCase
from photons_app.special import SpecialReference
from photons_app import helpers as hp

from photons_script.script import ATarget, Pipeline
from photons_protocol.messages import MultiOptions

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from collections import defaultdict
import binascii
import asyncio
import base64
import mock
import uuid
import json
import enum

class Device(object):
    def __init__(self, serial):
        self.serial = serial
        self.target = binascii.unhexlify(serial)
        self.connections = []
        self.received = []

    def finish(self):
        for conn in self.connections:
            conn.cancel()

    def connect(self):
        recvQueue = asyncio.Queue()
        resQueue = asyncio.Queue()

        async def receive():
            while True:
                got = Messages.unpack(await recvQueue.get(), None)
                self.received.append(got)
                if got.ack_required:
                    await resQueue.put(got.make_ack().tobytes())
                if got.res_required:
                    for res in got.make_res():
                        await resQueue.put(res.tobytes())
        self.connections.append(hp.async_as_background(receive()))
        return resQueue, recvQueue

class Services(enum.Enum):
    MEMORY = "memory"

class Packet(object):
    def __init__(self, source, sequence, target, payload, ack_required=False, res_required=True):
        if type(target) is str:
            target = binascii.unhexlify(target)
        elif target is None:
            target = sb.NotSpecified

        if source is None:
            source = sb.NotSpecified

        if sequence is None:
            sequene = sb.NotSpecified

        self.source = source
        self.sequence = sequence
        self.target = target
        self.payload = payload
        self.ack_required = ack_required
        self.res_required = res_required

    class Meta:
        multi = None

    @property
    def represents_ack(self):
        return self.payload and self.payload.get("ack")

    @property
    def serial(self):
        if self.target in (None, sb.NotSpecified):
            return None
        return binascii.hexlify(self.target[:6]).decode()

    def is_dynamic(self):
        return False

    def clone(self):
        return Packet(**self.as_dict())

    def update(self, kwargs):
        for k, v in kwargs.items():
            if not hasattr(self, k):
                raise Exception("Trying to update packet with unknown key: {0}".format(k))
            if k == "target" and type(v) is str:
                v = binascii.unhexlify(v)
            setattr(self, k, v)

    def __hash__(self):
        return hash("{0}{1}{2}".format(self.source, self.sequence, self.target))

    def pack(self, serial=None):
        return base64.b64encode(json.dumps(self.as_dict()).encode())
    tobytes = pack

    def make_ack(self):
        nw = Packet(**self.as_dict())
        nw.ack_required = False
        nw.res_required = False
        nw.payload = {"ack": True}
        return nw

    def make_res(self):
        if self.as_dict()["payload"]["action"] == "missing":
            return

        for payload in self.calculate(**self.payload):
            nw = Packet(**self.as_dict())
            nw.ack_required = False
            nw.res_required = False
            nw.payload = payload
            yield nw

    def __or__(self, other):
        return "many" in self.payload and other == "multireply"

    def calculate(self, uid, one, two, action):
        if action == "add":
            return [{"uid": uid, "result": one + two}]
        if action == "sub":
            return [{"uid": uid, "result": one - two}]
        if action == "mul":
            return [{"uid": uid, "result": one * two}]
        if action == "many":
            return [{"uid": uid, "result": one, "many": True}, {"uid": uid, "result": two, "many": True}]

    def as_dict(self):
        return {
              "source": None if self.source is sb.NotSpecified else self.source
            , "sequence": None if self.sequence is sb.NotSpecified else self.sequence
            , "target": None if self.target in (None, sb.NotSpecified) else self.serial
            , "payload": self.payload
            , "ack_required": self.ack_required
            , "res_required": self.res_required
            }

def EmptyPacket(one, two, action, **kwargs):
    return Packet(None, None, None, {"uid": str(uuid.uuid1()), "one": one, "two": two, "action": action}, **kwargs)

def Adder(one, two, **kwargs):
    return EmptyPacket(one, two, "add", **kwargs)

def Subtractor(one, two, **kwargs):
    return EmptyPacket(one, two, "sub", **kwargs)

def NoReply(**kwargs):
    return EmptyPacket(None, None, "missing", **kwargs)

def Multiplier(one, two, **kwargs):
    return EmptyPacket(one, two, "mul", **kwargs)

def Many(one, two, **kwargs):
    pkt = EmptyPacket(one, two, "many", **kwargs)

    class Meta:
        multi = MultiOptions(
              lambda req: "multireply"
            , lambda req, res: 2
            )
    pkt.Meta = Meta
    return pkt

class Messages(object):
    @classmethod
    def unpack(kls, data, protocol_register, unknown_ok=False):
        return Packet(**json.loads(base64.b64decode(data)))

class MemoryItem(TransportItem):
    pass

class MemoryTarget(TransportTarget):
    item_kls = lambda s: MemoryItem
    bridge_kls = lambda s: MemoryBridge

class MemoryBridge(TransportBridge):
    Messages = Messages
    default_desired_services = [Services.MEMORY]

    def __init__(self, *args, **kwargs):
        super(MemoryBridge, self).__init__(*args, **kwargs)
        D1 = Device("d073d5000001")
        D2 = Device("d073d5000002")
        D3 = Device("d073d5000003")
        self.devices = [D1, D2, D3]
        self.receivers = {}
        self.connections = {}

    def finish(self):
        super(MemoryBridge, self).finish()
        for target, task in self.receivers.items():
            task.cancel()
        for device in self.devices:
            device.finish()

    async def create_receiver(self, conn, packet, addr):
        if packet.target not in self.receivers:
            async def receive():
                while not self.stop_fut.finished():
                    if conn is True:
                        await asyncio.sleep(0.1)
                    else:
                        nxt = await conn[0].get()
                        self.received_data(nxt, addr, conn)
            self.receivers[packet.target] = hp.async_as_background(receive())

    async def spawn_conn(self, address, backoff=0.05, target=None, timeout=10):
        if address[0] == "255.255.255.255":
            return True
        target = address[0].target
        if target not in self.connections:
            self.connections[target] = address[0].connect()
        return self.connections[target]

    async def write_to_conn(self, conn, addr, packet, bts):
        if conn is not True:
            await conn[1].put(bts)

    async def find_devices(self, broadcast, **kwargs):
        found = {}
        for device in self.devices:
            found[device.target] = (
                  set([(Services.MEMORY, (device, 0))])
                , (device, 0)
                )
        return found

describe AsyncTestCase, "End2End":
    async before_each:
        self.final_future = asyncio.Future()
        self.protocol_register = mock.Mock(name="protocol_register")
        meta = Meta({"final_future": self.final_future, "protocol_register": self.protocol_register}, [])
        self.target = MemoryTarget.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta.at("targets").at("memory"), {})

    async after_each:
        self.final_future.cancel()

    async it "works with a special reference":
        called = []

        class Serials(SpecialReference):
            async def find_serials(s, afr, broadcast, find_timeout):
                called.append(("find_serials", afr, broadcast, find_timeout))
                return await afr.find_devices(broadcast, find_timeout=find_timeout)

        async with ATarget(self.target) as afr:
            msg = Adder(3, 4)
            results = []
            find_timeout = mock.Mock(name="find_timeout")
            async def doit():
                async for info in self.target.script(msg).run_with(Serials(), afr, find_timeout=find_timeout):
                    results.append(info)
            await self.wait_for(doit())

            self.assertEqual(len(afr.devices[0].connections), 1)
            self.assertEqual(len(afr.devices[1].connections), 1)
            self.assertEqual(len(afr.devices[2].connections), 1)

            self.assertEqual(len(afr.devices[0].received), 1)
            self.assertEqual(len(afr.devices[1].received), 1)
            self.assertEqual(len(afr.devices[2].received), 1)

            self.assertEqual(len(results), 3)
            by_target = defaultdict(list)
            for pkt, _, _ in results:
                by_target[pkt.target].append(pkt.payload)
            expected = {
                  afr.devices[0].target: [{"uid": msg.payload["uid"], "result": 7}]
                , afr.devices[1].target: [{"uid": msg.payload["uid"], "result": 7}]
                , afr.devices[2].target: [{"uid": msg.payload["uid"], "result": 7}]
                }
            self.assertEqual(dict(by_target), expected)
            self.assertEqual(len(set(hash(p) for p, _, _ in results)), 3)

            self.assertEqual(called, [("find_serials", afr, False, find_timeout)])

    async it "works":
        async with ATarget(self.target) as afr:
            msg = Adder(3, 4)
            results = []

            async def doit():
                async for info in self.target.script(msg).run_with([afr.devices[0].target], afr):
                    results.append(info)
            await self.wait_for(doit())

            self.assertEqual(len(afr.devices[0].connections), 1)
            self.assertEqual(len(afr.devices[1].connections), 0)
            self.assertEqual(len(afr.devices[2].connections), 0)

            self.assertEqual(len(afr.devices[0].received), 1)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][0].payload["uid"], msg.payload["uid"])
            self.assertEqual(results[0][0].payload["result"], 7)

            msg2 = Subtractor(7, 8, ack_required=True)
            msg3 = Multiplier(8, 8, ack_required=False)
            msg4 = Many(9001, 9002, ack_required=False)
            results = []

            async def doit():
                async for info in self.target.script(Pipeline(msg2, msg3, msg4)).run_with([d.target for d in afr.devices], afr):
                    results.append(info)
            await self.wait_for(doit())

            self.assertEqual(len(afr.devices[0].connections), 1)
            self.assertEqual(len(afr.devices[1].connections), 1)
            self.assertEqual(len(afr.devices[2].connections), 1)

            self.assertEqual(len(afr.devices[0].received), 4)
            self.assertEqual(len(afr.devices[1].received), 3)
            self.assertEqual(len(afr.devices[2].received), 3)

            self.assertEqual(len(results), 12)
            by_target = defaultdict(list)
            for pkt, _, _ in results:
                by_target[pkt.target].append(pkt.payload)
            expected = {
                  afr.devices[0].target: [
                      {"uid": msg2.payload["uid"], "result": -1}
                    , {"uid": msg3.payload["uid"], "result": 64}
                    , {"uid": msg4.payload["uid"], "result": 9001, "many": True}
                    , {"uid": msg4.payload["uid"], "result": 9002, "many": True}
                    ]
                , afr.devices[1].target: [
                      {"uid": msg2.payload["uid"], "result": -1}
                    , {"uid": msg3.payload["uid"], "result": 64}
                    , {"uid": msg4.payload["uid"], "result": 9001, "many": True}
                    , {"uid": msg4.payload["uid"], "result": 9002, "many": True}
                    ]
                , afr.devices[2].target: [
                      {"uid": msg2.payload["uid"], "result": -1}
                    , {"uid": msg3.payload["uid"], "result": 64}
                    , {"uid": msg4.payload["uid"], "result": 9001, "many": True}
                    , {"uid": msg4.payload["uid"], "result": 9002, "many": True}
                    ]
                }

            self.assertEqual(dict(by_target), expected)
            self.assertEqual(len(set(hash(p) for p, _, _ in results)), 9)

    async it "raises a single error if serials is None":
        async with ATarget(self.target) as afr:
            msg = NoReply()

            found = []
            async def doit():
                async for info in self.target.script(msg).run_with(None, broadcast=True, timeout=0.1):
                    found.append(info)

            with self.fuzzyAssertRaisesError(TimedOut, "Waiting for reply to a packet", serial=None):
                await self.wait_for(doit())

            self.assertEqual(found, [])

    async it "raises a single error if only one serial":
        async with ATarget(self.target) as afr:
            msg = NoReply()

            found = []
            async def doit():
                async for info in self.target.script(msg).run_with([afr.devices[0].target], timeout=0.1):
                    found.append(info)

            with self.fuzzyAssertRaisesError(TimedOut, "Waiting for reply to a packet", serial=afr.devices[0].serial):
                await self.wait_for(doit())

            self.assertEqual(found, [])

    async it "raises a RunErrors if multiple serials":
        async with ATarget(self.target) as afr:
            msg = NoReply()

            found = []

            async def doit():
                async for info in self.target.script(msg).run_with([afr.devices[0].target, afr.devices[1].target], timeout=0.1):
                    found.append(info)

            t1 = TimedOut("Waiting for reply to a packet", serial=afr.devices[0].serial)
            t2 = TimedOut("Waiting for reply to a packet", serial=afr.devices[1].serial)
            with self.fuzzyAssertRaisesError(RunErrors, _errors=[t1, t2]):
                await self.wait_for(doit())

            self.assertEqual(found, [])

    async it "doesn't raise errors if a error_catcher is specified":
        async with ATarget(self.target) as afr:
            msg1 = NoReply()
            msg2 = Adder(3, 4)

            errors = []
            results = []

            async def doit():
                async for info in self.target.script([msg1, msg2]).run_with([afr.devices[0].target, afr.devices[1].target], timeout=0.1, error_catcher=errors):
                    results.append(info)

            t1 = TimedOut("Waiting for reply to a packet", serial=afr.devices[0].serial)
            t2 = TimedOut("Waiting for reply to a packet", serial=afr.devices[1].serial)
            await self.wait_for(doit())

            by_target = defaultdict(list)
            for pkt, _, _ in results:
                by_target[pkt.target].append(pkt.payload)
            expected = {
                  afr.devices[0].target: [{"uid": msg2.payload["uid"], "result": 7}]
                , afr.devices[1].target: [{"uid": msg2.payload["uid"], "result": 7}]
                }
            self.assertEqual(dict(by_target), expected)

            self.assertEqual(sorted(errors), sorted([t1, t2]))

    async it "calls error_catcher if it's a function":
        async with ATarget(self.target) as afr:
            msg1 = NoReply()

            errors = []

            def catcher(e):
                errors.append(e)

            async def doit():
                async for _ in self.target.script(msg1).run_with([afr.devices[0].target, afr.devices[1].target], timeout=0.1, error_catcher=catcher):
                    pass

            t1 = TimedOut("Waiting for reply to a packet", serial=afr.devices[0].serial)
            t2 = TimedOut("Waiting for reply to a packet", serial=afr.devices[1].serial)
            await self.wait_for(doit())

            self.assertEqual(sorted(errors), sorted([t1, t2]))
