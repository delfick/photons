# coding: spec

from photons_app.option_spec.photons_app_spec import PhotonsApp
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.test_helpers import TestCase
from photons_app.errors import BadOption

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.meta import Meta
import asynctest
import platform
import asyncio
import mock

describe TestCase, "PhotonsApp":
    before_each:
        self.final_future = asyncio.Future()
        self.meta = Meta({"final_future": self.final_future}, []).at("photons_app")

    def make_photons_app(self, **kwargs):
        return PhotonsApp.FieldSpec(formatter=MergedOptionStringFormatter).normalise(self.meta, kwargs)

    describe "loop":
        it "gets a loop":
            photons_app = self.make_photons_app()
            loop = photons_app.loop
            assert not loop.get_debug()

        it "makes the loop debug if we are in debug":
            photons_app = self.make_photons_app(debug=True)

            loop = photons_app.loop
            assert loop.get_debug()

    describe "final_future":
        it "Is the final future":
            photons_app = self.make_photons_app()
            self.assertIs(photons_app.final_future, self.final_future)

    describe "extra_as_json":
        it "converts extra into json dictionary":
            photons_app = self.make_photons_app(extra='{"one": 2, "two": "three"}')
            self.assertEqual(photons_app.extra_as_json, {"one": 2, "two": "three"})

        it "complains if extra is not valid json":
            with self.fuzzyAssertRaisesError(BadOption, "The options after -- wasn't valid json"):
                self.make_photons_app(extra="{").extra_as_json

    describe "cleanup":
        it "runs all the cleaners and then calls finish on all the targets":
            called = []

            def call(num):
                def wrapped(*args, **kwargs):
                    called.append(num)
                return wrapped

            cleaner1 = asynctest.mock.CoroutineMock(name="cleaner1", side_effect=call(1))
            cleaner2 = asynctest.mock.CoroutineMock(name="cleaner2", side_effect=call(2))
            cleaner3 = asynctest.mock.CoroutineMock(name="cleaner3", side_effect=call(3))

            target1 = mock.Mock(name="target1")
            target1.finish = asynctest.mock.CoroutineMock(name="target1.finish", side_effect=call(4))

            target2 = mock.Mock(name="target2")
            target2.finish = asynctest.mock.CoroutineMock(name="target2.finish", side_effect=call(5))

            # And a target with no finish attribute
            target3 = mock.Mock(name="target3", spec=[])

            photons_app = self.make_photons_app()
            photons_app.cleaners.extend([cleaner1, cleaner2, cleaner3])

            targets = [target1, target2, target3]

            self.assertEqual(called, [])
            asyncio.new_event_loop().run_until_complete(photons_app.cleanup(targets))
            self.assertEqual(called, [1, 2, 3, 4, 5])
