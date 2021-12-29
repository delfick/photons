# coding: spec

from photons_control.device_finder import Filter, InvalidJson, InfoPoints

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb, Meta
from unittest import mock
import json

describe "Filter":
    describe "construction":

        def assertFltrMatches(self, filtr, expect):
            for field in Filter.fields:
                if field in ("refresh_info", "refresh_discovery") and field not in expect:
                    assert filtr[field] is False
                elif field in expect:
                    assert filtr[field] == expect[field]
                else:
                    assert filtr[field] is sb.NotSpecified

        it "defaults everything to NotSpecified":
            filtr = Filter.empty()
            assert len(filtr.fields) == 16
            self.assertFltrMatches(filtr, {})

        describe "from_json_str":
            it "treats the string as a json object":
                want = {"label": "kitchen", "location_name": ["one", "two"], "hue": "20-50"}
                expect = {"label": ["kitchen"], "location_name": ["one", "two"], "hue": [(20, 50)]}
                self.assertFltrMatches(Filter.from_json_str(json.dumps(want)), expect)

            it "complains if the string is not valid json":
                with assertRaises(InvalidJson):
                    Filter.from_json_str("{")

            it "complains if the string is not a dictionary":
                for s in ('"wat"', "[]", "1"):
                    # Make sure it's valid json
                    json.dumps(s)

                    # And make sure it complains it's not a dictionary
                    with assertRaises(InvalidJson, "Expected a dictionary"):
                        Filter.from_json_str(s)

        describe "from_key_value_str":
            it "treats the key,value as dictionary items":
                want = "label=bathroom,hallway location_id=identifier1 saturation=0.7,0.8-1"
                expect = {
                    "label": ["bathroom", "hallway"],
                    "location_id": ["identifier1"],
                    "saturation": [(0.7, 0.7), (0.8, 1.0)],
                }

                filtr = Filter.from_key_value_str(want)
                self.assertFltrMatches(filtr, expect)

            it "treats hsbk and refreshes appropriately":
                s = "hue=5,60 saturation=0.7,0.5-0.8 brightness=0.8,0.4 kelvin=3500,2500 refresh_info=true refresh_discovery=true"
                expect = {
                    "hue": [(5, 5), (60, 60)],
                    "saturation": [(0.7, 0.7), (0.5, 0.8)],
                    "brightness": [(0.8, 0.8), (0.4, 0.4)],
                    "kelvin": [(3500, 3500), (2500, 2500)],
                    "refresh_info": True,
                    "refresh_discovery": True,
                }
                self.assertFltrMatches(Filter.from_key_value_str(s), expect)

            it "ignores parts that aren't key=value":
                want = "label=bathroom,hallway location_ididentifier1"
                expect = {"label": ["bathroom", "hallway"]}
                self.assertFltrMatches(Filter.from_key_value_str(want), expect)

        describe "from_url_str":
            it "treats url_str as a dictionary":
                s = "label=kitchen&location_name=kitchen%20lights&location_name=two&hue=20-50&hue=0.6-0.9&refresh_discovery=true"
                expect = {
                    "label": ["kitchen"],
                    "location_name": ["kitchen lights", "two"],
                    "hue": [(20, 50), (0.6, 0.9)],
                    "refresh_discovery": True,
                }
                self.assertFltrMatches(Filter.from_url_str(s), expect)

        describe "from_kwargs":
            it "just passes the kwargs to from_options":
                filtr = mock.Mock(name="filtr")
                want = {"one": "two", "three": "four"}
                from_options = mock.Mock(name="from_options", return_value=filtr)

                with mock.patch.object(Filter, "from_options", from_options):
                    assert Filter.from_kwargs(**want) is filtr

                from_options.assert_called_once_with(want)

        describe "from_options":
            it "normalises the options":
                normalised = mock.Mock(name="normalised")

                spec = mock.Mock(name="spec")
                spec.normalise.return_value = normalised

                FieldSpec = mock.Mock(name="FieldSpec", return_value=spec)

                options = mock.Mock(name="options")

                with mock.patch.object(Filter, "FieldSpec", FieldSpec):
                    assert Filter.from_options(options) is normalised

                FieldSpec.assert_called_once_with()
                spec.normalise.assert_called_once_with(Meta.empty(), options)

            it "works":
                want = {
                    "label": ["bathroom", "hallway"],
                    "location_id": ["identifier1"],
                    "saturation": [(0.7, 0.7), (0.8, 1.0)],
                }
                filtr = Filter.from_options(want)
                self.assertFltrMatches(filtr, want)

        describe "empty":
            it "gives back a filter with just refresh options":
                self.assertFltrMatches(
                    Filter.empty(), {"refresh_info": False, "refresh_discovery": False}
                )
                self.assertFltrMatches(
                    Filter.empty(refresh_info=True),
                    {"refresh_info": True, "refresh_discovery": False},
                )
                self.assertFltrMatches(
                    Filter.empty(refresh_discovery=True),
                    {"refresh_info": False, "refresh_discovery": True},
                )
                self.assertFltrMatches(
                    Filter.empty(refresh_info=True, refresh_discovery=True),
                    {"refresh_info": True, "refresh_discovery": True},
                )

    describe "has":
        it "says no if not a valid field":
            filtr = Filter.empty()
            assert not filtr.has("blah")

        it "says no if the field has no value":
            filtr = Filter.empty()
            for field in filtr.fields:
                if field not in ("refresh_info", "refresh_discovery"):
                    assert filtr[field] == sb.NotSpecified
                    assert not filtr.has(field)

        it "says yes if the field has a value":
            filtr = Filter.from_kwargs(label="kitchen")
            assert filtr.has("label")

    describe "matches":
        it "says no if the field is a refresh":
            for field in ("refresh_info", "refresh_discovery"):
                filtr = Filter.empty(**{field: True})
                assert not filtr.matches(field, True)
                assert not filtr.matches(field, False)

                filtr = Filter.empty(**{field: False})
                assert not filtr.matches(field, True)
                assert not filtr.matches(field, False)

        it "says no if the field isn't in the filter":
            assert "blah" not in Filter.fields
            filtr = Filter.empty()
            assert not filtr.matches("blah", mock.ANY)

        it "says no if the field isn't specified":
            filtr = Filter.empty()
            for field in Filter.fields:
                if field not in ("refresh_info", "refresh_discovery"):
                    assert not filtr.matches(field, mock.ANY)

        it "matches ranges for hsbk":
            for field in ("hue", "saturation", "brightness", "kelvin"):
                filtr = Filter.from_options({field: "40-60,70,80-81"})
                assert filtr.matches(field, 40)
                assert filtr.matches(field, 50)
                assert filtr.matches(field, 60)
                assert filtr.matches(field, 70)
                assert filtr.matches(field, 80)
                assert filtr.matches(field, 81)

                assert not filtr.matches(field, 39)
                assert not filtr.matches(field, 61)
                assert not filtr.matches(field, 69)
                assert not filtr.matches(field, 71)
                assert not filtr.matches(field, 79)
                assert not filtr.matches(field, 82)

        it "matches against anything in a list":
            for field in (
                "label",
                "power",
                "group_id",
                "group_name",
                "location_id",
                "location_name",
                "firmware_version",
            ):
                filtr = Filter.from_options({field: ["one", "two"]})
                assert filtr.matches(field, "one")
                assert filtr.matches(field, "two")

                assert not filtr.matches(field, "three")

            for field in ("product_id",):
                filtr = Filter.from_options({field: [1, 2]})
                assert filtr.matches(field, 1)
                assert filtr.matches(field, 2)

                assert not filtr.matches(field, 3)

        it "matches with a glob for name fields":
            for field in Filter.empty().label_fields:
                filtr = Filter.from_options({field: ["option*"]})
                assert filtr.matches(field, "option1")
                assert filtr.matches(field, "option2")
                assert not filtr.matches(field, "o3")

                filtr = Filter.from_options({field: ["*1", "*2*"]})
                assert filtr.matches(field, "one2one")
                assert filtr.matches(field, "blah1")
                assert not filtr.matches(field, "blah")

        it "matches list against list for cap":
            filtr = Filter.from_options({"cap": ["multizone", "color"]})
            assert filtr.matches("cap", ["multizone"])
            assert filtr.matches("cap", ["color"])
            assert filtr.matches("cap", ["color", "multizone"])
            assert filtr.matches("cap", ["color", "ir"])
            assert not filtr.matches("cap", ["ir"])

    describe "label_fields":
        it "has a pre-filled list":
            filtr = Filter.empty()
            assert filtr.label_fields == (
                "label",
                "location_name",
                "group_name",
            )

    describe "matches_all":
        it "says yes if all the fields aren't specified":
            assert Filter.empty().matches_all
            assert Filter.empty(refresh_info=True).matches_all
            assert Filter.empty(refresh_discovery=True).matches_all

        it "says no if any of the fields are specified":
            for field in Filter.fields:
                if field not in ("refresh_info", "refresh_discovery"):
                    filtr = Filter.empty()
                    filtr[field] = mock.Mock(name="value")
                    assert not filtr.matches_all

    describe "points":
        it "returns the InfoPoint enums for the fields that have values":
            filtr = Filter.from_kwargs(label="kitchen", product_id=22)
            assert set(filtr.points) == set([InfoPoints.LABEL, InfoPoints.VERSION])

            filtr = Filter.from_kwargs(group_name="one")
            assert set(filtr.points) == set([InfoPoints.GROUP])

            assert set(Filter.empty().points) == set()
