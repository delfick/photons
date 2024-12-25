
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue, Meta
from photons_app import helpers as hp
from photons_app.photons_app import PhotonsApp, PhotonsAppSpec
from photons_app.registers import Target, TargetRegister


@pytest.fixture()
def V():
    class V:
        spec = PhotonsAppSpec()
        collector = mock.Mock(name="collector")
        final_future = mock.Mock(name="final_future")

        @hp.memoized_property
        def meta(s):
            return Meta({"collector": s.collector, "final_future": s.final_future}, []).at(
                "options"
            )

    return V()


class TestPhotonsAppSpec:

    class TestTargetNameSpec:

        @pytest.fixture()
        def tns(self, V):
            return V.spec.target_name_spec

        def test_it_complains_if_we_have_whitespace(self, tns, V):
            try:
                tns.normalise(V.meta, "adf ")
                assert False, "expected an exception"
            except BadSpecValue as error:
                assert "Expected no whitespace" in str(error)

        def test_it_complains_if_we_dont_match_our_regex(self, tns, V):
            for val in ("9asdf", "asdf^", "*asdf"):
                try:
                    tns.normalise(V.meta, val)
                    assert False, "expected an exception"
                except BadSpecValue as error:
                    assert "Expected value to match regex" in str(error)

        def test_it_returns_as_is_otherwise(self, tns, V):
            for val in ("asdf", "asdfdfDf", "asdf-asdfa-asdf", "asdf_asdfD_DDF.asdf", "a", "A"):
                assert tns.normalise(V.meta, val) == val

    class TestPhotonsAppSpec:
        def test_it_gets_us_back_a_PhotonsApp(self, V):
            res = V.spec.photons_app_spec.normalise(
                V.meta, {"task_specifier": "blah:things", "debug": True}
            )
            assert isinstance(res, PhotonsApp)
            assert res.task_specifier() == ("blah", "things")
            assert res.debug is True

    class TestTargetRegisterSpec:
        def test_it_gets_us_a_TargetRegister(self, V):
            register = V.spec.target_register_spec.normalise(V.meta.at("target_register"), {})
            assert isinstance(register, TargetRegister)

    class TestTargetsSpec:
        def test_it_gets_us_a_dictionary_of_targets(self, V):
            targets = {"one": {"type": "blah", "options": {"one": 2}}, "two": {"type": "meh"}}
            expected = {
                "one": Target(type="blah", options={"one": 2}, optional=False),
                "two": Target(type="meh", options={}, optional=False),
            }

            res = V.spec.targets_spec.normalise(V.meta, targets)
            assert res == expected

        def test_it_complains_if_a_target_has_an_invalid_name(self, V):
            targets = {"9one": {"type": "blah", "options": {"one": 2}}, "t^wo": {"type": "meh"}}
            with assertRaises(BadSpecValue):
                V.spec.targets_spec.normalise(V.meta, targets)
