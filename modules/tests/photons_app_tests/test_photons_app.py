import asyncio
import os
from unittest import mock

import alt_pytest_asyncio
import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta
from photons_app import helpers as hp
from photons_app.errors import BadOption
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.photons_app import PhotonsApp


def make_photons_app(**kwargs):
    meta = Meta.empty().at("photons_app")
    return PhotonsApp.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, kwargs)


class TestPhotonsApp:

    @pytest.fixture(autouse=True)
    def override_loop(self):
        with alt_pytest_asyncio.Loop(new_loop=False):
            yield

    class TestLoop:
        def test_it_gets_a_loop(self):
            photons_app = make_photons_app()
            loop = photons_app.loop
            assert not loop.get_debug()

        def test_it_makes_the_loop_debug_if_we_are_in_debug(self):
            photons_app = make_photons_app(debug=True)

            loop = photons_app.loop
            assert loop.get_debug()

    class TestFinalFuture:
        def test_it_belongs_to_the_loop(self):
            photons_app = make_photons_app()
            final_future = photons_app.final_future
            assert final_future._loop is photons_app.loop

    class TestExtraAsJson:
        def test_it_converts_extra_into_json_dictionary(self):
            photons_app = make_photons_app(extra='{"one": 2, "two": "three"}')
            assert photons_app.extra_as_json == {"one": 2, "two": "three"}

        def test_it_complains_if_extra_is_not_valid_json(self):
            with assertRaises(BadOption, "The options after -- wasn't valid json"):
                make_photons_app(extra="{").extra_as_json

        def test_it_can_read_json_from_a_file(self):
            with hp.a_temp_file() as fle:
                fle.write(b'{"power": "off"}')
                fle.flush()
                assert make_photons_app(extra=f"file://{fle.name}").extra_as_json == {
                    "power": "off"
                }

                path = os.path.relpath(fle.name, os.getcwd())
                assert not path.startswith("/")
                assert make_photons_app(extra=f"file://{path}").extra_as_json == {"power": "off"}

            with hp.a_temp_file() as fle:
                with assertRaises(
                    BadOption,
                    "The options after -- wasn't valid json",
                    read_from=os.path.abspath(fle.name),
                ):
                    fle.write(b'"power": "off"}')
                    fle.flush()
                    assert make_photons_app(extra=f"file://{fle.name}").extra_as_json == {
                        "power": "off"
                    }

            path = os.path.join(os.getcwd(), "no_exist_yo.json")
            with assertRaises(BadOption, f"The path {path} does not exist"):
                make_photons_app(extra="file://no_exist_yo.json").extra_as_json

    class TestCleanup:
        def test_it_runs_all_the_cleaners_and_then_calls_finish_on_all_the_targets(self):
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

            photons_app = make_photons_app()
            photons_app.cleaners.extend([cleaner1, cleaner2, cleaner3])

            targets = [target1, target2, target3]

            assert called == []
            asyncio.new_event_loop().run_until_complete(photons_app.cleanup(targets))
            assert called == [1, 2, 3, 4, 5]
