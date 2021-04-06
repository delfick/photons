from interactor.errors import InteractorError
from interactor.options import Options
from interactor.server import Server

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.tasks import task_register as task

from delfick_project.addons import addon_hook
import aiohttp
import logging

log = logging.getLogger("interactor.addon")


@addon_hook(extras=[("lifx.photons", "core")])
def __lifx__(collector, *args, **kwargs):
    collector.register_converters(
        {"interactor": Options.FieldSpec(formatter=MergedOptionStringFormatter)}
    )


@task.register(task_group="Interactor")
class interactor(task.GracefulTask):
    """
    Start a daemon that will watch your network for LIFX lights and interact with them
    """

    target = task.requires_target()

    @property
    def options(self):
        return self.collector.configuration["interactor"]

    async def execute_task(self, graceful_final_future, **kwargs):
        logging.getLogger("tornado.access").disabled = True

        await task.fill_task(self.collector, "migrate").run(extra="upgrade head")

        async with self.target.session() as sender:
            await Server(
                self.photons_app.final_future, server_end_future=graceful_final_future
            ).serve(
                self.options.host,
                self.options.port,
                self.options,
                tasks=self.task_holder,
                sender=sender,
                cleaners=self.photons_app.cleaners,
                animation_options=self.collector.configuration.get("animation_options", {}),
            )


@task.register(task_group="Interactor")
class migrate(task.Task):
    """
    Migrate a database

    This task will use `Alembic <http://alembic.zzzcomputing.com>`_ to perform
    database migration tasks.

    Usage looks like:

    ``migrate -- revision --autogenerate  -m doing_some_change``

    Or

    ``migrate -- upgrade head``

    Basically, everything after the ``--`` is passed as commandline arguments
    to alembic.
    """

    async def execute_task(self, extra=None, **kwargs):
        from interactor.database import database

        if extra is None:
            extra = self.photons_app.extra
        await database.migrate(self.collector.configuration["interactor"].database, extra)


@task.register(task_group="Interactor")
class interactor_healthcheck(task.Task):
    """
    Returns the current status of Interactor via exit code.

    An exit code of 0 indicates the status command returned successfully.
    An exit code of any other value indicates a failure.
    """

    async def execute_task(self, **kwargs):
        options = self.collector.configuration["interactor"]
        uri = f"http://{options.host}:{options.port}/v1/lifx/command"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.put(uri, json={"command": "status"}) as response:
                    if response.status != 200:
                        content = (await response.content.read()).decode()
                        raise InteractorError(f"Healthcheck failed: {response.status}: {content}")

            except aiohttp.client_exceptions.ClientConnectorError as error:
                raise InteractorError(f"Healthcheck failed: {error}")
