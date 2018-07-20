# coding: spec

from photons_protocol.types import Type, Optional, static_conversion_from_spec, json_spec
from photons_protocol.errors import BadConversion
from photons_protocol.types import Type as T

from photons_app.errors import ProgrammerError
from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.errors import BadSpecValue
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from contextlib import contextmanager
from bitarray import bitarray
import mock
import json

describe TestCase, "the json spec":
    it "can match just static types":
        for val in ("adsf", True, False, None, 0, 1, 1.2):
            self.assertEqual(json_spec.normalise(Meta.empty(), val), val)

    it "can match lists":
        for val in ([], ["asdf"], ["asdf", True, 1]):
            self.assertEqual(json_spec.normalise(Meta.empty(), val), val)

    it "can match nested lists":
        for val in ([[]], ["asdf", [1]], [["asdf", True], [1]]):
            self.assertEqual(json_spec.normalise(Meta.empty(), val), val)

    it "can match dictionaries":
        for val in ({}, {"1": "2", "2": 2, "3": False}):
            self.assertEqual(json_spec.normalise(Meta.empty(), val), val)

    it "can match nested dictionaries":
        val = {"asdf": {"adf": {"asdf": 2, "adf": False, "eieu": None}}}
        self.assertEqual(json_spec.normalise(Meta.empty(), val), val)

    it "complains about things that aren't json like objects, callables and non string keys":
        for val in (type("adf", (object, ), {}), any, json, lambda: 1):
            with self.fuzzyAssertRaisesError(BadSpecValue):
                json_spec.normalise(Meta.empty(), val)

        try:
            json_spec.normalise(Meta.empty(), {"one": {1: 2}})
            assert False, "Expected an error"
        except BadSpecValue as error:
            self.assertEqual(error.errors[0].errors[0].message, "Expected a string")

