"""
.. glossary::

    action
        A python callable that defines some specific functionality. It takes in
        ``(collector, loop, target, reference, artifact, tasks, **kwargs)``.

        loop
            asycnio event loop instance

        target
            The target instance as referenced by the user on the commandline.

        reference
            The reference string from the commandline

        artifact
            The artifact string from the commandline

        tasks
            A dictionary of all the tasks that have been defined

We define actions by using the ``an_action`` decorator.

.. autoclass:: photons_app.actions.an_action
"""

from photons_app.option_spec.task_objs import Task
from photons_app.errors import PhotonsAppError

from input_algorithms import spec_base as sb
from collections import defaultdict
from textwrap import dedent
import itertools
import logging

log = logging.getLogger("photons_app.actions")

all_tasks = {}
available_actions = {}

class an_action(object):
    """
    Records a task in the ``available_actions`` dictionary

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
    def __init__(self, target=None, special_reference=False, needs_reference=False, needs_target=False, label="Project"):
        self.label = label
        self.target = target
        self.needs_target = needs_target
        self.needs_reference = needs_reference
        self.special_reference = special_reference

    def __call__(self, func):
        target = self.target

        if target not in available_actions:
            available_actions[target] = {}
        available_actions[target][func.__name__] = func

        func.target = target
        func.needs_target = self.needs_target
        func.needs_reference = self.needs_reference
        func.special_reference = self.special_reference

        all_tasks[func.__name__] = Task(action=func.__name__, label=self.label)
        return func

@an_action()
async def nop(collector, **kwargs):
    """Literally do nothing"""

@an_action()
async def help(collector, tasks, reference, target, **kwargs):
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
    target_name = sb.NotSpecified
    if target is not sb.NotSpecified:
        target_name = collector.configuration["photons_app"].target

    if reference not in (None, "", sb.NotSpecified):
        if ":" in reference:
            target_name, task_name = reference.split(":", 1)
        else:
            task_name = reference

    target_register = collector.configuration["target_register"]
    if task_name in target_register.targets or task_name in target_register.types:
        target_name = task_name
        task_name = sb.NotSpecified

    if target_name is not sb.NotSpecified:
        if target_name in target_register.targets or target_name in target_register.types:
            kwargs["specific_target"] = target_name

        if target_name not in target_register.targets and target_name not in target_register.types:
            raise PhotonsAppError("Sorry, cannot find help for non existing target", wanted=target_name)

    if task_name is not sb.NotSpecified:
        kwargs["specific_task"] = task_name
        if task_name not in tasks:
            raise PhotonsAppError("Sorry, cannot find help for non existing task", wanted=task_name)

    await list_tasks(collector, tasks, **kwargs)

@an_action()
async def list_tasks(collector, tasks, specific_target=sb.NotSpecified, specific_task=sb.NotSpecified, **kwargs):
    """List the available_tasks"""
    print("Usage: (<target>:)<task> <options> -- <extra>")
    print("The following is targets and their associated tasks")
    target_register = collector.configuration["target_register"]
    found = defaultdict(list)
    max_target_length = 0

    for target in target_register.targets:
        if specific_target in (sb.NotSpecified, target, target_register.type_for(target)):
            typ = target_register.type_for(target)
            desc = target_register.desc_for(target)
            found[typ].append((target, desc))
            max_target_length = max([len(target), max_target_length])

    def get_tasks(tasks, targets, typ):
        result = []
        if typ not in available_actions:
            start = "This has" if len(targets) is 1 else "These have"
            result.append(("", ("\n    : {0} no target specific tasks".format(start))))
        else:
            available = available_actions[typ]
            found = {}
            for task, func in available.items():
                found[task] = (tasks[task], func)

            keygetter = lambda item: item[1][0].label or "Default"
            tasks = sorted(found.items(), key=keygetter)
            for index, (label, items) in enumerate(itertools.groupby(tasks, keygetter)):
                sorted_tasks = sorted(list(items), key=lambda item: len(item[1][0]))
                max_length = max([len(key) for key, _ in sorted_tasks])
                for key, (task, func) in sorted_tasks:
                    if specific_task in (sb.NotSpecified, key):
                        if label.strip():
                            result.append(("", ""))
                        desc = dedent(func.__doc__ or "").strip().split('\n')[0]
                        full_desc = func.__doc__ or ""
                        base_str = "    {1} :: {2}{3}".format(" ", label, key, " " * (max_length - len(key)))

                        if specific_task is not sb.NotSpecified:
                            result.append((key, base_str))
                            result.append((key, "\n".join("        {0}".format(line) for line in dedent(full_desc).split("\n"))))
                        else:
                            result.append((key, "{0} :-: {1}".format(base_str, desc)))
                        label = " " * len(label)
        return result

    for typ, infos in sorted(found.items()) + [(None, [("", "")])]:
        targets = [t for t, _ in infos]
        if typ is None or specific_target in [sb.NotSpecified, typ] + targets:
            task_lines = get_tasks(tasks, targets, typ)
            if specific_task in [sb.NotSpecified] + [k for k, _ in task_lines]:
                print("")
                print("_" * 80)
                for target, desc in infos:
                    if typ:
                        print(("{0:%ss} - Type {1} -- {2}" % max_target_length).format(target, typ, desc))
                    else:
                        print("Tasks that can be used with any target")
                print("_" * 80)
                for _, l in task_lines:
                    print(l)
                print(" ")
