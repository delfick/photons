"""
We have here the object representing a task.

Tasks contain a reference to the functionality it provides (in ``photons_app.actions``)
"""

from photons_app.errors import BadOption, BadTarget, BadTask
from photons_app.special import SpecialReference

from delfick_project.norms import sb, dictobj


class Task(dictobj):
    """
    A reference to an action with a label

    .. dictobj_params::

    When a task is run, it performs the following responsibilities:

    * Determine what target to use
    * Complain if no reference is provided if action requires a reference
    * Use default target if not is specified
    * Complain if there is no target but one is needed
    * Pass everything into the action
    """

    fields = {
        ("action", "nop"): "The action to run with this reference",
        ("label", "Project"): "The namespace when listing tasks",
    }

    async def run(self, target, collector, available_actions, tasks, **extras):
        """Run this task"""
        task_func = self.resolve_task_func(collector, target, available_actions)

        target = self.resolve_target(collector, target)
        artifact = self.resolve_artifact(collector)
        reference = self.resolve_reference(collector, task_func)

        try:
            return await task_func(
                collector,
                target=target,
                reference=reference,
                tasks=tasks,
                artifact=artifact,
                **extras
            )
        finally:
            if isinstance(reference, SpecialReference):
                await reference.finish()

    def resolve_task_func(self, collector, target, available_actions):
        """
        Find us the task function given our action and target

        This will complain if the task func needs a target and one isn't specified

        It will also complain if there is no action for the given target
        """
        if target in ("", None, sb.NotSpecified):
            available = available_actions[None]
        else:
            target_type = collector.configuration["target_register"].type_for(target)
            available = available_actions.get(target_type)
            if (
                not available or self.action not in available
            ) and self.action not in available_actions.get(None, {}):
                target_types = [
                    t for t, actions in available_actions.items() if self.action in actions
                ]
                if target_types:
                    choice = []
                    for target in collector.configuration["targets"]:
                        if (
                            collector.configuration["target_register"].type_for(target)
                            in target_types
                        ):
                            choice.append(target)
                    raise BadTarget(
                        "Action only exists for other targets",
                        action=self.action,
                        target_choice=sorted(choice),
                    )

        if (
            not available or self.action not in available
        ) and self.action not in available_actions.get(None, {}):
            possible = set()
            for t, actions in available_actions.items():
                for action in actions:
                    if t:
                        possible.add("<{0}>:{1}".format(t, action))
                    else:
                        possible.add(action)
            raise BadTask(
                "Can't find what to execute",
                action=self.action,
                target=target,
                available=sorted(possible),
            )

        task_func = (available or available_actions[None]).get(self.action) or available_actions[
            None
        ][self.action]

        if task_func.needs_target and target in ("", None, sb.NotSpecified):
            usage = "lifx <target>:<task> <reference> <artifact> -- '{{<options>}}'"
            raise BadTarget(
                "This task requires you specify a target", usage=usage, action=self.action
            )

        return task_func

    def resolve_reference(self, collector, task_func):
        """
        If the task func needs a reference and none is specified then complain

        If the task wants a special_reference then we return one of those

        Otherwise we return reference as is.
        """
        empty = lambda r: r in ("", None, sb.NotSpecified)

        reference = collector.photons_app.reference
        if task_func.needs_reference and empty(reference):
            raise BadOption(
                "This task requires you specify a reference, please do so!", action=self.action
            )

        if task_func.special_reference:
            return collector.reference_object(reference)

        return reference

    def resolve_target(self, collector, target):
        """
        Try to resolve the target

        Or if target is empty, return sb.NotSpecified
        """
        target_register = collector.configuration["target_register"]
        if target in ("", None, sb.NotSpecified):
            return sb.NotSpecified
        else:
            return target_register.resolve(target)

    def resolve_artifact(self, collector):
        """Get us the artifact from the photons_app options"""
        return collector.photons_app.artifact
