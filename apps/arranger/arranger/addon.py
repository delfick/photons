import importlib.resources
import logging
import os
import shlex
import socket
import subprocess
import webbrowser

from arranger.options import Options
from arranger.server import Server
from delfick_project.addons import addon_hook
from delfick_project.norms import sb
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.tasks import task_register as task

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


@task.register(task_group="Arranger")
class arrange(task.GracefulTask):
    """
    Start a web GUI you can use to change the positions of the panels in your tile sets
    such that the tile sets know where they are relative to each other.

    Your web browser will automatically open to this GUI unless you have ``NO_WEB_OPEN=1``
    in your environment.
    """

    target = task.requires_target()
    reference = task.provides_reference(special=True)

    @property
    def options(self):
        return self.collector.configuration["arranger"]

    async def open_browser(self):
        async with hp.tick(0.1, max_time=3) as ticker:
            async for _ in ticker:
                if port_connected(self.options.port):
                    break

        if not port_connected(self.options.port):
            self.photons_app.final_future.set_exception(
                PhotonsAppError("Failed to start the server")
            )
            return

        if "NO_WEB_OPEN" not in os.environ:
            webbrowser.open(f"http://{self.options.host}:{self.options.port}")

    async def execute_task(self, graceful_final_future, **kwargs):
        self.task_holder.add(self.open_browser())

        async with self.target.session() as sender:
            await Server(
                self.photons_app.final_future, server_end_future=graceful_final_future
            ).serve(
                self.options.host,
                self.options.port,
                self.options,
                self.task_holder,
                sender,
                self.reference,
                self.photons_app.cleaners,
            )


class arranger_assets(task.Task):
    reference = task.provides_reference()

    async def execute_task(self, **kwargs):
        extra = self.photons_app.extra
        assets = self.collector.configuration["arranger"].assets
        available = ["run", "install", "static", "watch"]

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
                assets.run("ci", no_node_env=True)

            if self.reference == "static":
                assets.run("run", "build")

            elif self.reference == "watch":
                assets.run("run", "generate")

            else:
                raise PhotonsAppError(
                    "Didn't get a recognised command", want=self.reference, available=available
                )
        except subprocess.CalledProcessError as error:
            raise PhotonsAppError("Failed to run command", error=error)


if (importlib.resources.files("arranger") / "static" / "js").exists():
    task.register(task_group="Arranger")(arranger_assets)
