
from textwrap import dedent
from unittest import mock

import alt_pytest_asyncio
import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue, Meta, dictobj, sb
from photons_app import helpers as hp
from photons_app.collector import Collector
from photons_app.errors import TargetNotFound
from photons_app.executor import App
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.tasks.specifier import task_specifier_spec
from photons_transport.targets import LanTarget
from photons_transport.targets.base import Target

class TestTaskSpecifierSpec:

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

            with alt_pytest_asyncio.Loop(new_loop=False), Prepare(), open(fle.name) as realfile:
                args_dict = {"photons_app": {"config": realfile}}

                app = App()
                logging_handler = mock.Mock(name="logging_handler")
                collector = app.setup_collector(args_dict, logging_handler, None)
                return Meta({"collector": collector}, [])

    def test_it_can_have_default(self, spec):
        for val in ("", None, sb.NotSpecified):
            result = spec.normalise(self.meta(), val)
            assert result == (sb.NotSpecified, "list_tasks")

    def test_it_can_treat_task_as_just_a_task(self, spec):
        result = spec.normalise(self.meta(), "things")
        assert result == (sb.NotSpecified, "things")

    def test_it_can_split_by_last(self, spec):
        result = spec.normalise(self.meta(), "one:two:three")
        assert result == ("one:two", "three")

        result = spec.normalise(self.meta(), "one:three")
        assert result == ("one", "three")

    class TestTakingInAnIterable:

        def test_it_can_take_a_two_item(self, spec):
            result = spec.normalise(self.meta(), ("one", "three"))
            assert result == ("one", "three")

            result = spec.normalise(self.meta(), ["one", "three"])
            assert result == ("one", "three")

        def test_it_complains_about_non_two_item(self, spec):
            invalids = [(), ("adsf",), ("adsf", "afd", "df"), (1,), (1, 2, 3)]
            for invalid in invalids:
                with assertRaises(BadSpecValue, "Expected tuple to be of a particular length"):
                    spec.normalise(self.meta(), invalid)

        def test_it_allows_not_specified_for_target(self, spec):
            result = spec.normalise(self.meta(), (sb.NotSpecified, "amaze"))
            assert result == (sb.NotSpecified, "amaze")

        def test_it_complains_about_a_two_item_tuple_with_bad_types(self, spec):
            invalids = [(None, None), ("asdf", sb.NotSpecified), (1, 2), ([], []), ({}, {})]
            for invalid in invalids:
                with assertRaises(BadSpecValue, "Value failed some specifications"):
                    spec.normalise(self.meta(), invalid)

    class TestOverridingATarget:
        def test_it_complains_if_the_target_being_overridden_doesnt_exist(self, spec):
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

        def test_it_complains_if_we_dont_cant_parse_tokens(self, spec):
            token_errors = ["wat(", "wat({)", "("]
            for specifier in token_errors:
                with assertRaises(BadSpecValue, "Failed to parse specifier"):
                    spec.normalise(self.meta(), f"{specifier}:meh")

        def test_it_complains_if_we_have_invalid_syntax(self, spec):
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

        def test_it_complains_about_keyword_arguments_that_arent_literals(self, spec):
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

        def test_it_can_override_properties_on_a_target(self, spec):
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

        def test_it_can_override_properties_with_another_target(self, spec):

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
