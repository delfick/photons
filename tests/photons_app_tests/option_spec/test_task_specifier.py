# coding: spec

from photons_app.option_spec.task_specifier import task_specifier_spec
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.test_helpers import TestCase
from photons_app.errors import TargetNotFound
from photons_app.collector import Collector
from photons_app import helpers as hp
from photons_app.executor import App

from photons_transport.targets.base import Target
from photons_transport.targets import LanTarget

from delfick_project.norms import Meta, sb, dictobj, BadSpecValue
from noseOfYeti.tokeniser.support import noy_sup_setUp
from textwrap import dedent
from unittest import mock

describe TestCase, "task_specifier_spec":
    before_each:
        self.spec = task_specifier_spec()

    def meta(self, config="", extra_prepare=None):
        with hp.a_temp_file() as fle:
            fle.write(dedent(config).encode())
            fle.close()

            original = Collector.extra_prepare_after_activation

            class Prepare:
                def __enter__(self):
                    if extra_prepare:

                        def extra(*args, **kwargs):
                            extra_prepare(*args, **kwargs)
                            return original(*args, **kwargs)

                        self.patch = mock.patch.object(
                            Collector, "extra_prepare_after_activation", extra
                        )
                        self.patch.start()

                def __exit__(self, exc_type, exc, tb):
                    if hasattr(self, "patch"):
                        self.patch.stop()

            with Prepare(), open(fle.name) as realfile:
                args_dict = {"photons_app": {"config": realfile}}

                app = App()
                logging_handler = mock.Mock(name="logging_handler")
                collector = app.setup_collector(args_dict, logging_handler, None)
                return Meta({"collector": collector}, [])

    it "can have default":
        for val in ("", None, sb.NotSpecified):
            result = self.spec.normalise(self.meta(), val)
            self.assertEqual(result, (sb.NotSpecified, "list_tasks"))

    it "can treat task as just a task":
        result = self.spec.normalise(self.meta(), "things")
        self.assertEqual(result, (sb.NotSpecified, "things"))

    it "can split by last :":
        result = self.spec.normalise(self.meta(), "one:two:three")
        self.assertEqual(result, ("one:two", "three"))

        result = self.spec.normalise(self.meta(), "one:three")
        self.assertEqual(result, ("one", "three"))

    describe "taking in an iterable":

        it "can take a two item":
            result = self.spec.normalise(self.meta(), ("one", "three"))
            self.assertEqual(result, ("one", "three"))

            result = self.spec.normalise(self.meta(), ["one", "three"])
            self.assertEqual(result, ("one", "three"))

        it "complains about non two item":
            invalids = [(), ("adsf",), ("adsf", "afd", "df"), (1,), (1, 2, 3)]
            for invalid in invalids:
                with self.fuzzyAssertRaisesError(
                    BadSpecValue, "Expected tuple to be of a particular length"
                ):
                    self.spec.normalise(self.meta(), invalid)

        it "allows not specified for target":
            result = self.spec.normalise(self.meta(), (sb.NotSpecified, "amaze"))
            self.assertEqual(result, (sb.NotSpecified, "amaze"))

        it "complains about a two item tuple with bad types":
            invalids = [(None, None), ("asdf", sb.NotSpecified), (1, 2), ([], []), ({}, {})]
            for invalid in invalids:
                with self.fuzzyAssertRaisesError(BadSpecValue, "Value failed some specifications"):
                    self.spec.normalise(self.meta(), invalid)

    describe "overriding a target":
        it "complains if the target being overridden doesn't exist":
            with self.fuzzyAssertRaisesError(TargetNotFound, name="wat", available=[]):
                self.spec.normalise(self.meta(), "wat():meh")

            config = """
            targets:
              wat:
                type: lan
                optional: true
            """

            with self.fuzzyAssertRaisesError(TargetNotFound, name="wat", available=[]):
                self.spec.normalise(self.meta(config), "wat():meh")

            config = """
            photons_app:
              addons:
                lifx.photons:
                  - transport
            """

            with self.fuzzyAssertRaisesError(TargetNotFound, name="wat"):
                self.spec.normalise(self.meta(config), "wat():meh")

        it "complains if we don't can't parse tokens":
            token_errors = ["wat(", "wat({)", "("]
            for specifier in token_errors:
                with self.fuzzyAssertRaisesError(BadSpecValue, "Failed to parse specifier"):
                    self.spec.normalise(self.meta(), f"{specifier}:meh")

        it "complains if we have invalid syntax":
            config = """
            photons_app:
              addons:
                lifx.photons:
                  - transport
            """

            syntax_errors = ["lan('a'=_)", "lan(=a)", "lan(10='a')"]
            for specifier in syntax_errors:
                with self.fuzzyAssertRaisesError(
                    BadSpecValue, "Target options must be valid dictionary syntax"
                ):
                    self.spec.normalise(self.meta(config), f"{specifier}:meh")

        it "complains about keyword arguments that aren't literals":
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
                with self.fuzzyAssertRaisesError(
                    BadSpecValue, "target options can only be python literals.+"
                ):
                    self.spec.normalise(self.meta(config), f"{specifier}:meh")

        it "can override properties on a target":
            config = """
            photons_app:
              addons:
                lifx.photons:
                  - transport
            """

            meta = self.meta(config)

            target_register = meta.everything["collector"].configuration["target_register"]
            original = list(target_register.targets)
            assert "lan" in original, original

            result = self.spec.normalise(meta, "lan(default_broadcast='9.8.7.6'):amazing_task")
            self.assertEqual(len(target_register.targets), len(original) + 1)

            self.assertEqual(result, (mock.ANY, "amazing_task"))
            assert result[0].startswith("lan_"), result[0]
            self.assertEqual(len(result[0]), 4 + 32)

            target = target_register.resolve(result[0])
            self.assertIsInstance(target, LanTarget)
            self.assertEqual(target.default_broadcast, "9.8.7.6")

            lan = target_register.resolve("lan")
            self.assertIsInstance(lan, LanTarget)
            self.assertEqual(lan.default_broadcast, "255.255.255.255")

        it "can override properties with another target":

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

            original = list(target_register.targets)
            assert "con" in original, original

            result = self.spec.normalise(meta, "con(network='{targets.lan2}'):amazing_task")
            self.assertEqual(len(target_register.targets), len(original) + 1)

            self.assertEqual(result, (mock.ANY, "amazing_task"))
            assert result[0].startswith("con_"), result[0]
            self.assertEqual(len(result[0]), 4 + 32)

            target = target_register.resolve(result[0])
            self.assertIsInstance(target, Container)
            self.assertIs(target.network, target_register.resolve("lan2"))

            con = target_register.resolve("con")
            self.assertIsInstance(con, Container)
            self.assertIs(con.network, target_register.resolve("lan"))
