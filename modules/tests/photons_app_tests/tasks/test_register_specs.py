# coding: spec

from photons_app.errors import BadTarget, TargetNotFound, BadOption, ResolverNotFound
from photons_app.tasks.register import artifact_spec, target_spec, reference_spec
from photons_app.special import HardCodedSerials, FoundSerials
from photons_control.device_finder import DeviceFinder
from photons_app.collector import Collector
from photons_app.registers import Target

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta, sb
from unittest import mock
import pytest


@pytest.fixture()
def meta():
    return Meta.empty()


describe "artifact_spec":
    it "cares not", meta:
        for thing in (
            None,
            0,
            1,
            True,
            False,
            [],
            [1],
            (),
            (1,),
            {},
            {1: 1},
            set(),
            set([1]),
            lambda: 1,
            type("a", (), {}),
            type("b", (), {})(),
            sb.NotSpecified,
        ):
            assert artifact_spec().normalise(meta, thing) is thing


describe "target_spec":
    describe "without a value":
        describe "mandatory":

            @pytest.mark.parametrize("val", [None, "", sb.NotSpecified])
            it "complains if nothing was specified and is mandatory", val:
                spec = target_spec({}, mandatory=True)

                with assertRaises(BadTarget, "This task requires you specify a target"):
                    spec.normalise(Meta.empty(), val)

            @pytest.mark.parametrize("val", [None, "", sb.NotSpecified])
            it "returns not specified if nothing was specified and isn't mandatory", val:
                spec = target_spec({}, mandatory=False)
                assert spec.normalise(Meta.empty(), val) is sb.NotSpecified

    describe "with a value":

        @pytest.fixture()
        def superman(self):
            return mock.Mock(name="resolvedsuperman")

        @pytest.fixture()
        def batman(self):
            return mock.Mock(name="resolvedbatman")

        @pytest.fixture()
        def vegemite(self):
            return mock.Mock(name="resolvedvegemite")

        @pytest.fixture()
        def meta(self, superman, batman, vegemite):
            collector = Collector()
            collector.prepare(None, {})
            reg = collector.configuration["target_register"]

            HeroTarget = mock.Mock(name="HeroTarget")
            herotarget = Target.FieldSpec().empty_normalise(type="hero")
            reg.register_type("hero", HeroTarget)

            VillianTarget = mock.Mock(name="VillianTarget")
            villiantarget = Target.FieldSpec().empty_normalise(type="villian")
            reg.register_type("villian", VillianTarget)

            supermancreator = mock.Mock(name="supermancreator", return_value=superman)
            reg.add_target("superman", herotarget, supermancreator)

            batmancreator = mock.Mock(name="batmancreator", return_value=batman)
            reg.add_target("batman", herotarget, batmancreator)

            vegemitecreator = mock.Mock(name="vegemitecreator", return_value=vegemite)
            reg.add_target("vegemite", villiantarget, vegemitecreator)

            return Meta({"collector": collector}, []).at("test")

        @pytest.mark.parametrize("mandatory", [True, False])
        it "can resolve the name", meta, mandatory, superman, vegemite:
            assert target_spec({}, mandatory=mandatory).normalise(meta, "superman") is superman
            assert target_spec({}, mandatory=mandatory).normalise(meta, "vegemite") is vegemite

        @pytest.mark.parametrize("mandatory", [True, False])
        it "can resolve the target if it's already been resolved in the past", meta, mandatory, superman, vegemite:
            with assertRaises(TargetNotFound):
                target_spec({}, mandatory=mandatory).normalise(meta, superman)
            assert target_spec({}, mandatory=mandatory).normalise(meta, "superman") is superman
            assert target_spec({}, mandatory=mandatory).normalise(meta, superman) is superman

            assert target_spec({}, mandatory=mandatory).normalise(meta, "vegemite") is vegemite
            assert target_spec({}, mandatory=mandatory).normalise(meta, vegemite) is vegemite

        @pytest.mark.parametrize("mandatory", [True, False])
        it "can restrict what it's searching for", meta, mandatory, superman, batman, vegemite:
            assert target_spec({}, mandatory=mandatory).normalise(meta, "superman") is superman
            with assertRaises(TargetNotFound):
                target_spec({"target_types": ["villian"]}, mandatory=mandatory).normalise(
                    meta, "superman"
                )
            with assertRaises(TargetNotFound):
                target_spec({"target_types": ["villian"]}, mandatory=mandatory).normalise(
                    meta, superman
                )

            assert (
                target_spec({"target_types": ["villian"]}, mandatory=mandatory).normalise(
                    meta, "vegemite"
                )
                is vegemite
            )

            assert (
                target_spec({"target_names": ["batman"]}, mandatory=mandatory).normalise(
                    meta, "batman"
                )
                is batman
            )
            assert (
                target_spec({"target_names": ["batman"]}, mandatory=mandatory).normalise(
                    meta, batman
                )
                is batman
            )


describe "reference_spec":
    describe "without a value":
        describe "mandatory":

            @pytest.mark.parametrize("val", [None, "", sb.NotSpecified])
            @pytest.mark.parametrize("special", [True, False])
            it "complains if nothing was specified and is mandatory", val, special:
                spec = reference_spec(mandatory=True, special=special)

                with assertRaises(BadOption, "This task requires you specify a reference"):
                    spec.normalise(Meta.empty(), val)

            @pytest.mark.parametrize("val", [None, "", sb.NotSpecified])
            it "returns not specified if nothing was specified and isn't mandatory", val:
                spec = reference_spec(mandatory=False, special=False)
                assert spec.normalise(Meta.empty(), val) is sb.NotSpecified

            @pytest.mark.parametrize("val", [None, "", sb.NotSpecified])
            it "returns a reference object if nothing but not mandatory", val:
                collector = Collector()
                collector.prepare(None, {})

                spec = reference_spec(mandatory=False, special=True)
                assert isinstance(
                    spec.normalise(Meta({"collector": collector}, []).at("test"), val), FoundSerials
                )

    describe "with a value":

        @pytest.fixture()
        def meta(self):
            collector = Collector()
            collector.prepare(None, {})

            def resolve(s):
                return DeviceFinder.from_url_str(s)

            collector.configuration["reference_resolver_register"].add("match", resolve)

            return Meta({"collector": collector}, []).at("test")

        @pytest.mark.parametrize(
            "special,mandatory", [(False, False), (False, True), (True, False), (True, True)]
        )
        it "returns as is if not a string", meta, special, mandatory:
            val = HardCodedSerials([])
            assert reference_spec(mandatory=mandatory, special=special).normalise(meta, val) is val

        @pytest.mark.parametrize("mandatory", [False, True])
        it "returns as is if a string and special is False", meta, mandatory:
            val = "stuffandthings"
            assert reference_spec(mandatory=mandatory, special=False).normalise(meta, val) is val

        @pytest.mark.parametrize("mandatory", [False, True])
        it "creates a reference object if special is true and val is a string", meta, mandatory:
            spec = reference_spec(mandatory=mandatory, special=True)

            result = spec.normalise(meta, "match:cap=hev")
            assert isinstance(result, DeviceFinder)
            assert result.fltr.cap == ["hev"]

            with assertRaises(ResolverNotFound):
                spec.normalise(meta, "nup:blah")
