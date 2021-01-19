from photons_app.tasks.tasks import GracefulTask, Task
from photons_app.errors import BadTarget, BadOption
from photons_app.registers import TargetRestriction
from photons_app.special import SpecialReference

from delfick_project.norms import sb


class artifact_spec(sb.Spec):
    def normalise(self, meta, val):
        return sb.optional_spec(sb.any_spec()).normalise(meta, val)


class target_spec(sb.Spec):
    def setup(self, mandatory=True):
        self.mandatory = mandatory

    def normalise_empty(self, meta):
        if not self.mandatory:
            return sb.NotSpecified

        usage = "lifx <target>:<task> <reference> <artifact> -- '{{<options>}}'"
        raise BadTarget("This task requires you specify a target", usage=usage, meta=meta)

    def normalise_filled(self, meta, val):
        if val in ("", None, sb.NotSpecified):
            if not self.mandatory:
                return sb.NotSpecified
            else:
                return self.normalise_empty(meta)

        collector = meta.everything["collector"]
        target_register = collector.configuration["target_register"]
        target_restriction = getattr(meta.everything["task_kls"], "target_restriction", None)
        return target_register.resolve(val, restriction=target_restriction)


class reference_spec(sb.Spec):
    def setup(self, mandatory=True, special=True):
        self.special = special
        self.mandatory = mandatory

    def normalise_empty(self, meta):
        if not self.mandatory:
            return sb.NotSpecified

        raise BadOption("This task requires you specify a reference, please do so!", meta=meta)

    def normalise_filled(self, meta, val):
        if val in ("", None, sb.NotSpecified):
            if not self.mandatory:
                return sb.NotSpecified
            else:
                return self.normalise_empty(meta)

        if self.special and isinstance(val, str):
            collector = meta.everything["collector"]
            return collector.reference_object(val)

        return val


class FunctionWrapperTask(Task):
    async def __call__(self, **kwargs):
        return await self._original(
            collector=self.collector,
            target=self.target,
            reference=self.reference,
            artifact=self.artifact,
            **kwargs
        )


class TaskRegister:
    Task = Task
    Graceful = GracefulTask

    def __init__(self):
        self.registered = []

    def from_class(self, *, label=sb.NotSpecified):
        """
        Creates a reference to a class that may be used as task

        label
            A string, that if specified will override the label on the class
        """

        def wrap(kls):
            kwargs = {}
            if label is not sb.NotSpecified:
                kwargs["label"] = label
            res = type(kls.__name__, (kls,), {**kwargs, "_original": kls})
            self._register(res)
            return res

        return wrap

    def from_function(
        self,
        target=None,
        special_reference=False,
        needs_reference=False,
        needs_target=False,
        label="Project",
    ):
        """
        Creates a reference to a function that may be used as a task

        It takes in:

        target
            The ``type`` of the target that applies to this action. For example
            ``lan`` or ``http``. This is so that you can have a different task with
            the same name registered for different targets

        needs_reference
            Specifies that a reference needs to be specified on the commandline

        special_reference
            Allow us to provide more detailed reference to devices.

            Empty string or '_' resolves to all serials found on the network

            comma seperated list of serials is split by comma.

            Otherwise, we use ``<resolver>:<options>`` to resolve our reference to serials

        needs_target
            Specifies that it needs the target type specified on the commandline

        label
            A string used by the help tasks to sort the actions into groups.
        """
        kwargs = {"label": label}

        kwargs["target_restriction"] = TargetRestriction.create(target)

        if needs_target:
            kwargs["target"] = self.requires_target()
        else:
            kwargs["target"] = self.provides_target()

        if needs_reference:
            kwargs["reference"] = self.requires_reference(special=special_reference)
        elif special_reference:
            kwargs["reference"] = self.provides_reference(special=True)
        else:
            kwargs["reference"] = self.provides_reference()

        kwargs["artifact"] = self.provides_artifact()

        async def post(instance):
            if isinstance(instance, SpecialReference):
                await instance.finish()

        def wrap(func):
            res = type(
                func.__name__, (FunctionWrapperTask,), {**kwargs, "post": post, "_original": func}
            )
            self._register(res)
            return res

        return wrap

    def _register(self, task):
        self.registered.append(task)

    def requires_target(self, target_type):
        return target_spec(mandatory=True)

    def provides_target(self, target_type):
        return target_spec(target_type, mandatory=False)

    def requires_reference(self, *, special=False):
        return reference_spec(special=special, mandatory=True)

    def provides_reference(self, *, special=False):
        return reference_spec(special=special, mandatory=False)

    def provides_artifact(self):
        return artifact_spec()


task_register = TaskRegister()
