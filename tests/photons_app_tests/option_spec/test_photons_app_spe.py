# coding: spec

from photons_app.option_spec.photons_app_spec import PhotonsAppSpec, PhotonsApp
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.registers import TargetRegister
from photons_app.test_helpers import TestCase
from photons_app.registers import Target

from noseOfYeti.tokeniser.support import noy_sup_setUp
from delfick_project.norms import Meta, BadSpecValue
from unittest import mock

describe TestCase, "PhotonsAppSpec":
    before_each:
        self.spec = PhotonsAppSpec()
        self.collector = mock.Mock(name="collector")
        self.final_future = mock.Mock(name="final_future")
        self.meta = Meta({"collector": self.collector, "final_future": self.final_future}, []).at(
            "options"
        )

    describe "target_name_spec":
        before_each:
            self.tns = self.spec.target_name_spec

        it "complains if we have whitespace":
            try:
                self.tns.normalise(self.meta, "adf ")
                assert False, "expected an exception"
            except BadSpecValue as error:
                assert "Expected no whitespace" in str(error)

        it "complains if we don't match our regex":
            for val in ("9asdf", "asdf^", "*asdf"):
                try:
                    self.tns.normalise(self.meta, val)
                    assert False, "expected an exception"
                except BadSpecValue as error:
                    assert "Expected value to match regex" in str(error)

        it "returns as is otherwise":
            for val in ("asdf", "asdfdfDf", "asdf-asdfa-asdf", "asdf_asdfD_DDF.asdf", "a", "A"):
                self.assertEqual(self.tns.normalise(self.meta, val), val)

    describe "photons_app_spec":
        it "gets us back a PhotonsApp":
            res = self.spec.photons_app_spec.normalise(self.meta, {"target": "blah", "debug": True})
            assert isinstance(res, PhotonsApp)
            self.assertEqual(res.target, "blah")
            self.assertEqual(res.debug, True)

    describe "target_register_spec":
        it "gets us a TargetRegister":
            register = self.spec.target_register_spec.normalise(self.meta.at("target_register"), {})
            assert isinstance(register, TargetRegister)
            self.assertIs(register.collector, self.collector)

    describe "targets spec":
        it "gets us a dictionary of targets":
            targets = {"one": {"type": "blah", "options": {"one": 2}}, "two": {"type": "meh"}}
            expected = {
                "one": Target(type="blah", options={"one": 2}, optional=False),
                "two": Target(type="meh", options={}, optional=False),
            }

            res = self.spec.targets_spec.normalise(self.meta, targets)
            self.assertEqual(res, expected)

        it "complains if a target has an invalid name":
            targets = {"9one": {"type": "blah", "options": {"one": 2}}, "t^wo": {"type": "meh"}}
            with self.fuzzyAssertRaisesError(BadSpecValue):
                self.spec.targets_spec.normalise(self.meta, targets)
