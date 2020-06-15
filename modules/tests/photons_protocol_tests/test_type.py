# coding: spec

from photons_protocol.types import Type, static_conversion_from_spec, json_spec
from photons_protocol.errors import BadConversion
from photons_protocol.types import Type as T

from photons_app.errors import ProgrammerError
from photons_app import helpers as hp

from delfick_project.norms import sb, Meta, BadSpecValue
from delfick_project.errors_pytest import assertRaises
from contextlib import contextmanager
from unittest import mock
import pytest
import json

describe "the json spec":
    it "can match just static types":
        for val in ("adsf", True, False, None, 0, 1, 1.2):
            assert json_spec.normalise(Meta.empty(), val) == val

    it "can match lists":
        for val in ([], ["asdf"], ["asdf", True, 1]):
            assert json_spec.normalise(Meta.empty(), val) == val

    it "can match nested lists":
        for val in ([[]], ["asdf", [1]], [["asdf", True], [1]]):
            assert json_spec.normalise(Meta.empty(), val) == val

    it "can match dictionaries":
        for val in ({}, {"1": "2", "2": 2, "3": False}):
            assert json_spec.normalise(Meta.empty(), val) == val

    it "can match nested dictionaries":
        val = {"asdf": {"adf": {"asdf": 2, "adf": False, "eieu": None}}}
        assert json_spec.normalise(Meta.empty(), val) == val

    it "complains about things that aren't json like objects, callables and non string keys":
        for val in (type("adf", (object,), {}), any, json, lambda: 1):
            with assertRaises(BadSpecValue):
                json_spec.normalise(Meta.empty(), val)

        try:
            json_spec.normalise(Meta.empty(), {"one": {1: 2}})
            assert False, "Expected an error"
        except BadSpecValue as error:
            assert error.errors[0].errors[0].message == "Expected a string"

