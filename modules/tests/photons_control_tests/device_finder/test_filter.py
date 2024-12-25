
import json
from unittest import mock

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta, sb
from photons_control.device_finder import Filter, InfoPoints, InvalidJson

class TestFilter:
    class TestConstruction:

        def assertFltrMatches(self, filtr, expect):
            for field in Filter.fields:
                if field in ("refresh_info", "refresh_discovery") and field not in expect:
                    assert filtr[field] is False
                elif field in expect:
                    assert filtr[field] == expect[field]
                else:
                    assert filtr[field] is sb.NotSpecified

        def test_it_defaults_everything_to_NotSpecified(self):
            filtr = Filter.empty()
            assert len(filtr.fields) == 16
            self.assertFltrMatches(filtr, {})

        class TestFromJsonStr:
            def test_it_treats_the_string_as_a_json_object(self):
                want = {"label": "kitchen", "location_name": ["one", "two"], "hue": "20-50"}
                expect = {"label": ["kitchen"], "location_name": ["one", "two"], "hue": [(20, 50)]}
                self.assertFltrMatches(Filter.from_json_str(json.dumps(want)), expect)

            def test_it_complains_if_the_string_is_not_valid_json(self):
                with assertRaises(InvalidJson):
                    Filter.from_json_str("{")

            def test_it_complains_if_the_string_is_not_a_dictionary(self):
                for s in ('"wat"', "[]", "1"):
                    # Make sure it's valid json
                    json.dumps(s)

                    # And make sure it complains it's not a dictionary
                    with assertRaises(InvalidJson, "Expected a dictionary"):
                        Filter.from_json_str(s)

        class TestFromKeyValueStr:
            def test_it_treats_the_keyvalue_as_dictionary_items(self):
                want = "label=bathroom,hallway location_id=identifier1 saturation=0.7,0.8-1"
                expect = {
                    "label": ["bathroom", "hallway"],
                    "location_id": ["identifier1"],
                    "saturation": [(0.7, 0.7), (0.8, 1.0)],
                }

                filtr = Filter.from_key_value_str(want)
                self.assertFltrMatches(filtr, expect)

            def test_it_treats_hsbk_and_refreshes_appropriately(self):
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

            def test_it_ignores_parts_that_arent_keyvalue(self):
                want = "label=bathroom,hallway location_ididentifier1"
                expect = {"label": ["bathroom", "hallway"]}
                self.assertFltrMatches(Filter.from_key_value_str(want), expect)

        class TestFromUrlStr:
            def test_it_treats_url_str_as_a_dictionary(self):
                s = "label=kitchen&location_name=kitchen%20lights&location_name=two&hue=20-50&hue=0.6-0.9&refresh_discovery=true"
                expect = {
                    "label": ["kitchen"],
                    "location_name": ["kitchen lights", "two"],
                    "hue": [(20, 50), (0.6, 0.9)],
                    "refresh_discovery": True,
                }
                self.assertFltrMatches(Filter.from_url_str(s), expect)

        class TestFromKwargs:
            def test_it_just_passes_the_kwargs_to_from_options(self):
                filtr = mock.Mock(name="filtr")
                want = {"one": "two", "three": "four"}
                from_options = mock.Mock(name="from_options", return_value=filtr)

                with mock.patch.object(Filter, "from_options", from_options):
                    assert Filter.from_kwargs(**want) is filtr

                from_options.assert_called_once_with(want)

        class TestFromOptions:
            def test_it_normalises_the_options(self):
                normalised = mock.Mock(name="normalised")

                spec = mock.Mock(name="spec")
                spec.normalise.return_value = normalised

                FieldSpec = mock.Mock(name="FieldSpec", return_value=spec)

                options = mock.Mock(name="options")

                with mock.patch.object(Filter, "FieldSpec", FieldSpec):
                    assert Filter.from_options(options) is normalised

                FieldSpec.assert_called_once_with()
                spec.normalise.assert_called_once_with(Meta.empty(), options)

            def test_it_works(self):
                want = {
                    "label": ["bathroom", "hallway"],
                    "location_id": ["identifier1"],
                    "saturation": [(0.7, 0.7), (0.8, 1.0)],
                }
                filtr = Filter.from_options(want)
                self.assertFltrMatches(filtr, want)

        class TestEmpty:
            def test_it_gives_back_a_filter_with_just_refresh_options(self):
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

    class TestHas:
        def test_it_says_no_if_not_a_valid_field(self):
            filtr = Filter.empty()
            assert not filtr.has("blah")

        def test_it_says_no_if_the_field_has_no_value(self):
            filtr = Filter.empty()
            for field in filtr.fields:
                if field not in ("refresh_info", "refresh_discovery"):
                    assert filtr[field] == sb.NotSpecified
                    assert not filtr.has(field)

        def test_it_says_yes_if_the_field_has_a_value(self):
            filtr = Filter.from_kwargs(label="kitchen")
            assert filtr.has("label")

    class TestMatches:
        def test_it_says_no_if_the_field_is_a_refresh(self):
            for field in ("refresh_info", "refresh_discovery"):
                filtr = Filter.empty(**{field: True})
                assert not filtr.matches(field, True)
                assert not filtr.matches(field, False)

                filtr = Filter.empty(**{field: False})
                assert not filtr.matches(field, True)
                assert not filtr.matches(field, False)

        def test_it_says_no_if_the_field_isnt_in_the_filter(self):
            assert "blah" not in Filter.fields
            filtr = Filter.empty()
            assert not filtr.matches("blah", mock.ANY)

        def test_it_says_no_if_the_field_isnt_specified(self):
            filtr = Filter.empty()
            for field in Filter.fields:
                if field not in ("refresh_info", "refresh_discovery"):
                    assert not filtr.matches(field, mock.ANY)

        def test_it_matches_ranges_for_hsbk(self):
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

        def test_it_matches_against_anything_in_a_list(self):
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

        def test_it_matches_with_a_glob_for_name_fields(self):
            for field in Filter.empty().label_fields:
                filtr = Filter.from_options({field: ["option*"]})
                assert filtr.matches(field, "option1")
                assert filtr.matches(field, "option2")
                assert not filtr.matches(field, "o3")

                filtr = Filter.from_options({field: ["*1", "*2*"]})
                assert filtr.matches(field, "one2one")
                assert filtr.matches(field, "blah1")
                assert not filtr.matches(field, "blah")

        def test_it_matches_list_against_list_for_cap(self):
            filtr = Filter.from_options({"cap": ["multizone", "color"]})
            assert filtr.matches("cap", ["multizone"])
            assert filtr.matches("cap", ["color"])
            assert filtr.matches("cap", ["color", "multizone"])
            assert filtr.matches("cap", ["color", "ir"])
            assert not filtr.matches("cap", ["ir"])

    class TestLabelFields:
        def test_it_has_a_pre_filled_list(self):
            filtr = Filter.empty()
            assert filtr.label_fields == (
                "label",
                "location_name",
                "group_name",
            )

    class TestMatchesAll:
        def test_it_says_yes_if_all_the_fields_arent_specified(self):
            assert Filter.empty().matches_all
            assert Filter.empty(refresh_info=True).matches_all
            assert Filter.empty(refresh_discovery=True).matches_all

        def test_it_says_no_if_any_of_the_fields_are_specified(self):
            for field in Filter.fields:
                if field not in ("refresh_info", "refresh_discovery"):
                    filtr = Filter.empty()
                    filtr[field] = mock.Mock(name="value")
                    assert not filtr.matches_all

    class TestPoints:
        def test_it_returns_the_InfoPoint_enums_for_the_fields_that_have_values(self):
            filtr = Filter.from_kwargs(label="kitchen", product_id=22)
            assert set(filtr.points) == set(
                [InfoPoints.LIGHT_STATE, InfoPoints.LABEL, InfoPoints.VERSION]
            )

            filtr = Filter.from_kwargs(group_name="one")
            assert set(filtr.points) == set([InfoPoints.GROUP])

            assert set(Filter.empty().points) == set()
