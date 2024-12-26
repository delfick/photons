from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_core import CommandSplitter, run


class TestCommandSplitter:
    def test_it_can_format_argv(self):
        command = "{@:2}:{@:1} {@:3:}"
        result = CommandSplitter({"argv": ["my_script", "one", "two", "three", "four"]}, command).split()
        assert result == ["two:one", "three", "four"]

        command = "{@:2:4}:{@:1} {@:4:}"
        result = CommandSplitter({"argv": ["my_script", "one", "two", "three", "four", "five"]}, command).split()
        assert result == ["two", "three:one", "four", "five"]

    def test_it_can_complain_about_an_env_specifier_without_a_name(self):
        with assertRaises(Exception, "env specifier used without saying what variable is needed"):
            command = "{:env}"
            CommandSplitter({"argv": ["my_script"]}, command).split()

    def test_it_can_complain_if_an_environment_variable_is_needed_but_doesnt_exist(self):
        with pytest.helpers.modified_env(THING=None):
            with assertRaises(SystemExit, "This script requires you have a 'THING' variable in your environment"):
                command = "{THING:env}"
                CommandSplitter({"argv": ["my_script"]}, command).split()

    def test_it_doesnt_complain_if_the_environment_variable_exists_but_is_empty(self):
        with pytest.helpers.modified_env(THING=""):
            command = "thing={THING:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["thing="]

            command = "{THING:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == []

    def test_it_can_have_default_values_for_environment_variables(self):
        with pytest.helpers.modified_env(THING=None):
            command = "thing={THING|stuff:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["thing=stuff"]

            command = "{THING|stuff:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["stuff"]

    def test_it_doesnt_use_default_if_env_variable_exists_but_is_empty(self):
        with pytest.helpers.modified_env(THING=""):
            command = "thing={THING|stuff:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["thing="]

            command = "{THING|stuff:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == []

    def test_it_complains_if_there_is_not_enough_argv_entries(self):
        with assertRaises(SystemExit, "Needed greater than 2 arguments to the script"):
            with pytest.helpers.modified_env(THING=""):
                command = "{@:2}"
                CommandSplitter({"argv": ["my_script"]}, command).split()

    def test_it_doesnt_complain_about_ranges_that_dont_have_values(self):
        command = "one {@:2:}"
        assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["one"]

    def test_it_doesnt_format_anything_after_a(self):
        command = """{@:1:} -- '{"power": "off"}"""
        assert CommandSplitter({"argv": ["my_script", "one"]}, command).split() == [
            "one",
            "--",
            '{"power": "off"}',
        ]

    def test_it_doesnt_need_the_json_after_the_to_be_wrapped_in_single_quotes(self):
        command = '{@:1:} -- {"power": "off"}'
        assert CommandSplitter({"argv": ["my_script", "one"]}, command).split() == [
            "one",
            "--",
            '{"power": "off"}',
        ]

    def test_it_retains_options(self):
        command = '{@:1:} --silent -- {"power": "off"}'
        assert CommandSplitter({"argv": ["my_script", "one"]}, command).split() == [
            "one",
            "--silent",
            "--",
            '{"power": "off"}',
        ]


class TestMainLines:
    @pytest.fixture()
    def sys_argv(self):
        argv = ["my_script", "from", "the", "commandline"]
        with mock.patch("sys.argv", argv):
            yield argv

    @pytest.fixture()
    def fake_command_splitter(self):
        split = mock.Mock(name="split", spec=[])
        command_splitter = mock.Mock(name="command_splitter", spec=["split"])
        command_splitter.split.return_value = split

        FakeCommandSplitter = mock.Mock(name="CommandSplitter", spec=[], return_value=command_splitter)

        with mock.patch("photons_core.CommandSplitter", FakeCommandSplitter):
            yield FakeCommandSplitter, split

    @pytest.fixture()
    def fake_main(self):
        main = mock.Mock(name="main")
        with mock.patch("photons_core.main", main):
            yield main

    @pytest.fixture()
    def V(self, sys_argv, fake_command_splitter, fake_main):
        class V:
            main = fake_main
            argv = sys_argv
            split = fake_command_splitter[1]
            CommandSplitter = fake_command_splitter[0]

        return V()

    def test_it_run_defaults_to_using_sysargv(self, V):
        run("command")
        V.CommandSplitter.assert_called_once_with({"argv": V.argv}, "command")
        V.main.assert_called_once_with(V.split, default_activate=["core"])

    def test_it_can_be_given_a_different_default_activate(self, V):
        run("command", default_activate=[])
        V.main.assert_called_once_with(V.split, default_activate=[])

        V.main.reset_mock()
        run("command", default_activate=["__all__"])
        V.main.assert_called_once_with(V.split, default_activate=["__all__"])

    def test_it_run_can_skip_going_through_the_splitter(self, V):
        run(["one", "two"])
        V.CommandSplitter.assert_not_called()
        V.main.assert_called_once_with(["one", "two"], default_activate=["core"])

    def test_it_run_can_be_given_argv(self, V):
        run("lan:stuff", argv=["one", "two"])
        V.CommandSplitter.assert_called_once_with({"argv": ["my_script", "one", "two"]}, "lan:stuff")
        V.main.assert_called_once_with(V.split, default_activate=["core"])

    def test_it_run_formats_correctly(self, fake_main):
        with pytest.helpers.modified_env(LAN_TARGET="well"):
            run(
                "{LAN_TARGET:env}:attr {@:1} {@:2:}",
                argv=["match:cap=chain", "--silent", "--", '{"one": "two"}'],
            )

        fake_main.assert_called_once_with(
            ["well:attr", "match:cap=chain", "--silent", "--", '{"one": "two"}'],
            default_activate=["core"],
        )

    def test_it_can_have_defaults_for_environment(self, fake_main):
        with pytest.helpers.modified_env(LAN_TARGET=None):
            run(
                "{LAN_TARGET|lan:env}:attr {@:1} {@:2:}",
                argv=["match:cap=chain", "--silent", "--", '{"one": "two"}'],
            )

        fake_main.assert_called_once_with(
            ["lan:attr", "match:cap=chain", "--silent", "--", '{"one": "two"}'],
            default_activate=["core"],
        )

    def test_it_will_not_format_json_dictionary(self, fake_main):
        with pytest.helpers.modified_env(LAN_TARGET=None):
            run("""lan:transform -- '{"power": "on"}'""", argv=["my_script"])

        fake_main.assert_called_once_with(["lan:transform", "--", '{"power": "on"}'], default_activate=["core"])
