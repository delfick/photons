# coding: spec

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import BadOptionFormat
from photons_app import helpers as hp

from delfick_project.option_merge import MergedOptions
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb, Meta
from unittest import mock
import pytest
import uuid

describe "MergedOptionStringFormatter":

    @pytest.fixture()
    def V(self):
        class V:
            spec = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
            target_register = mock.Mock(name="target_register")

            @hp.memoized_property
            def meta(s):
                options = MergedOptions.using(
                    {"target_register": s.target_register}, dont_prefix=[mock.Mock]
                )
                return Meta(options, [])

        return V()

    it "routes targets.* into the target_register", V:
        target = mock.Mock(name="target")
        V.target_register.resolve.return_value = target
        res = V.spec.normalise(V.meta, "{targets.one}")
        assert res is target
        V.target_register.resolve.assert_called_once_with("one")

    it "routes targets.* into the target_register and accesses from there", V:
        target = mock.Mock(name="target")
        V.target_register.resolve.return_value = target
        res = V.spec.normalise(V.meta, "{targets.one.two.three}")
        assert res is target.two.three
        V.target_register.resolve.assert_called_once_with("one")

    it "complains if the key is not in all_options", V:
        key = str(uuid.uuid1())
        with assertRaises(BadOptionFormat, "Can't find key in options", key=key):
            V.spec.normalise(V.meta, "{{{0}}}".format(key))

    it "otherwise just gets keys", V:
        val = str(uuid.uuid1())
        V.meta.everything[["one", "two"]] = val
        assert V.spec.normalise(V.meta, "{one.two}") == val

    it "complains if we have a recursive option", V:
        with assertRaises(BadOptionFormat, "Recursive option", chain=["one", "one"]):
            V.spec.normalise(V.meta.at("one"), "{one}")

    it "can use pkg_resources to find location of a resource", V:
        res = mock.Mock(name="res")
        resource_filename = mock.Mock(name="resource_filename", return_value=res)
        with mock.patch("pkg_resources.resource_filename", resource_filename):
            assert V.spec.normalise(V.meta, "{somewhere.nice/really/cool:resource}") is res

        resource_filename.assert_called_once_with("somewhere.nice", "really/cool")

    it "can return asyncio.Future objects", V:
        fut = hp.create_future()
        V.meta.everything["fut"] = fut
        assert V.spec.normalise(V.meta, "{fut}") is fut
