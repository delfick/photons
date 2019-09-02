# coding: spec

from photons_app.special import FoundSerials, HardCodedSerials, SpecialReference
from photons_app.errors import BadTask, BadTarget, BadOption
from photons_app.test_helpers import TestCase, AsyncTestCase
from photons_app.registers import ReferenceResolerRegister
from photons_app.option_spec.task_objs import Task

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
from unittest import mock
import asynctest
import binascii

describe AsyncTestCase, "Task run":
    describe "run":
        async before_each:
            self.tasks = mock.Mock(name="tasks")
            self.target = mock.Mock(name="target")
            self.collector = mock.Mock(name="collector")
            self.reference = mock.Mock(name="reference")
            self.available_actions = mock.Mock(name="available_actions")

            self.action = mock.Mock(name="action")
            self.task = Task(action=self.action)

        async it "resolves things and passes them in to the task_func":
            one = mock.Mock(name="one")
            final = mock.Mock(name="final")

            task_func = asynctest.mock.CoroutineMock(name="task_func", return_value=final)
            resolve_task_func = mock.Mock(name="resolve_task_func", return_value=task_func)

            target = mock.Mock(name="target")
            resolve_target = mock.Mock(name="resolve_target", return_value=target)

            artifact = mock.Mock(name="artifact")
            resolve_artifact = mock.Mock(name="resolve_artifact", return_value=artifact)

            reference = mock.Mock(name="reference")
            resolve_reference = mock.Mock(name="resolve_reference", return_value=reference)

            with mock.patch.multiple(
                self.task,
                resolve_task_func=resolve_task_func,
                resolve_target=resolve_target,
                resolve_artifact=resolve_artifact,
                resolve_reference=resolve_reference,
            ):
                self.assertIs(
                    await self.wait_for(
                        self.task.run(
                            self.target,
                            self.collector,
                            self.reference,
                            self.available_actions,
                            self.tasks,
                            one=one,
                            two=3,
                        )
                    ),
                    final,
                )

            task_func.assert_called_once_with(
                self.collector,
                target=target,
                reference=reference,
                artifact=artifact,
                tasks=self.tasks,
                one=one,
                two=3,
            )

        async it "finishes the reference if it's a SpecialReference":
            called = []

            one = mock.Mock(name="one")
            final = mock.Mock(name="final")

            async def task_func(*args, **kwargs):
                called.append("task")
                return final

            task_func = asynctest.mock.CoroutineMock(name="task_func", side_effect=task_func)
            resolve_task_func = mock.Mock(name="resolve_task_func", return_value=task_func)

            target = mock.Mock(name="target")
            resolve_target = mock.Mock(name="resolve_target", return_value=target)

            artifact = mock.Mock(name="artifact")
            resolve_artifact = mock.Mock(name="resolve_artifact", return_value=artifact)

            class Reference(SpecialReference):
                async def finish(s):
                    called.append("finish")

            reference = Reference()
            resolve_reference = mock.Mock(name="resolve_reference", return_value=reference)

            with mock.patch.multiple(
                self.task,
                resolve_task_func=resolve_task_func,
                resolve_target=resolve_target,
                resolve_artifact=resolve_artifact,
                resolve_reference=resolve_reference,
            ):
                self.assertIs(
                    await self.wait_for(
                        self.task.run(
                            self.target,
                            self.collector,
                            self.reference,
                            self.available_actions,
                            self.tasks,
                            one=one,
                            two=3,
                        )
                    ),
                    final,
                )

            task_func.assert_called_once_with(
                self.collector,
                target=target,
                reference=reference,
                artifact=artifact,
                tasks=self.tasks,
                one=one,
                two=3,
            )

            self.assertEqual(called, ["task", "finish"])

