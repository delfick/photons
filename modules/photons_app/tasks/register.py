from collections import namedtuple

from delfick_project.norms import dictobj, sb
from photons_app.errors import BadOption, BadTarget, BadTask
from photons_app.tasks.tasks import GracefulTask, Task

artifact_spec = lambda: sb.optional_spec(sb.any_spec())


class target_spec(sb.Spec):
    def setup(self, restrictions, *, mandatory=True):
        self.mandatory = mandatory
        self.restrictions = restrictions

    def normalise_empty(self, meta):
        if not self.mandatory:
            return sb.NotSpecified

        usage = "lifx <target>:<task> <reference> <artifact> -- '{{<options>}}'"
        raise BadTarget("This task requires you specify a target", usage=usage, meta=meta)

    def normalise(self, meta, val):
        if val in ("", None, sb.NotSpecified):
            return self.normalise_empty(meta)

        collector = meta.everything["collector"]
        target_register = collector.configuration["target_register"]
        return target_register.restricted(**self.restrictions).resolve(val)


class reference_spec(sb.Spec):
    def setup(self, mandatory=True, special=True):
        self.special = special
        self.mandatory = mandatory

    def normalise_empty(self, meta, val=sb.NotSpecified):
        if not self.mandatory:
            if self.special:
                return meta.everything["collector"].reference_object(val)
            return sb.NotSpecified

        raise BadOption("This task requires you specify a reference, please do so!", meta=meta)

    def normalise_filled(self, meta, val):
        if val in ("", None, sb.NotSpecified):
            return self.normalise_empty(meta, val=val)

        if self.special and isinstance(val, str):
            collector = meta.everything["collector"]
            return collector.reference_object(val)

        return val


RegisteredTask = namedtuple("RegisteredTask", ["name", "task", "task_group"])


