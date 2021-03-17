from photons_app.runner import run


class NormalRunner:
    def __init__(self, task, kwargs):
        self.task = task
        self.kwargs = kwargs

    def run_loop(self):
        photons_app = self.task.photons_app
        target_register = self.task.collector.configuration["target_register"]
        run(self.task.run(**self.kwargs), photons_app, target_register)
