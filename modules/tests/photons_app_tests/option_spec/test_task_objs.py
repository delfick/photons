# coding: spec

from photons_app.special import FoundSerials, HardCodedSerials
from photons_app.errors import BadTask, BadTarget, BadOption
from photons_app.registers import ReferenceResolerRegister
from photons_app.collector import Collector
from photons_app import helpers as hp
from photons_app.tasks import Task

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from unittest import mock
import binascii
import pytest


@pytest.fixture()
def V():
    class V:
        tasks = mock.Mock(name="tasks")
        target = mock.Mock(name="target")
        task_func = mock.Mock(name="task_func")
        reference = mock.Mock(name="reference")
        available_actions = mock.Mock(name="available_actions")

        action = mock.Mock(name="action")

        @hp.memoized_property
        def task(s):
            return Task(action=s.action)

        @hp.memoized_property
        def collector(s):
            collector = Collector()
            collector.prepare(None, {})
            return collector

    return V()


describe "Task run":
    describe "run":
        async it "resolves things and passes them in to the task_func", V:
            one = mock.Mock(name="one")
            final = mock.Mock(name="final")

            task_func = pytest.helpers.AsyncMock(name="task_func", return_value=final)
            resolve_task_func = mock.Mock(name="resolve_task_func", return_value=task_func)

            target = mock.Mock(name="target")
            resolve_target = mock.Mock(name="resolve_target", return_value=target)

            artifact = mock.Mock(name="artifact")
            resolve_artifact = mock.Mock(name="resolve_artifact", return_value=artifact)

            reference = mock.Mock(name="reference")
            resolve_reference = mock.Mock(name="resolve_reference", return_value=reference)

            with mock.patch.multiple(
                V.task,
                resolve_task_func=resolve_task_func,
                resolve_target=resolve_target,
                resolve_artifact=resolve_artifact,
                resolve_reference=resolve_reference,
            ):
                assert (
                    await V.task.run(
                        V.target, V.collector, V.available_actions, V.tasks, one=one, two=3
                    )
                ) is final

            task_func.assert_called_once_with(
                V.collector,
                target=target,
                reference=reference,
                artifact=artifact,
                tasks=V.tasks,
                one=one,
                two=3,
            )

