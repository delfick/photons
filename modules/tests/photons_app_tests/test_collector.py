import asyncio
import os
import sys
import uuid
from contextlib import contextmanager
from textwrap import dedent
from unittest import mock

import alt_pytest_asyncio
import pytest
from backports.entry_points_selectable import entry_points
from delfick_project.addons import Register
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue, dictobj, sb
from delfick_project.option_merge import MergedOptions
from delfick_project.option_merge.path import Path
from photons_app import helpers as hp
from photons_app.collector import Collector
from photons_app.errors import BadConfiguration, BadYaml, TargetNotFound
from photons_app.photons_app import PhotonsApp
from photons_app.registers import (
    ProtocolRegister,
    ReferenceResolverRegister,
    Target,
    TargetRegister,
)


@contextmanager
def mocks(collector, configuration, args_dict, photons_app, register):
    __main__ = mock.Mock(name="__main__")
    find_photons_app_options = mock.Mock(name="find_photons_app_options", return_value=photons_app)
    determine_mainline_module = mock.Mock(name="determine_mainline_module", return_value=__main__)
    setup_addon_register = mock.Mock(name="setup_addon_register", return_value=register)

    with mock.patch.multiple(
        collector,
        find_photons_app_options=find_photons_app_options,
        determine_mainline_module=determine_mainline_module,
        setup_addon_register=setup_addon_register,
    ):
        yield __main__

    find_photons_app_options.assert_called_once_with(configuration, args_dict)
    determine_mainline_module.assert_called_once_with()
    setup_addon_register.assert_called_once_with(photons_app, __main__)


