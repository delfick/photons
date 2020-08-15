"""
Responsible for finding tasks and executing them
"""

from photons_app.actions import available_actions, all_tasks
from photons_app.errors import BadTask


class TaskFinder:
    def __init__(self, collector):
        self.tasks = all_tasks
        self.collector = collector

    async def task_runner(self, target, task, **kwargs):
        if task not in self.tasks:
            raise BadTask("Unknown task", task=task, available=sorted(list(self.tasks.keys())))

        return await self.tasks[task].run(
            target, self.collector, available_actions, self.tasks, **kwargs
        )