describe TestCase, "Type":
    it "takes in struct_format and conversion":
        struct_format = mock.Mock(name="struct_format")
        conversion = mock.Mock(name="conversion")
        t = Type(struct_format, conversion)
        self.assertIs(t.struct_format, struct_format)
        self.assertIs(t.conversion, conversion)

    describe "Adding size_bits":
        before_each:
            self.struct_format = mock.Mock(name="struct_format")
            self.conversion = mock.Mock(name="conversion")
            self.t = Type(self.struct_format, self.conversion)

        describe "calling an instance":
            it "defers to the S function":
                S = mock.Mock(name="S")
                size_bits = mock.Mock(name="size_bits")
                left = mock.Mock(name="left")

                ret = mock.Mock(name="ret")
                S.return_value = ret
                with mock.patch.object(self.t, "S", S):
                    self.assertIs(self.t(size_bits, left=left), ret)

                S.assert_called_once_with(size_bits, left=left)

                # Doesn't touch the original type
                self.assertIs(self.t.size_bits, NotImplemented)

        describe "calling the S function":
            it "creates a new object and passes on 'private' attributes":
                field_names = (
                      "_enum"
                    , "_many"
                    , "_bitmask"
                    , "_dynamic"
                    , "_default"
                    , "_override"
                    , "_many_kls"
                    , "_many_size"
                    , "_transform"
                    , "_unpack_transform"
                    , "_allow_callable"
                    , "_optional"
                    , "_allow_float"
                    , "_version_number"
                    )

                fields = {}
                for field in field_names:
                    fields[field] = mock.Mock(name="field")
                    assert getattr(self.t, field) in (sb.NotSpecified, False)

                size_bits = mock.Mock(name="size_bits")
                left = mock.Mock(name="left")

                res = self.t.S(size_bits, left=left)
                self.assertIs(res.size_bits, size_bits)
                self.assertIs(res.left_cut, left)

                for name, val in fields.items():
                    setattr(res, name, val)

                for field in field_names:
                    assert getattr(self.t, field) in (sb.NotSpecified, False)
                    assert getattr(res, field) is fields[field]

                size_bits2 = mock.Mock(name="size_bits2")
                res2 = res.S(size_bits2)

                # Res is untouched
                self.assertIs(res.size_bits, size_bits)
                self.assertIs(res.left_cut, left)

                # res2 has the new things
                self.assertIs(res2.size_bits, size_bits2)
                self.assertIs(res2.left_cut, left)

                # Our custom fields are passed on
                for field in field_names:
                    assert getattr(res2, field) is fields[field]

    describe "Type.t":
        it "generates a new class from Type and instantiates it":
            struct_format = mock.Mock(name="struct_format")
            conversion = mock.Mock(name="conversion")
            t = Type.t("bob", struct_format, conversion)

            self.assertEqual(t.__class__.__name__, "bob")
            self.assertIs(t.struct_format, struct_format)
            self.assertIs(t.conversion, conversion)
            assert issubclass(t.__class__, Type)
            self.assertIsNot(t.__class__, Type)

    describe "modifiers":
        before_each:
            self.struct_format = mock.Mock(name="struct_format")
            self.conversion = mock.Mock(name="conversion")
            self.t = Type(self.struct_format, self.conversion)

        @contextmanager
        def clone(self, cloned=True):
            setd = {}
            class Clone(object):
                def __setattr__(s, name, val):
                    assert name not in setd
                    setd[name] = val

            size_bits = mock.Mock(name="size_bits")
            self.t.size_bits = size_bits

            res = Clone()
            S = mock.Mock(name="S", return_value=res)
            with mock.patch.object(self.t, "S", S):
                yield res, setd

            if cloned:
                S.assert_called_once_with(size_bits)
            else:
                self.assertEqual(len(S.mock_calls), 0)

        describe "allow_float":
            it "sets _allow_float to True":
                with self.clone() as (res, setd):
                    self.assertIs(self.t.allow_float(), res)
                self.assertEqual(setd, {"_allow_float": True})

        describe "version_number":
            it "sets _version_number to True":
                with self.clone() as (res, setd):
                    self.assertIs(self.t.version_number(), res)
                self.assertEqual(setd, {"_version_number": True})

        describe "enum":
            it "sets _enum to the value passed in":
                em = mock.Mock(name="enum")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.enum(em), res)
                self.assertEqual(setd, {"_enum": em})

        describe "many":
            it "sets _many_kls and _many_size to the values passed in":
                mn = mock.Mock(name="manyiser")
                ms = mock.Mock(name="sizer")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.many(mn, ms), res)
                self.assertEqual(setd, {"_many_kls": mn, "_many_size": ms, "_many": True})

        describe "dynamic":
            it "sets _dynamic to the value passed in":
                dn = mock.Mock(name="dynamiser")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.dynamic(dn), res)
                self.assertEqual(setd, {"_dynamic": dn})

        describe "bitmask":
            it "sets _bitmask to the value passed in":
                bm = mock.Mock(name="bitmask")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.bitmask(bm), res)
                self.assertEqual(setd, {"_bitmask": bm})

        describe "transform":
            it "sets _transform and _unpack_transform in that order":
                pack_func = mock.Mock(name="pack_Func")
                unpack_func = mock.Mock(name="unpack_func")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.transform(pack_func, unpack_func), res)
                self.assertEqual(setd, {"_transform": pack_func, "_unpack_transform": unpack_func})

            it "complains if either function isn't callable":
                pack_func = mock.Mock(name="pack_Func")
                unpack_func = mock.Mock(name="unpack_func")

                uncallable_pack_func = mock.NonCallableMock(name="uncallable_pack_func")
                uncallable_unpack_func = mock.NonCallableMock(name="uncallable_unpack_func")

                with self.clone(cloned=False) as (res, setd):
                    with self.fuzzyAssertRaisesError(ProgrammerError, "Sorry, transform can only be given two callables"):
                        self.t.transform(uncallable_pack_func, unpack_func)

                    with self.fuzzyAssertRaisesError(ProgrammerError, "Sorry, transform can only be given two callables"):
                        self.t.transform(pack_func, uncallable_unpack_func)

                    with self.fuzzyAssertRaisesError(ProgrammerError, "Sorry, transform can only be given two callables"):
                        self.t.transform(uncallable_pack_func, uncallable_unpack_func)

        describe "allow_callable":
            it "sets _allow_callable to the value passed in":
                with self.clone() as (res, setd):
                    self.assertIs(self.t.allow_callable(), res)
                self.assertEqual(setd, {"_allow_callable": True})

        describe "default":
            it "creates a function that takes in the pkt if not callable":
                pkt = mock.Mock(name="pkt")
                val = mock.NonCallableMock(name="value")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.default(val), res)
                self.assertEqual(list(setd), ["_default"])
                self.assertIs(setd["_default"](pkt), val)

            it "just sets the callable if already callable":
                val = mock.Mock(name="value")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.default(val), res)
                self.assertEqual(setd, {"_default": val})

        describe "optional":
            it "sets _optional to True":
                with self.clone() as (res, setd):
                    self.assertIs(self.t.optional(), res)
                self.assertEqual(setd, {"_optional": True})

        describe "override":
            it "sets _override to the value if callable":
                val = mock.Mock(name="val")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.override(val), res)
                self.assertEqual(setd, {"_override": val})

            it "sets _override to a callable taking in packet return value if not callable":
                pkt = mock.Mock(name="pkt")
                val = mock.NonCallableMock(name="val")
                with self.clone() as (res, setd):
                    self.assertIs(self.t.override(val), res)
                self.assertEqual(list(setd), ["_override"])
                self.assertIs(setd["_override"](pkt), val)

    describe "installing types":
        it "expects a list of (name, size, fmt, conversion) to create types from":
            install = [
                  ("D2", 64,   "<d",  float)
                , ("B2",  None, None, bytes)
                ]

            expected = {
                  # D2 has a non None size, so we expect it to be called with the size
                  ("D2", "<d", float): lambda s: ("D2", "<d", float, s)
                  # B2 has a None size, so we don't expect it to be called
                , ("B2", None, bytes): ("B2", None, bytes, None)
                }

            def t(n, f, c):
                return expected[(n, f, c)]

            try:
                with mock.patch.object(Type, "t", t):
                    assert not hasattr(Type, "D2")
                    assert not hasattr(Type, "B2")

                    Type.install(*install)

                    self.assertEqual(Type.D2, ("D2", "<d", float, 64))
                    self.assertEqual(Type.B2, ("B2", None, bytes, None))
            finally:
                if hasattr(Type, "D2"):
                    del Type.D2

                if hasattr(Type, "B2"):
                    del Type.B2

    describe "spec":
        before_each:
            self.struct_format = mock.Mock(name="struct_format")
            self.conversion = any
            self.t = Type(self.struct_format, self.conversion)

            self.pkt = mock.Mock(name="pkt")
            self.transform = mock.Mock(name="transform")
            self.unpacking = mock.Mock(name="unpacking")

        @contextmanager
        def mocked_spec(self, pkt, unpacking, transform):
            s = mock.Mock(name="untransformed_spec")
            spec = mock.Mock(name="spec")
            _spec = mock.Mock(name="_spec", return_value=s)
            _mts = mock.Mock(name="_maybe_transform_spec", return_value=spec)
            with mock.patch.object(Type, "_maybe_transform_spec", _mts):
                with mock.patch.object(Type, "_spec", _spec):
                    yield spec
            _spec.assert_called_once_with(pkt, unpacking=unpacking)
            _mts.assert_called_once_with(pkt, s, unpacking, transform=transform)

        it "returns override if that is specified":
            res = mock.Mock(name="res")
            overrider = mock.Mock(name="overrider")
            overridden = mock.Mock(name="overridden", return_value=res)
            with self.mocked_spec(self.pkt, self.unpacking, self.transform) as spec:
                with mock.patch("photons_protocol.types.overridden", overridden):
                    self.assertIs(self.t.override(overrider).spec(self.pkt, self.unpacking, transform=self.transform), res)

                overridden.assert_called_once_with(overrider, self.pkt)

            # and without mocks
            val = mock.NonCallableMock(name="val")
            pkt = mock.Mock(name="pkt", val=val)
            overrider = lambda pkt: pkt.val
            self.assertIs(self.t.override(overrider).spec(pkt).normalise(Meta.empty(), mock.Mock(name="whatever")), val)
            self.assertIs(self.t.override(val).spec(pkt).normalise(Meta.empty(), mock.Mock(name="whatever")), val)

        it "returns default if that is specified":
            res = mock.Mock(name="res")
            defaulter = mock.Mock(name="defaulter")
            defaulted = mock.Mock(name="defaulted", return_value=res)
            with self.mocked_spec(self.pkt, self.unpacking, self.transform) as spec:
                with mock.patch("photons_protocol.types.defaulted", defaulted):
                    self.assertIs(self.t.default(defaulter).spec(self.pkt, self.unpacking, transform=self.transform), res)

                defaulted.assert_called_once_with(spec, defaulter, self.pkt)

            # and without mocks
            val = mock.NonCallableMock(name="val")
            pkt = mock.Mock(name="pkt", val=val)
            defaulter = lambda pkt: pkt.val

            whatever = mock.Mock(name="whatever")
            self.assertIs(self.t.default(defaulter).spec(pkt).normalise(Meta.empty(), whatever), whatever)
            self.assertIs(self.t.default(defaulter).spec(pkt).normalise(Meta.empty(), sb.NotSpecified), val)
            self.assertIs(self.t.default(val).spec(pkt).normalise(Meta.empty(), sb.NotSpecified), val)

        it "returns optional if that is specified":
            res = mock.Mock(name="res")
            optional = mock.Mock(name="optional", return_value=res)
            with self.mocked_spec(self.pkt, self.unpacking, self.transform) as spec:
                with mock.patch("photons_protocol.types.optional", optional):
                    self.assertIs(self.t.optional().spec(self.pkt, self.unpacking, transform=self.transform), res)

                optional.assert_called_once_with(spec)

            # and without mocks
            pkt = mock.Mock(name="pkt")
            whatever = mock.Mock(name="whatever")
            self.assertIs(self.t.optional().spec(pkt).normalise(Meta.empty(), whatever), whatever)
            self.assertIs(self.t.optional().spec(pkt).normalise(Meta.empty(), sb.NotSpecified), Optional)

        it "returns just the spec otherwise":
            with self.mocked_spec(self.pkt, self.unpacking, transform=self.transform) as spec:
                self.assertIs(self.t.spec(self.pkt, self.unpacking, transform=self.transform), spec)

        it "wraps with callable_spec if we allow callable":
            t = T.String.allow_callable()
            spec = t.spec(self.pkt, self.unpacking)

            def cb(*args):
                return "hello"

            self.assertIs(spec.normalise(Meta.empty(), cb), cb)
            self.assertEqual(spec.normalise(Meta.empty(), "hello"), "hello")

    describe "dynamic_wrapper":
        before_each:
            self.struct_format = mock.Mock(name="struct_format")
            self.conversion = any
            self.t = Type(self.struct_format, self.conversion)

            self.spec = mock.Mock(name="spec")
            self.pkt = mock.Mock(name="pkt")
            self.unpacking = mock.Mock(name="unpacking")

        it "returns us an expand_spec with a made up PacketSpec class":
            res = mock.Mock(name="res")
            expand_spec = mock.Mock(name="expand_spec", return_value=res)

            def dynamic(pkt):
                self.assertIs(pkt, self.pkt)
                return [("one", T.Bool), ("two", T.Int8), ("three", T.Int8)]

            with mock.patch("photons_protocol.types.expand_spec", expand_spec):
                self.assertIs(self.t.dynamic(dynamic).dynamic_wrapper(self.spec, self.pkt, unpacking=self.unpacking), res)

            expand_spec.assert_called_once_with(mock.ANY, self.spec, self.unpacking)
            kls = expand_spec.mock_calls[0][1][0]
            self.assertEqual(kls.Meta.all_names, ["one", "two", "three"])
            instance = kls(one=True, two=1, three=4)
            self.assertEqual(instance.pack(), bitarray('11000000000100000'))

    describe "hidden _spec":
        before_each:
            self.struct_format = mock.Mock(name="struct_format")
            self.conversion = mock.Mock(name="conversion")
            self.t = Type(self.struct_format, self.conversion)

            self.pkt = mock.Mock(name="pkt")
            self.unpacking = mock.Mock(name="unpacking")

        it "returns spec as is if found one and no _dynamic and no _many":
            self.assertIs(self.t._dynamic, sb.NotSpecified)

            spec = mock.Mock(name="spec")
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=spec)

            with mock.patch.object(self.t, "spec_from_conversion", spec_from_conversion):
                self.assertIs(self.t._spec(self.pkt, unpacking=self.unpacking), spec)

            spec_from_conversion.assert_called_once_with(self.pkt, self.unpacking)

        it "returns dynamic_wraper if found one and _dynamic and no _many":
            dynamiser = mock.Mock(name="dynamiser")
            t = self.t.dynamic(dynamiser)

            res = mock.Mock(name="res")
            dynamic_wrapper = mock.Mock(name="dynamic_wrapper", return_value=res)

            spec = mock.Mock(name="spec")
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=spec)

            with mock.patch.object(t, "spec_from_conversion", spec_from_conversion):
                with mock.patch.object(t, "dynamic_wrapper", dynamic_wrapper):
                    self.assertIs(t._spec(self.pkt, unpacking=self.unpacking), res)

            spec_from_conversion.assert_called_once_with(self.pkt, self.unpacking)
            dynamic_wrapper.assert_called_once_with(spec, self.pkt, unpacking=self.unpacking)

        it "returns many_wraper if found one and _many":
            manyiser = mock.Mock(name="manyiser")
            sizer = mock.Mock(name="sizer")
            t = self.t.many(manyiser, sizer)

            res = mock.Mock(name="res")
            many_wrapper = mock.Mock(name="many_wrapper", return_value=res)

            spec = mock.Mock(name="spec")
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=spec)

            with mock.patch.object(t, "spec_from_conversion", spec_from_conversion):
                with mock.patch.object(t, "many_wrapper", many_wrapper):
                    self.assertIs(t._spec(self.pkt, unpacking=self.unpacking), res)

            spec_from_conversion.assert_called_once_with(self.pkt, self.unpacking)
            many_wrapper.assert_called_once_with(spec, self.pkt, unpacking=self.unpacking)

        it "complains if it can't find a spec for the conversion":
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=None)

            with self.fuzzyAssertRaisesError(BadConversion, "Cannot create a specification for this conversion", conversion=self.conversion):
                with mock.patch.object(self.t, "spec_from_conversion", spec_from_conversion):
                    self.t._spec(self.pkt, unpacking=self.unpacking)

    describe "_maybe_transform_spec":
        before_each:
            self.struct_format = mock.Mock(name="struct_format")
            self.conversion = mock.Mock(name="conversion")
            self.t = Type(self.struct_format, self.conversion)

            self.pkt = mock.Mock(name="pkt")
            self.spec = mock.Mock(name="spec")

        it "returns as is if unpacking or don't have _transform":
            self.t._transform = mock.Mock(name='transform')
            self.assertIs(self.t._maybe_transform_spec(self.pkt, self.spec, True), self.spec)

            self.t._transform = sb.NotSpecified
            self.assertIs(self.t._maybe_transform_spec(self.pkt, self.spec, False), self.spec)

        it "returns as is if no _transform":
            self.t._transform = sb.NotSpecified
            self.assertIs(self.t._maybe_transform_spec(self.pkt, self.spec, False), self.spec)
            self.assertIs(self.t._maybe_transform_spec(self.pkt, self.spec, True), self.spec)

        it "wraps in transform_spec if we have _transform and aren't unpacking":
            self.t._transform = mock.Mock(name="_transform")

            wrapped = mock.Mock(name='wrapped')
            transform_spec = mock.Mock(name='transform_spec', return_value=wrapped)

            with mock.patch("photons_protocol.types.transform_spec", transform_spec):
                self.assertIs(self.t._maybe_transform_spec(self.pkt, self.spec, False), wrapped)

            transform_spec.assert_called_once_with(self.pkt, self.spec, self.t.do_transform)

    describe "spec_from_conversion":
        it "returns from the static types if in there":
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")
            struct_format = mock.Mock(name="struct_format")

            self.assertEqual(type(static_conversion_from_spec), dict)
            self.assertEqual(len(static_conversion_from_spec), 5)

            for conv in static_conversion_from_spec:
                t = Type(struct_format, conv)
                self.assertIs(t.spec_from_conversion(pkt, unpacking), static_conversion_from_spec[conv])

        @contextmanager
        def mocked_spec(self, name, conversion):
            struct_format = mock.Mock(name="struct_format")
            size_bits = mock.Mock(name="size_bits")
            t = Type(struct_format, conversion).S(size_bits)

            spec = mock.Mock(name="spec")
            spec_maker = mock.Mock(name=name, return_value=spec)
            with mock.patch("photons_protocol.types.{0}".format(name), spec_maker):
                yield t, spec_maker, spec, size_bits

        it "gets us a bytes_spec if conversion is bytes":
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("bytes_spec", bytes) as (t, spec_maker, spec, size_bits):
                self.assertIs(t.spec_from_conversion(pkt, unpacking), spec)

            spec_maker.assert_called_once_with(pkt, size_bits)

        it "gets us an integer_spec if conversion is int":
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")

            spec = mock.Mock(name="spec")
            make_integer_spec = mock.Mock(name="make_integer_spec", return_value=spec)

            struct_format = mock.Mock(name="struct_format")
            t = Type(struct_format, int)

            with mock.patch.object(t, "make_integer_spec", make_integer_spec):
                self.assertIs(t.spec_from_conversion(pkt, unpacking), spec)

            make_integer_spec.assert_called_once_with(pkt, unpacking)

        it "gets us a bytes_as_string_spec if conversion is str":
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("bytes_as_string_spec", str) as (t, spec_maker, spec, size_bits):
                self.assertIs(t.spec_from_conversion(pkt, unpacking), spec)

            spec_maker.assert_called_once_with(pkt, size_bits, unpacking=unpacking)

        it "gets us a csv_spec if conversion is tuple of list, str and comma":
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("csv_spec", (list, str, ",")) as (t, spec_maker, spec, size_bits):
                self.assertIs(t.spec_from_conversion(pkt, unpacking), spec)

            spec_maker.assert_called_once_with(pkt, size_bits, unpacking=unpacking)

    describe "make_integer_spec":
        before_each:
            self.struct_format = mock.Mock(name="struct_format")
            self.t = Type(self.struct_format, int)

            self.allow_float = mock.Mock(name="allow_float")
            self.t._allow_float = self.allow_float

            self.pkt = mock.Mock(name="pkt")
            self.unpacking = mock.Mock(name="unpacking")

        @contextmanager
        def mocked_integer_spec(self):
            spec = mock.Mock(name="spec")
            integer_spec = mock.Mock(name="integer_spec", return_value=spec)
            with mock.patch("photons_protocol.types.integer_spec", integer_spec):
                yield integer_spec, spec

        @contextmanager
        def mocked_version_number_spec(self):
            spec = mock.Mock(name="spec")
            version_number_spec = mock.Mock(name="version_number_spec", return_value=spec)
            with mock.patch("photons_protocol.types.version_number_spec", version_number_spec):
                yield version_number_spec, spec

        it "creates version_number_spec if we have _version_number set":
            em = mock.Mock(name="em")

            with self.mocked_version_number_spec() as (version_number_spec, spec):
                self.assertIs(self.t.version_number().make_integer_spec(self.pkt, self.unpacking), spec)

            version_number_spec.assert_called_once_with(unpacking=self.unpacking)

        it "creates integer_spec with enum if we have one":
            em = mock.Mock(name="em")

            with self.mocked_integer_spec() as (integer_spec, spec):
                self.assertIs(self.t.enum(em).make_integer_spec(self.pkt, self.unpacking), spec)

            integer_spec.assert_called_once_with(self.pkt, em, None, unpacking=self.unpacking, allow_float=self.allow_float)

        it "creates integer_spec with bitmask if we have one":
            bitmask = mock.Mock(name="bitmask")

            with self.mocked_integer_spec() as (integer_spec, spec):
                self.assertIs(self.t.bitmask(bitmask).make_integer_spec(self.pkt, self.unpacking), spec)

            integer_spec.assert_called_once_with(self.pkt, None, bitmask, unpacking=self.unpacking, allow_float=self.allow_float)

        it "creates integer_spec with neither enum or bitmask if we have neither":
            with self.mocked_integer_spec() as (integer_spec, spec):
                self.assertIs(self.t.make_integer_spec(self.pkt, self.unpacking), spec)

            integer_spec.assert_called_once_with(self.pkt, None, None, unpacking=self.unpacking, allow_float=self.allow_float)

    describe "transforming":
        before_each:
            self.struct_format = mock.Mock(name="struct_format")
            self.conversion = mock.Mock(name="conversion")
            self.t = Type(self.struct_format, self.conversion)

            self.pkt = mock.Mock(name="pkt")
            self.value = mock.Mock(name="value")

            self.transformed = mock.Mock(name="transformed")
            self.transformer = mock.Mock(name="transformer", return_value=self.transformed)

            self.untransformed = mock.Mock(name="untransformed")
            self.untransformer = mock.Mock(name="untransformer", return_value=self.untransformed)

        describe "do_transform":
            it "return value if no transformer":
                self.assertIs(self.t.do_transform(self.pkt, self.value), self.value)

            it "uses the transformer if we have one":
                self.assertIs(self.t.transform(self.transformer, self.untransformer).do_transform(self.pkt, self.value), self.transformed)

        describe "untransform":
            it "does nothing if no untransformer":
                self.assertIs(self.t.untransform(self.value), self.value)

            it "transforms if we have an untransformer":
                self.assertIs(self.t.transform(self.transformer, self.untransformer).untransform(self.value), self.untransformed)
                self.untransformer.assert_called_once_with(self.value)
