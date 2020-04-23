# coding: spec

from photons_app.option_spec.photons_app_spec import PhotonsApp
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import BadOption
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta
from unittest import mock
import asyncio
import pytest
import os

describe "PhotonsApp":

    def make_photons_app(self, **kwargs):
        meta = Meta.empty().at("photons_app")
        return PhotonsApp.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, kwargs)

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
        it "belongs to the loop":
            photons_app = self.make_photons_app()
            final_future = photons_app.final_future
            assert final_future._loop is photons_app.loop

    describe "extra_as_json":
        it "converts extra into json dictionary":
            photons_app = self.make_photons_app(extra='{"one": 2, "two": "three"}')
            assert photons_app.extra_as_json == {"one": 2, "two": "three"}

        it "complains if extra is not valid json":
            with assertRaises(BadOption, "The options after -- wasn't valid json"):
                self.make_photons_app(extra="{").extra_as_json

        it "can read json from a file":
            with hp.a_temp_file() as fle:
                fle.write(b'{"power": "off"}')
                fle.flush()
                assert self.make_photons_app(extra=f"file://{fle.name}").extra_as_json == {
                    "power": "off"
                }

                path = os.path.relpath(fle.name, os.getcwd())
                assert not path.startswith("/")
                assert self.make_photons_app(extra=f"file://{path}").extra_as_json == {
                    "power": "off"
                }

            with hp.a_temp_file() as fle:
                with assertRaises(
                    BadOption,
                    "The options after -- wasn't valid json",
                    read_from=os.path.abspath(fle.name),
                ):
                    fle.write(b'"power": "off"}')
                    fle.flush()
                    assert self.make_photons_app(extra=f"file://{fle.name}").extra_as_json == {
                        "power": "off"
                    }

            path = os.path.join(os.getcwd(), "no_exist_yo.json")
            with assertRaises(BadOption, f"The path {path} does not exist"):
                self.make_photons_app(extra="file://no_exist_yo.json").extra_as_json

    describe "cleanup":
        it "runs all the cleaners and then calls finish on all the targets":
            called = []

            def call(num):
                def wrapped(*args, **kwargs):
                    called.append(num)

                return wrapped

            cleaner1 = pytest.helpers.AsyncMock(name="cleaner1", side_effect=call(1))
            cleaner2 = pytest.helpers.AsyncMock(name="cleaner2", side_effect=call(2))
            cleaner3 = pytest.helpers.AsyncMock(name="cleaner3", side_effect=call(3))

            target1 = mock.Mock(name="target1")
            target1.finish = pytest.helpers.AsyncMock(name="target1.finish", side_effect=call(4))

            target2 = mock.Mock(name="target2")
            target2.finish = pytest.helpers.AsyncMock(name="target2.finish", side_effect=call(5))

            # And a target with no finish attribute
            target3 = mock.Mock(name="target3", spec=[])

            photons_app = self.make_photons_app()
            photons_app.cleaners.extend([cleaner1, cleaner2, cleaner3])

            targets = [target1, target2, target3]

            assert called == []
            asyncio.new_event_loop().run_until_complete(photons_app.cleanup(targets))
            assert called == [1, 2, 3, 4, 5]
