class Finish(Exception):
    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return f"Finished: {self.reason}"
