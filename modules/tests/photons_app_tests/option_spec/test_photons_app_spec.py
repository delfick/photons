# coding: spec

from photons_app.option_spec.photons_app_spec import PhotonsAppSpec, PhotonsApp
from photons_app.registers import TargetRegister
from photons_app.registers import Target
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta, BadSpecValue
from unittest import mock
import pytest


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


describe "PhotonsAppSpec":

    describe "target_name_spec":

        @pytest.fixture()
        def tns(self, V):
            return V.spec.target_name_spec

        it "complains if we have whitespace", tns, V:
            try:
                tns.normalise(V.meta, "adf ")
                assert False, "expected an exception"
            except BadSpecValue as error:
                assert "Expected no whitespace" in str(error)

        it "complains if we don't match our regex", tns, V:
            for val in ("9asdf", "asdf^", "*asdf"):
                try:
                    tns.normalise(V.meta, val)
                    assert False, "expected an exception"
                except BadSpecValue as error:
                    assert "Expected value to match regex" in str(error)

        it "returns as is otherwise", tns, V:
            for val in ("asdf", "asdfdfDf", "asdf-asdfa-asdf", "asdf_asdfD_DDF.asdf", "a", "A"):
                assert tns.normalise(V.meta, val) == val

    describe "photons_app_spec":
        it "gets us back a PhotonsApp", V:
            res = V.spec.photons_app_spec.normalise(
                V.meta, {"task_specifier": "blah:things", "debug": True}
            )
            assert isinstance(res, PhotonsApp)
            assert res.task_specifier() == ("blah", "things")
            assert res.debug is True

    describe "target_register_spec":
        it "gets us a TargetRegister", V:
            register = V.spec.target_register_spec.normalise(V.meta.at("target_register"), {})
            assert isinstance(register, TargetRegister)

    describe "targets spec":
        it "gets us a dictionary of targets", V:
            targets = {"one": {"type": "blah", "options": {"one": 2}}, "two": {"type": "meh"}}
            expected = {
                "one": Target(type="blah", options={"one": 2}, optional=False),
                "two": Target(type="meh", options={}, optional=False),
            }

            res = V.spec.targets_spec.normalise(V.meta, targets)
            assert res == expected

        it "complains if a target has an invalid name", V:
            targets = {"9one": {"type": "blah", "options": {"one": 2}}, "t^wo": {"type": "meh"}}
            with assertRaises(BadSpecValue):
                V.spec.targets_spec.normalise(V.meta, targets)
