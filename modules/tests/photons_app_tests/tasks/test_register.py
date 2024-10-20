# coding: spec

from unittest import mock

import alt_pytest_asyncio
import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import dictobj, sb
from photons_app.collector import Collector
from photons_app.errors import BadOption, BadTarget, BadTask
from photons_app.registers import Target
from photons_app.special import FoundSerials
from photons_app.tasks import register as specs
from photons_app.tasks.register import RegisteredTask, TaskRegister


@pytest.fixture()
def register():
    return TaskRegister()


describe "TaskRegister":
    it "can register tasks", register:
        assert register.registered == []

        t1 = type("Tasky", (), {})
        t2 = type("BetterTask", (), {})
        t3 = type("BestTask", (), {})

        register(t1, name="bob", task_group="one")
        register(t2)
        register(t3, task_group="two")

        assert register.registered == [
            RegisteredTask("BestTask", t3, "two"),
            RegisteredTask("BetterTask", t2, "Project"),
            RegisteredTask("bob", t1, "one"),
        ]

    it "can get names from registered tasks", register:
        t1 = type("Tasky", (), {})
        t2 = type("BetterTask", (), {})
        t3 = type("BestTask", (), {})
        t4 = type("BestTask", (), {})
        t5 = type("Task", (), {})

        for t in (t1, t2, t3, t4, t5):
            register(t)

        assert register.names == ["BestTask", "BetterTask", "Task", "Tasky"]

    it "returns if we contain a task with a particular name", register:
        name = "Tasky"

        t = type(name, (), {})
        assert name not in register
        assert t not in register

        register(t)

        assert name in register
        assert t in register

        t2 = type(name, (), {})
        assert "other" not in register
        # Note that it has same name but it's not the same task
        assert t2 not in register

    it "can give specs to a class", register:

        class T(register.Task):
            req_targ1 = register.requires_target()
            req_targ2 = register.requires_target(target_types=["lan"])

            prov_targ1 = register.provides_target()
            prov_targ2 = register.provides_target(target_names=["bob"])

            req_ref1 = register.requires_reference()
            req_ref2 = register.requires_reference(special=True)

            prov_ref1 = register.provides_reference()
            prov_ref2 = register.provides_reference(special=True)

            art = register.provides_artifact()

        def assertField(got, want, **attrs):
            assert isinstance(got, dictobj.Field)
            assert isinstance(got.spec, want)
            for n, v in attrs.items():
                assert getattr(got.spec, n) == v

        assertField(T.req_targ1, specs.target_spec, mandatory=True)
        assertField(
            T.req_targ2, specs.target_spec, mandatory=True, restrictions={"target_types": ["lan"]}
        )
        assertField(T.prov_targ1, specs.target_spec, mandatory=False)
        assertField(
            T.prov_targ2, specs.target_spec, mandatory=False, restrictions={"target_names": ["bob"]}
        )

        assertField(T.req_ref1, specs.reference_spec, mandatory=True, special=False)
        assertField(T.req_ref2, specs.reference_spec, mandatory=True, special=True)
        assertField(T.prov_ref1, specs.reference_spec, mandatory=False, special=False)
        assertField(T.prov_ref2, specs.reference_spec, mandatory=False, special=True)

        assert isinstance(T.art, dictobj.Field)
        assert isinstance(T.art.spec, sb.optional_spec)
        assert isinstance(T.art.spec.spec, sb.any_spec)

    describe "task from a function":

        @pytest.fixture()
        def collector(self):
            with alt_pytest_asyncio.Loop(new_loop=False):
                collector = Collector()
                collector.prepare(None, {})
                yield collector

        async it "works", register, collector:
            ran = {}

            target_register = collector.configuration["target_register"]

            InfraTarget = mock.Mock(name="InfraTarget")
            infratarget = Target.FieldSpec().empty_normalise(type="infrastructure")
            target_register.register_type("infrastructure", InfraTarget)

            HeroTarget = mock.Mock(name="HeroTarget")
            herotarget = Target.FieldSpec().empty_normalise(type="hero")
            target_register.register_type("hero", HeroTarget)

            road = mock.Mock(
                name="resolvedroad", instantiated_name="road", spec=["instantiated_name"]
            )
            batman = mock.Mock(
                name="resolvedbatman", instantiated_name="batman", spec=["instantiated_name"]
            )

            roadcreator = mock.Mock(name="roadcreator", return_value=road)
            batmancreator = mock.Mock(name="batmancreator", return_value=batman)

            target_register.add_target("road", infratarget, roadcreator)
            target_register.add_target("batman", herotarget, batmancreator)

            road = target_register.resolve("road")
            batman = target_register.resolve("batman")

            @register.from_function()
            async def task1(**kwargs):
                ran["task1"] = kwargs

            t1 = register.registered[0].task
            assert t1._original is task1

            @register.from_function(target="hero")
            async def task2(**kwargs):
                ran["task2"] = kwargs

            t2 = register.registered[0].task
            assert t2._original is task2

            @register.from_function(target="hero", needs_target=True)
            async def task3(**kwargs):
                ran["task3"] = kwargs

            t3 = register.registered[0].task
            assert t3._original is task3

            @register.from_function(needs_reference=True)
            async def task4(**kwargs):
                ran["task4"] = kwargs

            t4 = register.registered[0].task
            assert t4._original is task4

            @register.from_function(special_reference=True)
            async def task5(**kwargs):
                ran["task5"] = kwargs

            t5 = register.registered[0].task
            assert t5._original is task5

            @register.from_function(needs_reference=True, special_reference=True)
            async def task6(**kwargs):
                ran["task6"] = kwargs

            t6 = register.registered[0].task
            assert t6._original is task6

            @register.from_function(
                needs_target=True, needs_reference=True, special_reference=True, label="Stuff"
            )
            async def task7(**kwargs):
                ran["task7"] = kwargs

            t7 = register.registered[0].task
            assert t7._original is task7

            class Found:
                def __eq__(s, other):
                    return isinstance(other, FoundSerials)

            action = register.fill_task(collector, t1)
            await action.run()
            assert ran == {
                "task1": {
                    "collector": collector,
                    "target": sb.NotSpecified,
                    "reference": sb.NotSpecified,
                    "artifact": sb.NotSpecified,
                }
            }
            ran.clear()
            assert ran == {}

            action = register.fill_task(collector, "task1")
            assert isinstance(action, t1)
            await action.run()
            assert ran == {
                "task1": {
                    "collector": collector,
                    "target": sb.NotSpecified,
                    "reference": sb.NotSpecified,
                    "artifact": sb.NotSpecified,
                }
            }
            ran.clear()

            action = register.fill_task(
                collector, "task1", target=batman, reference="d073d5000001", artifact="stuff"
            )
            assert isinstance(action, t1)
            await action.run()
            assert ran == {
                "task1": {
                    "collector": collector,
                    "target": batman,
                    "reference": "d073d5000001",
                    "artifact": "stuff",
                }
            }
            ran.clear()

            for kls, name in ((t2, "task2"), (t3, "task3")):

                if name == "task2":

                    action = register.fill_task(
                        collector, name, reference="d073d5000001", artifact="stuff"
                    )
                    assert isinstance(action, kls)
                    await action.run()
                    assert ran == {
                        name: {
                            "collector": collector,
                            "target": sb.NotSpecified,
                            "reference": "d073d5000001",
                            "artifact": "stuff",
                        }
                    }
                    ran.clear()
                else:
                    with assertRaises(
                        BadTask,
                        "Task was used with wrong type of target",
                        wanted_task=name,
                        wanted_target="NotSpecified",
                        available_targets=["batman"],
                        restrictions=[{"target_types": ["hero"]}],
                    ):
                        register.fill_task(
                            collector, name, reference="d073d5000001", artifact="stuff"
                        )

                action = register.fill_task(
                    collector, name, target=batman, reference="d073d5000001", artifact="stuff"
                )
                assert isinstance(action, kls)
                await action.run()
                assert ran == {
                    name: {
                        "collector": collector,
                        "target": batman,
                        "reference": "d073d5000001",
                        "artifact": "stuff",
                    }
                }
                ran.clear()

                with assertRaises(
                    BadTask,
                    "Task was used with wrong type of target",
                    wanted_task=name,
                    wanted_target="road",
                    available_targets=["batman"],
                    restrictions=[{"target_types": ["hero"]}],
                ):
                    register.fill_task(
                        collector, name, target="road", reference="d073d5000001", artifact="stuff"
                    )

            action = register.fill_task(collector, "task4", reference="d073d5000001")
            await action.run()
            assert ran == {
                "task4": {
                    "collector": collector,
                    "target": sb.NotSpecified,
                    "reference": "d073d5000001",
                    "artifact": sb.NotSpecified,
                }
            }
            ran.clear()

            with assertRaises(
                BadOption, "This task requires you specify a reference, please do so!"
            ):
                register.fill_task(collector, "task4")
            assert ran == {}

            action = register.fill_task(collector, "task5", reference="_")
            await action.run()
            assert ran == {
                "task5": {
                    "collector": collector,
                    "target": sb.NotSpecified,
                    "reference": Found(),
                    "artifact": sb.NotSpecified,
                }
            }
            ran.clear()

            action = register.fill_task(collector, "task5")
            await action.run()
            assert ran == {
                "task5": {
                    "collector": collector,
                    "target": sb.NotSpecified,
                    "reference": Found(),
                    "artifact": sb.NotSpecified,
                }
            }
            ran.clear()

            action = register.fill_task(collector, "task6", reference="_")
            await action.run()
            assert ran == {
                "task6": {
                    "collector": collector,
                    "target": sb.NotSpecified,
                    "reference": Found(),
                    "artifact": sb.NotSpecified,
                }
            }
            ran.clear()

            with assertRaises(
                BadOption, "This task requires you specify a reference, please do so!"
            ):
                register.fill_task(collector, "task6")

            with assertRaises(BadTarget, "This task requires you specify a target"):
                register.fill_task(collector, t7)

            with assertRaises(
                BadOption, "This task requires you specify a reference, please do so!"
            ):
                register.fill_task(collector, t7, target=batman)

            action = register.fill_task(collector, "task7", target=batman, reference="_")
            await action.run()
            assert ran == {
                "task7": {
                    "collector": collector,
                    "target": batman,
                    "reference": Found(),
                    "artifact": sb.NotSpecified,
                }
            }
            ran.clear()

            action = register.fill_task(
                collector, "task7", target=batman, reference="_", artifact="blah"
            )
            await action.run()
            assert ran == {
                "task7": {
                    "collector": collector,
                    "target": batman,
                    "reference": Found(),
                    "artifact": "blah",
                }
            }
            ran.clear()

    describe "task from a class":

        @pytest.fixture()
        def collector(self):
            with alt_pytest_asyncio.Loop(new_loop=False):
                collector = Collector()
                collector.prepare(None, {})
                yield collector

        async it "works", register, collector:
            ran = {}

            target_register = collector.configuration["target_register"]

            InfraTarget = mock.Mock(name="InfraTarget")
            infratarget = Target.FieldSpec().empty_normalise(type="infrastructure")
            target_register.register_type("infrastructure", InfraTarget)

            HeroTarget = mock.Mock(name="HeroTarget")
            herotarget = Target.FieldSpec().empty_normalise(type="hero")
            target_register.register_type("hero", HeroTarget)

            road = mock.Mock(
                name="resolvedroad", instantiated_name="road", spec=["instantiated_name"]
            )
            batman = mock.Mock(
                name="resolvedbatman", instantiated_name="batman", spec=["instantiated_name"]
            )

            roadcreator = mock.Mock(name="roadcreator", return_value=road)
            batmancreator = mock.Mock(name="batmancreator", return_value=batman)

            target_register.add_target("road", infratarget, roadcreator)
            target_register.add_target("batman", herotarget, batmancreator)

            road = target_register.resolve("road")
            batman = target_register.resolve("batman")

            @register
            class task1(register.Task):
                async def execute_task(self, **kwargs):
                    ran["task1"] = {"collector": self.collector}

            t1 = task1

            @register
            class task2(register.Task):
                target = register.provides_target(target_types="hero")

                async def execute_task(self, **kwargs):
                    ran["task2"] = {"collector": self.collector, "target": self.target}

            t2 = task2

            @register
            class task3(register.Task):
                target = register.requires_target(target_types="hero")

                async def execute_task(self, **kwargs):
                    ran["task3"] = {"collector": self.collector, "target": self.target}

            t3 = task3

            @register
            class task4(register.Task):
                reference = register.requires_reference()

                async def execute_task(self, **kwargs):
                    ran["task4"] = {"collector": self.collector, "reference": self.reference}

            @register
            class task5(register.Task):
                reference = register.provides_reference(special=True)

                async def execute_task(self, **kwargs):
                    ran["task5"] = {"collector": self.collector, "reference": self.reference}

            @register
            class task6(register.Task):
                reference = register.requires_reference(special=True)

                async def execute_task(self, **kwargs):
                    ran["task6"] = {"collector": self.collector, "reference": self.reference}

            @register.register(task_group="Stuff")
            class task7(register.Task):
                target = register.requires_target()
                reference = register.requires_reference(special=True)
                artifact = register.provides_artifact()

                async def execute_task(self, **kwargs):
                    ran["task7"] = {
                        "collector": self.collector,
                        "photons_app": self.photons_app,
                        "target": self.target,
                        "reference": self.reference,
                        "artifact": self.artifact,
                    }

            t7 = task7

            action = register.fill_task(collector, t1)
            await action.run()
            assert ran == {
                "task1": {
                    "collector": collector,
                }
            }
            ran.clear()
            assert ran == {}

            action = register.fill_task(collector, "task1")
            assert isinstance(action, t1)
            await action.run()
            assert ran == {
                "task1": {
                    "collector": collector,
                }
            }
            ran.clear()

            action = register.fill_task(
                collector, "task1", target=batman, reference="d073d5000001", artifact="stuff"
            )
            assert isinstance(action, t1)
            await action.run()
            assert ran == {
                "task1": {
                    "collector": collector,
                }
            }
            ran.clear()

            for kls, name in ((t2, "task2"), (t3, "task3")):

                if name == "task2":

                    action = register.fill_task(
                        collector, name, reference="d073d5000001", artifact="stuff"
                    )
                    assert isinstance(action, kls)
                    await action.run()
                    assert ran == {
                        name: {
                            "collector": collector,
                            "target": sb.NotSpecified,
                        }
                    }
                    ran.clear()
                else:
                    with assertRaises(
                        BadTask,
                        "Task was used with wrong type of target",
                        wanted_task=name,
                        wanted_target="NotSpecified",
                        available_targets=["batman"],
                        restrictions=[{"target_types": "hero"}],
                    ):
                        register.fill_task(
                            collector, name, reference="d073d5000001", artifact="stuff"
                        )

                action = register.fill_task(
                    collector, name, target=batman, reference="d073d5000001", artifact="stuff"
                )
                assert isinstance(action, kls)
                await action.run()
                assert ran == {
                    name: {
                        "collector": collector,
                        "target": batman,
                    }
                }
                ran.clear()

                with assertRaises(
                    BadTask,
                    "Task was used with wrong type of target",
                    wanted_task=name,
                    wanted_target="road",
                    available_targets=["batman"],
                    restrictions=[{"target_types": "hero"}],
                ):
                    register.fill_task(
                        collector, name, target="road", reference="d073d5000001", artifact="stuff"
                    )

            action = register.fill_task(collector, "task4", reference="d073d5000001")
            await action.run()
            assert ran == {
                "task4": {
                    "collector": collector,
                    "reference": "d073d5000001",
                }
            }
            ran.clear()

            with assertRaises(
                BadOption, "This task requires you specify a reference, please do so!"
            ):
                register.fill_task(collector, "task4")
            assert ran == {}

            class Found:
                def __eq__(s, other):
                    return isinstance(other, FoundSerials)

            action = register.fill_task(collector, "task5", reference="_")
            await action.run()
            assert ran == {
                "task5": {
                    "collector": collector,
                    "reference": Found(),
                }
            }
            ran.clear()

            action = register.fill_task(collector, "task5")
            await action.run()
            assert ran == {
                "task5": {
                    "collector": collector,
                    "reference": Found(),
                }
            }
            ran.clear()

            action = register.fill_task(collector, "task6", reference="_")
            await action.run()
            assert ran == {
                "task6": {
                    "collector": collector,
                    "reference": Found(),
                }
            }
            ran.clear()

            with assertRaises(
                BadOption, "This task requires you specify a reference, please do so!"
            ):
                register.fill_task(collector, "task6")

            with assertRaises(BadTarget, "This task requires you specify a target"):
                register.fill_task(collector, t7)

            with assertRaises(
                BadOption, "This task requires you specify a reference, please do so!"
            ):
                register.fill_task(collector, t7, target=batman)

            action = register.fill_task(collector, "task7", target=batman, reference="_")
            await action.run()
            assert ran == {
                "task7": {
                    "collector": collector,
                    "target": batman,
                    "reference": Found(),
                    "artifact": sb.NotSpecified,
                    "photons_app": collector.configuration["photons_app"],
                }
            }
            ran.clear()

            action = register.fill_task(
                collector, "task7", target=batman, reference="_", artifact="blah"
            )
            await action.run()
            assert ran == {
                "task7": {
                    "collector": collector,
                    "target": batman,
                    "reference": Found(),
                    "artifact": "blah",
                    "photons_app": collector.configuration["photons_app"],
                }
            }
            ran.clear()

    describe "find":

        @pytest.fixture()
        def collector(self):
            with alt_pytest_asyncio.Loop(new_loop=False):
                superman = mock.Mock(
                    name="resolvedsuperman",
                    instantiated_name="superman",
                    spec=["instantiated_name"],
                )
                batman = mock.Mock(
                    name="resolvedbatman", instantiated_name="batman", spec=["instantiated_name"]
                )
                vegemite = mock.Mock(
                    name="resolvedvegemite",
                    instantiated_name="vegemite",
                    spec=["instantiated_name"],
                )
                road = mock.Mock(
                    name="resolvedroad", instantiated_name="road", spec=["instantiated_name"]
                )

                collector = Collector()
                collector.prepare(None, {})
                reg = collector.configuration["target_register"]

                HeroTarget = mock.Mock(name="HeroTarget")
                herotarget = Target.FieldSpec().empty_normalise(type="hero")
                reg.register_type("hero", HeroTarget)

                VillianTarget = mock.Mock(name="VillianTarget")
                villiantarget = Target.FieldSpec().empty_normalise(type="villian")
                reg.register_type("villian", VillianTarget)

                InfraTarget = mock.Mock(name="InfraTarget")
                infratarget = Target.FieldSpec().empty_normalise(type="infrastructure")
                reg.register_type("infrastructure", InfraTarget)

                supermancreator = mock.Mock(name="supermancreator", return_value=superman)
                reg.add_target("superman", herotarget, supermancreator)

                batmancreator = mock.Mock(name="batmancreator", return_value=batman)
                reg.add_target("batman", herotarget, batmancreator)

                vegemitecreator = mock.Mock(name="vegemitecreator", return_value=vegemite)
                reg.add_target("vegemite", villiantarget, vegemitecreator)

                roadcreator = mock.Mock(name="roadcreator", return_value=road)
                reg.add_target("road", infratarget, roadcreator)

                yield collector

        @pytest.fixture()
        def superman(self, collector):
            return collector.configuration["target_register"].resolve("superman")

        @pytest.fixture()
        def batman(self, collector):
            return collector.configuration["target_register"].resolve("batman")

        @pytest.fixture()
        def vegemite(self, collector):
            return collector.configuration["target_register"].resolve("vegemite")

        @pytest.fixture()
        def road(self, collector):
            return collector.configuration["target_register"].resolve("road")

        @pytest.fixture()
        def register(self):
            register = TaskRegister()

            class tasks:
                pass

            @register
            class One(register.Task):
                target = register.provides_target()

            tasks.tOne = One

            @register
            class Two(register.Task):
                target = register.requires_target()

            tasks.tTwo = Two

            @register
            class three(register.Task):
                target = register.requires_target(target_names=["batman", "vegemite"])

            tasks.tThree = three

            @register
            class Four(register.Task):
                target = register.requires_target(target_types=["hero"])

            tasks.tFourHero = Four

            @register
            class Four(register.Task):
                target = register.requires_target(target_types=["villian"])

            tasks.tFourVillian = Four

            @register
            class Five(register.Task):
                target = register.requires_target(target_types=["other"])

            tasks.tFive = Five

            @register.from_function(target="hero", needs_target=True)
            def six(collector, target):
                pass

            tasks.tSix = register.registered[0].task
            assert tasks.tSix._original is six

            @register.from_function()
            def six2(collector, target):
                pass

            tasks.tSix2 = register.registered[0].task
            assert tasks.tSix2._original is six2

            @register.from_function(needs_target=True)
            def six3(collector, target):
                pass

            tasks.tSix3 = register.registered[0].task
            assert tasks.tSix3._original is six3

            return register, tasks

        it "can find the correct task", batman, superman, vegemite, road, register, collector:
            register, tasks = register

            available = sorted(["One", "Two", "three", "Four", "Five", "six", "six2", "six3"])
            assert register.names == available
            assert not any(r.task is None for r in register.registered)

            target_register = collector.configuration["target_register"]

            # Must exist
            with assertRaises(BadTask, available=available, wanted="nope"):
                register.find(target_register, "nope", sb.NotSpecified)

            # Case matters
            with assertRaises(BadTask, available=available, wanted="one"):
                register.find(target_register, "one", sb.NotSpecified)
            assert register.find(target_register, "One", sb.NotSpecified) is tasks.tOne

            # Matches on target type for same tasks with the same name
            with assertRaises(
                BadTask,
                "Task was used with wrong type of target",
                wanted_task="Four",
                wanted_target="NotSpecified",
                available_targets=["batman", "superman", "vegemite"],
                restrictions=[{"target_types": ["villian"]}, {"target_types": ["hero"]}],
            ):
                register.find(target_register, "Four", sb.NotSpecified)
            with assertRaises(
                BadTask,
                "Task was used with wrong type of target",
                wanted_task="Four",
                wanted_target="road",
                available_targets=["batman", "superman", "vegemite"],
                restrictions=[{"target_types": ["villian"]}, {"target_types": ["hero"]}],
            ):
                register.find(target_register, "Four", road)
            assert register.find(target_register, "Four", superman) is tasks.tFourHero
            assert register.find(target_register, "Four", batman) is tasks.tFourHero
            assert register.find(target_register, "Four", vegemite) is tasks.tFourVillian

            # or based on the name
            with assertRaises(
                BadTask,
                "Task was used with wrong type of target",
                wanted_task="three",
                wanted_target="road",
                available_targets=["batman", "vegemite"],
                restrictions=[{"target_names": ["batman", "vegemite"]}],
            ):
                register.find(target_register, "three", road)
            assert register.find(target_register, "three", batman) is tasks.tThree
            assert register.find(target_register, "three", vegemite) is tasks.tThree

            # or with undefined target
            with assertRaises(
                BadTask,
                "Task was used with wrong type of target",
                wanted_task="Five",
                wanted_target="road",
                available_targets=[],
                restrictions=[{"target_types": ["other"]}],
            ):
                register.find(target_register, "Five", road)

            # Works on function defined tasks
            with assertRaises(
                BadTask,
                "Task was used with wrong type of target",
                wanted_task="six",
                wanted_target="road",
                available_targets=["batman", "superman"],
                restrictions=[{"target_types": ["hero"]}],
            ):
                register.find(target_register, "six", road)
            assert register.find(target_register, "six", batman) is tasks.tSix

            assert register.find(target_register, "six2", sb.NotSpecified) is tasks.tSix2
            assert register.find(target_register, "six2", road) is tasks.tSix2
            assert register.find(target_register, "six2", vegemite) is tasks.tSix2
            assert register.find(target_register, "six2", sb.NotSpecified) is tasks.tSix2

            with assertRaises(
                BadTask,
                "Task was used with wrong type of target",
                wanted_task="six3",
                wanted_target="NotSpecified",
                available_targets=["batman", "road", "superman", "vegemite"],
            ):
                register.find(target_register, "six3", sb.NotSpecified)
