# coding: spec

from photons_app.collector import Collector
from photons_app import helpers as hp
from photons_app.executor import App

from alt_pytest_asyncio.plugin import OverrideLoop
from delfick_project.app import App as DelfickApp
from delfick_project.norms import sb
from textwrap import dedent
from unittest import mock
import pytest
import os


@pytest.fixture(autouse=True)
def override_loop():
    with OverrideLoop(new_loop=False):
        yield


describe "App":
    describe "setup_collector":

        def from_config(self, config):
            with hp.a_temp_file() as fle:
                fle.write(dedent(config).encode())
                fle.close()

                with open(fle.name) as realfile:
                    args_dict = {"photons_app": {"config": realfile}}

                    app = App()
                    logging_handler = mock.Mock(name="logging_handler")
                    collector = app.setup_collector(args_dict, logging_handler, None)
                return fle.name, args_dict, logging_handler, collector

        it "prepares the collector with the photons_app.config":
            collector = Collector()
            FakeCollector = mock.Mock(name="Collector", return_value=collector)

            original_prepare = Collector.prepare

            def prepare(*args, **kwargs):
                return original_prepare(collector, *args, **kwargs)

            prepare = mock.Mock(name="prepare", side_effect=prepare)

            with mock.patch("photons_app.executor.Collector", FakeCollector):
                with mock.patch.object(Collector, "prepare", prepare):
                    location, args_dict, logging_handler, collector = self.from_config("")

            prepare.assert_called_once_with(location, args_dict, extra_files=None)

        it "gets us the task_specifier":
            location, args_dict, logging_handler, collector = self.from_config(
                """
                ---

                photons_app:
                  task_specifier: "blah:yeap"
            """
            )

            result = collector.photons_app.task_specifier()
            assert result == ("blah", "yeap")

        it "doesn't set target if task_specifier doesn't specify target":
            location, args_dict, logging_handler, collector = self.from_config(
                """
                ---

                photons_app:
                  task_specifier: "blah"
            """
            )

            result = collector.photons_app.task_specifier()
            assert result == (sb.NotSpecified, "blah")

        it "sets up logging theme if term_colors is specified":
            setup_logging_theme = mock.Mock(name="setup_logging_theme")

            with mock.patch.object(App, "setup_logging_theme", setup_logging_theme):
                location, args_dict, logging_handler, collector = self.from_config(
                    """
                    ---

                    term_colors: light
                """
                )

            setup_logging_theme.assert_called_once_with(logging_handler, colors="light")

    describe "mainline":

        def using_argv(self, argv):
            original_mainline = mock.Mock(name="original_mainline")

            with mock.patch.object(DelfickApp, "mainline", original_mainline):
                App().mainline(argv)

            original_mainline.assert_called_once_with(mock.ANY, mock.ANY)
            call_list = original_mainline.mock_calls[0].call_list()[0][1]
            return call_list[0]

        it "adds PHOTONS_SILENT_BY_DEFAULT if there are no options":
            with pytest.helpers.modified_env(PHOTONS_SILENT_BY_DEFAULT=None):
                assert "PHOTONS_SILENT_BY_DEFAULT" not in os.environ
                used_args = self.using_argv([])
                assert used_args == []
                assert os.environ["PHOTONS_SILENT_BY_DEFAULT"] == "1"

        it "adds PHOTONS_SILENT_BY_DEFAULT if the task is list_tasks or help":
            for attempt in ("list_tasks", "help", "target:list_tasks", "target:help"):
                with pytest.helpers.modified_env(PHOTONS_SILENT_BY_DEFAULT=None):
                    assert "PHOTONS_SILENT_BY_DEFAULT" not in os.environ
                    used_args = self.using_argv([attempt])
                    assert used_args == [attempt]
                    assert os.environ["PHOTONS_SILENT_BY_DEFAULT"] == "1"
