from photons_app.tasks.register import task_register, Task, GracefulTask

__import__("photons_app.tasks.default_tasks")

__all__ = ["task_register", "Task", "GracefulTask"]
