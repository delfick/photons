from interactor.errors import InteractorError
from interactor.options import Options
from interactor.server import Server

from photons_app.errors import UserQuit, ApplicationCancelled, ApplicationStopped
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.actions import an_action
from photons_app import helpers as hp

from delfick_project.addons import addon_hook
import aiohttp
import asyncio
import logging

log = logging.getLogger("interactor.addon")


@addon_hook(extras=[("lifx.photons", "core")])
def __lifx__(collector, *args, **kwargs):
    collector.register_converters(
        {"interactor": Options.FieldSpec(formatter=MergedOptionStringFormatter)}
    )


@an_action(needs_target=True, label="Interactor")
async def interactor(collector, target, **kwargs):
    await migrate(collector, extra="upgrade head")

    options = collector.configuration["interactor"]
    photons_app = collector.photons_app
    with photons_app.using_graceful_future() as final_future:
        async with target.session() as sender, hp.TaskHolder(
            final_future, name="cli_arrange"
        ) as ts:
            try:
                await Server(final_future).serve(
                    options.host,
                    options.port,
                    options,
                    tasks=ts,
                    sender=sender,
                    cleaners=photons_app.cleaners,
                    animation_options=collector.configuration.get("animation_options", {}),
                )
            except asyncio.CancelledError:
                raise
            except (UserQuit, ApplicationCancelled, ApplicationStopped):
                pass


@an_action(label="Interactor")
async def migrate(collector, extra=None, **kwargs):
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
    from interactor.database import database

    if extra is None:
        extra = collector.configuration["photons_app"].extra
    await database.migrate(collector.configuration["interactor"].database, extra)


@an_action(label="Interactor")
async def interactor_healthcheck(collector, **kwargs):
    """
    Returns the current status of Interactor via exit code.

    An exit code of 0 indicates the status command returned successfully.
    An exit code of any other value indicates a failure.
    """
    options = collector.configuration["interactor"]
    uri = f"http://{options.host}:{options.port}/v1/lifx/command"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.put(uri, json={"command": "status"}) as response:
                if response.status != 200:
                    content = (await response.content.read()).decode()
                    raise InteractorError(f"Healthcheck failed: {response.status}: {content}")

        except aiohttp.client_exceptions.ClientConnectorError as error:
            raise InteractorError(f"Healthcheck failed: {error}")
