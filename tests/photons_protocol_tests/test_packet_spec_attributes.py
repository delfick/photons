# coding: spec

from photons_protocol.packets import dictobj, PacketSpecMixin, Initial, Optional
from photons_protocol.types import Type as T

from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from bitarray import bitarray
from unittest import mock
import binascii
import uuid

describe TestCase, "Packet attributes":
    describe "__getitem__":
        it "raises KeyError if the key is not on the packet":

            class P(dictobj.PacketSpec):
                fields = []

            p = P()
            with self.fuzzyAssertRaisesError(KeyError):
                p["one"]

        it "does not raise KeyError if the key is a group":

            class P(dictobj.PacketSpec):
                fields = [("payload", "Payload")]

                class Payload(dictobj.PacketSpec):
                    fields = []

            p = P()
            self.assertEqual(p["payload"], P.Payload())

        it "uses sb.NotSpecified if there is no value for the key":

            class P(dictobj.PacketSpec):
                fields = [("one", T.String)]

            val = mock.Mock(name="val")
            getitem_spec = mock.Mock(name="getitem_spec", return_value=val)

            p = P()
            with mock.patch.object(p, "getitem_spec", getitem_spec):
                self.assertIs(p["one"], val)

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
                self.assertIs(p["one"], val)

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
                self.assertIs(p.__getitem__("one", **options), val)

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
                self.assertEqual(P(payload=val).payload, b.tobytes())
                self.assertEqual(P(payload=val).__getitem__("payload", allow_bitarray=True), b)

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

            self.assertEqual(Child(one=True).payload, Child.Payload(one=True))

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
            self.assertEqual(sorted(g.items()), sorted([("one", True), ("two", 3), ("three", 4)]))
            self.assertEqual(type(g), G)

        it "does not use getitem_spec if do_spec is False":

            class P(dictobj.PacketSpec):
                fields = [("one", T.String)]

            getitem_spec = mock.Mock(name="getitem_spec")

            p = P()
            with mock.patch.object(p, "getitem_spec", getitem_spec):
                self.assertIs(p.__getitem__("one", do_spec=False), sb.NotSpecified)

            v = mock.Mock(name="v")
            p = P(one=v)
            with mock.patch.object(p, "getitem_spec", getitem_spec):
                self.assertIs(p.__getitem__("one", do_spec=False), v)

            self.assertEqual(len(getitem_spec.mock_calls), 0)

        it "works for transformed values":

            def pack_t(p, v):
                return v + 5

            def unpack_t(p, v):
                return v - 5

            class P(dictobj.PacketSpec):
                fields = [("one", T.Int8.transform(pack_t, unpack_t))]

            p = P(one=0)
            self.assertEqual(p["one"], 0)
            self.assertEqual(p.__getitem__("one", unpacking=False), 5)

        it "works for bytes values":

            class P(dictobj.PacketSpec):
                fields = [("one", T.Bytes)]

            b = bitarray(endian="little")
            val = binascii.unhexlify("d073d5")
            b.frombytes(val)

            p = P(one="d073d5")
            self.assertEqual(p["one"], val)
            self.assertEqual(p.__getitem__("one", allow_bitarray=True), b)

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
            self.assertIs(p.one, sb.NotSpecified)

    describe "getitem_spec":
        before_each:
            self.normalised = mock.Mock(name="normalised")
            self.initd_spec = mock.Mock(name="specd")
            self.initd_spec.normalise.return_value = self.normalised
            self.untransformed = mock.Mock(name="untransformed")
            self.untransform = mock.Mock(name="untransform", return_value=self.untransformed)
            self.typ = mock.Mock(name="typ", _allow_callable=False, untransform=self.untransform)
            self.typ.spec.return_value = self.initd_spec

            self.key = str(uuid.uuid1())
            self.parent = mock.Mock(name="parent")
            self.serial = mock.Mock(name="serial")
            self.unpacking = mock.Mock(name="unpacking")

        def getitem_spec(self, pkt, actual, do_transform, allow_bitarray):
            return pkt.getitem_spec(
                self.typ,
                self.key,
                actual,
                self.parent,
                self.serial,
                do_transform=do_transform,
                allow_bitarray=allow_bitarray,
                unpacking=self.unpacking,
            )

        it "calls the value if it's allowed to be callable and is callable":
            self.typ._allow_callable = True
            cald = mock.Mock(name="actual return value")
            actual = mock.Mock(name="actual", return_value=cald)

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            self.assertIs(
                self.getitem_spec(p, actual, do_transform=True, allow_bitarray=True),
                self.untransformed,
            )

            actual.assert_called_with(self.parent, self.serial)
            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), cald)
            self.untransform.assert_called_with(p, self.normalised)

        it "does not call the value if it's not allowed to be callable and is callable":
            actual = mock.Mock(name="actual")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            self.assertIs(
                self.getitem_spec(p, actual, do_transform=True, allow_bitarray=True),
                self.untransformed,
            )

            self.assertEqual(len(actual.mock_calls), 0)
            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), actual)
            self.untransform.assert_called_with(p, self.normalised)

        it "does not transform if do_transform is False":
            actual = mock.Mock(name="actual")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            self.assertIs(
                self.getitem_spec(p, actual, do_transform=False, allow_bitarray=True),
                self.normalised,
            )

            self.assertEqual(len(actual.mock_calls), 0)
            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), actual)
            self.assertEqual(len(self.untransform.mock_calls), 0)

        it "does not transform if the value from spec is sb.NotSpecified":

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()

            self.initd_spec.normalise.return_value = sb.NotSpecified
            self.assertIs(
                self.getitem_spec(p, sb.NotSpecified, do_transform=True, allow_bitarray=True),
                sb.NotSpecified,
            )

            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), sb.NotSpecified)
            self.assertEqual(len(self.untransform.mock_calls), 0)

        it "does not transform if the value from spec is Optional":

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()

            self.initd_spec.normalise.return_value = Optional
            self.assertIs(
                self.getitem_spec(p, sb.NotSpecified, do_transform=True, allow_bitarray=True),
                Optional,
            )

            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), sb.NotSpecified)
            self.assertEqual(len(self.untransform.mock_calls), 0)

        it "turns bitarrays into bytes if not allow_bitarray":
            actual = b"\x00"
            self.initd_spec.normalise.return_value = bitarray("0000")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            self.assertEqual(
                self.getitem_spec(p, actual, do_transform=False, allow_bitarray=False), b"\x00"
            )

            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), actual)
            self.assertEqual(len(self.untransform.mock_calls), 0)

        it "turns transformed values as bitarrays into bytes if not allow_bitarray":
            actual = b"\x00"
            self.untransform.return_value = bitarray("0000")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            self.assertEqual(
                self.getitem_spec(p, actual, do_transform=True, allow_bitarray=False), b"\x00"
            )

            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), actual)
            self.untransform.assert_called_with(p, self.normalised)

        it "keeps transformed values as bitarrays if allow_bitarray":
            actual = b"\x00"
            self.untransform.return_value = bitarray("0000")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            self.assertEqual(
                self.getitem_spec(p, actual, do_transform=True, allow_bitarray=True),
                bitarray("0000"),
            )

            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), actual)
            self.untransform.assert_called_with(p, self.normalised)

        it "keeps untransformed values as bitarrays if allow_bitarray":
            actual = b"\x00"
            self.initd_spec.normalise.return_value = bitarray("0000")

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            self.assertEqual(
                self.getitem_spec(p, actual, do_transform=False, allow_bitarray=True),
                bitarray("0000"),
            )

            self.typ.spec.assert_called_once_with(p, self.unpacking, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), actual)
            self.assertEqual(len(self.untransform.mock_calls), 0)

        it "does not transform if we are not unpacking":
            actual = sb.NotSpecified

            class P(PacketSpecMixin):
                pass

            p = P()
            meta = Meta.empty()
            self.unpacking = False
            self.assertEqual(
                self.getitem_spec(p, actual, do_transform=True, allow_bitarray=True),
                self.normalised,
            )

            self.typ.spec.assert_called_once_with(p, False, transform=False)
            self.initd_spec.normalise.assert_called_with(meta.at(self.key), actual)
            self.assertEqual(len(self.untransform.mock_calls), 0)

    describe "__getattr__":
        it "uses __getitem__ if is a Group":

            class P(PacketSpecMixin):
                class Meta:
                    groups = ["one"]

            ret = mock.Mock(name="ret")
            __getitem__ = mock.Mock(name="__getitem__", return_value=ret)

            p = P()
            with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                self.assertIs(p.one, ret)

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
                self.assertIs(p.one, ret)

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
                self.assertIs(P().one, attr_one)

            class P(PacketSpecMixin):
                one = attr_one

                class Meta:
                    groups = []
                    all_names = ["one"]

            with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                self.assertIs(P().one, attr_one)

            class P(PacketSpecMixin):
                def one(self):
                    pass

                class Meta:
                    groups = []
                    all_names = ["one"]

            with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                self.assertIs(P().one.__func__, P.one)

            class P(PacketSpecMixin):
                class Meta:
                    groups = []
                    all_names = []

            with self.fuzzyAssertRaisesError(AttributeError):
                with mock.patch.object(PacketSpecMixin, "__getitem__", __getitem__):
                    P().one

            self.assertEqual(len(__getitem__.mock_calls), 0)

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
            with mock.patch("input_algorithms.dictobj.dictobj.__setattr__", dictobj__setattr__):
                with mock.patch.object(PacketSpecMixin, "__setitem__", __setitem__):
                    p.one = val

            self.assertEqual(len(__setitem__.mock_calls), 0)
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

            self.assertEqual(p.one, binascii.unhexlify("d073d5"))
            self.assertEqual(p.two, 5)

            self.assertEqual(p.actual("two"), 10)

    describe "__setitem__":
        it "does nothing if the key is a group and value is Initial":

            class G(dictobj.PacketSpec):
                fields = [("one", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P()

            self.assertEqual(list(p.items()), [("one", sb.NotSpecified)])
            p["g"] = Initial
            self.assertEqual(list(p.items()), [("one", sb.NotSpecified)])

        it "uses _set_group_item if key is a group and value is not Initial":
            val = mock.Mock(name="val")

            class G(dictobj.PacketSpec):
                fields = [("one", T.String)]

            class P(dictobj.PacketSpec):
                fields = [("g", G)]

            p = P()

            _set_group_item = mock.Mock(name="_set_group_item")

            self.assertEqual(list(p.items()), [("one", sb.NotSpecified)])
            with mock.patch.object(dictobj.PacketSpec, "_set_group_item", _set_group_item):
                p["g"] = val

            _set_group_item.assert_called_once_with("g", val)
            self.assertEqual(list(p.items()), [("one", sb.NotSpecified)])

        describe "transformation":
            before_each:
                self.for_packing = str(uuid.uuid1())
                self.pack_t = mock.Mock(name="pack_t", return_value=self.for_packing)

                self.for_user = str(uuid.uuid1())
                self.unpack_t = mock.Mock(name="unpack_t", return_value=self.for_user)

                self.two_typ = mock.Mock(
                    name="two_typ", _transform=sb.NotSpecified, spec=["_transform"]
                )

                class P(dictobj.PacketSpec):
                    fields = [
                        ("one", T.String.transform(self.pack_t, self.unpack_t)),
                        ("two", self.two_typ),
                    ]

                self.P = P

            it "does no transformation if the typ has no transformation":
                val = mock.Mock(name="val")

                p = self.P()
                p["two"] = val

                self.assertEqual(list(p.items()), [("one", sb.NotSpecified), ("two", val)])

            it "does no transformation if the val is sb.NotSpecified":
                p = self.P()
                p["one"] = sb.NotSpecified

                self.assertEqual(
                    list(p.items()), [("one", sb.NotSpecified), ("two", sb.NotSpecified)]
                )
                self.assertEqual(len(self.pack_t.mock_calls), 0)
                self.assertEqual(len(self.unpack_t.mock_calls), 0)

            it "does no transformation if the val is Optional":
                p = self.P()
                p["one"] = Optional

                self.assertEqual(list(p.items()), [("one", Optional), ("two", sb.NotSpecified)])
                self.assertEqual(len(self.pack_t.mock_calls), 0)
                self.assertEqual(len(self.unpack_t.mock_calls), 0)

            it "does transformation for other values":
                p = self.P()
                p["one"] = self.for_user

                self.assertEqual(
                    list(p.items()), [("one", self.for_packing), ("two", sb.NotSpecified)]
                )
                self.pack_t.assert_called_once_with(p, self.for_user)
                self.assertEqual(len(self.unpack_t.mock_calls), 0)

                self.assertEqual(p.one, self.for_user)
                self.unpack_t.assert_called_once_with(p, self.for_packing)
                self.pack_t.assert_called_once_with(p, self.for_user)

    describe "_set_group_item":
        describe "setting empty payload":
            before_each:

                class P(dictobj.PacketSpec):
                    fields = [("payload", "Payload")]

                    class Payload(dictobj.PacketSpec):
                        message_type = 0
                        fields = []

                self.P = P

            it "complains if we aren't setting bytes or str or bitarray":
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
                    self.P.Payload(),
                    sb.NotSpecified,
                ):
                    with self.fuzzyAssertRaisesError(
                        ValueError, "Setting non bytes payload on a packet.+"
                    ):
                        self.P()["payload"] = val

            it "sets the value if it's str, bytes or bitarray":
                for val in ("wat", b"wat", bitarray("0")):
                    p = self.P()
                    p["payload"] = val
                    self.assertEqual(dictobj.__getitem__(p, "payload"), val)

        describe "setting a group as sb.NotSpecified":
            before_each:

                class G(dictobj.PacketSpec):
                    fields = [("one", T.String), ("two", T.Int8)]

                class P(dictobj.PacketSpec):
                    fields = [("g", G)]

                self.P = P

            it "sets all the fields in that group as NotSpecified":
                p = self.P(one="wat", two=8)
                self.assertEqual(sorted(p.items()), sorted([("one", "wat"), ("two", 8)]))

                p["g"] = sb.NotSpecified
                self.assertEqual(
                    sorted(p.items()), sorted([("one", sb.NotSpecified), ("two", sb.NotSpecified)])
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
                self.assertEqual(len(unpack_t.mock_calls), 0)

                self.assertEqual(
                    sorted(p.items()),
                    sorted(
                        [
                            ("one", sb.NotSpecified),
                            ("two", sb.NotSpecified),
                            ("three", sb.NotSpecified),
                            ("four", sb.NotSpecified),
                        ]
                    ),
                )

                p["g"] = g

                pack_t.assert_called_once_with(g, for_user)
                self.assertEqual(len(unpack_t.mock_calls), 0)

                self.assertEqual(
                    sorted(p.items()),
                    sorted(
                        [
                            ("one", for_packing),
                            ("two", "whatevs"),
                            ("three", 8),
                            ("four", sb.NotSpecified),
                        ]
                    ),
                )

        describe "setting a group from not an instance of that group":
            before_each:
                self.for_packing = str(uuid.uuid1())
                self.pack_t = mock.Mock(name="pack_t", return_value=self.for_packing)

                self.for_user = str(uuid.uuid1())
                self.unpack_t = mock.Mock(name="unpack_t", return_value=self.for_user)

                class G(dictobj.PacketSpec):
                    fields = [
                        ("one", T.String.transform(self.pack_t, self.unpack_t)),
                        ("two", T.Bytes),
                    ]

                class P(dictobj.PacketSpec):
                    fields = [("g", G)]

                self.P = P

            it "complains if the value does not have items":
                val = mock.Mock(name="val", spec=[])
                p = self.P()
                with self.fuzzyAssertRaisesError(
                    ValueError,
                    "Setting a group on a packet must be done with a value that has an items\(\) method.+",
                ):
                    p["g"] = val

            it "sets values from items on the val":
                val = mock.Mock(name="val", spec=["items"])
                val.items.return_value = [
                    ("one", self.for_user),
                    ("two", "d073d5"),
                    ("three", "not given"),
                ]

                p = self.P()
                self.assertEqual(
                    sorted(p.items()), sorted([("one", sb.NotSpecified), ("two", sb.NotSpecified)])
                )

                p["g"] = val
                self.assertEqual(
                    sorted(p.items()), sorted([("one", self.for_packing), ("two", "d073d5")])
                )

                self.assertEqual(p.one, self.for_user)
                self.assertEqual(p.two, binascii.unhexlify("d073d5"))
