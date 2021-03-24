from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import BadOption, BadTarget, BadTask
from photons_app.tasks.runner import Runner
from photons_app import helpers as hp

from delfick_project.norms import dictobj, sb, Meta


class photons_app_spec(sb.Spec):
    def normalise(self, meta, val):
        return meta.everything["collector"].photons_app


class NewTask(dictobj.Spec):
    """
    Responsible for managing the life cycle of a photons program
    """

    instantiated_name = dictobj.Field(sb.string_spec)

    collector = dictobj.Field(
        sb.overridden("{collector}"),
        format_into=lambda: sb.typed(__import__("photons_app.collector").collector.Collector),
    )

    photons_app = dictobj.Field(
        sb.overridden("{photons_app}"),
        format_into=lambda: sb.typed(__import__("photons_app.photons_app").photons_app.PhotonsApp),
    )

    @classmethod
    def create(kls, collector, where=None, instantiated_name=None, **kwargs):
        if where is None:
            where = "<Task.create>"

        if instantiated_name is None:
            instantiated_name = kls.__name__

        configuration = collector.configuration.wrapped()
        kwargs.update({"instantiated_name": instantiated_name})
        configuration.update(kwargs)
        meta = Meta(configuration, []).at(where)

        # Make errors follow nice order for errors on cli
        spec = kls.FieldSpec(MergedOptionStringFormatter).make_spec(meta)
        transfer_set = {}
        transfer_create = {}
        for key in ("target", "reference", "artifact"):
            if key in spec.expected:
                transfer_set[key] = spec.expected.pop(key)
                transfer_create[key] = spec.expected_spec.options.pop(key)
        transfer_set.update(spec.expected)
        transfer_create.update(spec.expected_spec.options)
        spec.expected_spec.options = transfer_set
        spec.expected = transfer_create

        return spec.normalise(meta, kwargs)

    @hp.memoized_property
    def task_holder(self):
        return hp.TaskHolder(
            self.photons_app.final_future, name=f"Task({self.__class__.__name__})::task_holder"
        )

    def run_loop(self, **kwargs):
        return Runner(self, kwargs).run_loop()

    async def run(self, **kwargs):
        async with self.task_holder:
            try:
                return await self.execute_task(**kwargs)
            finally:
                await self.post(**kwargs)

    async def execute_task(self, **kwargs):
        raise NotImplementedError()

    async def post(self, **kwargs):
        pass


class GracefulTask(NewTask):
    """
    Responsible for managing the life cycle of a photons program that uses the graceful future
    """

    def run_loop(self, **kwargs):
        with self.photons_app.using_graceful_future() as graceful:
            kwargs["graceful_final_future"] = graceful
            super().run_loop(**kwargs)


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

        return await task_func(
            collector, target=target, reference=reference, tasks=tasks, artifact=artifact, **extras
        )

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
