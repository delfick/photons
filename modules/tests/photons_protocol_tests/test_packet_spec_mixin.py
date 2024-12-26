import binascii
import enum
import uuid
from contextlib import contextmanager
from unittest import mock

import pytest
from bitarray import bitarray
from delfick_project.norms import Meta
from photons_app import helpers as hp
from photons_protocol.packets import dictobj
from photons_protocol.types import Type as T


@pytest.fixture()
def V():
    class V:
        value = mock.Mock(name="value")
        payload = mock.Mock(name="payload")
        parent = mock.Mock(name="parent")
        serial = mock.Mock(name="serial")
        packing_kls = mock.Mock(name="packing_kls")

    return V()


class TestPacketSpecMixin:
    class TestSimple:
        @pytest.fixture()
        def Group1(self):
            class Group1(dictobj.PacketSpec):
                fields = [("one", T.String), ("two", T.Int16)]

            return Group1

        @pytest.fixture()
        def Packet(self, Group1):
            class Packet(dictobj.PacketSpec):
                fields = [("g1", Group1), ("another", T.Bool)]

            return Packet

        @pytest.fixture()
        def packet(self, Packet):
            return Packet(one="wat", two=2, another=True)

        class TestPack:
            def test_it_uses_the_provided_packing_kls(self, packet, V):
                res = mock.Mock(name="res")
                V.packing_kls.pack.return_value = res

                r = packet.pack(payload=V.payload, parent=V.parent, serial=V.serial, packing_kls=V.packing_kls)

                assert r is res
                V.packing_kls.pack.assert_called_once_with(packet, V.payload, V.parent, V.serial)

            def test_it_has_defaults(self, packet):
                res = mock.Mock(name="res")
                pack = mock.Mock(name="pack", return_value=res)

                with mock.patch("photons_protocol.packing.PacketPacking.pack", pack):
                    assert packet.pack() is res

                pack.assert_called_once_with(packet, None, None, None)

    class TestSizeBits:
        def test_it_adds_up_from_Metafield_types(self):
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
                fields = [("one", one_typ), ("two", T.Bytes(1).multiple(3, kls=two_typ))]

            class Group2(dictobj.PacketSpec):
                fields = [("three", T.Bytes(100).multiple(3, kls=three_typ)), ("four", four_typ)]

            class Together(dictobj.PacketSpec):
                fields = [("g1", Group1), ("g2", Group2), ("another", "Another")]

                class Another(dictobj.PacketSpec):
                    fields = []

            class Child(Together):
                class Another(dictobj.PacketSpec):
                    fields = [("five", five_typ), ("six", six_typ)]

            values = mock.Mock(name="values")
            assert Group1.size_bits(values) == 23
            assert Group2.size_bits(values) == 1300
            four_typ.size_bits.assert_called_once_with(values)

            assert Together.size_bits(values) == 1323
            assert Child.size_bits(values) == 1335
            six_typ.size_bits.assert_called_once_with(values)

    class TestSpecWithMocks:
        @pytest.fixture()
        def V(self):
            class V:
                os = mock.Mock(name="one_spec_initd")
                pkt = mock.Mock(name="pkt")
                spec = mock.Mock(name="spec")

                @hp.memoized_property
                def one_spec(s):
                    return mock.Mock(name="one_spec", return_value=s.os)

                @hp.memoized_property
                def one_typ(s):
                    one_typ = mock.Mock(name="one_typ", spec=["spec"])
                    one_typ.spec = s.one_spec
                    return one_typ

                @hp.memoized_property
                def two_spec(s):
                    return mock.NonCallableMock(name="two_spec")

                @hp.memoized_property
                def two_typ(s):
                    two_typ = mock.Mock(name="two_typ", spec=["spec"])
                    two_typ.spec = s.two_spec
                    return two_typ

                @hp.memoized_property
                def three_spec(s):
                    ts = mock.Mock(name="three_spec_initd")
                    return mock.Mock(name="two_spec", return_value=ts)

                @hp.memoized_property
                def three_typ(s):
                    three_typ = mock.Mock(name="three_typ", spec=["spec"])
                    three_typ.spec = s.three_spec
                    return three_typ

                @hp.memoized_property
                def four_spec(s):
                    return mock.NonCallableMock(name="four_spec")

                @hp.memoized_property
                def four_typ(s):
                    four_typ = mock.Mock(name="four_typ", spec=["spec"])
                    four_typ.spec = s.four_spec
                    return four_typ

                @hp.memoized_property
                def five_spec(s):
                    return mock.NonCallableMock(name="five_spec")

                @hp.memoized_property
                def five_typ(s):
                    five_typ = mock.Mock(name="five_typ", spec=["spec"])
                    five_typ.spec = s.five_spec
                    return five_typ

                @hp.memoized_property
                def six_spec(s):
                    ss = mock.Mock(name="six_spec_initd")
                    return mock.Mock(name="two_spec", return_value=ss)

                @hp.memoized_property
                def six_typ(s):
                    six_typ = mock.Mock(name="six_typ", spec=["spec"])
                    six_typ.spec = s.six_spec
                    return six_typ

                @hp.memoized_property
                def Group1(s):
                    class Group1(dictobj.PacketSpec):
                        fields = [("one", s.one_typ), ("two", s.two_typ)]

                    return Group1

                @hp.memoized_property
                def Group2(s):
                    class Group2(dictobj.PacketSpec):
                        fields = [("three", s.three_typ), ("four", s.four_typ)]

                    return Group2

                @hp.memoized_property
                def Together(s):
                    class Together(dictobj.PacketSpec):
                        parent_packet = True
                        fields = [("g1", s.Group1), ("g2", s.Group2), ("another", "Another")]

                        class Another(dictobj.PacketSpec):
                            message_type = 0
                            fields = []

                    return Together

                @hp.memoized_property
                def Child(s):
                    class Child(s.Together):
                        class Another(dictobj.PacketSpec):
                            fields = [("five", s.five_typ), ("six", s.six_typ)]

                    return Child

                @contextmanager
                def patched_packet_spec(s):
                    packet_spec = mock.Mock(name="packet_spec", return_value=s.spec)
                    with mock.patch("photons_protocol.packets.packet_spec", packet_spec):
                        yield packet_spec

            return V()

        def test_it_it_works_on_a_normal_PacketSpec(self, V):
            with V.patched_packet_spec() as packet_spec:
                assert V.Group1.spec() is V.spec
            packet_spec.assert_called_once_with(V.Group1, [("one", V.one_spec), ("two", V.two_spec)], {})

        def test_it_it_works_on_a_PacketSpec_with_groups(self, V):
            with V.patched_packet_spec() as packet_spec:
                assert V.Together.spec() is V.spec

            packet_spec.assert_called_once_with(
                V.Together,
                [
                    ("one", V.one_spec),
                    ("two", V.two_spec),
                    ("three", V.three_spec),
                    ("four", V.four_spec),
                    ("another", T.Bytes.spec),
                ],
                {"one": "g1", "two": "g1", "three": "g2", "four": "g2"},
            )

        def test_it_it_works_on_a_child_PacketSpec_with_string_group(self, V):
            with V.patched_packet_spec() as packet_spec:
                assert V.Child.spec() is V.spec

            packet_spec.assert_called_once_with(
                V.Child,
                [
                    ("one", V.one_spec),
                    ("two", V.two_spec),
                    ("three", V.three_spec),
                    ("four", V.four_spec),
                    ("five", V.five_spec),
                    ("six", V.six_spec),
                ],
                {
                    "one": "g1",
                    "two": "g1",
                    "three": "g2",
                    "four": "g2",
                    "five": "another",
                    "six": "another",
                },
            )

    class TestSpecWithoutMocks:
        @pytest.fixture()
        def V(self):
            class V:
                class Group1(dictobj.PacketSpec):
                    fields = [("one", T.Bool)]

                class Group2(dictobj.PacketSpec):
                    fields = [
                        (
                            "two",
                            T.Int16.transform(
                                lambda _, v: (int(str(v).split(".")[0]) << 0x10) + int(str(v).split(".")[1]),
                                lambda _, v: float(f"{v >> 0x10}.{v & 0xFF}"),
                            ),
                        ),
                        ("mod", T.String.default(lambda p: f"{p['two']}.modified")),
                        ("sb", T.Int8),
                        ("bts", T.Bytes(lambda p: p["sb"])),
                    ]

                @hp.memoized_property
                def Together(s):
                    class Together(dictobj.PacketSpec):
                        parent_packet = True
                        fields = [("g1", s.Group1), ("g2", s.Group2), ("three", T.String)]

                    return Together

            return V()

        def test_it_works(self, V):
            spec = V.Together.spec()
            t = spec.normalise(
                Meta.empty(),
                {"one": False, "two": 1.2, "three": b"whatever\x00\x00", "sb": 24, "bts": b"\x01"},
            )
            assert t.one is False
            assert t.two == 1.2
            assert t.mod == "1.2.modified"
            assert t.three == "whatever"
            assert t.sb == 24
            assert t.bts == b"\x01\x00\x00"

            assert t.actual("two") == 65538
            assert t.actual("three").tobytes() == b"whatever\x00\x00"

        def test_it_works_when_value_given_as_groups(self, V):
            spec = V.Together.spec()
            t = spec.normalise(
                Meta.empty(),
                {
                    "g1": {"one": False},
                    "g2": {"sb": 24, "bts": b"\x01", "two": 1.2},
                    "three": b"whatever\x00\x00",
                },
            )

            assert t.one is False
            assert t.two == 1.2
            assert t.mod == "1.2.modified"
            assert t.three == "whatever"
            assert t.sb == 24
            assert t.bts == b"\x01\x00\x00"

            assert t.actual("two") == 65538
            assert t.actual("three").tobytes() == b"whatever\x00\x00"

    class TestActual:
        def test_it_uses_getitem_with_do_spec_of_False(self):
            key = mock.Mock(name="key")
            val = mock.Mock(name="val")
            fake__getitem__ = mock.Mock(name="__getitem__", return_value=val)

            class Packet(dictobj.PacketSpec):
                fields = [("one", T.String)]

            packet = Packet(one="asdf")

            with mock.patch.object(packet, "__getitem__", fake__getitem__):
                assert packet.actual(key) is val

            fake__getitem__.assert_called_once_with(key, do_spec=False)

        def test_it_works(self):
            b = bitarray(endian="little")
            b.frombytes(b"wat")
            b = b + bitarray("0" * 10)

            class Thing(dictobj.PacketSpec):
                fields = [("one", T.String)]

            thing = Thing(one=b)
            assert thing.actual("one") == b
            assert thing.one == "wat"

    class TestIsDynamic:
        def test_it_says_no_if_no_field_allows_callable(self):
            class P(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            p = P(one=True, two="three")
            assert not p.is_dynamic

        def test_it_says_no_if_a_field_allows_callable_but_has_not_a_callable_alue(self):
            class P(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String.allow_callable())]

            p = P(one=True, two="three")
            assert not p.is_dynamic

        def test_it_says_yes_if_a_field_allows_callable_and_has_a_callable_alue(self):
            class P(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String.allow_callable())]

            p = P(one=True, two=lambda *args: "three")
            assert p.is_dynamic

    class TestContains:
        def test_it_says_yes_if_the_field_is_on_the_packet(self):
            class P(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            p = P(one=True, two=lambda *args: "three")
            assert "one" in p
            assert "three" not in p

        def test_it_says_yes_if_the_field_is_in_a_group(self):
            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P(one=True, two=lambda *args: "three")
            assert "one" in p
            assert "three" not in p

        def test_it_says_yes_if_the_field_is_a_group(self):
            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P(one=True, two=lambda *args: "three")
            assert "g" in p

    class TestCloning:
        def test_it_works(self):
            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P(one=True, two=b"wat")
            assert sorted(p.actual_items()) == sorted([("one", True), ("two", b"wat")])
            assert p.two == "wat"

            clone = p.clone()
            assert clone is not p

            assert sorted(clone.actual_items()) == sorted([("one", True), ("two", b"wat")])
            assert clone.two == "wat"

            clone.two = "hello"
            assert p.two == "wat"

        def test_it_works_with_payload_overrides(self):
            for_packing = str(uuid.uuid1())
            for_user = str(uuid.uuid1())

            called = []

            def pack_t_sideeffect(p, v):
                if v is for_user:
                    called.append("pack")
                    return for_packing
                else:
                    return v

            def unpack_t_sideeffect(p, v):
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
            assert sorted(p.actual_items()) == sorted([("one", True), ("two", b"wat")])
            assert p.two == "wat"

            assert called == []

            clone = p.clone(overrides={"two": for_user})
            assert called == ["pack"]
            assert clone is not p

            assert sorted(clone.actual_items()) == sorted([("one", True), ("two", for_packing)])

            assert called == ["pack"]
            assert clone.two == for_user
            assert called == ["pack", "unpack"]

    class TestSimplify:
        def test_it_creates_a_parent_with_a_packed_payload_and_filled_in_fields(self):
            val = str(uuid.uuid1())
            cb = mock.Mock(name="cb", return_value=val)

            cb2 = mock.Mock(name="cb2", return_value=65)

            class G1(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.String), ("cb", T.String.allow_callable())]

            class G2(dictobj.PacketSpec):
                fields = [("typ", T.Int16.default(lambda pkt: pkt.Payload.message_type))]

            class P(dictobj.PacketSpec):
                parent_packet = True

                fields = [("g1", G1), ("g2", G2), ("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            class CPayload(dictobj.PacketSpec):
                message_type = 25

                fields = [("three", T.Int16), ("four", T.Bool), ("cb2", T.Int8.allow_callable())]

            class Child(P):
                parent_packet = False
                Payload = CPayload

            Child.Meta.parent = P

            pkt = Child(one=True, two="wat", three=16, four=True, cb=cb, cb2=cb2)
            serial = mock.Mock(name="serial")
            smpl = pkt.simplify(serial=serial)

            assert type(smpl) is P
            assert sorted(smpl.actual_items()) == (
                sorted(
                    [
                        ("one", True),
                        ("two", "wat"),
                        ("typ", 25),
                        ("cb", val),
                        ("payload", bitarray("0000100000000000110000010", endian="little")),
                    ]
                )
            )

            cb.assert_called_once_with(pkt, serial)

    class TestTobytes:
        def test_it_just_packs_if_payload_is_already_simple(self):
            class P(dictobj.PacketSpec):
                fields = [("payload", T.Bytes)]

            b = bitarray(endian="little")
            b.frombytes(binascii.unhexlify("d073d5"))

            serial = mock.Mock(name="serial")

            pack = mock.Mock(name="pack", return_value=b)
            p = P(payload="d073d5")
            with mock.patch.object(p, "pack", pack):
                assert p.tobytes(serial) == b.tobytes()

            pack.assert_called_once_with(payload=b)

        def test_it_simplifies_first_if_payload_is_not_str_bytes_or_bitarray(self):
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
                assert p.tobytes(serial) == val

            simplify.assert_called_once_with(serial)
            simple.pack.assert_called_once_with()
            packd.tobytes.assert_called_once_with()

    class TestAsDict:
        def test_it_returns_groups_with_transformed_values(self):
            def pack_t(p, v):
                return v + 2

            def unpack_t(p, v):
                return v - 2

            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.Int8.transform(pack_t, unpack_t))]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            dct = P(one=True, two=1).as_dict()
            assert dct == {"g": {"one": True, "two": 1}}

        def test_it_returns_groups_with_untransformed_values_if_asked_not_to_transform(self):
            def pack_t(p, v):
                return v + 2

            def unpack_t(p, v):
                return v - 2

            class G(dictobj.PacketSpec):
                fields = [("one", T.Bool), ("two", T.Int8.transform(pack_t, unpack_t))]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            dct = P(one=True, two=1).as_dict(transformed=False)
            assert dct == {"g": {"one": True, "two": 3}}

        def test_it_includes_payload_as_simple_if_we_are_a_parent_packet(self):
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
            assert dct == {"g": {"one": True}, "payload": b.tobytes()}

        def test_it_includes_payload_as_complex_if_we_are_not_a_parent_packet(self):
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
            assert dct == {"g": {"one": True}, "payload": {"two": 65}}

        def test_it_converts_lists(self):
            class P(dictobj.PacketSpec):
                fields = [("one", T.Int16.transform(lambda _, v: int(v / 1000), lambda _, v: v * 1000))]

            class Q(dictobj.PacketSpec):
                fields = [("things", T.Bytes(16).multiple(3, kls=lambda pkt: P))]

            q = Q.create(things=[{"one": 1000}, {"one": 2000}, {"one": 0}])
            assert q.things[0].actual("one") == 1
            assert q.things[1].actual("one") == 2
            assert q.things[2].actual("one") == 0
            assert q.as_dict() == {"things": [P(one=1000), P(one=2000), P(one=0)]}

    class TestRepr:
        def test_it_converts_bytes_and_bitarray_to_hexlified(self):
            payload = "d073d5"
            b = bitarray(endian="little")

            payloadb = binascii.unhexlify(payload)
            b.frombytes(payloadb)

            class P(dictobj.PacketSpec):
                fields = [("payload", T.Bytes)]

            p = P(payload=payload)

            as_dict = mock.Mock(name="as_dict", return_value={"payload": b})
            with mock.patch.object(p, "as_dict", as_dict):
                assert repr(p) == '{"payload": "d073d5"}'

            as_dict = mock.Mock(name="as_dict", return_value={"payload": payloadb})
            with mock.patch.object(p, "as_dict", as_dict):
                assert repr(p) == '{"payload": "d073d5"}'

        def test_it_reprs_what_isnt_jsonfiable(self):
            class E(enum.Enum):
                ONE = 1

            class P(dictobj.PacketSpec):
                fields = [("one", T.Int8.enum(E)), ("two", T.Bool)]

            p = P(one=E.ONE, two=True)
            assert p.as_dict() == {"one": E.ONE, "two": True}
            assert repr(p) == '{"one": "<E.ONE: 1>", "two": true}'

    class TestCreating:
        def test_it_uses_the_spec_on_the_kls(self):
            class P(dictobj.PacketSpec):
                fields = []

            val = mock.Mock(name="val")
            normalised = mock.Mock(name="normalised")

            initd_spec = mock.Mock(name="initd_spec")
            initd_spec.normalise.return_value = normalised
            spec = mock.Mock(name="spec", return_value=initd_spec)

            with mock.patch.object(P, "spec", spec):
                assert P.create(val) is normalised

            spec.assert_called_once_with()
            initd_spec.normalise.assert_called_once_with(mock.ANY, val)

        def test_it_allows_kwargs_val_with_create(self):
            class P(dictobj.PacketSpec):
                fields = []

            empty = Meta.empty()

            one = mock.Mock(name="one")
            two = mock.Mock(name="two")
            val = {"one": one, "two": two}

            normalised = mock.Mock(name="normalised")

            initd_spec = mock.Mock(name="initd_spec")
            initd_spec.normalise.return_value = normalised
            spec = mock.Mock(name="spec", return_value=initd_spec)

            with mock.patch.object(P, "spec", spec):
                assert P.create(**val) is normalised

            spec.assert_called_once_with()
            initd_spec.normalise.assert_called_once_with(empty, val)
