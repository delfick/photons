# coding: spec

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import BadOptionFormat
from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from delfick_project.option_merge import MergedOptions
from delfick_project.norms import sb, Meta
from unittest import mock
import asyncio
import uuid

describe TestCase, "MergedOptionStringFormatter":
    before_each:
        self.target_register = mock.Mock(name="target_register")
        self.spec = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
        self.options = MergedOptions.using(
            {"target_register": self.target_register}, dont_prefix=[mock.Mock]
        )
        self.meta = Meta(self.options, [])

    it "routes targets.* into the target_register":
        target = mock.Mock(name="target")
        self.target_register.resolve.return_value = target
        res = self.spec.normalise(self.meta, "{targets.one}")
        self.assertIs(res, target)
        self.target_register.resolve.assert_called_once_with("one")

    it "routes targets.* into the target_register and accesses from there":
        target = mock.Mock(name="target")
        self.target_register.resolve.return_value = target
        res = self.spec.normalise(self.meta, "{targets.one.two.three}")
        self.assertIs(res, target.two.three)
        self.target_register.resolve.assert_called_once_with("one")

    it "complains if the key is not in all_options":
        key = str(uuid.uuid1())
        with self.fuzzyAssertRaisesError(BadOptionFormat, "Can't find key in options", key=key):
            self.spec.normalise(self.meta, "{{{0}}}".format(key))

    it "otherwise just gets keys":
        val = str(uuid.uuid1())
        self.meta.everything[["one", "two"]] = val
        self.assertEqual(self.spec.normalise(self.meta, "{one.two}"), val)

    it "complains if we have a recursive option":
        with self.fuzzyAssertRaisesError(BadOptionFormat, "Recursive option", chain=["one", "one"]):
            self.spec.normalise(self.meta.at("one"), "{one}")

    it "can use pkg_resources to find location of a resource":
        res = mock.Mock(name="res")
        resource_filename = mock.Mock(name="resource_filename", return_value=res)
        with mock.patch("pkg_resources.resource_filename", resource_filename):
            self.assertIs(
                self.spec.normalise(self.meta, "{somewhere.nice/really/cool:resource}"), res
            )

        resource_filename.assert_called_once_with("somewhere.nice", "really/cool")

    it "can return asyncio.Future objects":
        fut = asyncio.Future()
        self.meta.everything["fut"] = fut
        self.assertIs(self.spec.normalise(self.meta, "{fut}"), fut)
