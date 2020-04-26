# coding: spec

from photons_core import run_script, run_cli, CommandSplitter

from photons_app.test_helpers import modified_env

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import pytest

describe "CommandSplitter":
    it "can format argv":
        command = "{@:2}:{@:1} {@:3:}"
        result = CommandSplitter(
            {"argv": ["my_script", "one", "two", "three", "four"]}, command
        ).split()
        assert result == ["two:one", "three", "four"]

        command = "{@:2:4}:{@:1} {@:4:}"
        result = CommandSplitter(
            {"argv": ["my_script", "one", "two", "three", "four", "five"]}, command
        ).split()
        assert result == ["two", "three:one", "four", "five"]

    it "can complain about an env specifier without a name":
        with assertRaises(Exception, "env specifier used without saying what variable is needed"):
            command = "{:env}"
            CommandSplitter({"argv": ["my_script"]}, command).split()

    it "can complain if an environment variable is needed but doesn't exist":
        with modified_env(THING=None):
            with assertRaises(
                SystemExit, "This script requires you have a 'THING' variable in your environment"
            ):
                command = "{THING:env}"
                CommandSplitter({"argv": ["my_script"]}, command).split()

    it "doesn't complain if the environment variable exists but is empty":
        with modified_env(THING=""):
            command = "thing={THING:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["thing="]

            command = "{THING:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == []

    it "can have default values for environment variables":
        with modified_env(THING=None):
            command = "thing={THING|stuff:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["thing=stuff"]

            command = "{THING|stuff:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["stuff"]

    it "doesn't use default if env variable exists but is empty":
        with modified_env(THING=""):
            command = "thing={THING|stuff:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["thing="]

            command = "{THING|stuff:env}"
            assert CommandSplitter({"argv": ["my_script"]}, command).split() == []

    it "complains if there is not enough argv entries":
        with assertRaises(SystemExit, "Needed greater than 2 arguments to the script"):
            with modified_env(THING=""):
                command = "{@:2}"
                CommandSplitter({"argv": ["my_script"]}, command).split()

    it "doesn't complain about ranges that don't have values":
        command = "one {@:2:}"
        assert CommandSplitter({"argv": ["my_script"]}, command).split() == ["one"]

    it "doesn't format anything after a --":
        command = """{@:1:} -- '{"power": "off"}"""
        assert CommandSplitter({"argv": ["my_script", "one"]}, command).split() == [
            "one",
            "--",
            '{"power": "off"}',
        ]

    it "doesn't need the json after the -- to be wrapped in single quotes":
        command = '{@:1:} -- {"power": "off"}'
        assert CommandSplitter({"argv": ["my_script", "one"]}, command).split() == [
            "one",
            "--",
            '{"power": "off"}',
        ]

    it "retains --options":
        command = '{@:1:} --silent -- {"power": "off"}'
        assert CommandSplitter({"argv": ["my_script", "one"]}, command).split() == [
            "one",
            "--silent",
            "--",
            '{"power": "off"}',
        ]


describe "main lines":

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

        FakeCommandSplitter = mock.Mock(
            name="CommandSplitter", spec=[], return_value=command_splitter
        )

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

    it "run_cli defaults to using sys.argv", V:
        run_cli("command")
        V.CommandSplitter.assert_called_once_with({"argv": V.argv}, "command")
        V.main.assert_called_once_with(V.split, default_activate=["__all__"])

    it "run_script defaults to using sys.argv", V:
        run_script("command")
        V.CommandSplitter.assert_called_once_with({"argv": V.argv}, "command")
        V.main.assert_called_once_with(V.split, default_activate=None)

    it "run_cli can skip going through the splitter", V:
        run_cli(["one", "two"])
        V.CommandSplitter.assert_not_called()
        V.main.assert_called_once_with(["one", "two"], default_activate=["__all__"])

    it "run_script can skip going through the splitter", V:
        run_cli(["one", "two"])
        V.CommandSplitter.assert_not_called()
        V.main.assert_called_once_with(["one", "two"], default_activate=["__all__"])

    it "run_cli can be given argv", V:
        run_cli("lan:stuff", argv=["one", "two"])
        V.CommandSplitter.assert_called_once_with(
            {"argv": ["my_script", "one", "two"]}, "lan:stuff"
        )
        V.main.assert_called_once_with(V.split, default_activate=["__all__"])

    it "run_cli formats correctly", fake_main:
        with modified_env(LAN_TARGET="well"):
            run_cli(
                "{LAN_TARGET:env}:get_attr {@:1} {@:2:}",
                argv=["match:cap=chain", "--silent", "--", '{"one": "two"}'],
            )

        fake_main.assert_called_once_with(
            ["well:get_attr", "match:cap=chain", "--silent", "--", '{"one": "two"}'],
            default_activate=["__all__"],
        )

    it "run_script formats correctly", fake_main:
        with modified_env(LAN_TARGET="well"):
            run_script(
                "{LAN_TARGET:env}:get_attr {@:1} {@:2:}",
                argv=["match:cap=chain", "--silent", "--", '{"one": "two"}'],
            )

        fake_main.assert_called_once_with(
            ["well:get_attr", "match:cap=chain", "--silent", "--", '{"one": "two"}'],
            default_activate=None,
        )

    it "can have defaults for environment", fake_main:
        with modified_env(LAN_TARGET=None):
            run_script(
                "{LAN_TARGET|lan:env}:get_attr {@:1} {@:2:}",
                argv=["match:cap=chain", "--silent", "--", '{"one": "two"}'],
            )

        fake_main.assert_called_once_with(
            ["lan:get_attr", "match:cap=chain", "--silent", "--", '{"one": "two"}'],
            default_activate=None,
        )

    it "can not format json dictionary", fake_main:
        with modified_env(LAN_TARGET=None):
            run_cli("""lan:transform -- '{"power": "on"}'""", argv=["my_script"])

        fake_main.assert_called_once_with(
            ["lan:transform", "--", '{"power": "on"}'], default_activate=["__all__"],
        )
