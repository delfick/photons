class NormalRunner:
    def __init__(self, task, kwargs):
        self.task = task
        self.kwargs = kwargs

    def run_loop(self):
        pass


class GracefulRunner(NormalRunner):
    pass
