from photons_app.tasks.register import GracefulTask, Task, task_register

__import__("photons_app.tasks.default_tasks")

__all__ = ["task_register", "Task", "GracefulTask"]
