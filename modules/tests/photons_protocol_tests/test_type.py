import enum
import json
from contextlib import contextmanager
from unittest import mock

import pytest
from bitarray import bitarray
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue, Meta, sb
from photons_app import helpers as hp
from photons_app.errors import ProgrammerError
from photons_protocol.errors import BadConversion
from photons_protocol.types import Optional, Type, UnknownEnum, json_spec, static_conversion_from_spec
from photons_protocol.types import Type as T


class TestTheJsonSpec:
    def test_it_can_match_just_static_types(self):
        for val in ("adsf", True, False, None, 0, 1, 1.2):
            assert json_spec.normalise(Meta.empty(), val) == val

    def test_it_can_match_lists(self):
        for val in ([], ["asdf"], ["asdf", True, 1]):
            assert json_spec.normalise(Meta.empty(), val) == val

    def test_it_can_match_nested_lists(self):
        for val in ([[]], ["asdf", [1]], [["asdf", True], [1]]):
            assert json_spec.normalise(Meta.empty(), val) == val

    def test_it_can_match_dictionaries(self):
        for val in ({}, {"1": "2", "2": 2, "3": False}):
            assert json_spec.normalise(Meta.empty(), val) == val

    def test_it_can_match_nested_dictionaries(self):
        val = {"asdf": {"adf": {"asdf": 2, "adf": False, "eieu": None}}}
        assert json_spec.normalise(Meta.empty(), val) == val

    def test_it_complains_about_things_that_arent_json_like_objects_callables_and_non_string_keys(
        self,
    ):
        for val in (type("adf", (object,), {}), any, json, lambda: 1):
            with assertRaises(BadSpecValue):
                json_spec.normalise(Meta.empty(), val)

        try:
            json_spec.normalise(Meta.empty(), {"one": {1: 2}})
            assert False, "Expected an error"
        except BadSpecValue as error:
            assert error.errors[0].errors[0].message == "Expected a string"


