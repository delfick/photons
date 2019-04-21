# coding: spec

from photons_protocol.packets import dictobj
from photons_protocol.types import Type as T

from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.meta import Meta
from contextlib import contextmanager
from bitarray import bitarray
from unittest import mock
import binascii
import enum
import uuid

describe TestCase, "PacketSpecMixin":
    before_each:
        # packet to work with
        class Group1(dictobj.PacketSpec):
            fields = [("one", T.String), ("two", T.Int16)]

        class Packet(dictobj.PacketSpec):
            fields = [("g1", Group1), ("another", T.Bool)]

        self.Packet = Packet
        self.packet = Packet(one="wat", two=2, another=True)

    describe "pack":
        before_each:
            self.payload = mock.Mock(name="payload")
            self.parent = mock.Mock(name="parent")
            self.serial = mock.Mock(name="serial")
            self.packing_kls = mock.Mock(name="packing_kls")

        it "uses the provided packing_kls":
            res = mock.Mock(name="res")
            self.packing_kls.pack.return_value = res

            r = self.packet.pack(
                  payload=self.payload
                , parent=self.parent
                , serial=self.serial
                , packing_kls=self.packing_kls
                )

            self.assertIs(r, res)
            self.packing_kls.pack.assert_called_once_with(self.packet, self.payload, self.parent, self.serial)

        it "has defaults":
            res = mock.Mock(name="res")
            pack = mock.Mock(name="pack", return_value=res)

            with mock.patch("photons_protocol.packing.PacketPacking.pack", pack):
                self.assertIs(self.packet.pack(), res)

            pack.assert_called_once_with(self.packet, None, None, None)

    describe "unpack":
        before_each:
            self.value = mock.Mock(name="value")
            self.packing_kls = mock.Mock(name="packing_kls")

        it "uses the provided packing_kls":
            res = mock.Mock(name="res")
            self.packing_kls.unpack.return_value = res

            r = self.Packet.unpack(self.value, packing_kls=self.packing_kls)

            self.assertIs(r, res)
            self.packing_kls.unpack.assert_called_once_with(self.Packet, self.value)

        it "has defaults":
            res = mock.Mock(name="res")
            unpack = mock.Mock(name="unpack", return_value=res)

            with mock.patch("photons_protocol.packing.PacketPacking.unpack", unpack):
                self.assertIs(self.Packet.unpack(self.value), res)

            unpack.assert_called_once_with(self.Packet, self.value)

    describe "size_bits":
        it "adds up from Meta.field_types":
            one_typ = mock.Mock(name="one_typ", spec=["size_bits"], size_bits=20)
            two_typ = mock.Mock(name="two_typ", spec=["size_bits"], size_bits=1)
            three_typ = mock.Mock(name="three_typ", spec=["size_bits"], size_bits=100)

            four_typ = mock.Mock(name="four_typ", spec=["size_bits"])
            four_typ.size_bits.return_value = 1000

            five_typ = mock.Mock(name="five_typ", spec=["size_bits"], size_bits=2)

            six_typ = mock.Mock(name="six_typ", spec=["size_bits"])
            six_typ.size_bits.return_value = 10

            # Make us example groups
            class Group1(dictobj.PacketSpec):
                fields = [("one", one_typ), ("two", two_typ)]

            class Group2(dictobj.PacketSpec):
                fields = [("three", three_typ), ("four", four_typ)]

            class Together(dictobj.PacketSpec):
                fields = [("g1", Group1), ("g2", Group2), ("another", "Another")]

                class Another(dictobj.PacketSpec):
                    fields = []

            class Child(Together):
                class Another(dictobj.PacketSpec):
                    fields = [("five", five_typ), ("six", six_typ)]

            values = mock.Mock(name='values')
            self.assertEqual(Group1.size_bits(values), 21)
            self.assertEqual(Group2.size_bits(values), 1100)
            four_typ.size_bits.assert_called_once_with(values)

            self.assertEqual(Together.size_bits(values), 1121)
            self.assertEqual(Child.size_bits(values), 1133)
            six_typ.size_bits.assert_called_once_with(values)

    describe "spec with mocks":
        before_each:
            self.os = mock.Mock(name="one_spec_initd")
            self.one_spec = mock.Mock(name="one_spec", return_value=self.os)
            self.one_typ = mock.Mock(name="one_typ", spec=["spec"])
            self.one_typ.spec = self.one_spec

            self.two_spec = mock.NonCallableMock(name="two_spec")
            self.two_typ = mock.Mock(name="two_typ", spec=["spec"])
            self.two_typ.spec = self.two_spec

            self.ts = mock.Mock(name="three_spec_initd")
            self.three_spec = mock.Mock(name="three_spec", return_value=self.ts)
            self.three_typ = mock.Mock(name="three_typ", spec=["spec"])
            self.three_typ.spec = self.three_spec

            self.four_spec = mock.NonCallableMock(name="four_spec")
            self.four_typ = mock.Mock(name="four_typ", spec=["spec"])
            self.four_typ.spec = self.four_spec

            self.five_spec = mock.NonCallableMock(name="five_spec")
            self.five_typ = mock.Mock(name="five_typ", spec=["spec"])
            self.five_typ.spec = self.five_spec

            self.ss = mock.Mock(name="six_spec_initd")
            self.six_spec = mock.Mock(name="six_spec", return_value=self.ss)
            self.six_typ = mock.Mock(name="six_typ", spec=["spec"])
            self.six_typ.spec = self.six_spec

            # Make us example groups
            class Group1(dictobj.PacketSpec):
                fields = [("one", self.one_typ), ("two", self.two_typ)]

            class Group2(dictobj.PacketSpec):
                fields = [("three", self.three_typ), ("four", self.four_typ)]

            class Together(dictobj.PacketSpec):
                parent_packet = True
                fields = [("g1", Group1), ("g2", Group2), ("another", "Another")]

                class Another(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            class Child(Together):
                class Another(dictobj.PacketSpec):
                    fields = [("five", self.five_typ), ("six", self.six_typ)]

            self.Group1 = Group1
            self.Group2 = Group2
            self.Together = Together
            self.Child = Child

            self.spec = mock.Mock(name='spec')
            self.pkt = mock.Mock(name="pkt")

        @contextmanager
        def patched_packet_spec(self):
            packet_spec = mock.Mock(name="packet_spec", return_value=self.spec)
            with mock.patch("photons_protocol.packets.packet_spec", packet_spec):
                yield packet_spec

        it "it works on a normal PacketSpec":
            with self.patched_packet_spec() as packet_spec:
                self.assertIs(self.Group1.spec(), self.spec)
            packet_spec.assert_called_once_with(self.Group1
                , [("one", self.one_spec), ("two", self.two_spec)]
                , {}
                )

        it "it works on a PacketSpec with groups":
            with self.patched_packet_spec() as packet_spec:
                self.assertIs(self.Together.spec(), self.spec)

            packet_spec.assert_called_once_with(self.Together
                , [ ("one", self.one_spec)
                  , ("two", self.two_spec)
                  , ("three", self.three_spec)
                  , ("four", self.four_spec)
                  , ("another", T.Bytes.spec)
                  ]
                , { "one": "g1"
                  , "two": "g1"
                  , "three": "g2"
                  , "four": "g2"
                  }
                )

        it "it works on a child PacketSpec with string group":
            with self.patched_packet_spec() as packet_spec:
                self.assertIs(self.Child.spec(), self.spec)

            packet_spec.assert_called_once_with(self.Child
                , [ ("one", self.one_spec)
                  , ("two", self.two_spec)
                  , ("three", self.three_spec)
                  , ("four", self.four_spec)
                  , ("five", self.five_spec)
                  , ("six", self.six_spec)
                  ]
                , { "one": "g1"
                  , "two": "g1"
                  , "three": "g2"
                  , "four": "g2"
                  , "five": "another"
                  , "six": "another"
                  }
                )

    describe "spec without mocks":
        before_each:
            # Make our packet to test with
            class Group1(dictobj.PacketSpec):
                fields = [
                      ("one", T.Bool)
                    ]

            class Group2(dictobj.PacketSpec):
                fields = [
                      ( "two", T.Int16.transform(
                              lambda _, v: (int(str(v).split(".")[0]) << 0x10) + int(str(v).split(".")[1])
                            , lambda v: float("{0}.{1}".format(v >> 0x10, v & 0xFF))
                            )
                        )
                    , ( "mod", T.String.default(lambda p: "{0}.modified".format(p["two"])))
                    , ( "sb", T.Int8)
                    , ( "bts", T.Bytes(lambda p: p["sb"]))
                    ]

            class Together(dictobj.PacketSpec):
                parent_packet = True
                fields = [("g1", Group1), ("g2", Group2), ("three", T.String)]

            self.Together = Together

        it "works":
            spec = self.Together.spec()
            t = spec.normalise(Meta.empty()
                , {"one": False, "two": 1.2, "three": b"whatever\x00\x00", "sb": 24, "bts": b"\x01"}
                )
            self.assertIs(t.one, False)
            self.assertEqual(t.two, 1.2)
            self.assertEqual(t.mod, "1.2.modified")
            self.assertEqual(t.three, "whatever")
            self.assertEqual(t.sb, 24)
            self.assertEqual(t.bts, b"\x01\x00\x00")

            self.assertEqual(t.actual("two"), 65538)
            self.assertEqual(t.actual("three").tobytes(), b"whatever\x00\x00")

        it "works when value given as groups":
            spec = self.Together.spec()
            t = spec.normalise(Meta.empty()
                , { "g1": { "one": False }
                  , "g2": { "sb": 24, "bts": b"\x01", "two": 1.2}
                  , "three": b"whatever\x00\x00"
                  }
                )

            self.assertIs(t.one, False)
            self.assertEqual(t.two, 1.2)
            self.assertEqual(t.mod, "1.2.modified")
            self.assertEqual(t.three, "whatever")
            self.assertEqual(t.sb, 24)
            self.assertEqual(t.bts, b"\x01\x00\x00")

            self.assertEqual(t.actual("two"), 65538)
            self.assertEqual(t.actual("three").tobytes(), b"whatever\x00\x00")

    describe "actual":
        it "uses __getitem__ with do_spec of False":
            key = mock.Mock(name="key")
            val = mock.Mock(name="val")
            fake__getiem__ = mock.Mock(name="__getitem__", return_value=val)

            with mock.patch.object(self.packet, "__getitem__", fake__getiem__):
                self.assertIs(self.packet.actual(key), val)

            fake__getiem__.assert_called_once_with(key, do_spec=False)

        it "works":
            b = bitarray(endian="little")
            b.frombytes("wat".encode())
            b = b + bitarray('0' * 10)

            class Thing(dictobj.PacketSpec):
                fields = [("one", T.String)]

            thing = Thing(one=b)
            self.assertEqual(thing.actual("one"), b)
            self.assertEqual(thing.one, "wat")

    describe "is_dynamic":
        it "says no if no field allows callable":
            class P(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            p = P(one=True, two="three")
            assert not p.is_dynamic

        it "says no if a field allows callable but has not a callable alue":
            class P(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String.allow_callable())]

            p = P(one=True, two="three")
            assert not p.is_dynamic

        it "says yes if a field allows callable and has a callable alue":
            class P(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String.allow_callable())]

            p = P(one=True, two=lambda *args: "three")
            assert p.is_dynamic

    describe "__contains__":
        it "says yes if the field is on the packet":
            class P(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            p = P(one=True, two=lambda *args: "three")
            assert "one" in p
            assert "three" not in p

        it "says yes if the field is in a group":
            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P(one=True, two=lambda *args: "three")
            assert "one" in p
            assert "three" not in p

        it "says yes if the field is a group":
            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P(one=True, two=lambda *args: "three")
            assert "g" in p

    describe "cloning":
        it "works":
            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P(one=True, two=b"wat")
            self.assertEqual(sorted(p.items()), sorted([("one", True), ("two", b"wat")]))
            self.assertEqual(p.two, "wat")

            clone = p.clone()
            assert clone is not p

            self.assertEqual(sorted(clone.items()), sorted([("one", True), ("two", b"wat")]))
            self.assertEqual(clone.two, "wat")

            clone.two = "hello"
            self.assertEqual(p.two, "wat")

        it "works with payload overrides":
            for_packing = str(uuid.uuid1())
            for_user = str(uuid.uuid1())

            called = []

            def pack_t_sideeffect(p, v):
                if v is for_user:
                    called.append("pack")
                    return for_packing
                else:
                    return v

            def unpack_t_sideeffect(v):
                if v is for_packing:
                    called.append("unpack")
                    return for_user
                else:
                    return v

            pack_t = mock.Mock(name="pack_transform", side_effect=pack_t_sideeffect)
            unpack_t = mock.Mock(name="unpack_transform", side_effect=unpack_t_sideeffect)

            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String.transform(pack_t, unpack_t))]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P(one=True, two=b"wat")
            self.assertEqual(sorted(p.items()), sorted([("one", True), ("two", b"wat")]))
            self.assertEqual(p.two, "wat")

            self.assertEqual(called, [])

            clone = p.clone(overrides={"two": for_user})
            self.assertEqual(called, ["pack"])
            assert clone is not p

            self.assertEqual(sorted(clone.items()), sorted([("one", True), ("two", for_packing)]))

            self.assertEqual(called, ["pack"])
            self.assertEqual(clone.two, for_user)
            self.assertEqual(called, ["pack", "unpack"])

    describe "Simplify":
        it "creates a parent with a packed payload and filled in fields":
            val = str(uuid.uuid1())
            cb = mock.Mock(name="cb", return_value=val)

            cb2 = mock.Mock(name="cb2", return_value=65)

            class G1(dictobj.PacketSpec):
                fields = [
                      ("one", T.Bool)
                    , ("two", T.String)
                    , ("cb", T.String.allow_callable())
                    ]

            class G2(dictobj.PacketSpec):
                fields = [
                      ("typ", T.Int16.default(lambda pkt: pkt.Payload.message_type))
                    ]

            class P(dictobj.PacketSpec):
                parent_packet = True

                fields = [("g1", G1), ('g2', G2), ('payload', 'Payload')]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            class CPayload(dictobj.PacketSpec):
                message_type = 25

                fields = [
                      ("three", T.Int16)
                    , ("four", T.Bool)
                    , ("cb2", T.Int8.allow_callable())
                    ]

            class Child(P):
                parent_packet = False
                Payload = CPayload
            Child.Meta.parent = P

            pkt = Child(one=True, two="wat", three=16, four=True, cb=cb, cb2=cb2)
            serial = mock.Mock(name='serial')
            smpl = pkt.simplify(serial=serial)

            self.assertIs(type(smpl), P)
            self.assertEqual(sorted(smpl.items())
                , sorted(
                    [ ("one", True)
                    , ("two", "wat")
                    , ("typ", 25)
                    , ("cb", val)
                    , ("payload", bitarray('0000100000000000110000010', endian="little"))
                    ]
                  )
                )

            cb.assert_called_once_with(pkt, serial)

    describe "tobytes":
        it "just packs if payload is already simple":
            class P(dictobj.PacketSpec):
                fields = [("payload", T.Bytes)]

            b = bitarray(endian="little")
            b.frombytes(binascii.unhexlify("d073d5"))

            serial = mock.Mock(name="serial")

            pack = mock.Mock(name="pack", return_value=b)
            p = P(payload="d073d5")
            with mock.patch.object(p, "pack", pack):
                self.assertEqual(p.tobytes(serial), b.tobytes())

            pack.assert_called_once_with(payload=b)

        it "simplifies first if payload is not str, bytes or bitarray":
            class P(dictobj.PacketSpec):
                fields = [("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    fields = []

            class Child(P):
                class Payload(dictobj.PacketSpec):
                    fields = [("one", T.Int8)]

            val = str(uuid.uuid1())
            packd = mock.Mock(name="packd")
            packd.tobytes.return_value = val

            simple = mock.Mock(name="simple")
            simple.pack.return_value = packd

            simplify = mock.Mock(name="simplify", return_value=simple)
            serial = mock.Mock(name="serial")

            p = Child(one=65)
            with mock.patch.object(p, "simplify", simplify):
                self.assertEqual(p.tobytes(serial), val)

            simplify.assert_called_once_with(serial)
            simple.pack.assert_called_once_with()
            packd.tobytes.assert_called_once_with()

    describe "as_dict":
        it "returns groups with transformed values":
            def pack_t(p, v):
                return v + 2

            def unpack_t(v):
                return v - 2

            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.Int8.transform(pack_t, unpack_t))]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            dct = P(one=True, two=1).as_dict()
            self.assertEqual(dct, {"g": {"one": True, "two": 1}})

        it "returns groups with untransformed values if asked not to transform":
            def pack_t(p, v):
                return v + 2

            def unpack_t(v):
                return v - 2

            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.Int8.transform(pack_t, unpack_t))]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            dct = P(one=True, two=1).as_dict(transformed=False)
            self.assertEqual(dct, {"g": {"one": True, "two": 3}})

        it "includes payload as simple if we are a parent_packet":
            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool)]

            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("g", G), ("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            payload = "d073d5"
            b = bitarray(endian="little")
            b.frombytes(binascii.unhexlify(payload))

            dct = P(one=True, payload=b).as_dict()
            self.assertEqual(dct, {"g": {"one": True}, "payload": b.tobytes()})

        it "includes payload as complex if we are not a parent_packet":
            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool)]

            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("g", G), ("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            class Child(P):
                parent_packet = False

                class Payload(dictobj.PacketSpec):
                    fields = [("two", T.Int8)]

            dct = Child(one=True, two=65).as_dict()
            self.assertEqual(dct, {"g": {"one": True}, "payload": {"two": 65}})

        it "converts lists":
            class P(dictobj.PacketSpec):
                fields = [
                      ( "one", T.Int16.transform(
                            lambda _, v: int(v / 1000)
                          , lambda v: v * 1000
                          )
                       )
                    ]

            class Q(dictobj.PacketSpec):
                fields = [("things", T.Bytes(16 * 3).many(lambda pkt: P))]

            q = Q.empty_normalise(things=[{"one": 1000}, {"one": 2000}, {"one": 0}])
            self.assertEqual(q.things[0].actual("one"), 1)
            self.assertEqual(q.things[1].actual("one"), 2)
            self.assertEqual(q.things[2].actual("one"), 0)
            self.assertEqual(q.as_dict(), {"things": [{"one": 1000}, {"one": 2000}, {"one": 0}]})

    describe "__repr__":
        it "converts bytes and bitarray to hexlified":
            payload = "d073d5"
            b = bitarray(endian="little")

            payloadb = binascii.unhexlify(payload)
            b.frombytes(payloadb)

            class P(dictobj.PacketSpec):
                fields = [("payload", T.Bytes)]

            p = P(payload=payload)

            as_dict = mock.Mock(name='as_dict', return_value={"payload": b})
            with mock.patch.object(p, "as_dict", as_dict):
                self.assertEqual(repr(p), '{"payload": "d073d5"}')

            as_dict = mock.Mock(name='as_dict', return_value={"payload": payloadb})
            with mock.patch.object(p, "as_dict", as_dict):
                self.assertEqual(repr(p), '{"payload": "d073d5"}')

        it "reprs what isn't jsonfiable":
            class E(enum.Enum):
                ONE = 1

            class P(dictobj.PacketSpec):
                fields = [("one", T.Int8.enum(E)), ("two", T.Bool)]

            p = P(one=E.ONE, two=True)
            self.assertEqual(p.as_dict(), {"one": E.ONE, "two": True})
            self.assertEqual(repr(p), '{"one": "<E.ONE: 1>", "two": true}')

    describe "normalising":
        it "uses the spec on the kls":
            class P(dictobj.PacketSpec):
                fields = []

            val = mock.Mock(name="val")
            normalised = mock.Mock(name="normalised")
            meta = mock.Mock(name="meta")

            initd_spec = mock.Mock(name="initd_spec")
            initd_spec.normalise.return_value = normalised
            spec = mock.Mock(name="spec", return_value=initd_spec)

            with mock.patch.object(P, "spec", spec):
                self.assertIs(P.normalise(meta, val), normalised)

            spec.assert_called_once_with()
            initd_spec.normalise.assert_called_once_with(meta, val)

        it "allows kwargs val with empty_normalise":
            class P(dictobj.PacketSpec):
                fields = []

            empty = Meta.empty()

            one = mock.Mock(name="one")
            two = mock.Mock(name="two")
            val = {"one": one, "two": two}

            normalised = mock.Mock(name="normalised")
            meta = mock.Mock(name="meta")

            initd_spec = mock.Mock(name="initd_spec")
            initd_spec.normalise.return_value = normalised
            spec = mock.Mock(name="spec", return_value=initd_spec)

            with mock.patch.object(P, "spec", spec):
                self.assertIs(P.empty_normalise(**val), normalised)

            spec.assert_called_once_with()
            initd_spec.normalise.assert_called_once_with(empty, val)
