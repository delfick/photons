from photons_app.tasks.specifier import task_specifier_spec
from photons_app.tasks.register import task_register
from photons_app.tasks.tasks import Task

__import__("photons_app.tasks.default_tasks")

__all__ = ["task_specifier_spec", "Task", "task_register"]