describe "Task":
    it "takes in action and label":
        action = mock.Mock(name="action")
        label = mock.Mock(name="label")
        task = Task(action=action, label=label)

        assert task.action is action
        assert task.label is label

    it "has defaults for action and label":
        task = Task()

        assert task.action == "nop"
        assert task.label == "Project"

    describe "resolve_task_func":

        it "gets from available_actions[None] if target isn't specified", V:
            available_actions = {None: {V.action: V.task_func}}
            V.task_func.needs_target = False

            for target in ("", None, sb.NotSpecified):
                assert (
                    V.task.resolve_task_func(V.collector, target, available_actions) is V.task_func
                )

        it "complains if no target is specified and task needs target", V:
            available_actions = {None: {V.action: V.task_func}}
            V.task_func.needs_target = True

            for target in ("", None, sb.NotSpecified):
                with assertRaises(BadTarget, "This task requires you specify a target"):
                    assert (
                        V.task.resolve_task_func(V.collector, target, available_actions)
                        is V.task_func
                    )

        it "complains if we've specified a target and this action requires a different target", V:
            action_task = mock.Mock(name="action_task")
            action_task2 = mock.Mock(name="action_task2")
            available_actions = {
                "nt": {V.action: action_task},
                "thing": {V.action: action_task2},
            }

            targets = {"nt1": {}, "thing1": {}, "thing2": {}, "ignored": {}}
            target_register = mock.Mock(name="target_register")

            def type_for(t):
                if t is V.target:
                    return "other"
                else:
                    if t.startswith("nt"):
                        return "nt"
                    elif t.startswith("thing"):
                        return "thing"
                    else:
                        return "meh"

            target_register.type_for.side_effect = type_for

            V.collector.configuration = {"targets": targets, "target_register": target_register}

            target_choice = ["nt1", "thing1", "thing2"]
            with assertRaises(
                BadTarget,
                "Action only exists for other targets",
                action=V.action,
                target_choice=target_choice,
            ):
                V.task.resolve_task_func(V.collector, V.target, available_actions)

        it "complains if there is no task", V:
            available_actions = {"nt": {"one": {}, "two": {}}, None: {"three": {}}}
            possible = ["<nt>:one", "<nt>:two", "three"]

            target_register = mock.Mock(name="target_register")
            target_register.type_for.return_value = "meh"

            V.collector.configuration = {"target_register": target_register}
            with assertRaises(
                BadTask,
                "Can't find what to execute",
                action=V.action,
                target=V.target,
                available=possible,
            ):
                V.task.resolve_task_func(V.collector, V.target, available_actions)

            target_register.type_for.assert_called_once_with(V.target)

        it "returns the found task", V:
            one_task = mock.Mock(name="one_task", needs_target=False)
            one_task2 = mock.Mock(name="one_task2", needs_target=False)
            available_actions = {"nt": {V.action: one_task}, None: {V.action: one_task2}}

            target_register = mock.Mock(name="target_register")
            target_register.type_for.return_value = "nt"

            V.collector.configuration = {"target_register": target_register}

            assert V.task.resolve_task_func(V.collector, V.target, available_actions) is one_task
            target_register.type_for.assert_called_once_with(V.target)

            for target in ("", None, sb.NotSpecified):
                assert V.task.resolve_task_func(V.collector, target, available_actions) is one_task2

            # ensure it wasn't called again
            target_register.type_for.assert_called_once_with(V.target)

    describe "resolve_reference":

        @pytest.fixture()
        def reference_setter(self, V):
            def set_reference(reference):
                photons_app = mock.Mock(name="photons_app", reference=reference)
                V.collector.photons_app = photons_app

            return set_reference

        it "complains if we need a reference and none is given", V, reference_setter:
            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=False)
            for reference in ("", None, sb.NotSpecified):
                with assertRaises(
                    BadOption,
                    "This task requires you specify a reference, please do so!",
                    action=V.action,
                ):
                    reference_setter(reference)
                    V.task.resolve_reference(V.collector, task_func)

        it "complains if we need a reference and none is given even if special_reference is True", V, reference_setter:
            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=True)
            for reference in ("", None, sb.NotSpecified):
                with assertRaises(
                    BadOption,
                    "This task requires you specify a reference, please do so!",
                    action=V.action,
                ):
                    reference_setter(reference)
                    V.task.resolve_reference(V.collector, task_func)

        it "returns reference as is", V, reference_setter:
            task_func = mock.Mock(name="task_func", needs_reference=False, special_reference=False)
            for reference in ("", None, sb.NotSpecified, "what"):
                reference_setter(reference)
                assert V.task.resolve_reference(V.collector, task_func) is reference

            reference_setter("what")
            assert V.task.resolve_reference(V.collector, task_func) == "what"

        it "returns the reference as a SpecialReference if special_reference is True", V, reference_setter:
            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=True)
            reference = "d073d5000001,d073d5000002"
            reference_setter(reference)
            resolved = V.task.resolve_reference(V.collector, task_func)
            wanted = [binascii.unhexlify(ref) for ref in reference.split(",")]

            assert resolved.targets == wanted
            assert type(resolved) == HardCodedSerials

        it "returns a FoundSerials instruction if no reference is specified and special_reference is True", V, reference_setter:
            task_func = mock.Mock(name="task_func", needs_reference=False, special_reference=True)
            for r in ("", "_", None, sb.NotSpecified):
                reference_setter(r)
                references = V.task.resolve_reference(V.collector, task_func)
                assert isinstance(references, FoundSerials), references

        it "returns the resolved reference if of type typ:options", V, reference_setter:
            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=True)
            ret = HardCodedSerials(["d073d5000001", "d073d5000002"])
            resolver = mock.Mock(name="resolver", return_value=ret)

            register = ReferenceResolerRegister()
            register.add("my_resolver", resolver)

            V.collector.configuration = {"reference_resolver_register": register}

            reference = "my_resolver:blah:and,stuff"
            reference_setter(reference)
            resolved = V.task.resolve_reference(V.collector, task_func)
            assert resolved is ret
            resolver.assert_called_once_with("blah:and,stuff")

        it "returns a SpecialReference if our resolver returns not a special reference", V, reference_setter:
            ret = "d073d5000001,d073d5000002"
            wanted = [binascii.unhexlify(ref) for ref in ret.split(",")]

            task_func = mock.Mock(name="task_func", needs_reference=True, special_reference=True)

            for reference in (ret, ret.split(",")):
                resolver = mock.Mock(name="resolver", return_value=reference)

                register = ReferenceResolerRegister()
                register.add("my_resolver", resolver)

                V.collector.configuration = {"reference_resolver_register": register}

                reference = "my_resolver:blah:and,stuff"
                reference_setter(reference)
                resolved = V.task.resolve_reference(V.collector, task_func)
                assert type(resolved) == HardCodedSerials, resolved
                assert resolved.targets == wanted
                resolver.assert_called_once_with("blah:and,stuff")

    describe "resolve_target":

        it "returns NotSpecified if target is empty", V:
            for target in ("", None, sb.NotSpecified):
                assert V.task.resolve_target(V.collector, target) is sb.NotSpecified

        it "resolves the target if not empty", V:
            resolved = mock.Mock(name="resolved")
            resolve = mock.Mock(name="resolve", return_value=resolved)

            with mock.patch.object(
                V.collector.configuration["target_register"], "resolve", resolve
            ):
                assert V.task.resolve_target(V.collector, "targetname") is resolved

            resolve.assert_called_once_with("targetname")

    describe "resolve_artfiact":
        it "returns from the photons_app optios":
            artifact = mock.Mock(name="artifact")
            photons_app = mock.Mock(name="photons_app", artifact=artifact)
            collector = mock.Mock(name="collector", photons_app=photons_app)

            assert Task().resolve_artifact(collector) is artifact
