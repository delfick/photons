import sys
from collections import defaultdict
from io import StringIO
from textwrap import dedent

from delfick_project.norms import Meta, sb
from delfick_project.option_merge import MergedOptions
from photons_app.errors import PhotonsAppError
from photons_app.tasks.register import task_register
from photons_app.tasks.specifier import task_specifier_spec

task = task_register


@task
class nop(task.Task):
    """Literally do nothing"""

    async def execute_task(self, **kwargs):
        pass


@task
class help(task.Task):
    """
    Display more help information for specified target:task

    This task takes an extra argument that can be:

    <target>
        A specific target, will show associated tasks for that target

    <target type>
        Will show what targets are available for this type and their
        associated tasks

    <task>
        Will show expanded help information for this task

    You can also be tricky and do something like ``<target>:help`` instead
    of ``help <target>``
    """

    target = task.provides_target()
    reference = task.provides_reference()

    specific_task_groups = task.NullableField(sb.tupleof(sb.string_spec()))

    async def execute_task(self, **kwargs):
        task_name = sb.NotSpecified
        target_name = self.target

        if self.reference is not sb.NotSpecified:
            if ":" in self.reference:
                target_name, task_name = task_specifier_spec().normalise(
                    Meta.empty(), self.reference
                )
            else:
                task_name = self.reference

        target_register = self.collector.configuration["target_register"]

        if task_name in target_register.registered or task_name in target_register.types:
            target_name = task_name
            task_name = sb.NotSpecified

        for name, target in target_register.created.items():
            if target is target_name:
                target_name = name
                break

        if target_name is not sb.NotSpecified:
            if target_name in target_register.registered or target_name in target_register.types:
                kwargs["specific_target"] = target_name

            if (
                target_name not in target_register.registered
                and target_name not in target_register.types
            ):
                raise PhotonsAppError(
                    "Sorry, cannot find help for non existing target", wanted=target_name
                )

        if task_name is not sb.NotSpecified:
            kwargs["specific_task"] = task_name
            if task_name not in task_register:
                raise PhotonsAppError(
                    "Sorry, cannot find help for non existing task",
                    wanted=task_name,
                    available=task_register.names,
                )

        await task_register.fill_task(
            self.collector, list_tasks, specific_task_groups=self.specific_task_groups, **kwargs
        ).run()


@task
class list_tasks(task.Task):
    """List the available_tasks"""

    output = task.Field(sb.any_spec, default=sys.stdout)
    specific_task = task.Field(sb.any_spec, wrapper=sb.optional_spec)
    specific_target = task.Field(sb.any_spec, wrapper=sb.optional_spec)

    specific_task_groups = task.NullableField(sb.tupleof(sb.string_spec()))

    def __call__(self, s=""):
        print(s, file=self.output)

    @property
    def target_register(self):
        return self.collector.configuration["target_register"]

    async def execute_task(self, **kwargs):
        self("Usage: (<target>:)<task> <options> -- <extra>")

        target_register = self.target_register
        initial_restrictions = {}
        if self.specific_target is not sb.NotSpecified:
            initial_restrictions.update(dict(target_names=[self.specific_target]))
            target_register = target_register.restricted(**initial_restrictions)

        targets_by_name = defaultdict(list)
        for name, target in self.target_register.registered.items():
            typ = self.target_register.type_for(name)
            desc = self.target_register.desc_for(name)
            targets_by_name[name] = (typ, desc)

        tasks = []
        for task in task_register.registered:
            if (
                self.specific_task_groups is not None
                and task.task_group not in self.specific_task_groups
            ):
                continue

            if self.specific_task is sb.NotSpecified or task.name == self.specific_task:
                _, restrictions = task_register.determine_target_restrictions(task.task)
                if not restrictions:
                    tasks.append((task, restrictions))
                    continue

                restrict = MergedOptions.using(initial_restrictions, restrictions).as_dict()
                reg = target_register.restricted(**restrict)
                if reg.registered:
                    tasks.append((task, restrictions))

        if len(tasks) == 1:
            self()
            self.print_one_task(targets_by_name, *tasks[0])
        elif tasks:
            self()
            self.print_tasks(targets_by_name, tasks)
        else:
            self("Found no tasks to print help for...")

    def print_one_task(self, targets_by_name, t, restriction):
        self("=" * 80)
        self(t.name)
        self("-" * 80)
        self.print_target_restrictions(targets_by_name, restriction)
        self("-" * 80)
        self("\n".join(f"  {line}" for line in dedent(t.task.__doc__ or "").split("\n")))
        self()

    def print_target_restrictions(self, targets_by_name, restriction):
        if restriction:
            self("- Can be used with only specific targets")
            for n, v in sorted(restriction.items()):
                self(f"  * {n} = {v}")
            for name in self.target_register.restricted(**restriction).registered:
                self(f"  : {name} - ({targets_by_name[name][0]}) - {targets_by_name[name][1]}")
        else:
            self("- Can be used with any target")

    def print_tasks(self, targets_by_name, tasks):
        by_restriction = defaultdict(list)
        for t, restriction in tasks:
            doc = (t.task.__doc__ or "").strip()
            if doc:
                doc = doc.split("\n")[0]

            o = StringIO()
            task_register.fill_task(
                self.collector, self.__class__, output=o
            ).print_target_restrictions(targets_by_name, restriction)
            o.flush()
            o.seek(0)
            by_restriction[o.read()].append((t.name, t.task_group, doc))

        for show_those_without_restriction in (False, True):
            for restriction, tasks in by_restriction.items():
                if (
                    restriction.startswith("- Can be used with any target")
                    ^ show_those_without_restriction
                ):
                    continue

                self("=" * 80)
                self(restriction)
                self("  " * 10 + "-" * 40)
                self()

                by_label = defaultdict(list)
                for name, label, doc in tasks:
                    by_label[label].append((name, doc))

                for label, ts in by_label.items():
                    t = f"  {label}::"
                    self(t)
                    self("  " + "#" * (len(t) - 2))
                    max_length = 0
                    for name, _ in ts:
                        max_length = max([max_length, len(name) + 1])

                    for i, (name, doc) in enumerate(sorted(ts)):
                        self(f"    {name:{max_length}}: {doc}")
                        if i != 0 and i % 5 == 0:
                            self()
                    self()