class TestCollector:

    @pytest.fixture()
    def collector(self):
        with alt_pytest_asyncio.Loop(new_loop=False):
            collector = Collector()
            collector.prepare(None, {})
            yield collector

    def test_it_has_a_shortcut_to_the_photons_app(self, collector):
        assert collector.photons_app is collector.configuration["photons_app"]

    def test_it_has_a_shortcut_to_resolve_a_target(self):

        class Target(dictobj.Spec):
            pass

        class C(Collector):
            def add_targets(s, target_register, targets):
                target_register.register_type("lan", Target.FieldSpec())
                super().add_targets(target_register, targets)

        with alt_pytest_asyncio.Loop(new_loop=False):
            collector = C()
            collector.prepare(None, {}, extra_files=[{"targets": {"lan": {"type": "lan"}}}])

            lan = collector.configuration["target_register"].resolve("lan")
            assert collector.resolve_target("lan") is lan

    def test_it_has_a_shortcut_to_the_run_helper(self, collector):
        coro = mock.Mock(name="coro")
        run = mock.Mock(name="run", spec=[])
        Run = mock.Mock(name="Run", return_value=mock.Mock("RunInstance", run=run))
        Runner = mock.Mock(name="Runner", Run=Run, spec=["Run"])

        photons_app = collector.photons_app
        target_register = collector.configuration["target_register"]

        with mock.patch("photons_app.collector.Runner", Runner):
            collector.run_coro_as_main(coro)

        Run.assert_called_once_with(coro, photons_app, target_register)
        run.assert_called_once_with()

    def test_it_can_be_cloned(self):
        with alt_pytest_asyncio.Loop(new_loop=False):
            collector = Collector()

            prepare = mock.Mock(name="prepare")
            with hp.a_temp_file() as fle:
                fle.write(
                    dedent(
                        """
                ---

                photons_app:
                   artifact: "blah"
                   ignored: "an option"

                """
                    ).encode()
                )
                fle.close()
                collector.prepare(fle.name, {"one": 2})

                with mock.patch.object(Collector, "prepare", prepare):
                    clone = collector.clone({"two": 3})

                clone2 = collector.clone()

            assert clone is not collector

            call = prepare.mock_calls[0].call_list()[0][1]
            assert call[0] == fle.name
            assert call[1].storage.data == [
                (Path(""), {"two": 3}, None),
                (Path(""), {"photons_app": collector.photons_app.as_dict()}, None),
                (Path(""), {"one": 2}, None),
            ]

            assert clone2.configuration["photons_app"].artifact == "blah"
            assert clone2.configuration["photons_app"] is not collector.photons_app

    class TestExtraPrepare:

        def test_it_puts_things_into_the_configuration_and_sets_up_the_addon_register(self):
            extra = str(uuid.uuid1())
            photons_app = {"extra": extra}
            configuration = MergedOptions()
            collector = Collector()
            register = mock.Mock(name="register")
            args_dict = mock.Mock(name="args_dict")

            with mocks(collector, configuration, args_dict, photons_app, register):
                collector.extra_prepare(configuration, args_dict)

            class AFuture:
                def __eq__(s, other):
                    return isinstance(other, asyncio.Future)

            assert collector.register is register
            assert configuration.as_dict() == {
                "$@": extra,
                "collector": collector,
                "photons_app": photons_app,
            }

    class TestFindPhotonsAppOptions:
        def test_it_returns_us_a_dictionary_with_options_from_configuration_and_args_dict(self):
            configuration = MergedOptions.using({"photons_app": {"one": 1, "two": 2}})
            args_dict = {"photons_app": {"one": 3, "three": 4}}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            assert photons_app == {"one": 3, "two": 2, "three": 4}

        def test_it_doesnt_care_if_configuration_has_no_photons_app(self):
            configuration = MergedOptions()
            args_dict = {"photons_app": {"one": 3, "three": 4}}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            assert photons_app == {"one": 3, "three": 4}

            for v in (None, "", sb.NotSpecified):
                configuration = MergedOptions.using({"photons_app": v})
                photons_app = Collector().find_photons_app_options(configuration, args_dict)
                assert photons_app == {"one": 3, "three": 4}

        def test_it_doesnt_care_if_args_dict_has_no_photons_app(self):
            configuration = MergedOptions.using({"photons_app": {"one": 1}})
            args_dict = {}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            assert photons_app == {"one": 1}

            for v in (None, "", sb.NotSpecified):
                args_dict["photons_app"] = v
                photons_app = Collector().find_photons_app_options(configuration, args_dict)
                assert photons_app == {"one": 1}

    class TestDetermineMainlineModule:
        def test_it_does_nothing_if_there_is_no_main(self):
            fake__import__ = mock.Mock(name="__import__", side_effect=ImportError)

            assert not any(ep.name == "__main__" for ep in entry_points(group="lifx.photons"))

            with mock.patch("sys.meta_path", list(sys.meta_path)):
                with mock.patch("builtins.__import__", fake__import__):
                    assert Collector().determine_mainline_module() is None

            fake__import__.assert_called_once_with("__main__")
            assert not any(ep.name == "__main__" for ep in entry_points(group="lifx.photons"))

        def test_it_adds_an_entrypoint_if_we_have_main(self):
            __main__ = mock.Mock(name="__main__")
            fake__import__ = mock.Mock(name="__import__", return_value=__main__)

            assert not any(ep.name == "__main__" for ep in entry_points(group="lifx.photons"))

            with mock.patch("sys.meta_path", list(sys.meta_path)):
                with mock.patch("builtins.__import__", fake__import__):
                    assert Collector().determine_mainline_module() is __main__
                assert any(ep.name == "__main__" for ep in entry_points(group="lifx.photons"))
                assert entry_points(group="lifx.photons")["__main__"].load() is __main__

            assert not any(ep.name == "__main__" for ep in entry_points(group="lifx.photons"))
            fake__import__.assert_called_once_with("__main__")

    class TestSetupAddonRegister:
        def test_it_works(self):
            original = Register
            info = {}
            called = []

            def R(*args):
                register = info["register"] = original(*args)
                return register

            FakeRegister = mock.Mock(name="Register", side_effect=R)

            def rik(*args):
                register = info["register"]
                assert sorted(register.addon_getter.namespaces.keys()) == sorted(
                    ["delfick_project.addons", "lifx.photons"]
                )
                assert register.known == [("lifx.photons", "one"), ("lifx.photons", "two")]
                called.append("recursive_import_known")

            recursive_import_known = mock.Mock(name="recursive_import_known", side_effect=rik)

            def rri():
                called.append("recursive_resolve_imported")

            recursive_resolve_imported = mock.Mock(
                name="recursive_resolve_imported", side_effect=rri
            )

            with mock.patch("photons_app.collector.Register", FakeRegister):
                with mock.patch.multiple(
                    Register,
                    recursive_import_known=recursive_import_known,
                    recursive_resolve_imported=recursive_resolve_imported,
                ):
                    Collector().setup_addon_register(
                        {"addons": {"lifx.photons": ["one", "two"]}}, None
                    )

            recursive_import_known.assert_called_once_with()
            recursive_resolve_imported.assert_called_once_with()
            assert called == ["recursive_import_known", "recursive_resolve_imported"]

        def test_it_adds_pair_for_main_if_thats_a_thing(self):
            original = Register
            info = {}
            called = []

            def R(*args):
                register = info["register"] = original(*args)
                return register

            FakeRegister = mock.Mock(name="Register", side_effect=R)

            def rik(*args):
                register = info["register"]
                assert sorted(register.addon_getter.namespaces.keys()) == sorted(
                    ["delfick_project.addons", "lifx.photons"]
                )
                assert register.known == [
                    ("lifx.photons", "one"),
                    ("lifx.photons", "two"),
                    ("lifx.photons", "__main__"),
                ]
                called.append("recursive_import_known")

            recursive_import_known = mock.Mock(name="recursive_import_known", side_effect=rik)

            def rri():
                called.append("recursive_resolve_imported")

            recursive_resolve_imported = mock.Mock(
                name="recursive_resolve_imported", side_effect=rri
            )

            with mock.patch("photons_app.collector.Register", FakeRegister):
                with mock.patch.multiple(
                    Register,
                    recursive_import_known=recursive_import_known,
                    recursive_resolve_imported=recursive_resolve_imported,
                ):
                    Collector().setup_addon_register(
                        {"addons": {"lifx.photons": ["one", "two"]}}, True
                    )

            recursive_import_known.assert_called_once_with()
            recursive_resolve_imported.assert_called_once_with()
            assert called == ["recursive_import_known", "recursive_resolve_imported"]

        def test_it_adds_nothing_if_photons_app_has_no_addons_option(self):
            original = Register
            info = {}
            called = []

            def R(*args):
                register = info["register"] = original(*args)
                return register

            FakeRegister = mock.Mock(name="Register", side_effect=R)

            def rik(*args):
                register = info["register"]
                assert sorted(register.addon_getter.namespaces.keys()) == sorted(
                    ["delfick_project.addons", "lifx.photons"]
                )
                assert register.known == []
                called.append("recursive_import_known")

            recursive_import_known = mock.Mock(name="recursive_import_known", side_effect=rik)

            def rri():
                called.append("recursive_resolve_imported")

            recursive_resolve_imported = mock.Mock(
                name="recursive_resolve_imported", side_effect=rri
            )

            with mock.patch("photons_app.collector.Register", FakeRegister):
                with mock.patch.multiple(
                    Register,
                    recursive_import_known=recursive_import_known,
                    recursive_resolve_imported=recursive_resolve_imported,
                ):
                    Collector().setup_addon_register({}, None)

            recursive_import_known.assert_called_once_with()
            recursive_resolve_imported.assert_called_once_with()
            assert called == ["recursive_import_known", "recursive_resolve_imported"]

    class TestExtraPrepareAfterActivation:
        def test_it_calls_post_register(self):
            register = mock.Mock(name="register")
            collector = Collector()
            collector.register = register

            final_future = hp.create_future()
            photons_app = mock.Mock(name="photons_app", final_future=final_future)

            configuration = MergedOptions.using({"photons_app": photons_app}, dont_prefix=[dictobj])
            args_dict = mock.Mock(name="args_dict")

            # Necessary setup for extra_prepare_after_activation
            collector.extra_configuration_collection(configuration)
            collector.register_converters(
                {
                    "photons_app": sb.any_spec(),
                },
                configuration=configuration,
            )
            configuration.converters._converters.insert(
                0, configuration.converters._converters.pop()
            )
            configuration.converters.activate()

            collector.extra_prepare_after_activation(configuration, args_dict)
            assert configuration["final_future"] is final_future

            register.post_register.assert_called_once_with({"lifx.photons": {}})

        def test_it_creates_and_sets_up_a_task_finder(self):
            final_future = hp.create_future()
            photons_app = mock.Mock(name="photons_app", final_future=final_future)

            configuration = MergedOptions.using({"photons_app": photons_app}, dont_prefix=[dictobj])
            args_dict = mock.Mock(name="args_dict")

            collector = Collector()
            collector.register = mock.Mock(name="register")

            # Necessary setup for extra_prepare_after_activation
            collector.extra_configuration_collection(configuration)
            collector.register_converters(
                {
                    "photons_app": sb.any_spec(),
                },
                configuration=configuration,
            )
            configuration.converters._converters.insert(
                0, configuration.converters._converters.pop()
            )
            configuration.converters.activate()

            collector.extra_prepare_after_activation(configuration, args_dict)
            collector.register.post_register.assert_called_once_with(mock.ANY)

        def test_it_sets_up_targets(self):
            final_future = hp.create_future()
            photons_app = mock.Mock(name="photons_app", final_future=final_future)

            configuration = MergedOptions.using(
                {"photons_app": photons_app, "targets": {"l": {"type": "joke", "options": {}}}},
                dont_prefix=[dictobj],
            )
            args_dict = mock.Mock(name="args_dict")

            collector = Collector()
            collector.register = mock.Mock(name="register")

            # Necessary setup for extra_prepare_after_activation
            collector.extra_configuration_collection(configuration)
            collector.register_converters(
                {
                    "photons_app": sb.any_spec(),
                },
                configuration=configuration,
            )
            configuration.converters._converters.insert(
                0, configuration.converters._converters.pop()
            )
            configuration.converters.activate()

            add_targets = mock.Mock(name="add_targets")
            with mock.patch.object(collector, "add_targets", add_targets):
                collector.extra_prepare_after_activation(configuration, args_dict)

            collector.configuration = configuration

            add_targets.assert_called_once_with(
                configuration["target_register"], configuration["targets"]
            )

            target_register = configuration["target_register"]
            with assertRaises(TargetNotFound):
                target_register.resolve("l")

            class Target(dictobj.Spec):
                pass

            target_register.register_type("joke", Target.FieldSpec())
            collector.add_targets(target_register, configuration["targets"])
            assert isinstance(target_register.resolve("l"), Target)

    class TestHomeDirConfigurationLocation:
        def test_it_returns_location_to_a_photons_apprcyml(self):
            have_current_home = "HOME" in os.environ
            current_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = "/home/bob"
                assert (
                    Collector().home_dir_configuration_location() == "/home/bob/.photons_apprc.yml"
                )
            finally:
                if have_current_home:
                    os.environ["HOME"] = current_home
                elif "HOME" in os.environ:
                    del os.environ["HOME"]

    class TestStartConfiguration:
        def test_it_returns_MergedOptions_that_doesnt_prefix_dictobj_objects(self):

            class D(dictobj):
                fields = ["one"]

            d = D(one=D(1))
            configuration = Collector().start_configuration()
            assert type(configuration) is MergedOptions

            configuration["thing"] = d
            assert configuration["thing"] is d

    class TestReadFile:
        def test_it_reads_it_as_yaml(self):
            with hp.a_temp_file() as fle:
                fle.write(
                    dedent(
                        """
                    ---

                    one: 2

                    two:
                      three: 3
                """
                    ).encode()
                )
                fle.close()

                read = Collector().read_file(fle.name)
                assert read == {"one": 2, "two": {"three": 3}}

        def test_it_complains_if_its_not_valid_yaml(self):
            with hp.a_temp_file() as fle:
                fle.write(
                    dedent(
                        """
                    [1, 2
                """
                    ).encode()
                )
                fle.close()

                with assertRaises(BadYaml, "Failed to read yaml", location=fle.name):
                    print(Collector().read_file(fle.name))

    class TestAddConfiguration:
        def test_it_removes_config_root_from_result_if_we_already_have_that_in_the_configuration(
            self,
        ):
            config_root = str(uuid.uuid1())
            configuration = MergedOptions.using({"config_root": config_root})
            result = {"config_root": str(uuid.uuid1()), "one": 1}
            done = {}
            src = str(uuid.uuid1())

            collect_another_source = mock.NonCallableMock(name="collect_another_source")
            Collector().add_configuration(configuration, collect_another_source, done, result, src)

            assert configuration.storage.data[0] == (Path(""), {"one": 1}, src)

            assert configuration["config_root"] == config_root

        def test_it_removes_config_root_if_its_the_home_dir_configuration(self):
            home_location = "/home/bob/{0}".format(str(uuid.uuid1()))
            configuration = MergedOptions.using({"config_root": "/home/bob"})

            new_config_root = str(uuid.uuid1())
            result = {"config_root": new_config_root, "one": 1}

            done = {}
            src = str(uuid.uuid1())

            home_dir_configuration_location = mock.Mock(
                name="home_dir_configuration_location", return_value=home_location
            )
            collect_another_source = mock.NonCallableMock(name="collect_another_source")
            collector = Collector()

            with mock.patch.object(
                collector, "home_dir_configuration_location", home_dir_configuration_location
            ):
                collector.add_configuration(
                    configuration, collect_another_source, done, result, src
                )

            home_dir_configuration_location.assert_called_once_with()
            assert configuration.storage.data[0] == (
                Path(""),
                {"config_root": new_config_root, "one": 1},
                src,
            )
            assert configuration["config_root"] == new_config_root

        def test_it_sets_the_source_in_terms_of_the_config_root(self):
            src_item = str(uuid.uuid1())
            src = "/one/two/{0}".format(src_item)
            configuration = MergedOptions.using({"config_root": "/one/two"})

            result = {"one": 1}

            done = {}
            expected_src = "{config_root}/" + src_item

            collect_another_source = mock.NonCallableMock(name="collect_another_source")
            Collector().add_configuration(configuration, collect_another_source, done, result, src)

            assert configuration.storage.data[0] == (Path(""), {"one": 1}, expected_src)

        def test_it_collects_other_sources_after_adding_the_current_result(self):
            src = str(uuid.uuid1())
            one = str(uuid.uuid1())
            configuration = MergedOptions.using({"config_root": "/one/two"})

            result = {"photons_app": {"extra_files": ["{config_root}/three", "/four"]}, "one": one}

            done = {}

            expected = ["/one/two/three", "/four"]

            def cas(name):
                assert configuration["one"] == one
                assert expected.pop(0) == name

            collect_another_source = mock.Mock(name="collect_another_source", side_effect=cas)

            alwaystrue = mock.Mock(name="alwaystrue", return_value=True)

            collector = Collector()
            with mock.patch("os.path.exists", alwaystrue), mock.patch("os.path.isfile", alwaystrue):
                collector.add_configuration(
                    configuration, collect_another_source, done, result, src
                )

            assert collect_another_source.mock_calls == [
                mock.call("/one/two/three"),
                mock.call("/four"),
            ]

        def test_it_complains_if_an_extra_source_doesnt_exist(self):
            src = str(uuid.uuid1())
            one = str(uuid.uuid1())
            configuration = MergedOptions.using({"config_root": "/one/two"})

            result = {"photons_app": {"extra_files": ["{config_root}/three", "/four"]}, "one": one}

            done = {}

            collect_another_source = mock.NonCallableMock(name="collect_another_source")

            exists = mock.Mock(name="exists", return_value=False)

            with mock.patch("os.path.exists", exists):
                with assertRaises(
                    BadConfiguration,
                    "Specified extra file doesn't exist",
                    filename="/one/two/three",
                    source=src,
                ):
                    Collector().add_configuration(
                        configuration, collect_another_source, done, result, src
                    )

            exists.assert_called_once_with("/one/two/three")

        def test_it_can_do_extra_files_before_and_after_current_configuration(self, a_temp_dir):
            with a_temp_dir() as (d, make_file):

                make_file(
                    "before1.yml",
                    """
                ---

                one: 1
                two:
                  three: 3
                  first: true
                """,
                )

                make_file(
                    "before2.yml",
                    """
                ---

                one: 4
                two:
                  four: 4
                  second: true

                five:
                  six: 9
                """,
                )

                rootyml = make_file(
                    "root.yml",
                    """
                ---

                photons_app:
                  extra_files:
                    before:
                      - "{config_root}/before1.yml"
                      - filename: "{config_root}/before2.yml"
                    after:
                      - filename: "{config_root}/after1.yml"
                      - filename: "{config_root}/nonexistant.yml"
                        optional: true
                      - filename: "{config_root}/after2.yml"

                one: 9
                two:
                  tree: "tree"
                """,
                )

                make_file(
                    "after1.yml",
                    """
                ---

                two:
                  four: plane
                five:
                  eight: cloud
                """,
                )

                make_file(
                    "after2.yml",
                    """
                ---

                two:
                  four: plane
                  last: true
                five:
                  eight: evenmorecloud
                """,
                )

                with alt_pytest_asyncio.Loop(new_loop=False):
                    collector = Collector()
                    collector.prepare(rootyml, {})

                    expected = {
                        "one": 9,
                        "two": {
                            "three": 3,
                            "four": "plane",
                            "tree": "tree",
                            "first": True,
                            "second": True,
                            "last": True,
                        },
                        "config_root": d,
                        "five": {"six": 9, "eight": "evenmorecloud"},
                    }

                    dct = collector.configuration.as_dict()
                    for key, val in expected.items():
                        assert dct[key] == val

        def test_it_complains_if_a_filename_is_not_a_file(self, a_temp_dir):
            with a_temp_dir() as (d, make_file):
                d1 = os.path.join(d, "one")
                os.makedirs(d1)

                d2 = os.path.join(d, "two")
                os.makedirs(d2)

                d3 = os.path.join(d, "three")
                os.makedirs(d3)

                rootyml = make_file(
                    "root.yml",
                    """
                ---

                photons_app:
                  extra_files:
                    before:
                     - "{config_root}/one"
                    after:
                     - filename: "{config_root}/two"
                     - "{config_root}/three"
                """,
                )

                with alt_pytest_asyncio.Loop(new_loop=False):
                    collector = Collector()

                    errs = []
                    try:
                        collector.prepare(rootyml, {})
                        assert False, "Expect an error"
                    except BadSpecValue as error:
                        for err in error.errors:
                            errs.extend(err.errors)

                    paths = []

                    assert len(errs) == 3, errs
                    for err in errs:
                        assert isinstance(err, BadSpecValue)
                        assert err.message == "Got something that exists but isn't a file"
                        paths.append(err.kwargs["filename"])

                    assert sorted(paths) == sorted([d1, d2, d3])

    class TestExtraConfigurationCollection:
        def test_it_registers_converters_for_serveral_things(self):
            configuration = MergedOptions.using(
                {"targets": {"one": {"type": "special", "options": {1: 2}}}}
            )

            collector = Collector()
            configuration["collector"] = collector
            collector.extra_configuration_collection(configuration)
            configuration.converters.activate()

            photons_app = configuration["photons_app"]
            targets = configuration["targets"]
            target_register = configuration["target_register"]
            protocol_register = configuration["protocol_register"]
            reference_resolver_register = configuration["reference_resolver_register"]

            assert type(photons_app) is PhotonsApp

            assert list(targets.keys()) == ["one"]
            assert type(targets["one"]) is Target
            assert targets["one"].as_dict() == {
                "type": "special",
                "optional": False,
                "options": {1: 2},
            }

            assert type(target_register) is TargetRegister
            assert type(protocol_register) is ProtocolRegister
            assert type(reference_resolver_register) is ReferenceResolverRegister

    class TestStopPhotonsApp:
        async def test_it_cleans_up_photons(self, collector):
            cleaners = collector.photons_app.cleaners
            final_future = collector.photons_app.final_future

            called = []

            async def clean1():
                called.append("clean1")

            async def clean2():
                called.append("clean2")

            cleaners.append(clean1)
            cleaners.append(clean2)

            await collector.stop_photons_app()

            assert called == ["clean1", "clean2"]
            assert final_future.cancelled()

        async def test_it_cleans_up_targets(self):
            with alt_pytest_asyncio.Loop(new_loop=False):
                collector = Collector()
                collector.prepare(
                    None,
                    {},
                    extra_files=[{"photons_app": {"addons": {"lifx.photons": ["transport"]}}}],
                )
                target = collector.resolve_target("lan")

                finish = pytest.helpers.AsyncMock(name="finish")

                with mock.patch.object(target, "finish", finish, create=True):
                    await collector.stop_photons_app()

                finish.assert_called_once_with()
