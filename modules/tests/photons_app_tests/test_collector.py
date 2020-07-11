# coding: spec

from photons_app.registers import Target, TargetRegister, ProtocolRegister, ReferenceResolerRegister
from photons_app.option_spec.photons_app_spec import PhotonsApp
from photons_app.errors import BadYaml, BadConfiguration
from photons_app.collector import Collector
from photons_app import helpers as hp

from delfick_project.norms import dictobj, sb, BadSpecValue
from delfick_project.errors_pytest import assertRaises
from delfick_project.option_merge import MergedOptions
from delfick_project.option_merge.path import Path
from delfick_project.addons import Register
from contextlib import contextmanager
from textwrap import dedent
from unittest import mock
import asyncio
import pytest
import uuid
import os


describe "Collector":

    it "has a shortcut to the photons_app":
        collector = Collector()
        collector.prepare(None, {})
        assert collector.photons_app is collector.configuration["photons_app"]

    it "has a shortcut to resolve a target":
        collector = Collector()
        collector.prepare(None, {}, extra_files=[{"targets": {"lan": {"type": "lan"}}}])

        class Target(dictobj.Spec):
            pass

        collector.configuration["target_register"].register_type("lan", Target.FieldSpec())
        collector.configuration["target_register"].add_targets(collector.configuration["targets"])

        lan = collector.configuration["target_register"].resolve("lan")
        assert collector.resolve_target("lan") is lan

    it "has a shortcut to the run helper":
        coro = mock.Mock(name="coro")
        run = mock.Mock(name="run")
        collector = Collector()
        collector.prepare(None, {})

        photons_app = collector.photons_app
        target_register = collector.configuration["target_register"]

        with mock.patch("photons_app.collector.run", run):
            collector.run_coro_as_main(coro)

        run.assert_called_once_with(coro, photons_app, target_register)

    it "can be cloned":
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

    describe "extra_prepare":

        @contextmanager
        def mocks(self, collector, configuration, args_dict, photons_app, register):
            __main__ = mock.Mock(name="__main__")
            find_photons_app_options = mock.Mock(
                name="find_photons_app_options", return_value=photons_app
            )
            determine_mainline_module = mock.Mock(
                name="determine_mainline_module", return_value=__main__
            )
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

        it "puts things into the configuration and sets up the addon register":
            extra = str(uuid.uuid1())
            photons_app = {"extra": extra}
            configuration = MergedOptions()
            collector = Collector()
            register = mock.Mock(name="register")
            args_dict = mock.Mock(name="args_dict")

            with self.mocks(collector, configuration, args_dict, photons_app, register):
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

    describe "find_photons_app_options":
        it "returns us a dictionary with options from configuration and args_dict":
            configuration = MergedOptions.using({"photons_app": {"one": 1, "two": 2}})
            args_dict = {"photons_app": {"one": 3, "three": 4}}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            assert photons_app == {"one": 3, "two": 2, "three": 4}

        it "doesn't care if configuration has no photons_app":
            configuration = MergedOptions()
            args_dict = {"photons_app": {"one": 3, "three": 4}}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            assert photons_app == {"one": 3, "three": 4}

            for v in (None, "", sb.NotSpecified):
                configuration = MergedOptions.using({"photons_app": v})
                photons_app = Collector().find_photons_app_options(configuration, args_dict)
                assert photons_app == {"one": 3, "three": 4}

        it "doesn't care if args_dict has no photons_app":
            configuration = MergedOptions.using({"photons_app": {"one": 1}})
            args_dict = {}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            assert photons_app == {"one": 1}

            for v in (None, "", sb.NotSpecified):
                args_dict["photons_app"] = v
                photons_app = Collector().find_photons_app_options(configuration, args_dict)
                assert photons_app == {"one": 1}

    describe "determine_mainline_module":
        it "does nothing if there is no __main__":
            fake__import__ = mock.Mock(name="__import__", side_effect=ImportError)
            working_set = mock.Mock(name="working_set", spec=[])
            with mock.patch("pkg_resources.working_set", working_set):
                with mock.patch("builtins.__import__", fake__import__):
                    assert Collector().determine_mainline_module() is None

            fake__import__.assert_called_once_with("__main__")

        it "adds an entrypoint to the working_set if we have __main__":
            __main__ = mock.Mock(name="__main__")
            fake__import__ = mock.Mock(name="__import__", return_value=__main__)
            working_set = mock.Mock(name="working_set")
            with mock.patch("pkg_resources.working_set", working_set):
                with mock.patch("builtins.__import__", fake__import__):
                    assert Collector().determine_mainline_module() is __main__

            fake__import__.assert_called_once_with("__main__")

            assert len(working_set.add.mock_calls) == 1
            call = working_set.add.mock_calls[0].call_list()[0][1]
            dist = call[0]
            working_set.add.assert_called_once_with(dist, entry="__main__")

            em = dist.get_entry_map("lifx.photons")
            assert em["__main__"].name == "__main__"
            assert em["__main__"].module_name == "__main__"

            assert dist.get_entry_map("other") == {}
            assert dist.get_entry_map() == {}

    describe "setup_addon_register":
        it "works":
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

        it "adds pair for __main__ if that's a thing":
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

        it "adds nothing if photons_app has no addons option":
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

    describe "extra_prepare_after_activation":
        it "calls post_register":
            register = mock.Mock(name="register")
            collector = Collector()
            collector.register = register

            final_future = hp.create_future()
            photons_app = mock.Mock(name="photons_app", final_future=final_future)

            configuration = {"photons_app": photons_app}
            args_dict = mock.Mock(name="args_dict")

            collector.extra_prepare_after_activation(configuration, args_dict)
            assert configuration["final_future"] is final_future

            register.post_register.assert_called_once_with({"lifx.photons": {}})

        it "creates and sets up a task finder":
            final_future = hp.create_future()
            photons_app = mock.Mock(name="photons_app", final_future=final_future)

            configuration = {"photons_app": photons_app}
            args_dict = mock.Mock(name="args_dict")

            collector = Collector()
            collector.register = mock.Mock(name="register")

            task_finder = mock.Mock(name="task_finder")
            FakeTaskFinder = mock.Mock(name="TaskFinder", return_value=task_finder)

            with mock.patch("photons_app.collector.TaskFinder", FakeTaskFinder):
                collector.extra_prepare_after_activation(configuration, args_dict)

            assert configuration["task_runner"] is task_finder.task_runner
            collector.register.post_register.assert_called_once_with(mock.ANY)

    describe "home_dir_configuration_location":
        it "returns location to a .photons_apprc.yml":
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

    describe "start_configuration":
        it "returns MergedOptions that doesn't prefix dictobj objects":

            class D(dictobj):
                fields = ["one"]

            d = D(one=D(1))
            configuration = Collector().start_configuration()
            assert type(configuration) == MergedOptions

            configuration["thing"] = d
            assert configuration["thing"] is d

    describe "read_file":
        it "reads it as yaml":
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

        it "complains if it's not valid yaml":
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

    describe "add_configuration":
        it "removes config_root from result if we already have that in the configuration":
            config_root = str(uuid.uuid1())
            configuration = MergedOptions.using({"config_root": config_root})
            result = {"config_root": str(uuid.uuid1()), "one": 1}
            done = {}
            src = str(uuid.uuid1())

            collect_another_source = mock.NonCallableMock(name="collect_another_source")
            Collector().add_configuration(configuration, collect_another_source, done, result, src)

            assert configuration.storage.data[0] == (Path(""), {"one": 1}, src)

            assert configuration["config_root"] == config_root

        it "removes config_root if it's the home dir configuration":
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

        it "sets the source in terms of the config_root":
            src_item = str(uuid.uuid1())
            src = "/one/two/{0}".format(src_item)
            configuration = MergedOptions.using({"config_root": "/one/two"})

            result = {"one": 1}

            done = {}
            expected_src = "{config_root}/" + src_item

            collect_another_source = mock.NonCallableMock(name="collect_another_source")
            Collector().add_configuration(configuration, collect_another_source, done, result, src)

            assert configuration.storage.data[0] == (Path(""), {"one": 1}, expected_src)

        it "collects other sources after adding the current result":
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

        it "complains if an extra source doesn't exist":
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

        it "can do extra files before and after current configuration", a_temp_dir:
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

        it "complains if a filename is not a file", a_temp_dir:
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

    describe "extra_configuration_collection":
        it "registers converters for serveral things":
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

            assert type(photons_app) == PhotonsApp

            assert list(targets.keys()) == ["one"]
            assert type(targets["one"]) == Target
            assert targets["one"].as_dict() == {
                "type": "special",
                "optional": False,
                "options": {1: 2},
            }

            assert type(target_register) == TargetRegister
            assert type(protocol_register) == ProtocolRegister
            assert type(reference_resolver_register) == ReferenceResolerRegister

    describe "stop_photons_app":
        async it "cleans up photons":
            collector = Collector()
            collector.prepare(None, {})

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

        async it "cleans up targets":
            collector = Collector()
            collector.prepare(
                None, {}, extra_files=[{"photons_app": {"addons": {"lifx.photons": ["transport"]}}}]
            )
            collector.configuration["target_register"].add_targets(
                collector.configuration["targets"]
            )
            target = collector.resolve_target("lan")

            finish = pytest.helpers.AsyncMock(name="finish")

            with mock.patch.object(target, "finish", finish, create=True):
                await collector.stop_photons_app()

            finish.assert_called_once_with()
