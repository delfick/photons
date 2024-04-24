import importlib
import logging
import shlex
import subprocess

import aiohttp
from delfick_project.addons import addon_hook
from delfick_project.norms import sb
from interactor.errors import InteractorError
from interactor.options import Options
from interactor.server import InteractorServer as Server
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.tasks import task_register as task
from photons_web_server.server import WebServerTask

log = logging.getLogger("interactor.addon")


@addon_hook(extras=[("lifx.photons", "core"), ("lifx.photons", "web_server")])
def __lifx__(collector, *args, **kwargs):
    collector.register_converters(
        {"interactor": Options.FieldSpec(formatter=MergedOptionStringFormatter)}
    )


@task.register(task_group="Interactor")
class interactor(WebServerTask):
    """
    Start a daemon that will watch your network for LIFX lights and interact with them
    """

    ServerKls = Server
    target = task.requires_target()

    @property
    def options(self):
        return self.collector.configuration["interactor"]

    @property
    def host(self):
        return self.options.host

    @property
    def port(self):
        return self.options.port

    @hp.asynccontextmanager
    async def server_kwargs(self):
        async with self.target.session() as sender:
            yield dict(
                reference_resolver_register=self.collector.configuration[
                    "reference_resolver_register"
                ],
                sender=sender,
                options=self.options,
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
        # make all the models available so that the migrate command knows about them
        __import__("interactor.database.models")

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


class interactor_assets(task.Task):
    reference = task.provides_reference()

    async def execute_task(self, **kwargs):
        extra = self.photons_app.extra
        assets = self.collector.configuration["interactor"].assets
        available = ["run", "install", "dev", "build"]

        if self.reference is sb.NotSpecified:
            raise PhotonsAppError("Please specify what command to run", available=available)

        assets.ensure_npm()

        try:
            if self.reference == "install":
                assets.run("install", *shlex.split(extra))
                return

            if self.reference == "run":
                assets.run(*shlex.split(extra))
                return

            if assets.needs_install:
                assets.run("ci")

            if self.reference == "dev":
                assets.run("run", "watch")

            elif self.reference == "build":
                assets.run("run", "build")

            else:
                raise PhotonsAppError(
                    "Didn't get a recognised command", want=self.reference, available=available
                )
        except subprocess.CalledProcessError as error:
            raise PhotonsAppError("Failed to run command", error=error)


if (
    importlib.resources.files("interactor") / ".." / "interactor_webapp" / "interactor" / "src"
).exists():
    task.register(task_group="Interactor")(interactor_assets)
