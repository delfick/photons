"""
Responsible for finding tasks and executing them
"""

from photons_app.actions import available_actions, all_tasks
from photons_app.errors import BadTask

from input_algorithms.spec_base import NotSpecified

class TaskFinder(object):
    def __init__(self, collector):
        self.tasks = all_tasks
        self.collector = collector

    def task_runner(self, task, reference, **kwargs):
        target = NotSpecified
        if ":" in task:
            target, task = task.split(":", 1)

        if task not in self.tasks:
            raise BadTask("Unknown task", task=task, available=sorted(list(self.tasks.keys())))

        return self.tasks[task].run(target, self.collector, reference, available_actions, self.tasks, **kwargs)
