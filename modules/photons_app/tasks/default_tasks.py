from photons_app.tasks.specifier import task_specifier_spec
from photons_app.tasks.register import task_register
from photons_app.errors import PhotonsAppError

from delfick_project.option_merge import MergedOptions
from delfick_project.norms import sb, Meta
from collections import defaultdict
from textwrap import dedent
from io import StringIO
import sys


@task_register.from_function()
async def nop(collector, **kwargs):
    """Literally do nothing"""


@task_register.from_function()
async def help(collector, reference, target, **kwargs):
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
    task_name = sb.NotSpecified
    target_name = target

    if reference is not sb.NotSpecified:
        if ":" in reference:
            target_name, task_name = task_specifier_spec().normalise(Meta.empty(), reference)
        else:
            task_name = reference

    target_register = collector.configuration["target_register"]

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

    await list_tasks(collector, **kwargs)


@task_register.from_function()
async def list_tasks(
    collector,
    specific_target=sb.NotSpecified,
    specific_task=sb.NotSpecified,
    output=sys.stdout,
    **kwargs,
):
    """List the available_tasks"""

    def p(s=""):
        print(s, file=output)

    p("Usage: (<target>:)<task> <options> -- <extra>")

    original_target_register = collector.configuration["target_register"]
    target_register = original_target_register
    initial_restrictions = {}
    if specific_target is not sb.NotSpecified:
        initial_restrictions.update(dict(target_names=[specific_target]))
        target_register = target_register.restricted(**initial_restrictions)

    targets_by_name = defaultdict(list)
    for name, target in target_register.registered.items():
        typ = target_register.type_for(name)
        desc = target_register.desc_for(name)
        targets_by_name[name] = (typ, desc)

    tasks = []
    for task in task_register.registered:
        if specific_task is sb.NotSpecified or task.name == specific_task:
            restrictions = getattr(task, "target_restrictions", {})
            if not restrictions:
                tasks.append((task, restrictions))
                continue

            restrict = MergedOptions.using(initial_restrictions, restrictions).as_dict()
            reg = target_register.restricted(**restrict)
            if reg.registered:
                tasks.append((task, restrictions))

    if len(tasks) == 1:
        p()
        print_one_task(p, original_target_register, targets_by_name, *tasks[0])
    elif tasks:
        p()
        print_tasks(p, original_target_register, targets_by_name, tasks)
    else:
        p("Found no tasks to print help for...")


def print_one_task(p, target_register, targets_by_name, t, restriction):
    p("=" * 80)
    p(t.name)
    p("-" * 80)
    print_target_restrictions(p, target_register, targets_by_name, restriction)
    p("-" * 80)
    p("\n".join(f"  {line}" for line in dedent(t.task.__doc__ or "").split("\n")))
    p()


def print_target_restrictions(p, target_register, targets_by_name, restriction):
    if restriction:
        p("- Can be used with only specific targets")
        for n, v in sorted(restriction.items()):
            p(f"  * {n} = {v}")
        for name in target_register.restricted(**restriction).registered:
            p(f"  : {name} - ({targets_by_name[name][0]}) - {targets_by_name[name][1]}")
    else:
        p("- Can be used with any target")


def print_tasks(p, target_register, targets_by_name, tasks):
    by_restriction = defaultdict(list)
    for t, restriction in tasks:
        doc = (t.task.__doc__ or "").strip()
        if doc:
            doc = doc.split("\n")[0]

        o = StringIO()
        pp = lambda s="": print(s, file=o)
        print_target_restrictions(pp, target_register, targets_by_name, restriction)
        o.flush()
        o.seek(0)
        by_restriction[o.read()].append((t.name, t.task_group, doc))

    for restriction, tasks in by_restriction.items():
        p("=" * 80)
        p(restriction)
        p("  " * 10 + "-" * 40)
        p()

        by_label = defaultdict(list)
        for name, label, doc in tasks:
            by_label[label].append((name, doc))

        for label, ts in by_label.items():
            t = f"  {label}::"
            p(t)
            p("  " + "#" * (len(t) - 2))
            max_length = 0
            for name, _ in ts:
                max_length = max([max_length, len(name) + 1])

            for i, (name, doc) in enumerate(sorted(ts)):
                p(f"    {name:{max_length}}: {doc}")
                if i != 0 and i % 5 == 0:
                    p()
            p()
