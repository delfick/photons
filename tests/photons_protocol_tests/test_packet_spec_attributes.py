# coding: spec

from photons_protocol.packets import dictobj, PacketSpecMixin, Initial, Optional, Information
from photons_protocol.types import Type as T

from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb, Meta
from bitarray import bitarray
from unittest import mock
import binascii
import pytest
import uuid

describe "Packet attributes":
    describe "__getitem__":
        it "raises KeyError if the key is not on the packet":

            class P(dictobj.PacketSpec):
                fields = []

            p = P()
            with assertRaises(KeyError):
                p["one"]

        it "does not raise KeyError if the key is a group":

            class P(dictobj.PacketSpec):
                fields = [("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    fields = []

            p = P()
            assert p["payload"] == P.Payload()

        it "uses sb.NotSpecified if there is no value for the key":

            class P(dictobj.PacketSpec):
                fields = [("one", T.String)]

            val = mock.Mock(name="val")
            getitem_spec = mock.Mock(name="getitem_spec", return_value=val)

            p = P()
            with mock.patch.object(p, "getitem_spec", getitem_spec):
                assert p["one"] is val

            getitem_spec.assert_called_once_with(
                T.String, "one", sb.NotSpecified, None, None, True, False, True
            )

        it "uses found value if there is a value for the key":

            class P(dictobj.PacketSpec):
                fields = [("one", T.String)]

            v = mock.Mock(name="v")
            val = mock.Mock(name="val")
            getitem_spec = mock.Mock(name="getitem_spec", return_value=val)

            p = P(one=v)
            with mock.patch.object(p, "getitem_spec", getitem_spec):
                assert p["one"] is val

            getitem_spec.assert_called_once_with(T.String, "one", v, None, None, True, False, True)

        it "passes along information provided to getitem_spec":

            class P(dictobj.PacketSpec):
                fields = [("one", T.String)]

            do_transform = mock.Mock(name="do_transform")
            parent = mock.Mock(name="parent")
            serial = mock.Mock(name="serial")
            allow_bitarray = mock.Mock(name="allow_bitarray")
            unpacking = mock.Mock(name="unpacking")

            options = dict(
                do_transform=do_transform,
                parent=parent,
                serial=serial,
                allow_bitarray=allow_bitarray,
                unpacking=unpacking,
            )

            v = mock.Mock(name="v")
            val = mock.Mock(name="val")
            getitem_spec = mock.Mock(name="getitem_spec", return_value=val)

            p = P(one=v)
            with mock.patch.object(p, "getitem_spec", getitem_spec):
                assert p.__getitem__("one", **options) is val

            getitem_spec.assert_called_once_with(
                T.String, "one", v, parent, serial, do_transform, allow_bitarray, unpacking
            )

        it "returns empty payload as a bitarray":

            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            b = bitarray(endian="little")
            b.frombytes(binascii.unhexlify("d073d5"))

            for val in (b, binascii.unhexlify("d073d5"), "d073d5"):
                assert P(payload=val).payload == b.tobytes()
                assert P(payload=val).__getitem__("payload", allow_bitarray=True) == b

        it "returns nonempty payload as that payload":

            class P(dictobj.PacketSpec):
                parent_packet = True
                fields = [("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    message_type = 0
                    fields = []

            class Child(P):
                parent_packet = False

                class Payload(dictobj.PacketSpec):
                    message_type = 25
                    fields = [("one", T.Bool)]

            assert Child(one=True).payload == Child.Payload(one=True)

        it "returns groups as filled in":

            class G(dictobj.PacketSpec):
                fields = [
                    ("one", T.Bool.default(lambda p: True)),
                    ("two", T.Int8),
                    ("three", T.Int8.default(lambda p: p.two + 1)),
                ]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            g = P(two=3).g
            assert sorted(g.actual_items()) == sorted([("one", True), ("two", 3), ("three", 4)])
            assert type(g) == G

        it "does not use getitem_spec if do_spec is False":

            class P(dictobj.PacketSpec):
                fields = [("one", T.String)]

            getitem_spec = mock.Mock(name="getitem_spec")

            p = P()
            with mock.patch.object(p, "getitem_spec", getitem_spec):
                assert p.__getitem__("one", do_spec=False) is sb.NotSpecified

            v = mock.Mock(name="v")
            p = P(one=v)
            with mock.patch.object(p, "getitem_spec", getitem_spec):
                assert p.__getitem__("one", do_spec=False) is v

            assert len(getitem_spec.mock_calls) == 0

        it "works for transformed values":

            def pack_t(p, v):
                return v + 5

            def unpack_t(p, v):
                return v - 5

            class P(dictobj.PacketSpec):
                fields = [("one", T.Int8.transform(pack_t, unpack_t))]

            p = P(one=0)
            assert p["one"] == 0
            assert p.__getitem__("one", unpacking=False) == 5

        it "works for bytes values":

            class P(dictobj.PacketSpec):
                fields = [("one", T.Bytes)]

            b = bitarray(endian="little")
            val = binascii.unhexlify("d073d5")
            b.frombytes(val)

            p = P(one="d073d5")
            assert p["one"] == val
            assert p.__getitem__("one", allow_bitarray=True) == b

        it "works for transform values that have no value":

            class P(dictobj.PacketSpec):
                fields = [
                    (
                        "one",
                        T.Int16.transform(
                            lambda _, v: (int(str(v).split(".")[0]) << 0x10)
                            + int(str(v).split(".")[1]),
                            lambda v: float("{0}.{1}".format(v >> 0x10, v & 0xFF)),
                        ),
                    )
                ]

            p = P()
            assert p.one is sb.NotSpecified

    describe "getitem_spec":

        @pytest.fixture()
        def V(self):
            class V:
                key = str(uuid.uuid1())
                parent = mock.Mock(name="parent")
                serial = mock.Mock(name="serial")
                unpacking = mock.Mock(name="unpacking")
                normalised = mock.Mock(name="normalised")
                untransformed = mock.Mock(name="untransformed")

                @hp.memoized_property
                def initd_spec(s):
                    initd_spec = mock.Mock(name="specd")
                    initd_spec.normalise.return_value = s.normalised
                    return initd_spec

                @hp.memoized_property
                def untransform(s):
                    return mock.Mock(name="untransform", return_value=s.untransformed)

                @hp.memoized_property
                def typ(s):
                    typ = mock.Mock(name="typ", _allow_callable=False, untransform=s.untransform)
                    typ.spec.return_value = s.initd_spec
                    return typ

                def getitem_spec(s, pkt, actual, do_transform, allow_bitarray):
                    return pkt.getitem_spec(
                        s.typ,
                        s.key,
                        actual,
                        s.parent,
                        s.serial,
                        do_transform=do_transform,
                        allow_bitarray=allow_bitarray,
                        unpacking=s.unpacking,
                    )

            return V()

        it "calls the value if it's allowed to be callable and is callable", V:
            V.typ._allow_callable = True
            cald = mock.Mock(name="actual return value")
            actual = mock.Mock(name="actual", return_value=cald)

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            assert (
                V.getitem_spec(p, actual, do_transform=True, allow_bitarray=True) is V.untransformed
            )

            actual.assert_called_with(V.parent, V.serial)
            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), cald)
            V.untransform.assert_called_with(p, V.normalised)

        it "does not call the value if it's not allowed to be callable and is callable", V:
            actual = mock.Mock(name="actual")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            assert (
                V.getitem_spec(p, actual, do_transform=True, allow_bitarray=True) is V.untransformed
            )

            assert len(actual.mock_calls) == 0
            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), actual)
            V.untransform.assert_called_with(p, V.normalised)

        it "does not transform if do_transform is False", V:
            actual = mock.Mock(name="actual")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            assert (
                V.getitem_spec(p, actual, do_transform=False, allow_bitarray=True) is V.normalised
            )

            assert len(actual.mock_calls) == 0
            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), actual)
            assert len(V.untransform.mock_calls) == 0

        it "does not transform if the value from spec is sb.NotSpecified", V:

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()

            V.initd_spec.normalise.return_value = sb.NotSpecified
            assert (
                V.getitem_spec(p, sb.NotSpecified, do_transform=True, allow_bitarray=True)
                is sb.NotSpecified
            )

            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), sb.NotSpecified)
            assert len(V.untransform.mock_calls) == 0

        it "does not transform if the value from spec is Optional", V:

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()

            V.initd_spec.normalise.return_value = Optional
            assert (
                V.getitem_spec(p, sb.NotSpecified, do_transform=True, allow_bitarray=True)
                is Optional
            )

            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), sb.NotSpecified)
            assert len(V.untransform.mock_calls) == 0

        it "turns bitarrays into bytes if not allow_bitarray", V:
            actual = b"\x00"
            V.initd_spec.normalise.return_value = bitarray("0000")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            assert V.getitem_spec(p, actual, do_transform=False, allow_bitarray=False) == b"\x00"

            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), actual)
            assert len(V.untransform.mock_calls) == 0

        it "turns transformed values as bitarrays into bytes if not allow_bitarray", V:
            actual = b"\x00"
            V.untransform.return_value = bitarray("0000")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            assert V.getitem_spec(p, actual, do_transform=True, allow_bitarray=False) == b"\x00"

            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), actual)
            V.untransform.assert_called_with(p, V.normalised)

        it "keeps transformed values as bitarrays if allow_bitarray", V:
            actual = b"\x00"
            V.untransform.return_value = bitarray("0000")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            assert V.getitem_spec(p, actual, do_transform=True, allow_bitarray=True) == bitarray(
                "0000"
            )

            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), actual)
            V.untransform.assert_called_with(p, V.normalised)

        it "keeps untransformed values as bitarrays if allow_bitarray", V:
            actual = b"\x00"
            V.initd_spec.normalise.return_value = bitarray("0000")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            assert V.getitem_spec(p, actual, do_transform=False, allow_bitarray=True) == bitarray(
                "0000"
            )

            V.typ.spec.assert_called_once_with(p, V.unpacking, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), actual)
            assert len(V.untransform.mock_calls) == 0

        it "does not transform if we are not unpacking", V:
            actual = sb.NotSpecified

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            V.unpacking = False
            assert V.getitem_spec(p, actual, do_transform=True, allow_bitarray=True) == V.normalised

            V.typ.spec.assert_called_once_with(p, False, transform=False)
            V.initd_spec.normalise.assert_called_with(meta.at(V.key), actual)
            assert len(V.untransform.mock_calls) == 0

    describe "__getattr__":
        it "uses __getitem__ if is a Group":

            class P(PacketSpecMixin):
                class Meta:
                    groups = ["one"]

            ret = mock.Mock(name="ret")
            __getitem__ = mock.Mock(name="__getitem__", return_value=ret)

            p = P()
            with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                assert p.one is ret

            __getitem__.assert_called_once_with("one")

        it "uses __getitem__ if is in all_names":

            class P(PacketSpecMixin):
                class Meta:
                    groups = []
                    all_names = ["one"]

            ret = mock.Mock(name="ret")
            __getitem__ = mock.Mock(name="__getitem__", return_value=ret)

            p = P()
            with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                assert p.one is ret

            __getitem__.assert_called_once_with("one")

        it "bypasses __getitem__ if on the class":
            attr_one = mock.Mock(name="attr_one")

            ret = mock.Mock(name="ret")
            __getitem__ = mock.Mock(name="__getitem__", return_value=ret)

            class P(PacketSpecMixin):
                one = attr_one

                class Meta:
                    groups = ["one"]
                    all_names = []

            with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                assert P().one is attr_one

            class P(PacketSpecMixin):
                one = attr_one

                class Meta:
                    groups = []
                    all_names = ["one"]

            with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                assert P().one is attr_one

            class P(PacketSpecMixin):
                def one(s):
                    pass

                class Meta:
                    groups = []
                    all_names = ["one"]

            with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                assert P().one.__func__ is P.one

            class P(PacketSpecMixin):
                class Meta:
                    groups = []
                    all_names = []

            with assertRaises(AttributeError):
                with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                    P().one

            assert len(__getitem__.mock_calls) == 0

    describe "__setattr__":
        it "uses __setitem__ if key is a group":

            class P(PacketSpecMixin):
                class Meta:
                    groups = ["one"]

            ret = mock.Mock(name="ret")
            __setitem__ = mock.Mock(name="__setitem__", return_value=ret)

            p = P()
            val = mock.Mock(name="val")
            with mock.patch.object(PacketSpecMixin, "__setitem__", __setitem__):
                p.one = val

            __setitem__.assert_called_once_with("one", val)

        it "uses __setitem__ if key is a field":

            class P(PacketSpecMixin):
                class Meta:
                    groups = []
                    all_names = ["one"]

            ret = mock.Mock(name="ret")
            __setitem__ = mock.Mock(name="__setitem__", return_value=ret)

            p = P()
            val = mock.Mock(name="val")
            with mock.patch.object(PacketSpecMixin, "__setitem__", __setitem__):
                p.one = val

            __setitem__.assert_called_once_with("one", val)

        it "uses dictobj.__setattr__ if key is neither a group or field":

            class P(PacketSpecMixin):
                class Meta:
                    groups = []
                    all_names = []

            ret = mock.Mock(name="ret")
            dret = mock.Mock(name="dret")

            __setitem__ = mock.Mock(name="__setitem__", return_value=ret)
            dictobj__setattr__ = mock.Mock(name="dictobj.__setattr__", return_value=dret)

            p = P()
            assert not hasattr(p, "one")

            val = mock.Mock(name="val")
            with mock.patch("delfick_project.norms.dictobj.__setattr__", dictobj__setattr__):
                with mock.patch.object(PacketSpecMixin, "__setitem__", __setitem__):
                    p.one = val

            assert len(__setitem__.mock_calls) == 0
            dictobj__setattr__.assert_called_once_with(p, "one", val)

        it "works in union with getattr semantics":

            def pack_t(p, v):
                return v + 5

            def unpack_t(p, v):
                return v - 5

            class P(dictobj.PacketSpec):
                fields = [("one", T.Bytes), ("two", T.Int8.transform(pack_t, unpack_t))]

            p = P()
            p.one = "d073d5"
            p.two = 5

            assert p.one == binascii.unhexlify("d073d5")
            assert p.two == 5

            assert p.actual("two") == 10

    describe "__setitem__":
        it "does nothing if the key is a group and value is Initial":

            class G(dictobj.PacketSpec):
                fields = [("one", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P()

            assert list(p.actual_items()) == [("one", sb.NotSpecified)]
            p["g"] = Initial
            assert list(p.actual_items()) == [("one", sb.NotSpecified)]

        it "uses _set_group_item if key is a group and value is not Initial":
            val = mock.Mock(name="val")

            class G(dictobj.PacketSpec):
                fields = [("one", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P()

            _set_group_item = mock.Mock(name="_set_group_item")

            assert list(p.actual_items()) == [("one", sb.NotSpecified)]
            with mock.patch.object(dictobj.PacketSpec, "_set_group_item", _set_group_item):
                p["g"] = val

            _set_group_item.assert_called_once_with("g", val)
            assert list(p.actual_items()) == [("one", sb.NotSpecified)]

        describe "transformation":

            @pytest.fixture()
            def V(self):
                class V:
                    for_user = str(uuid.uuid1())
                    for_packing = str(uuid.uuid1())

                    @hp.memoized_property
                    def pack_t(s):
                        return mock.Mock(name="pack_t", return_value=s.for_packing)

                    @hp.memoized_property
                    def unpack_t(s):
                        return mock.Mock(name="unpack_t", return_value=s.for_user)

                    @hp.memoized_property
                    def two_typ(s):
                        return mock.Mock(
                            name="two_typ", _transform=sb.NotSpecified, spec=["_transform"]
                        )

                    @hp.memoized_property
                    def P(s):
                        class P(dictobj.PacketSpec):
                            fields = [
                                ("one", T.String.transform(s.pack_t, s.unpack_t)),
                                ("two", s.two_typ),
                            ]

                        return P

                return V()

            it "does no transformation if the typ has no transformation", V:
                val = mock.Mock(name="val")

                p = V.P()
                p["two"] = val

                assert list(p.actual_items()) == [("one", sb.NotSpecified), ("two", val)]

            it "does no transformation if the val is sb.NotSpecified", V:
                p = V.P()
                p["one"] = sb.NotSpecified

                assert list(p.actual_items()) == [
                    ("one", sb.NotSpecified),
                    ("two", sb.NotSpecified),
                ]
                assert len(V.pack_t.mock_calls) == 0
                assert len(V.unpack_t.mock_calls) == 0

            it "does no transformation if the val is Optional", V:
                p = V.P()
                p["one"] = Optional

                assert list(p.actual_items()) == [("one", Optional), ("two", sb.NotSpecified)]
                assert len(V.pack_t.mock_calls) == 0
                assert len(V.unpack_t.mock_calls) == 0

            it "does transformation for other values", V:
                p = V.P()
                p["one"] = V.for_user

                assert list(p.actual_items()) == [
                    ("one", V.for_packing),
                    ("two", sb.NotSpecified),
                ]
                V.pack_t.assert_called_once_with(p, V.for_user)
                assert len(V.unpack_t.mock_calls) == 0

                assert p.one == V.for_user
                V.unpack_t.assert_called_once_with(p, V.for_packing)
                V.pack_t.assert_called_once_with(p, V.for_user)

    describe "_set_group_item":
        describe "setting empty payload":

            @pytest.fixture()
            def P(self):
                class P(dictobj.PacketSpec):
                    fields = [("payload", "Payload")]

                    class Payload(dictobj.PacketSpec):
                        message_type = 0
                        fields = []

                return P

            it "complains if we aren't setting bytes or str or bitarray", P:
                for val in (
                    0,
                    1,
                    None,
                    True,
                    False,
                    [],
                    [1],
                    {},
                    {1: 2},
                    lambda: 1,
                    P.Payload(),
                    sb.NotSpecified,
                ):
                    with assertRaises(ValueError, "Setting non bytes payload on a packet.+"):
                        P()["payload"] = val

            it "sets the value if it's str, bytes or bitarray", P:
                for val in ("wat", b"wat", bitarray("0")):
                    p = P()
                    p["payload"] = val
                    assert dictobj.__getitem__(p, "payload") == val

        describe "setting a group as sb.NotSpecified":

            @pytest.fixture()
            def P(self):
                class G(dictobj.PacketSpec):
                    fields = [("one", T.String), ("two", T.Int8)]

                class P(dictobj.PacketSpec):
                    fields = [("g", G)]

                return P

            it "sets all the fields in that group as NotSpecified", P:
                p = P(one="wat", two=8)
                assert sorted(p.actual_items()) == sorted([("one", "wat"), ("two", 8)])

                p["g"] = sb.NotSpecified
                assert sorted(p.actual_items()) == sorted(
                    [("one", sb.NotSpecified), ("two", sb.NotSpecified)]
                )

        describe "setting a group from an instance of that group":
            it "does a direct copy without going through transformation or specs":
                for_packing = str(uuid.uuid1())
                pack_t = mock.Mock(name="pack_t", return_value=for_packing)

                for_user = str(uuid.uuid1())
                unpack_t = mock.Mock(name="unpack_t", return_value=for_user)

                two_typ = mock.Mock(
                    name="two_typ",
                    _allow_callable=False,
                    _transform=sb.NotSpecified,
                    untransform=lambda v: v,
                    spec=["_allow_callable", "_transform"],
                )

                class G(dictobj.PacketSpec):
                    fields = [
                        ("one", T.String.transform(pack_t, unpack_t)),
                        ("two", two_typ),
                        ("three", T.Int8),
                        ("four", T.String),
                    ]

                class P(dictobj.PacketSpec):
                    fields = [("g", G)]

                p = P()
                g = G(one=for_user, two="whatevs", three=8)

                pack_t.assert_called_once_with(g, for_user)
                assert len(unpack_t.mock_calls) == 0

                assert sorted(p.actual_items()) == (
                    sorted(
                        [
                            ("one", sb.NotSpecified),
                            ("two", sb.NotSpecified),
                            ("three", sb.NotSpecified),
                            ("four", sb.NotSpecified),
                        ]
                    )
                )

                p["g"] = g

                pack_t.assert_called_once_with(g, for_user)
                assert len(unpack_t.mock_calls) == 0

                assert sorted(p.actual_items()) == (
                    sorted(
                        [
                            ("one", for_packing),
                            ("two", "whatevs"),
                            ("three", 8),
                            ("four", sb.NotSpecified),
                        ]
                    )
                )

        describe "setting a group from not an instance of that group":

            @pytest.fixture()
            def V(self):
                class V:
                    for_user = str(uuid.uuid1())
                    for_packing = str(uuid.uuid1())

                    @hp.memoized_property
                    def pack_t(s):
                        return mock.Mock(name="pack_t", return_value=s.for_packing)

                    @hp.memoized_property
                    def unpack_t(s):
                        return mock.Mock(name="unpack_t", return_value=s.for_user)

                    @hp.memoized_property
                    def G(s):
                        class G(dictobj.PacketSpec):
                            fields = [
                                ("one", T.String.transform(s.pack_t, s.unpack_t)),
                                ("two", T.Bytes),
                            ]

                        return G

                    @hp.memoized_property
                    def P(s):
                        class P(dictobj.PacketSpec):
                            fields = [("g", s.G)]

                        return P

                return V()

            it "complains if the value does not have items", V:
                val = mock.Mock(name="val", spec=[])
                p = V.P()
                with assertRaises(
                    ValueError,
                    r"Setting a group on a packet must be done with a value that has an items\(\) method.+",
                ):
                    p["g"] = val

            it "sets values from items on the val", V:
                val = mock.Mock(name="val", spec=["items"])
                val.items.return_value = [
                    ("one", V.for_user),
                    ("two", "d073d5"),
                    ("three", "not given"),
                ]

                p = V.P()
                assert sorted(p.actual_items()) == sorted(
                    [("one", sb.NotSpecified), ("two", sb.NotSpecified)]
                )

                p["g"] = val
                assert sorted(p.actual_items()) == sorted(
                    [("one", V.for_packing), ("two", "d073d5")]
                )

                assert p.one == V.for_user
                assert p.two == binascii.unhexlify("d073d5")

    describe "Information":

        @pytest.fixture
        def V(self):
            class V:
                @hp.memoized_property
                def P(s):
                    class P(dictobj.PacketSpec):
                        fields = [("g", T.String(32))]

                    return P

            return V()

        it "is able to set an Information object that is memoized", V:
            pkt1 = V.P(g="hello")
            pkt2 = V.P(g="there")

            sender1 = mock.Mock(name="sender1")
            sender2 = mock.Mock(name="sender2")

            for pkt in (pkt1, pkt2):
                assert isinstance(pkt.Information, Information)
                assert pkt.Information.remote_addr is None
                assert pkt.Information.sender_message is None

            pkt1.Information.update(remote_addr=("127.0.0.1", 6789), sender_message=sender1)
            assert pkt1.Information.remote_addr == ("127.0.0.1", 6789)
            assert pkt1.Information.sender_message is sender1

            # Information is per packet
            assert pkt2.Information.remote_addr is None
            assert pkt2.Information.sender_message is None

            pkt2.Information.update(remote_addr=("127.0.2.4", 1234), sender_message=sender2)
            assert pkt2.Information.remote_addr == ("127.0.2.4", 1234)
            assert pkt2.Information.sender_message is sender2

            assert pkt1.Information.remote_addr == ("127.0.0.1", 6789)
            assert pkt1.Information.sender_message is sender1

            for (pkt, dct) in ((pkt1, {"g": "hello"}), (pkt2, {"g": "there"})):
                assert pkt.as_dict() == dct
                assert sorted(pkt.keys()) == sorted(dct.keys())
                assert sorted(pkt.values()) == sorted(dct.values())
                assert sorted(pkt.items()) == sorted(dct.items())
