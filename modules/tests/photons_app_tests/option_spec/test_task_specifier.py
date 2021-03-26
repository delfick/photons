# coding: spec

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.task_specifier import task_specifier_spec
from photons_app.errors import TargetNotFound
from photons_app.collector import Collector
from photons_app import helpers as hp
from photons_app.executor import App

from photons_transport.targets.base import Target
from photons_transport.targets import LanTarget

from delfick_project.norms import Meta, sb, dictobj, BadSpecValue
from delfick_project.errors_pytest import assertRaises
from textwrap import dedent
from unittest import mock
import pytest

describe "task_specifier_spec":

    @pytest.fixture()
    def spec(self):
        return task_specifier_spec()

    def meta(self, config="", extra_prepare=None):
        with hp.a_temp_file() as fle:
            fle.write(dedent(config).encode())
            fle.close()

            original = Collector.extra_prepare_after_activation

            class Prepare:
                def __enter__(s):
                    if extra_prepare:

                        def extra(*args, **kwargs):
                            extra_prepare(*args, **kwargs)
                            return original(*args, **kwargs)

                        s.patch = mock.patch.object(
                            Collector, "extra_prepare_after_activation", extra
                        )
                        s.patch.start()

                def __exit__(s, exc_typ, exc, tb):
                    if hasattr(s, "patch"):
                        s.patch.stop()

            with Prepare(), open(fle.name) as realfile:
                args_dict = {"photons_app": {"config": realfile}}

                app = App()
                logging_handler = mock.Mock(name="logging_handler")
                collector = app.setup_collector(args_dict, logging_handler, None)
                return Meta({"collector": collector}, [])

    it "can have default", spec:
        for val in ("", None, sb.NotSpecified):
            result = spec.normalise(self.meta(), val)
            assert result == (sb.NotSpecified, "list_tasks")

    it "can treat task as just a task", spec:
        result = spec.normalise(self.meta(), "things")
        assert result == (sb.NotSpecified, "things")

    it "can split by last :", spec:
        result = spec.normalise(self.meta(), "one:two:three")
        assert result == ("one:two", "three")

        result = spec.normalise(self.meta(), "one:three")
        assert result == ("one", "three")

    describe "taking in an iterable":

        it "can take a two item", spec:
            result = spec.normalise(self.meta(), ("one", "three"))
            assert result == ("one", "three")

            result = spec.normalise(self.meta(), ["one", "three"])
            assert result == ("one", "three")

        it "complains about non two item", spec:
            invalids = [(), ("adsf",), ("adsf", "afd", "df"), (1,), (1, 2, 3)]
            for invalid in invalids:
                with assertRaises(BadSpecValue, "Expected tuple to be of a particular length"):
                    spec.normalise(self.meta(), invalid)

        it "allows not specified for target", spec:
            result = spec.normalise(self.meta(), (sb.NotSpecified, "amaze"))
            assert result == (sb.NotSpecified, "amaze")

        it "complains about a two item tuple with bad types", spec:
            invalids = [(None, None), ("asdf", sb.NotSpecified), (1, 2), ([], []), ({}, {})]
            for invalid in invalids:
                with assertRaises(BadSpecValue, "Value failed some specifications"):
                    spec.normalise(self.meta(), invalid)

    describe "overriding a target":
        it "complains if the target being overridden doesn't exist", spec:
            with assertRaises(TargetNotFound, name="wat", available=[]):
                spec.normalise(self.meta(), "wat():meh")

            config = """
            targets:
              wat:
                type: lan
                optional: true
            """

            with assertRaises(TargetNotFound, name="wat", available=[]):
                spec.normalise(self.meta(config), "wat():meh")

            config = """
            photons_app:
              addons:
                lifx.photons:
                  - transport
            """

            with assertRaises(TargetNotFound, name="wat"):
                spec.normalise(self.meta(config), "wat():meh")

        it "complains if we don't can't parse tokens", spec:
            token_errors = ["wat(", "wat({)", "("]
            for specifier in token_errors:
                with assertRaises(BadSpecValue, "Failed to parse specifier"):
                    spec.normalise(self.meta(), f"{specifier}:meh")

        it "complains if we have invalid syntax", spec:
            config = """
            photons_app:
              addons:
                lifx.photons:
                  - transport
            """

            syntax_errors = ["lan('a'=_)", "lan(=a)", "lan(10='a')"]
            for specifier in syntax_errors:
                with assertRaises(BadSpecValue, "Target options must be valid dictionary syntax"):
                    spec.normalise(self.meta(config), f"{specifier}:meh")

        it "complains about keyword arguments that aren't literals", spec:
            config = """
            photons_app:
              addons:
                lifx.photons:
                  - transport
            """

            syntax_errors = [
                "lan(a=_)",
                "lan(a=__import__('os').path.join('one', 'two'))",
                "lan(a=open('somewhere'))",
            ]
            for specifier in syntax_errors:
                with assertRaises(BadSpecValue, "target options can only be python literals.+"):
                    spec.normalise(self.meta(config), f"{specifier}:meh")

        it "can override properties on a target", spec:
            config = """
            photons_app:
              addons:
                lifx.photons:
                  - transport
            """

            meta = self.meta(config)

            target_register = meta.everything["collector"].configuration["target_register"]
            original = list(target_register.registered)
            assert "lan" in original, original

            result = spec.normalise(meta, "lan(default_broadcast='9.8.7.6'):amazing_task")
            assert len(target_register.registered) == len(original) + 1

            assert result == (mock.ANY, "amazing_task")
            assert result[0].startswith("lan_"), result[0]
            assert len(result[0]) == 4 + 32

            target = target_register.resolve(result[0])
            assert isinstance(target, LanTarget)
            assert target.default_broadcast == "9.8.7.6"

            lan = target_register.resolve("lan")
            assert isinstance(lan, LanTarget)
            assert lan.default_broadcast == "255.255.255.255"

        it "can override properties with another target", spec:

            class Container(Target):
                network = dictobj.Field(format_into=sb.any_spec, wrapper=sb.required)

            def extra_prepare(collector, configuration, args_dict):
                collector.configuration["target_register"].register_type(
                    "container", Container.FieldSpec(formatter=MergedOptionStringFormatter)
                )

            config = """
            photons_app:
              addons:
                lifx.photons:
                  - transport

            targets:
              con:
                type: container
                options:
                  network: "{targets.lan}"

              lan2:
                type: lan
                options:
                  default_broadcast: 1.1.1.255
            """

            meta = self.meta(config, extra_prepare=extra_prepare)
            target_register = meta.everything["collector"].configuration["target_register"]

            original = list(target_register.registered)
            assert "con" in original, original

            result = spec.normalise(meta, "con(network='{targets.lan2}'):amazing_task")
            assert len(target_register.registered) == len(original) + 1

            assert result == (mock.ANY, "amazing_task")
            assert result[0].startswith("con_"), result[0]
            assert len(result[0]) == 4 + 32

            target = target_register.resolve(result[0])
            assert isinstance(target, Container)
            assert target.network is target_register.resolve("lan2")

            con = target_register.resolve("con")
            assert isinstance(con, Container)
            assert con.network is target_register.resolve("lan")