class TaskRegister:
    Task = Task
    GracefulTask = GracefulTask

    Field = dictobj.Field
    NullableField = dictobj.NullableField

    def __init__(self):
        self.registered = []

    @property
    def names(self):
        return sorted(set([r.name for r in self.registered]))

    def register(self, *, name=None, task_group="Project"):
        return lambda task: self(task, name=name, task_group=task_group)

    def from_function(
        self,
        target=None,
        special_reference=False,
        needs_reference=False,
        needs_target=False,
        label="Project",
    ):
        '''
        Registers a function as a task. The name of the task will be the name
        of the function. When the function is called it will be provided
        ``collector``, ``target``, ``reference``, ``artifact`` and any other
        keyword arguments that were provided when the task was invoked.

        The decorator has the following options for changing the values provided
        to the function:

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

        For example:

        .. code-block:: python

            from photons_app.tasks import task_register as task


            @task.from_function(target="lan", special_reference=True)
            def my_amazing_task(collector, target, reference, **kwargs):
                """This task does cool things"""
                ...

        Is equivalent to:

        .. code-block:: python

            from photons_app.tasks import task_register as task


            @task
            class my_amazing_task(task.Task):
                """This task does cool things"""

                target = task.requires_target(target_types=["lan"])
                reference = task.provides_reference(special=True)

                async def execute_task(self, **kwargs):
                    ...

        It is recommended you create tasks rather than functions for tasks.
        '''
        kwargs = {}

        restrictions = {}
        if target is not None:
            restrictions["target_types"] = [target]

        if needs_target:
            kwargs["target"] = self.requires_target(**restrictions)
        else:
            kwargs["target"] = self.provides_target(**restrictions)

        if needs_reference:
            kwargs["reference"] = self.requires_reference(special=special_reference)
        elif special_reference:
            kwargs["reference"] = self.provides_reference(special=True)
        else:
            kwargs["reference"] = self.provides_reference()

        kwargs["artifact"] = self.provides_artifact()

        async def execute_task(instance, **kwargs):
            kw = dict(
                collector=instance.collector,
                target=instance.target,
                reference=instance.reference,
                artifact=instance.artifact,
            )
            kw.update(kwargs)
            return await instance._original(**kw)

        def wrap(func):
            res = type(
                func.__name__,
                (Task,),
                {
                    **kwargs,
                    "__doc__": func.__doc__,
                    "_original": staticmethod(func),
                    "execute_task": execute_task,
                },
            )
            self._register(func.__name__, res, task_group=label)
            return func

        return wrap

    def __call__(self, task, *, name=None, task_group="Project"):
        if name is None:
            name = task.__name__
        self._register(name, task, task_group=task_group)
        return task

    def _register(self, name, task, task_group):
        self.registered.insert(0, RegisteredTask(name, task, task_group))

    def __contains__(self, name):
        return any(name == r.name or name is r.task for r in self.registered)

    def requires_target_spec(self, **restrictions):
        return target_spec(restrictions, mandatory=True)

    def requires_target(self, **restrictions):
        return dictobj.Field(self.requires_target_spec(**restrictions))

    def provides_target_spec(self, **restrictions):
        return target_spec(restrictions, mandatory=False)

    def provides_target(self, **restrictions):
        return dictobj.Field(self.provides_target_spec(**restrictions))

    def requires_reference_spec(self, *, special=False):
        return reference_spec(special=special, mandatory=True)

    def requires_reference(self, *, special=False):
        return dictobj.Field(self.requires_reference_spec(special=special))

    def provides_reference_spec(self, *, special=False):
        return reference_spec(special=special, mandatory=False)

    def provides_reference(self, *, special=False):
        return dictobj.Field(self.provides_reference_spec(special=special))

    def provides_artifact_spec(self):
        return artifact_spec()

    def provides_artifact(self):
        return dictobj.Field(self.provides_artifact_spec())

    def determine_target_restrictions(self, task):
        mandatory = False
        target_restrictions = {}
        if isinstance(task, type) and issubclass(task, Task) and "target" in task.fields:
            mandatory = task.fields["target"].spec.mandatory
            target_restrictions = task.fields["target"].spec.restrictions
        elif hasattr(task, "target_restrictions"):
            mandatory = True
            target_restrictions = getattr(task, "target_restrictions", {})

        return mandatory, target_restrictions

    def find(self, target_register, task, target):
        found = False
        choices = []
        restrictions = []
        available_tasks = []
        possible_targets = []
        for r in self.registered:
            available_tasks.append(r.name)
            if r.name == task:
                found = True

                mandatory, target_restrictions = self.determine_target_restrictions(r.task)
                if target_restrictions:
                    restrictions.append(target_restrictions)

                register = target_register.restricted(**target_restrictions)
                possible_targets.extend(list(register.registered))

                if target in ("", None, sb.NotSpecified):
                    if not mandatory:
                        choices.append(r.task)
                    continue

                if not target_restrictions or target in register:
                    choices.append(r.task)

        if not found:
            raise BadTask(wanted=task, available=sorted(set(available_tasks)))

        if choices:
            return choices[0]

        kw = {}
        if restrictions:
            kw["restrictions"] = restrictions

        raise BadTask(
            "Task was used with wrong type of target",
            wanted_task=task,
            wanted_target=getattr(
                target, "instantiated_name", getattr(target, "__name__", repr(target))
            ),
            available_targets=sorted(set(possible_targets)),
            **kw,
        )

    def fill_task(
        self,
        collector,
        task,
        *,
        target=sb.NotSpecified,
        reference=sb.NotSpecified,
        where=None,
        **kwargs,
    ):
        """
        Resolve our task and target and return a filled Task object
        """
        if isinstance(target, str):
            target = collector.resolve_target(target)

        task_name = None
        if isinstance(task, str):
            task_name = task
            task = self.find(collector.configuration["target_register"], task, target)

        return task.create(
            collector,
            where=where,
            instantiated_name=task_name,
            target=target,
            reference=reference,
            **kwargs,
        )


task_register = TaskRegister()