class TestType:
    def test_it_takes_in_struct_format_and_conversion(self):
        struct_format = mock.Mock(name="struct_format")
        conversion = mock.Mock(name="conversion")
        t = Type(struct_format, conversion)
        assert t.struct_format is struct_format
        assert t.conversion is conversion

    class TestAddingSizeBits:
        @pytest.fixture()
        def V(self):
            class V:
                struct_format = mock.Mock(name="struct_format")
                conversion = mock.Mock(name="conversion")

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

            return V()

        class TestCallingAnInstance:
            def test_it_defers_to_the_S_function(self, V):
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

        class TestCallingTheSFunction:
            def test_it_creates_a_new_object_and_passes_on_private_attributes(self, V):
                field_names = (
                    "_enum",
                    "_bitmask",
                    "_dynamic",
                    "_default",
                    "_optional",
                    "_multiple",
                    "_override",
                    "_transform",
                    "_allow_float",
                    "_multiple_kls",
                    "_allow_callable",
                    "_version_number",
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

    class TestTypet:
        def test_it_generates_a_new_class_from_Type_and_instantiates_it(self):
            struct_format = mock.Mock(name="struct_format")
            conversion = mock.Mock(name="conversion")
            t = Type.t("bob", struct_format, conversion)

            assert t.__class__.__name__ == "bob"
            assert t.struct_format is struct_format
            assert t.conversion is conversion
            assert issubclass(t.__class__, Type)
            assert t.__class__ is not Type

    class TestModifiers:
        @pytest.fixture()
        def V(self):
            class V:
                struct_format = mock.Mock(name="struct_format")
                conversion = mock.Mock(name="conversion")

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

                @contextmanager
                def clone(s, cloned=True):
                    setd = {}

                    class Clone:
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

        class TestAllowFloat:
            def test_it_sets_allow_float_to_True(self, V):
                with V.clone() as (res, setd):
                    assert V.t.allow_float() is res
                assert setd == {"_allow_float": True}

        class TestVersionNumber:
            def test_it_sets_version_number_to_True(self, V):
                with V.clone() as (res, setd):
                    assert V.t.version_number() is res
                assert setd == {"_version_number": True}

        class TestEnum:
            def test_it_sets_enum_to_the_value_passed_in(self, V):
                em = mock.Mock(name="enum")
                with V.clone() as (res, setd):
                    assert V.t.enum(em) is res
                assert setd == {"_enum": em, "_unknown_enum_values": True}

            def test_it_allows_unknown_enums_by_default(self, V):
                class E(enum.Enum):
                    ONE = 1
                    TWO = 2

                field = V.t.Uint8.enum(E)
                spec = field.spec(mock.Mock(name="pkt"), unpacking=True)

                value = spec.normalise(Meta.empty(), 6)
                assert value == UnknownEnum(6)

                value = spec.normalise(Meta.empty(), 1)
                assert value == E.ONE

                value = spec.normalise(Meta.empty(), E.ONE)
                assert value == E.ONE

            def test_it_sets_unknown_enum_values_to_the_allow_unknown_value_passed_in(self, V):
                em = mock.Mock(name="enum")
                allow_unknown = mock.Mock(name="allow_unknown")
                with V.clone() as (res, setd):
                    assert V.t.enum(em, allow_unknown=allow_unknown) is res
                assert setd == {"_enum": em, "_unknown_enum_values": allow_unknown}

        class TestDynamic:
            def test_it_sets_dynamic_to_the_value_passed_in(self, V):
                dn = mock.Mock(name="dynamiser")
                with V.clone() as (res, setd):
                    assert V.t.dynamic(dn) is res
                assert setd == {"_dynamic": dn}

        class TestBitmask:
            def test_it_sets_bitmask_to_the_value_passed_in(self, V):
                bm = mock.Mock(name="bitmask")
                with V.clone() as (res, setd):
                    assert V.t.bitmask(bm) is res
                assert setd == {"_bitmask": bm}

        class TestTransform:
            def test_it_sets_transform_and_unpack_transform_in_that_order(self, V):
                pack_func = mock.Mock(name="pack_Func")
                unpack_func = mock.Mock(name="unpack_func")
                with V.clone() as (res, setd):
                    assert V.t.transform(pack_func, unpack_func) is res
                assert setd == {"_transform": pack_func, "_unpack_transform": unpack_func}

            def test_it_complains_if_either_function_isnt_callable(self, V):
                pack_func = mock.Mock(name="pack_Func")
                unpack_func = mock.Mock(name="unpack_func")

                uncallable_pack_func = mock.NonCallableMock(name="uncallable_pack_func")
                uncallable_unpack_func = mock.NonCallableMock(name="uncallable_unpack_func")

                with V.clone(cloned=False) as (res, setd):
                    with assertRaises(ProgrammerError, "Sorry, transform can only be given two callables"):
                        V.t.transform(uncallable_pack_func, unpack_func)

                    with assertRaises(ProgrammerError, "Sorry, transform can only be given two callables"):
                        V.t.transform(pack_func, uncallable_unpack_func)

                    with assertRaises(ProgrammerError, "Sorry, transform can only be given two callables"):
                        V.t.transform(uncallable_pack_func, uncallable_unpack_func)

        class TestAllowCallable:
            def test_it_sets_allow_callable_to_the_value_passed_in(self, V):
                with V.clone() as (res, setd):
                    assert V.t.allow_callable() is res
                assert setd == {"_allow_callable": True}

        class TestDefault:
            def test_it_creates_a_function_that_takes_in_the_pkt_if_not_callable(self, V):
                pkt = mock.Mock(name="pkt")
                val = mock.NonCallableMock(name="value")
                with V.clone() as (res, setd):
                    assert V.t.default(val) is res
                assert list(setd) == ["_default"]
                assert setd["_default"](pkt) is val

            def test_it_just_sets_the_callable_if_already_callable(self, V):
                val = mock.Mock(name="value")
                with V.clone() as (res, setd):
                    assert V.t.default(val) is res
                assert setd == {"_default": val}

        class TestOptional:
            def test_it_sets_optional_to_True(self, V):
                with V.clone() as (res, setd):
                    assert V.t.optional() is res
                assert setd == {"_optional": True}

        class TestOverride:
            def test_it_sets_override_to_the_value_if_callable(self, V):
                val = mock.Mock(name="val")
                with V.clone() as (res, setd):
                    assert V.t.override(val) is res
                assert setd == {"_override": val}

            def test_it_sets_override_to_a_callable_taking_in_packet_return_value_if_not_callable(self, V):
                pkt = mock.Mock(name="pkt")
                val = mock.NonCallableMock(name="val")
                with V.clone() as (res, setd):
                    assert V.t.override(val) is res
                assert list(setd) == ["_override"]
                assert setd["_override"](pkt) is val

    class TestInstallingTypes:
        def test_it_expects_a_list_of_name_size_fmt_conversion_to_create_types_from(self):
            install = [("D2", 64, "<d", float), ("B2", None, None, bytes)]

            expected = {
                # D2 has a non None size, so we expect it to be called with the size
                ("D2", "<d", float): lambda s: ("D2", "<d", float, s),
                # B2 has a None size, so we don't expect it to be called
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

    class TestSpec:
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

                @contextmanager
                def mocked_spec(s):
                    uts = mock.Mock(name="untransformed_spec")

                    spec = mock.Mock(name="spec")
                    _spec = mock.Mock(name="_spec", return_value=uts)
                    _mts = mock.Mock(name="_maybe_transform_spec", return_value=spec)

                    with mock.patch.object(Type, "_maybe_transform_spec", _mts):
                        with mock.patch.object(Type, "_spec", _spec):
                            yield spec

                    _spec.assert_called_once_with(s.pkt, unpacking=s.unpacking)
                    _mts.assert_called_once_with(s.pkt, uts, s.unpacking, transform=s.transform)

            return V()

        def test_it_returns_override_if_that_is_specified(self, V):
            res = mock.Mock(name="res")
            overrider = mock.Mock(name="overrider")
            overridden = mock.Mock(name="overridden", return_value=res)
            with V.mocked_spec():
                with mock.patch("photons_protocol.types.overridden", overridden):
                    assert (V.t.override(overrider).spec(V.pkt, V.unpacking, transform=V.transform)) is res

                overridden.assert_called_once_with(overrider, V.pkt)

            # and without mocks
            val = mock.NonCallableMock(name="val")
            pkt = mock.Mock(name="pkt", val=val)

            def overrider(pkt):
                return pkt.val

            assert (V.t.override(overrider).spec(pkt).normalise(Meta.empty(), mock.Mock(name="whatever"))) is val
            assert V.t.override(val).spec(pkt).normalise(Meta.empty(), mock.Mock(name="whatever")) is val

        def test_it_returns_default_if_that_is_specified(self, V):
            res = mock.Mock(name="res")
            defaulter = mock.Mock(name="defaulter")
            defaulted = mock.Mock(name="defaulted", return_value=res)
            with V.mocked_spec() as spec:
                with mock.patch("photons_protocol.types.defaulted", defaulted):
                    assert (V.t.default(defaulter).spec(V.pkt, V.unpacking, transform=V.transform)) is res

                defaulted.assert_called_once_with(spec, defaulter, V.pkt)

            # and without mocks
            val = mock.NonCallableMock(name="val")
            pkt = mock.Mock(name="pkt", val=val)

            def defaulter(pkt):
                return pkt.val

            whatever = mock.Mock(name="whatever")
            assert V.t.default(defaulter).spec(pkt).normalise(Meta.empty(), whatever) is whatever
            assert V.t.default(defaulter).spec(pkt).normalise(Meta.empty(), sb.NotSpecified) is val
            assert V.t.default(val).spec(pkt).normalise(Meta.empty(), sb.NotSpecified) is val

        def test_it_returns_optional_if_that_is_specified(self, V):
            res = mock.Mock(name="res")
            optional = mock.Mock(name="optional", return_value=res)
            with V.mocked_spec() as spec:
                with mock.patch("photons_protocol.types.optional", optional):
                    assert V.t.optional().spec(V.pkt, V.unpacking, transform=V.transform) is res

                optional.assert_called_once_with(spec)

            # and without mocks
            pkt = mock.Mock(name="pkt")
            whatever = mock.Mock(name="whatever")
            assert V.t.optional().spec(pkt).normalise(Meta.empty(), whatever) is whatever
            assert V.t.optional().spec(pkt).normalise(Meta.empty(), sb.NotSpecified) is Optional

        def test_it_returns_just_the_spec_otherwise(self, V):
            with V.mocked_spec() as spec:
                assert V.t.spec(V.pkt, V.unpacking, transform=V.transform) is spec

        def test_it_wraps_with_callable_spec_if_we_allow_callable(self, V):
            t = T.String.allow_callable()
            spec = t.spec(V.pkt, V.unpacking)

            def cb(*args):
                return "hello"

            assert spec.normalise(Meta.empty(), cb) is cb
            assert spec.normalise(Meta.empty(), "hello") == "hello"

    class TestDynamicWrapper:
        @pytest.fixture()
        def V(self):
            class V:
                struct_format = mock.Mock(name="struct_format")
                conversion = any

                spec = mock.Mock(name="spec")
                pkt = mock.Mock(name="pkt")
                unpacking = mock.Mock(name="unpacking")

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

            return V()

        def test_it_returns_us_an_expand_spec_with_a_made_up_PacketSpec_class(self, V):
            res = mock.Mock(name="res")
            expand_spec = mock.Mock(name="expand_spec", return_value=res)

            def dynamic(pkt):
                assert pkt is V.pkt
                return [("one", T.Bool), ("two", T.Int8), ("three", T.Int8)]

            with mock.patch("photons_protocol.types.expand_spec", expand_spec):
                assert (V.t.dynamic(dynamic).dynamic_wrapper(V.spec, V.pkt, unpacking=V.unpacking)) is res

            expand_spec.assert_called_once_with(mock.ANY, V.spec, V.unpacking)
            kls = expand_spec.mock_calls[0][1][0]
            assert kls.Meta.all_names == ["one", "two", "three"]
            instance = kls(one=True, two=1, three=4)
            assert instance.pack() == bitarray("11000000000100000")

    class TestHiddenSpec:
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

        def test_it_returns_spec_as_is_if_found_one_and_no_dynamic(self, V):
            assert V.t._dynamic is sb.NotSpecified

            spec = mock.Mock(name="spec")
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=spec)

            with mock.patch.object(V.t, "spec_from_conversion", spec_from_conversion):
                assert V.t._spec(V.pkt, unpacking=V.unpacking) is spec

            spec_from_conversion.assert_called_once_with(V.pkt, V.unpacking)

        def test_it_returns_dynamic_wraper_if_found_one_and_dynamic(self, V):
            dynamiser = mock.Mock(name="dynamiser")
            t = V.t.dynamic(dynamiser)

            res = mock.Mock(name="res")
            dynamic_wrapper = mock.Mock(name="dynamic_wrapper", return_value=res)

            spec = mock.Mock(name="spec")
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=spec)

            with mock.patch.object(t, "spec_from_conversion", spec_from_conversion):
                with mock.patch.object(t, "dynamic_wrapper", dynamic_wrapper):
                    assert t._spec(V.pkt, unpacking=V.unpacking) is res

            spec_from_conversion.assert_called_once_with(V.pkt, V.unpacking)
            dynamic_wrapper.assert_called_once_with(spec, V.pkt, unpacking=V.unpacking)

        def test_it_complains_if_it_cant_find_a_spec_for_the_conversion(self, V):
            spec_from_conversion = mock.Mock(name="spec_from_conversion", return_value=None)

            with assertRaises(
                BadConversion,
                "Cannot create a specification for this conversion",
                conversion=V.conversion,
            ):
                with mock.patch.object(V.t, "spec_from_conversion", spec_from_conversion):
                    V.t._spec(V.pkt, unpacking=V.unpacking)

    class TestMaybeTransformSpec:
        @pytest.fixture()
        def V(self):
            class V:
                struct_format = mock.Mock(name="struct_format")
                conversion = mock.Mock(name="conversion")

                pkt = mock.Mock(name="pkt")
                spec = mock.Mock(name="spec")

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

            return V()

        def test_it_returns_as_is_if_unpacking_or_dont_have_transform(self, V):
            V.t._transform = mock.Mock(name="transform")
            assert V.t._maybe_transform_spec(V.pkt, V.spec, True) is V.spec

            V.t._transform = sb.NotSpecified
            assert V.t._maybe_transform_spec(V.pkt, V.spec, False) is V.spec

        def test_it_returns_as_is_if_no_transform(self, V):
            V.t._transform = sb.NotSpecified
            assert V.t._maybe_transform_spec(V.pkt, V.spec, False) is V.spec
            assert V.t._maybe_transform_spec(V.pkt, V.spec, True) is V.spec

        def test_it_wraps_in_transform_spec_if_we_have_transform_and_arent_unpacking(self, V):
            V.t._transform = mock.Mock(name="_transform")

            wrapped = mock.Mock(name="wrapped")
            transform_spec = mock.Mock(name="transform_spec", return_value=wrapped)

            with mock.patch("photons_protocol.types.transform_spec", transform_spec):
                assert V.t._maybe_transform_spec(V.pkt, V.spec, False) is wrapped

            transform_spec.assert_called_once_with(V.pkt, V.spec, V.t.do_transform)

    class TestSpecFromConversion:
        @contextmanager
        def mocked_spec(self, name, conversion):
            struct_format = mock.Mock(name="struct_format")
            size_bits = mock.Mock(name="size_bits")
            t = Type(struct_format, conversion).S(size_bits)

            spec = mock.Mock(name="spec")
            spec_maker = mock.Mock(name=name, return_value=spec)
            with mock.patch(f"photons_protocol.types.{name}", spec_maker):
                yield t, spec_maker, spec, size_bits

        def test_it_returns_from_the_static_types_if_in_there(self):
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")
            struct_format = mock.Mock(name="struct_format")

            assert type(static_conversion_from_spec) is dict
            assert len(static_conversion_from_spec) == 5

            for conv in static_conversion_from_spec:
                t = Type(struct_format, conv)
                assert t.spec_from_conversion(pkt, unpacking) is static_conversion_from_spec[conv]

        def test_it_gets_us_a_bytes_spec_if_conversion_is_bytes(self):
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("bytes_spec", bytes) as (t, spec_maker, spec, size_bits):
                assert t.spec_from_conversion(pkt, unpacking) is spec

            spec_maker.assert_called_once_with(pkt, size_bits)

        def test_it_gets_us_an_integer_spec_if_conversion_is_int(self):
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")

            spec = mock.Mock(name="spec")
            make_integer_spec = mock.Mock(name="make_integer_spec", return_value=spec)

            struct_format = mock.Mock(name="struct_format")
            t = Type(struct_format, int)

            with mock.patch.object(t, "make_integer_spec", make_integer_spec):
                assert t.spec_from_conversion(pkt, unpacking) is spec

            make_integer_spec.assert_called_once_with(pkt, unpacking)

        def test_it_gets_us_a_bytes_as_string_spec_if_conversion_is_str(self):
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("bytes_as_string_spec", str) as (t, spec_maker, spec, size_bits):
                assert t.spec_from_conversion(pkt, unpacking) is spec

            spec_maker.assert_called_once_with(pkt, size_bits, unpacking=unpacking)

        def test_it_gets_us_a_csv_spec_if_conversion_is_tuple_of_list_str_and_comma(self):
            pkt = mock.Mock(name="pkt")
            unpacking = mock.Mock(name="unpacking")

            with self.mocked_spec("csv_spec", (list, str, ",")) as (
                t,
                spec_maker,
                spec,
                size_bits,
            ):
                assert t.spec_from_conversion(pkt, unpacking) is spec

            spec_maker.assert_called_once_with(pkt, size_bits, unpacking=unpacking)

    class TestMakeIntegerSpec:
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

                @contextmanager
                def mocked_integer_spec(s):
                    spec = mock.Mock(name="spec")
                    integer_spec = mock.Mock(name="integer_spec", return_value=spec)
                    with mock.patch("photons_protocol.types.integer_spec", integer_spec):
                        yield integer_spec, spec

                @contextmanager
                def mocked_version_number_spec(s):
                    spec = mock.Mock(name="spec")
                    version_number_spec = mock.Mock(name="version_number_spec", return_value=spec)
                    with mock.patch("photons_protocol.types.version_number_spec", version_number_spec):
                        yield version_number_spec, spec

            return V()

        def test_it_creates_version_number_spec_if_we_have_version_number_set(self, V):
            with V.mocked_version_number_spec() as (version_number_spec, spec):
                assert V.t.version_number().make_integer_spec(V.pkt, V.unpacking) is spec

            version_number_spec.assert_called_once_with(unpacking=V.unpacking)

        def test_it_creates_integer_spec_with_enum_if_we_have_one(self, V):
            em = mock.Mock(name="em")

            with V.mocked_integer_spec() as (integer_spec, spec):
                t = V.t.enum(em, allow_unknown=V.unknown_enum_values)
                assert t.make_integer_spec(V.pkt, V.unpacking) is spec

            integer_spec.assert_called_once_with(
                V.pkt,
                em,
                None,
                unpacking=V.unpacking,
                allow_float=V.allow_float,
                unknown_enum_values=V.unknown_enum_values,
            )

        def test_it_creates_integer_spec_with_bitmask_if_we_have_one(self, V):
            bitmask = mock.Mock(name="bitmask")

            with V.mocked_integer_spec() as (integer_spec, spec):
                assert V.t.bitmask(bitmask).make_integer_spec(V.pkt, V.unpacking) is spec

            integer_spec.assert_called_once_with(
                V.pkt,
                None,
                bitmask,
                unpacking=V.unpacking,
                allow_float=V.allow_float,
                unknown_enum_values=V.unknown_enum_values,
            )

        def test_it_creates_integer_spec_with_neither_enum_or_bitmask_if_we_have_neither(self, V):
            with V.mocked_integer_spec() as (integer_spec, spec):
                assert V.t.make_integer_spec(V.pkt, V.unpacking) is spec

            integer_spec.assert_called_once_with(
                V.pkt,
                None,
                None,
                unpacking=V.unpacking,
                allow_float=V.allow_float,
                unknown_enum_values=V.unknown_enum_values,
            )

    class TestTransforming:
        @pytest.fixture()
        def V(self):
            class V:
                pkt = mock.Mock(name="pkt")
                value = mock.Mock(name="value")
                conversion = mock.Mock(name="conversion")
                transformed = mock.Mock(name="transformed")
                struct_format = mock.Mock(name="struct_format")
                untransformed = mock.Mock(name="untransformed")

                @hp.memoized_property
                def transformer(s):
                    return mock.Mock(name="transformer", return_value=s.transformed)

                @hp.memoized_property
                def untransformer(s):
                    return mock.Mock(name="untransformer", return_value=s.untransformed)

                @hp.memoized_property
                def t(s):
                    return Type(s.struct_format, s.conversion)

            return V()

        class TestDoTransform:
            def test_it_return_value_if_no_transformer(self, V):
                assert V.t.do_transform(V.pkt, V.value) is V.value

            def test_it_uses_the_transformer_if_we_have_one(self, V):
                assert (V.t.transform(V.transformer, V.untransformer).do_transform(V.pkt, V.value)) is V.transformed

        class TestUntransform:
            def test_it_does_nothing_if_no_untransformer(self, V):
                assert V.t.untransform(V.pkt, V.value) is V.value

            def test_it_transforms_if_we_have_an_untransformer(self, V):
                assert (V.t.transform(V.transformer, V.untransformer).untransform(V.pkt, V.value)) is V.untransformed
                V.untransformer.assert_called_once_with(V.pkt, V.value)
