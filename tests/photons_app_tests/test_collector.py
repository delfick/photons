# coding: spec

from photons_app.registers import Target, TargetRegister, ProtocolRegister, ReferenceResolerRegister
from photons_app.option_spec.photons_app_spec import PhotonsApp
from photons_app.errors import BadYaml, BadConfiguration
from photons_app.option_spec.task_objs import Task
from photons_app.test_helpers import TestCase
from photons_app.collector import Collector
from photons_app import helpers as hp

from delfick_project.option_merge import MergedOptions
from delfick_project.norms import dictobj, sb, Meta
from delfick_project.option_merge.path import Path
from delfick_project.addons import Register
from contextlib import contextmanager
from textwrap import dedent
from unittest import mock
import pkg_resources
import asyncio
import uuid
import os

describe TestCase, "Collector":
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

        self.assertIsNot(clone, collector)

        call = prepare.mock_calls[0].call_list()[0][1]
        self.assertEqual(call[0], fle.name)
        self.assertEqual(
            call[1].storage.data,
            [
                (Path(""), {"two": 3}, None),
                (Path(""), {"photons_app": collector.configuration["photons_app"].as_dict()}, None),
                (Path(""), {"one": 2}, None),
            ],
        )

        self.assertEqual(clone2.configuration["photons_app"].artifact, "blah")
        self.assertIsNot(
            clone2.configuration["photons_app"], collector.configuration["photons_app"]
        )

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
                def __eq__(self, other):
                    return isinstance(other, asyncio.Future)

            self.assertIs(collector.register, register)
            self.assertEqual(
                configuration.as_dict(),
                {"$@": extra, "collector": collector, "photons_app": photons_app},
            )

    describe "find_photons_app_options":
        it "returns us a dictionary with options from configuration and args_dict":
            configuration = MergedOptions.using({"photons_app": {"one": 1, "two": 2}})
            args_dict = {"photons_app": {"one": 3, "three": 4}}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            self.assertEqual(photons_app, {"one": 3, "two": 2, "three": 4})

        it "doesn't care if configuration has no photons_app":
            configuration = MergedOptions()
            args_dict = {"photons_app": {"one": 3, "three": 4}}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            self.assertEqual(photons_app, {"one": 3, "three": 4})

            for v in (None, "", sb.NotSpecified):
                configuration = MergedOptions.using({"photons_app": v})
                photons_app = Collector().find_photons_app_options(configuration, args_dict)
                self.assertEqual(photons_app, {"one": 3, "three": 4})

        it "doesn't care if args_dict has no photons_app":
            configuration = MergedOptions.using({"photons_app": {"one": 1}})
            args_dict = {}

            photons_app = Collector().find_photons_app_options(configuration, args_dict)
            self.assertEqual(photons_app, {"one": 1})

            for v in (None, "", sb.NotSpecified):
                args_dict["photons_app"] = v
                photons_app = Collector().find_photons_app_options(configuration, args_dict)
                self.assertEqual(photons_app, {"one": 1})

    describe "determine_mainline_module":
        it "does nothing if there is no __main__":
            fake__import__ = mock.Mock(name="__import__", side_effect=ImportError)
            working_set = mock.Mock(name="working_set", spec=[])
            with mock.patch("pkg_resources.working_set", working_set):
                with mock.patch("builtins.__import__", fake__import__):
                    self.assertIs(Collector().determine_mainline_module(), None)

            fake__import__.assert_called_once_with("__main__")

        it "adds an entrypoint to the working_set if we have __main__":
            __main__ = mock.Mock(name="__main__")
            fake__import__ = mock.Mock(name="__import__", return_value=__main__)
            working_set = mock.Mock(name="working_set")
            with mock.patch("pkg_resources.working_set", working_set):
                with mock.patch("builtins.__import__", fake__import__):
                    self.assertIs(Collector().determine_mainline_module(), __main__)

            fake__import__.assert_called_once_with("__main__")

            self.assertEqual(len(working_set.add.mock_calls), 1)
            call = working_set.add.mock_calls[0].call_list()[0][1]
            dist = call[0]
            working_set.add.assert_called_once_with(dist, entry="__main__")

            em = dist.get_entry_map("lifx.photons")
            self.assertEqual(em["__main__"].name, "__main__")
            self.assertEqual(em["__main__"].module_name, "__main__")

            self.assertEqual(dist.get_entry_map("other"), {})
            self.assertEqual(dist.get_entry_map(), {})

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
                self.assertEqual(
                    sorted(register.addon_getter.namespaces.keys()),
                    sorted(["delfick_project.addons", "lifx.photons"]),
                )
                self.assertEqual(register.known, [("lifx.photons", "one"), ("lifx.photons", "two")])
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
            self.assertEqual(called, ["recursive_import_known", "recursive_resolve_imported"])

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
                self.assertEqual(
                    sorted(register.addon_getter.namespaces.keys()),
                    sorted(["delfick_project.addons", "lifx.photons"]),
                )
                self.assertEqual(
                    register.known,
                    [
                        ("lifx.photons", "one"),
                        ("lifx.photons", "two"),
                        ("lifx.photons", "__main__"),
                    ],
                )
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
            self.assertEqual(called, ["recursive_import_known", "recursive_resolve_imported"])

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
                self.assertEqual(
                    sorted(register.addon_getter.namespaces.keys()),
                    sorted(["delfick_project.addons", "lifx.photons"]),
                )
                self.assertEqual(register.known, [])
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
            self.assertEqual(called, ["recursive_import_known", "recursive_resolve_imported"])

    describe "extra_prepare_after_activation":
        it "calls post_register":
            register = mock.Mock(name="register")
            collector = Collector()
            collector.register = register

            final_future = asyncio.Future()
            photons_app = mock.Mock(name="photons_app", final_future=final_future)

            configuration = {"photons_app": photons_app}
            args_dict = mock.Mock(name="args_dict")

            collector.extra_prepare_after_activation(configuration, args_dict)
            self.assertIs(configuration["final_future"], final_future)

            register.post_register.assert_called_once_with({"lifx.photons": {}})

        it "creates and sets up a task finder":
            final_future = asyncio.Future()
            photons_app = mock.Mock(name="photons_app", final_future=final_future)

            configuration = {"photons_app": photons_app}
            args_dict = mock.Mock(name="args_dict")

            collector = Collector()
            collector.register = mock.Mock(name="register")

            task_finder = mock.Mock(name="task_finder")
            FakeTaskFinder = mock.Mock(name="TaskFinder", return_value=task_finder)

            with mock.patch("photons_app.collector.TaskFinder", FakeTaskFinder):
                collector.extra_prepare_after_activation(configuration, args_dict)

            self.assertIs(configuration["task_runner"], task_finder.task_runner)
            collector.register.post_register.assert_called_once_with(mock.ANY)

    describe "home_dir_configuration_location":
        it "returns location to a .photons_apprc.yml":
            have_current_home = "HOME" in os.environ
            current_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = "/home/bob"
                self.assertEqual(
                    Collector().home_dir_configuration_location(), "/home/bob/.photons_apprc.yml"
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
            self.assertEqual(type(configuration), MergedOptions)

            configuration["thing"] = d
            self.assertIs(configuration["thing"], d)

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
                self.assertEqual(read, {"one": 2, "two": {"three": 3}})

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

                with self.fuzzyAssertRaisesError(BadYaml, "Failed to read yaml", location=fle.name):
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

            self.assertEqual(configuration.storage.data[0], (Path(""), {"one": 1}, src))

            self.assertEqual(configuration["config_root"], config_root)

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
            self.assertEqual(
                configuration.storage.data[0],
                (Path(""), {"config_root": new_config_root, "one": 1}, src),
            )
            self.assertEqual(configuration["config_root"], new_config_root)

        it "sets the source in terms of the config_root":
            src_item = str(uuid.uuid1())
            src = "/one/two/{0}".format(src_item)
            configuration = MergedOptions.using({"config_root": "/one/two"})

            result = {"one": 1}

            done = {}
            expected_src = "{config_root}/" + src_item

            collect_another_source = mock.NonCallableMock(name="collect_another_source")
            Collector().add_configuration(configuration, collect_another_source, done, result, src)

            self.assertEqual(configuration.storage.data[0], (Path(""), {"one": 1}, expected_src))

        it "collects other sources after adding the current result":
            src = str(uuid.uuid1())
            one = str(uuid.uuid1())
            configuration = MergedOptions.using({"config_root": "/one/two"})

            result = {"photons_app": {"extra_files": ["{config_root}/three", "/four"]}, "one": one}

            done = {}

            expected = ["/one/two/three", "/four"]

            def cas(name):
                self.assertEqual(configuration["one"], one)
                self.assertEqual(expected.pop(0), name)

            collect_another_source = mock.Mock(name="collect_another_source", side_effect=cas)

            exists = mock.Mock(name="exists", return_value=True)

            with mock.patch("os.path.exists", exists):
                Collector().add_configuration(
                    configuration, collect_another_source, done, result, src
                )

            self.assertEqual(
                collect_another_source.mock_calls, [mock.call("/one/two/three"), mock.call("/four")]
            )

        it "complains if an extra source doesn't exist":
            src = str(uuid.uuid1())
            one = str(uuid.uuid1())
            configuration = MergedOptions.using({"config_root": "/one/two"})

            result = {"photons_app": {"extra_files": ["{config_root}/three", "/four"]}, "one": one}

            done = {}

            collect_another_source = mock.NonCallableMock(name="collect_another_source")

            exists = mock.Mock(name="exists", return_value=False)

            with mock.patch("os.path.exists", exists):
                with self.fuzzyAssertRaisesError(
                    BadConfiguration,
                    "Specified extra file doesn't exist",
                    extra="/one/two/three",
                    source=src,
                ):
                    Collector().add_configuration(
                        configuration, collect_another_source, done, result, src
                    )

            exists.assert_called_once_with("/one/two/three")

    describe "extra_configuration_collection":
        it "registers converters for serveral things":
            f = asyncio.Future()
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

            self.assertEqual(type(photons_app), PhotonsApp)

            self.assertEqual(list(targets.keys()), ["one"])
            self.assertEqual(type(targets["one"]), Target)
            self.assertEqual(
                targets["one"].as_dict(), {"type": "special", "optional": False, "options": {1: 2}}
            )

            self.assertEqual(type(target_register), TargetRegister)
            self.assertEqual(type(protocol_register), ProtocolRegister)
            self.assertEqual(type(reference_resolver_register), ReferenceResolerRegister)
