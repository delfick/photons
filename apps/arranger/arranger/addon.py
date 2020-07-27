from arranger.options import Options
from arranger.server import Server

from photons_app.errors import UserQuit, ApplicationCancelled, ApplicationStopped
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action
from photons_app import helpers as hp

from delfick_project.addons import addon_hook
from delfick_project.norms import sb
import pkg_resources
import webbrowser
import subprocess
import logging
import asyncio
import socket
import shlex
import time
import os

log = logging.getLogger("arranger.addon")


@addon_hook(extras=[("lifx.photons", "__all__")])
def __lifx__(collector, *args, **kwargs):
    collector.register_converters(
        {"arranger": Options.FieldSpec(formatter=MergedOptionStringFormatter)}
    )


def port_connected(port):
    """
    Return whether something is listening on this port
    """
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


@an_action(label="Arranger", needs_target=True, special_reference=True)
async def arrange(collector, target, reference, **kwargs):
    conf = collector.configuration
    options = conf["arranger"]
    photons_app = collector.photons_app

    with photons_app.using_graceful_future() as final_future:
        async with target.session() as sender, hp.TaskHolder(
            final_future, name="cli_arrange"
        ) as ts:

            async def run():
                try:
                    await Server(final_future).serve(
                        options.host,
                        options.port,
                        conf["arranger"],
                        ts,
                        sender,
                        reference,
                        conf["photons_app"].cleaners,
                    )
                except asyncio.CancelledError:
                    raise
                except (UserQuit, ApplicationCancelled, ApplicationStopped):
                    pass

            ts.add(run())

            start = time.time()
            while not port_connected(options.port) and time.time() - start < 3:
                await asyncio.sleep(0.1)

            if not port_connected(options.port):
                final_future.set_exception(PhotonsAppError("Failed to start the server"))
                return

            if "NO_WEB_OPEN" not in os.environ:
                webbrowser.open(f"http://{options.host}:{options.port}")


async def arranger_assets(collector, reference, **kwargs):
    extra = collector.photons_app.extra
    assets = collector.configuration["arranger"].assets
    available = ["run", "add", "static", "watch"]

    if reference in (None, "", sb.NotSpecified):
        raise PhotonsAppError("Please specify what command to run", available=available)

    assets.ensure_yarn()

    try:
        if reference == "add":
            assets.run("add", *shlex.split(extra))
            return

        if reference == "run":
            assets.run(*shlex.split(extra))
            return

        if assets.needs_install:
            assets.run("install")

        if reference == "static":
            assets.run("run", "build")

        elif reference == "watch":
            assets.run("run", "generate")

        else:
            raise PhotonsAppError(
                "Didn't get a recognised command", want=reference, available=available
            )
    except subprocess.CalledProcessError as error:
        raise PhotonsAppError("Failed to run command", error=error)


if os.path.exists(pkg_resources.resource_filename("arranger", "static/js")):
    an_action(label="Arranger")(arranger_assets)
