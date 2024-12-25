import os
from textwrap import dedent
from unittest import mock

import alt_pytest_asyncio
import pytest
from delfick_project.app import App as DelfickApp
from delfick_project.norms import sb
from photons_app import helpers as hp
from photons_app.collector import Collector
from photons_app.executor import App


@pytest.fixture(autouse=True)
def override_loop():
    with alt_pytest_asyncio.Loop(new_loop=False):
        yield


class TestApp:
    class TestSetupCollector:

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

        def test_it_prepares_the_collector_with_the_photons_appconfig(self):
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

        def test_it_gets_us_the_task_specifier(self):
            location, args_dict, logging_handler, collector = self.from_config(
                """
                ---

                photons_app:
                  task_specifier: "blah:yeap"
            """
            )

            result = collector.photons_app.task_specifier()
            assert result == ("blah", "yeap")

        def test_it_doesnt_set_target_if_task_specifier_doesnt_specify_target(self):
            location, args_dict, logging_handler, collector = self.from_config(
                """
                ---

                photons_app:
                  task_specifier: "blah"
            """
            )

            result = collector.photons_app.task_specifier()
            assert result == (sb.NotSpecified, "blah")

        def test_it_sets_up_logging_theme_if_term_colors_is_specified(self):
            setup_logging_theme = mock.Mock(name="setup_logging_theme")

            with mock.patch.object(App, "setup_logging_theme", setup_logging_theme):
                location, args_dict, logging_handler, collector = self.from_config(
                    """
                    ---

                    term_colors: light
                """
                )

            setup_logging_theme.assert_called_once_with(logging_handler, colors="light")

    class TestMainline:

        def using_argv(self, argv):
            original_mainline = mock.Mock(name="original_mainline")

            with mock.patch.object(DelfickApp, "mainline", original_mainline):
                App().mainline(argv)

            original_mainline.assert_called_once_with(mock.ANY, mock.ANY)
            call_list = original_mainline.mock_calls[0].call_list()[0][1]
            return call_list[0]

        def test_it_adds_PHOTONS_SILENT_BY_DEFAULT_if_there_are_no_options(self):
            with pytest.helpers.modified_env(PHOTONS_SILENT_BY_DEFAULT=None):
                assert "PHOTONS_SILENT_BY_DEFAULT" not in os.environ
                used_args = self.using_argv([])
                assert used_args == []
                assert os.environ["PHOTONS_SILENT_BY_DEFAULT"] == "1"

        def test_it_adds_PHOTONS_SILENT_BY_DEFAULT_if_the_task_is_list_tasks_or_help(self):
            for attempt in ("list_tasks", "help", "target:list_tasks", "target:help"):
                with pytest.helpers.modified_env(PHOTONS_SILENT_BY_DEFAULT=None):
                    assert "PHOTONS_SILENT_BY_DEFAULT" not in os.environ
                    used_args = self.using_argv([attempt])
                    assert used_args == [attempt]
                    assert os.environ["PHOTONS_SILENT_BY_DEFAULT"] == "1"
