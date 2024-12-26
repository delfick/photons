import pathlib
import uuid
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta, sb
from delfick_project.option_merge import MergedOptions
from photons_app import helpers as hp
from photons_app.errors import BadOptionFormat
from photons_app.formatter import MergedOptionStringFormatter

photons_app_dir = pathlib.Path(__file__).parent.parent.parent / "photons_app"


class TestMergedOptionStringFormatter:
    @pytest.fixture()
    def V(self):
        class V:
            spec = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
            target_register = mock.Mock(name="target_register")

            @hp.memoized_property
            def meta(s):
                options = MergedOptions.using({"target_register": s.target_register}, dont_prefix=[mock.Mock])
                return Meta(options, [])

        return V()

    def test_it_routes_targets_into_the_target_register(self, V):
        target = mock.Mock(name="target")
        V.target_register.resolve.return_value = target
        res = V.spec.normalise(V.meta, "{targets.one}")
        assert res is target
        V.target_register.resolve.assert_called_once_with("one")

    def test_it_routes_targets_into_the_target_register_and_accesses_from_there(self, V):
        target = mock.Mock(name="target")
        V.target_register.resolve.return_value = target
        res = V.spec.normalise(V.meta, "{targets.one.two.three}")
        assert res is target.two.three
        V.target_register.resolve.assert_called_once_with("one")

    def test_it_complains_if_the_key_is_not_in_all_options(self, V):
        key = str(uuid.uuid1())
        with assertRaises(BadOptionFormat, "Can't find key in options", key=key):
            V.spec.normalise(V.meta, f"{{{key}}}")

    def test_it_otherwise_just_gets_keys(self, V):
        val = str(uuid.uuid1())
        V.meta.everything[["one", "two"]] = val
        assert V.spec.normalise(V.meta, "{one.two}") == val

    def test_it_complains_if_we_have_a_recursive_option(self, V):
        with assertRaises(BadOptionFormat, "Recursive option", chain=["one", "one"]):
            V.spec.normalise(V.meta.at("one"), "{one}")

    def test_it_can_find_location_of_a_resource(self, V):
        got = V.spec.normalise(V.meta, "{photons_app/actions.py:resource}")
        assert got == str((photons_app_dir / "actions.py").resolve())

    def test_it_can_return_asyncioFuture_objects(self, V):
        fut = hp.create_future()
        V.meta.everything["fut"] = fut
        assert V.spec.normalise(V.meta, "{fut}") is fut
