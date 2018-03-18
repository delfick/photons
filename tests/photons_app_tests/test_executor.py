# coding: spec

from photons_app.registers import TargetRegister
from photons_app.test_helpers import TestCase
from photons_app.collector import Collector
from photons_app import helpers as hp
from photons_app.executor import App

from input_algorithms import spec_base as sb
from delfick_app import App as DelfickApp
from textwrap import dedent
import uuid
import mock

describe TestCase, "App":
    describe "setup_collector":
        def from_config(self, config):
            with hp.a_temp_file() as fle:
                fle.write(dedent(config).encode())
                fle.flush()

                args_dict = {
                      "photons_app":
                      { "config": open(fle.name)
                      , "own_ca": sb.NotSpecified
                      }
                    }

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

        it "gets us the target from chosen_task if we haven't already got a target":
            location, args_dict, logging_handler, collector = self.from_config("""
                ---

                photons_app:
                  chosen_task: "blah:yeap"
            """)

            self.assertEqual(collector.configuration["photons_app"].target, "blah")

        it "doesn't set target if chosen_task doesn't specify target":
            location, args_dict, logging_handler, collector = self.from_config("""
                ---

                photons_app:
                  chosen_task: "blah"
            """)

            self.assertEqual(collector.configuration["photons_app"].target, sb.NotSpecified)

        it "doesn't set target if it's already specified":
            location, args_dict, logging_handler, collector = self.from_config("""
                ---

                photons_app:
                  target: other
                  chosen_task: "blah:yeap"
            """)

            self.assertEqual(collector.configuration["photons_app"].target, "other")

        it "sets up logging theme if term_colors is specified":
            setup_logging_theme = mock.Mock(name="setup_logging_theme")

            with mock.patch.object(App, "setup_logging_theme", setup_logging_theme):
                location, args_dict, logging_handler, collector = self.from_config("""
                    ---

                    term_colors: light
                """)

            setup_logging_theme.assert_called_once_with(logging_handler, colors="light")

        it "sets up the target register":
            add_targets = mock.Mock(name="add_targets")

            with mock.patch.object(TargetRegister, "add_targets", add_targets):
                location, args_dict, logging_handler, collector = self.from_config("""
                    ---

                    targets:
                      one:
                        type: thing
                        options: {1: 2}
                """)

            assert "one" in collector.configuration["targets"]
            add_targets.assert_called_once_with(collector.configuration["targets"])

    describe "mainline":
        def run_with(self, argv):
            original_mainline = mock.Mock(name="original_mainline")

            with mock.patch.object(DelfickApp, "mainline", original_mainline):
                App().mainline(argv)

            original_mainline.assert_called_once_with(mock.ANY, mock.ANY)
            call_list = original_mainline.mock_calls[0].call_list()[0][1]
            return call_list[0]

        it "adds --silent to the argv if there are no options":
            used_args = self.run_with([])
            self.assertEqual(used_args, ["--silent"])

        it "adds --silent if the task is list_tasks or help":
            for attempt in ("list_tasks", "help", "target:list_tasks", "target:help"):
                used_args = self.run_with([attempt])
                self.assertEqual(used_args, [attempt, "--silent"])

        it "adds --silent before any --":
            for attempt in ("list_tasks", "help", "target:list_tasks", "target:help"):
                used_args = self.run_with([attempt, "--", "other"])
                self.assertEqual(used_args, [attempt, "--silent", "--", "other"])
