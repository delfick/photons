from photons_app.tasks.runner import NormalRunner, GracefulRunner

from delfick_project.norms import dictobj, sb


class photons_app_spec(sb.Spec):
    def normalise(self, meta, val):
        return meta.everything["collector"].photons_app


class Task(dictobj):
    """
    Responsible for managing the life cycle of a photons program
    """

    collector = dictobj.Field(
        sb.overridden("{collector}"),
        format_into=lambda: sb.typed(__import__("photons_app.collector").collector.Collector),
    )

    photons_app = dictobj.Field(
        sb.overridden("{photons_app}"),
        format_into=lambda: sb.typed(__import__("photons_app.photons_app").photons_app.PhotonsApp),
    )

    def run_loop(self, **kwargs):
        return NormalRunner(self, kwargs).run_loop()

    async def run(self, task_holder, **kwargs):
        try:
            await self.execute_task(task_holder, **kwargs)
        finally:
            await self.post()

    async def execute_task(self, task_holder, **kwargs):
        raise NotImplementedError()

    async def post(self):
        pass


class GracefulTask(Task):
    def run_loop(self, **kwargs):
        return GracefulRunner(self, kwargs).run_loop()