describe TestCase, "Task":
    it "takes in action and label":
        action = mock.Mock(name="action")
        label = mock.Mock(name="label")
        task = Task(action=action, label=label)

        self.assertIs(task.action, action)
        self.assertIs(task.label, label)

    it "has defaults for action and label":
        task = Task()

        self.assertEqual(task.action, "nop")
        self.assertEqual(task.label, "Project")

    describe "resolve_task_func":
        before_each:
            self.action = mock.Mock(name="action")
            self.task = Task(action=self.action)
            self.task_func = mock.Mock(name="task_func")

            self.collector = mock.Mock(name="collector")
            self.target = mock.Mock(name="target")

        it "gets from available_actions[None] if target isn't specified":
            available_actions = {None: {self.action: self.task_func}}
            self.task_func.needs_target = False

            for target in ("", None, sb.NotSpecified):
                self.assertIs(
                    self.task.resolve_task_func(self.collector, target, available_actions),
                    self.task_func,
                )

        it "complains if no target is specified and task needs target":
            available_actions = {None: {self.action: self.task_func}}
            self.task_func.needs_target = True

            for target in ("", None, sb.NotSpecified):
                with self.fuzzyAssertRaisesError(
                    BadTarget, "This task requires you specify a target"
                ):
                    self.assertIs(
                        self.task.resolve_task_func(self.collector, target, available_actions),
                        self.task_func,
                    )

        it "complains if we've specified a target and this action requires a different target":
            action_task = mock.Mock(name="action_task")
            action_task2 = mock.Mock(name="action_task2")
            available_actions = {
                "nt": {self.action: action_task},
                "thing": {self.action: action_task2},
            }

            targets = {"nt1": {}, "thing1": {}, "thing2": {}, "ignored": {}}
            target_register = mock.Mock(name="target_register")

            def type_for(t):
                if t is self.target:
                    return "other"
                else:
                    if t.startswith("nt"):
                        return "nt"
                    elif t.startswith("thing"):
                        return "thing"
                    else:
                        return "meh"

            target_register.type_for.side_effect = type_for

            self.collector.configuration = {"targets": targets, "target_register": target_register}

            target_choice = ["nt1", "thing1", "thing2"]
            with self.fuzzyAssertRaisesError(
                BadTarget,
                "Action only exists for other targets",
                action=self.action,
                target_choice=target_choice,
            ):
                self.task.resolve_task_func(self.collector, self.target, available_actions)

        it "complains if there is no task":
            available_actions = {"nt": {"one": {}, "two": {}}, None: {"three": {}}}
            possible = ["<nt>:one", "<nt>:two", "three"]

            target_register = mock.Mock(name="target_register")
            target_register.type_for.return_value = "meh"

            self.collector.configuration = {"target_register": target_register}
            with self.fuzzyAssertRaisesError(
                BadTask,
                "Can't find what to execute",
                action=self.action,
                target=self.target,
                available=possible,
            ):
                self.task.resolve_task_func(self.collector, self.target, available_actions)

            target_register.type_for.assert_called_once_with(self.target)

        it "returns the found task":
            one_task = mock.Mock(name="one_task", needs_target=False)
            one_task2 = mock.Mock(name="one_task2", needs_target=False)
            available_actions = {"nt": {self.action: one_task}, None: {self.action: one_task2}}

            target_register = mock.Mock(name="target_register")
            target_register.type_for.return_value = "nt"

            self.collector.configuration = {"target_register": target_register}

            self.assertIs(
                self.task.resolve_task_func(self.collector, self.target, available_actions),
                one_task,
            )
            target_register.type_for.assert_called_once_with(self.target)

            for target in ("", None, sb.NotSpecified):
                self.assertIs(
                    self.task.resolve_task_func(self.collector, target, available_actions),
                    one_task2,
                )

            # ensure it wasn't called again
            target_register.type_for.assert_called_once_with(self.target)

    describe "resolve_reference":
        before_each:
            self.action = mock.Mock(name="action")
            self.task = Task(action=self.action)
            self.target = mock.Mock(name="target")

            self.collector = mock.Mock(name="collector")

        it "complains if we need a reference and none is given":
            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=False)
            for reference in ("", None, sb.NotSpecified):
                with self.fuzzyAssertRaisesError(
                    BadOption,
                    "This task requires you specify a reference, please do so!",
                    action=self.action,
                ):
                    self.task.resolve_reference(self.collector, task_func, reference, self.target)

        it "complains if we need a reference and none is given even if special_reference is True":
            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=True)
            for reference in ("", None, sb.NotSpecified):
                with self.fuzzyAssertRaisesError(
                    BadOption,
                    "This task requires you specify a reference, please do so!",
                    action=self.action,
                ):
                    self.task.resolve_reference(self.collector, task_func, reference, self.target)

        it "returns reference as is":
            task_func = mock.Mock(name="task_func", needs_reference=False, special_reference=False)
            for reference in ("", None, sb.NotSpecified, "what"):
                self.assertIs(
                    self.task.resolve_reference(self.collector, task_func, reference, self.target),
                    reference,
                )

            task_func2 = mock.Mock(name="task_func", needs_reference=True, special_reference=False)
            self.assertEqual(
                self.task.resolve_reference(self.collector, task_func, "what", self.target), "what"
            )

        it "returns the reference as a SpecialReference if special_reference is True":
            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=True)
            reference = "d073d5000001,d073d5000002"
            resolved = self.task.resolve_reference(
                self.collector, task_func, reference, self.target
            )
            wanted = [binascii.unhexlify(ref) for ref in reference.split(",")]

            self.assertEqual(resolved.targets, wanted)
            self.assertEqual(type(resolved), HardCodedSerials)

        it "returns a FoundSerials instruction if no reference is specified and special_reference is True":
            task_func = mock.Mock(name="task_func", needs_reference=False, special_reference=True)
            for r in ("", "_", None, sb.NotSpecified):
                references = self.task.resolve_reference(self.collector, task_func, r, self.target)
                assert isinstance(references, FoundSerials), references

        it "returns the resolved reference if of type typ:options":
            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=True)
            ret = HardCodedSerials(["d073d5000001", "d073d5000002"])
            resolver = mock.Mock(name="resolver", return_value=ret)

            register = ReferenceResolerRegister()
            register.add("my_resolver", resolver)

            self.collector.configuration = {"reference_resolver_register": register}

            reference = "my_resolver:blah:and,stuff"
            resolved = self.task.resolve_reference(
                self.collector, task_func, reference, self.target
            )
            self.assertIs(resolved, ret)
            resolver.assert_called_once_with("blah:and,stuff", self.target)

        it "returns a SpecialReference if our resolver returns not a special reference":
            ret = "d073d5000001,d073d5000002"
            wanted = [binascii.unhexlify(ref) for ref in ret.split(",")]

            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=True)

            for reference in (ret, ret.split(",")):
                resolver = mock.Mock(name="resolver", return_value=reference)

                register = ReferenceResolerRegister()
                register.add("my_resolver", resolver)

                self.collector.configuration = {"reference_resolver_register": register}

                reference = "my_resolver:blah:and,stuff"
                resolved = self.task.resolve_reference(
                    self.collector, task_func, reference, self.target
                )
                self.assertEqual(type(resolved), HardCodedSerials)
                self.assertEqual(resolved.targets, wanted)
                resolver.assert_called_once_with("blah:and,stuff", self.target)

    describe "resolve_target":
        before_each:
            self.action = mock.Mock(name="action")
            self.task = Task(action=self.action)

            self.target_register = mock.Mock(name="target_register")
            self.collector = mock.Mock(name="collector")
            self.collector.configuration = {"target_register": self.target_register}

        it "returns NotSpecified if target is empty":
            for target in ("", None, sb.NotSpecified):
                self.assertIs(self.task.resolve_target(self.collector, target), sb.NotSpecified)

        it "resolves the target if not empty":
            resolved = mock.Mock(name="resolved")
            self.target_register.resolve.return_value = resolved
            self.assertIs(self.task.resolve_target(self.collector, "targetname"), resolved)

            self.target_register.resolve.assert_called_once_with("targetname")

    describe "resolve_artfiact":
        it "returns from the photons_app optios":
            collector = mock.Mock(name="collector")
            artifact = mock.Mock(name="artifact")
            photons_app = mock.Mock(name="photons_app", artifact=artifact)
            collector.configuration = {"photons_app": photons_app}

            self.assertIs(Task().resolve_artifact(collector), artifact)