describe "Type":
    it "takes in struct_format and conversion":
        struct_format = mock.Mock(name="struct_format")
        conversion = mock.Mock(name="conversion")
        t = Type(struct_format, conversion)
        assert t.struct_format is struct_format
        assert t.conversion is conversion

    describe "Adding size_bits":

        @pytest.fixture()
        def V(self):
            class V:
                struct_format = mock.Mock(name="struct_format")
                conversion = mock.Mock(name="conversion")

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

            return V()

        describe "calling an instance":
            it "defers to the S function", V:
                S = mock.Mock(name="S")
                size_bits = mock.Mock(name="size_bits")
                left = mock.Mock(name="left")

                ret = mock.Mock(name="ret")
                S.return_value = ret
                with mock.patch.object(V.t, "S", S):
                    assert V.t(size_bits, left=left) is ret

                S.assert_called_once_with(size_bits, left=left)

                # Doesn't touch the original type
                assert V.t.size_bits is NotImplemented

        describe "calling the S function":
            it "creates a new object and passes on 'private' attributes", V:
                field_names = (
                    "_enum",
                    "_bitmask",
                    "_dynamic",
                    "_default",
                    "_optional",
                    "_multiple",
                    "_override",
                    "_allow_float",
                    "_multiple_kls",
                    "_allow_callable",
                    "_pack_transform",
                    "_unpack_transform",
                    "_unknown_enum_values",
                )

                fields = {}
                for field in field_names:
                    fields[field] = mock.Mock(name="field")
                    assert getattr(V.t, field) in (sb.NotSpecified, False)

                size_bits = mock.Mock(name="size_bits")
                left = mock.Mock(name="left")

                res = V.t.S(size_bits, left=left)
                assert res.size_bits is size_bits
                assert res.left_cut is left

                for name, val in fields.items():
                    setattr(res, name, val)

                for field in field_names:
                    assert getattr(V.t, field) in (sb.NotSpecified, False)
                    assert getattr(res, field) is fields[field]

                size_bits2 = mock.Mock(name="size_bits2")
                res2 = res.S(size_bits2)

                # Res is untouched
                assert res.size_bits is size_bits
                assert res.left_cut is left

                # res2 has the new things
                assert res2.size_bits is size_bits2
                assert res2.left_cut is left

                # Our custom fields are passed on
                for field in field_names:
                    assert getattr(res2, field) is fields[field]

    describe "Type.t":
        it "generates a new class from Type and instantiates it":
            struct_format = mock.Mock(name="struct_format")
            conversion = mock.Mock(name="conversion")
            t = Type.t("bob", struct_format, conversion)

            assert t.__class__.__name__ == "bob"
            assert t.struct_format is struct_format
            assert t.conversion is conversion
            assert issubclass(t.__class__, Type)
            assert t.__class__ is not Type

    describe "modifiers":

        @pytest.fixture()
        def V(self):
            class V:
                pkt = mock.Mock(name="pkt")
                struct_format = mock.Mock(name="struct_format")
                conversion = mock.Mock(name="conversion")

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

                @contextmanager
                def clone(s, cloned=True):
                    setd = {}

                    class Clone(object):
                        def __setattr__(s, name, val):
                            assert name not in setd
                            setd[name] = val

                    size_bits = mock.Mock(name="size_bits")
                    s.t.size_bits = size_bits

                    res = Clone()
                    S = mock.Mock(name="S", return_value=res)
                    with mock.patch.object(s.t, "S", S):
                        yield res, setd

                    if cloned:
                        S.assert_called_once_with(size_bits)
                    else:
                        assert len(S.mock_calls) == 0

            return V()

        describe "allow_float":
            it "sets _allow_float to True", V:
                with V.clone() as (res, setd):
                    assert V.t.allow_float() is res
                assert setd == {"_allow_float": True}

        describe "enum":
            it "sets _enum to the value passed in", V:
                em = mock.Mock(name="enum")
                with V.clone() as (res, setd):
                    assert V.t.enum(em) is res
                assert setd == {"_enum": em, "_unknown_enum_values": False}

            it "sets _unknown_enum_values to the allow_unknown value passed in", V:
                em = mock.Mock(name="enum")
                allow_unknown = mock.Mock(name="allow_unknown")
                with V.clone() as (res, setd):
                    assert V.t.enum(em, allow_unknown=allow_unknown) is res
                assert setd == {"_enum": em, "_unknown_enum_values": allow_unknown}

        describe "dynamic":
            it "sets _dynamic to the value passed in", V:
                dn = mock.Mock(name="dynamiser")
                with V.clone() as (res, setd):
                    assert V.t.dynamic(dn) is res
                assert setd == {"_dynamic": dn}

        describe "bitmask":
            it "sets _bitmask to the value passed in", V:
                bm = mock.Mock(name="bitmask")
                with V.clone() as (res, setd):
                    assert V.t.bitmask(bm) is res
                assert setd == {"_bitmask": bm}

        describe "transform":
            it "sets _pack_transform and _unpack_transform in that order", V:
                pack_func = mock.Mock(name="pack_Func")
                unpack_func = mock.Mock(name="unpack_func")
                with V.clone() as (res, setd):
                    assert V.t.transform(pack_func, unpack_func) is res
                assert setd == {"_pack_transform": pack_func, "_unpack_transform": unpack_func}

            it "complains if either function isn't callable", V:
                pack_func = mock.Mock(name="pack_Func")
                unpack_func = mock.Mock(name="unpack_func")

                uncallable_pack_func = mock.NonCallableMock(name="uncallable_pack_func")
                uncallable_unpack_func = mock.NonCallableMock(name="uncallable_unpack_func")

                with V.clone(cloned=False) as (res, setd):
                    with assertRaises(ProgrammerError, "transform can only be given two callables"):
                        V.t.transform(uncallable_pack_func, unpack_func)

                    with assertRaises(ProgrammerError, "transform can only be given two callables"):
                        V.t.transform(pack_func, uncallable_unpack_func)

                    with assertRaises(ProgrammerError, "transform can only be given two callables"):
                        V.t.transform(uncallable_pack_func, uncallable_unpack_func)

        describe "allow_callable":
            it "sets _allow_callable to the value passed in", V:
                with V.clone() as (res, setd):
                    assert V.t.allow_callable() is res
                assert setd == {"_allow_callable": True}

        describe "default":
            it "creates a function that takes in the pkt if not callable", V:
                val = mock.NonCallableMock(name="value")
                with V.clone() as (res, setd):
                    assert V.t.default(val) is res
                assert list(setd) == ["_default"]
                assert setd["_default"](V.pkt) is val

            it "just sets the callable if already callable", V:
                val = mock.Mock(name="value")
                with V.clone() as (res, setd):
                    assert V.t.default(val) is res
                assert setd == {"_default": val}

        describe "optional":
            it "sets _optional to True", V:
                with V.clone() as (res, setd):
                    assert V.t.optional() is res
                assert setd == {"_optional": True}

        describe "override":
            it "sets _override to the value if callable", V:
                val = mock.Mock(name="val")
                with V.clone() as (res, setd):
                    assert V.t.override(val) is res
                assert setd == {"_override": val}

            it "sets _override to a callable taking in packet return value if not callable", V:
                val = mock.NonCallableMock(name="val")
                with V.clone() as (res, setd):
                    assert V.t.override(val) is res
                assert list(setd) == ["_override"]
                assert setd["_override"](V.pkt) is val

    describe "installing types":
        it "expects a list of (name, size, fmt, conversion) to create types from":
            install = [("D2", 64, "<d", float), ("B2", None, None, bytes)]

            expected = {
                # D2 has a non None size, so we expect it to be called with the size
                ("D2", "<d", float): lambda s: ("D2", "<d", float, s)
                # B2 has a None size, so we don't expect it to be called
                ,
                ("B2", None, bytes): ("B2", None, bytes, None),
            }

            def t(n, f, c):
                return expected[(n, f, c)]

            try:
                with mock.patch.object(Type, "t", t):
                    assert not hasattr(Type, "D2")
                    assert not hasattr(Type, "B2")

                    Type.install(*install)

                    assert Type.D2 == ("D2", "<d", float, 64)
                    assert Type.B2 == ("B2", None, bytes, None)
            finally:
                if hasattr(Type, "D2"):
                    del Type.D2

                if hasattr(Type, "B2"):
                    del Type.B2

    describe "spec":

        @pytest.fixture()
        def V(self):
            class V:
                struct_format = mock.Mock(name="struct_format")
                conversion = any

                pkt = mock.Mock(name="pkt")
                transform = mock.Mock(name="transform")
                unpacking = mock.Mock(name="unpacking")

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

                @hp.memoized_property
                def meta(s):
                    return Meta({"pkt": s.pkt}, [])

            return V()

        it "returns spec as is if found one", V:
            spec = mock.Mock(name="spec")
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=spec)

            with mock.patch.object(V.t, "spec_from_conversion", spec_from_conversion):
                assert V.t.spec(unpacking=V.unpacking) is spec

            spec_from_conversion.assert_called_once_with(V.unpacking)

        it "complains if it can't find a spec for the conversion", V:
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=None)

            with assertRaises(
                BadConversion,
                "Cannot create a specification for this conversion",
                conversion=V.conversion,
            ):
                with mock.patch.object(V.t, "spec_from_conversion", spec_from_conversion):
                    V.t.spec(unpacking=V.unpacking)

        it "returns override if that is specified", V:
            res = mock.Mock(name="res")
            overrider = mock.Mock(name="overrider")
            overridden = mock.Mock(name="overridden", return_value=res)
            with mock.patch("photons_protocol.types.overridden", overridden):
                assert (V.t.override(overrider).spec(V.unpacking)) is res

                overridden.assert_called_once_with(overrider)

            # and without mocks
            val = mock.NonCallableMock(name="val")
            V.pkt.val = val
            overrider = lambda pkt: pkt.val
            assert (
                V.t.override(overrider).spec().normalise(V.meta, mock.Mock(name="whatever"))
            ) is val
            assert V.t.override(val).spec().normalise(V.meta, mock.Mock(name="whatever")) is val

        it "wraps with callable_spec if we allow callable", V:
            t = T.String.allow_callable()
            spec = t.spec(V.unpacking)

            def cb(*args):
                return "hello"

            assert spec.normalise(V.meta, cb) is cb
            assert spec.normalise(V.meta, "hello") == "hello"

    describe "hidden _spec":

        @pytest.fixture()
        def V(self):
            class V:
                struct_format = mock.Mock(name="struct_format")
                conversion = mock.Mock(name="conversion")

                pkt = mock.Mock(name="pkt")
                unpacking = mock.Mock(name="unpacking")

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

            return V()

    describe "spec_from_conversion":

        @contextmanager
        def mocked_spec(self, name, conversion):
            struct_format = mock.Mock(name="struct_format")
            size_bits = mock.Mock(name="size_bits")
            t = Type(struct_format, conversion).S(size_bits)

            spec = mock.Mock(name="spec")
            spec_maker = mock.Mock(name=name, return_value=spec)
            with mock.patch("photons_protocol.types.{0}".format(name), spec_maker):
                yield t, spec_maker, spec, size_bits

        it "returns from the static types if in there":
            unpacking = mock.Mock(name="unpacking")
            struct_format = mock.Mock(name="struct_format")

            assert type(static_conversion_from_spec) == dict
            assert len(static_conversion_from_spec) == 5

            for conv in static_conversion_from_spec:
                t = Type(struct_format, conv)
                assert t.spec_from_conversion(unpacking) is static_conversion_from_spec[conv]

        it "gets us a bytes_spec if conversion is bytes":
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("bytes_spec", bytes) as (t, spec_maker, spec, size_bits):
                assert t.spec_from_conversion(unpacking) is spec

            spec_maker.assert_called_once_with(size_bits, unpacking=unpacking)

        it "gets us an integer_spec if conversion is int":
            unpacking = mock.Mock(name="unpacking")

            spec = mock.Mock(name="spec")
            make_integer_spec = mock.Mock(name="make_integer_spec", return_value=spec)

            struct_format = mock.Mock(name="struct_format")
            t = Type(struct_format, int)

            with mock.patch.object(t, "make_integer_spec", make_integer_spec):
                assert t.spec_from_conversion(unpacking) is spec

            make_integer_spec.assert_called_once_with(unpacking)

        it "gets us a bytes_as_string_spec if conversion is str":
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("bytes_as_string_spec", str) as (t, spec_maker, spec, size_bits):
                assert t.spec_from_conversion(unpacking) is spec

            spec_maker.assert_called_once_with(size_bits, unpacking=unpacking)

        it "gets us a csv_spec if conversion is tuple of list, str and comma":
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("csv_spec", (list, str, ",")) as (
                t,
                spec_maker,
                spec,
                size_bits,
            ):
                assert t.spec_from_conversion(unpacking) is spec

            spec_maker.assert_called_once_with(size_bits, unpacking=unpacking)

    describe "make_integer_spec":

        @pytest.fixture()
        def V(self):
            class V:
                pkt = mock.Mock(name="pkt")
                unpacking = mock.Mock(name="unpacking")
                allow_float = mock.Mock(name="allow_float")
                struct_format = mock.Mock(name="struct_format")
                unknown_enum_values = mock.Mock(name="unknown_enum_values")

                @hp.memoized_property
                def t(s):
                    t = Type(s.struct_format, int)
                    t._allow_float = s.allow_float
                    t._unknown_enum_values = s.unknown_enum_values
                    return t

                @hp.memoized_property
                def meta(s):
                    return Meta({"pkt": s.pkt}, [])

                @contextmanager
                def mocked_integer_spec(s):
                    spec = mock.Mock(name="spec")
                    integer_spec = mock.Mock(name="integer_spec", return_value=spec)
                    with mock.patch("photons_protocol.types.integer_spec", integer_spec):
                        yield integer_spec, spec

            return V()

        it "creates integer_spec with enum if we have one", V:
            em = mock.Mock(name="em")

            with V.mocked_integer_spec() as (integer_spec, spec):
                t = V.t.enum(em, allow_unknown=V.unknown_enum_values)
                assert t.make_integer_spec(V.unpacking) is spec

            integer_spec.assert_called_once_with(
                em,
                None,
                unpacking=V.unpacking,
                allow_float=V.allow_float,
                unknown_enum_values=V.unknown_enum_values,
            )

        it "creates integer_spec with bitmask if we have one", V:
            bitmask = mock.Mock(name="bitmask")

            with V.mocked_integer_spec() as (integer_spec, spec):
                assert V.t.bitmask(bitmask).make_integer_spec(V.unpacking) is spec

            integer_spec.assert_called_once_with(
                None,
                bitmask,
                unpacking=V.unpacking,
                allow_float=V.allow_float,
                unknown_enum_values=V.unknown_enum_values,
            )

        it "creates integer_spec with neither enum or bitmask if we have neither", V:
            with V.mocked_integer_spec() as (integer_spec, spec):
                assert V.t.make_integer_spec(V.unpacking) is spec

            integer_spec.assert_called_once_with(
                None,
                None,
                unpacking=V.unpacking,
                allow_float=V.allow_float,
                unknown_enum_values=V.unknown_enum_values,
            )

    describe "transforming":

        @pytest.fixture()
        def V(self):
            class V:
                pkt = mock.Mock(name="pkt")
                value = mock.Mock(name="value")
                packd = mock.Mock(name="packd")
                unpackd = mock.Mock(name="unpackd")
                conversion = mock.Mock(name="conversion")
                struct_format = mock.Mock(name="struct_format")

                @hp.memoized_property
                def meta(s):
                    return Meta({"pkt": s.pkt}, [])

                @hp.memoized_property
                def pack_func(s):
                    return mock.Mock(name="pack_func", return_value=s.packd)

                @hp.memoized_property
                def unpack_func(s):
                    return mock.Mock(name="unpack_func", return_value=s.unpackd)

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

            return V()

        describe "do_pack_transform":
            it "return value if no transformer", V:
                assert V.t.do_pack_transform(V.pkt, V.value) is V.value

            it "uses the transformer if we have one", V:
                t = V.t.transform(V.pack_func, V.unpack_func)
                assert t._pack_transform is V.pack_func
                assert t.do_pack_transform(V.pkt, V.value) is V.packd

        describe "untransform":
            it "does nothing if no transformer", V:
                assert V.t.do_unpack_transform(V.pkt, V.value) is V.value

            it "transforms if we have one", V:
                t = V.t.transform(V.pack_func, V.unpack_func)
                assert t._unpack_transform is V.unpack_func
                assert t.do_unpack_transform(V.pkt, V.value) is V.unpackd
