import asyncio
import importlib.resources
import logging
import os
import shlex
import shutil
import socket
import sys
import time
import webbrowser

from aiohttp import web
from delfick_project.addons import addon_hook
from delfick_project.norms import dictobj, sb
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.tasks import task_register as task
from photons_app.tasks.default_tasks import help, list_tasks
from sphinx.cmd.build import build_main

log = logging.getLogger("photons_docs")

this_dir = os.path.abspath(os.path.dirname(__file__))


class DocOptions(dictobj.Spec):
    out = dictobj.Field(wrapper=sb.required, format_into=sb.string_spec)
    src = dictobj.Field(wrapper=sb.required, format_into=sb.directory_spec)


@addon_hook()
def __lifx__(collector, *args, **kwargs):
    collector.register_converters({"documentation": DocOptions.FieldSpec(formatter=MergedOptionStringFormatter)})


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


class when_docs(sb.Spec):
    def __init__(self, want, otherwise=None):
        self.want = want
        self.otherwise = otherwise

    def normalise(self, meta, val):
        if "for_docs" in meta.everything["collector"].configuration:
            return self.want
        return self.otherwise


@task
class list_tasks(list_tasks):
    specific_task_groups = task.Field(when_docs(("Docs",)))


@task
class help(help):
    specific_task_groups = task.Field(when_docs(("Docs",)))


class build_options_spec(sb.Spec):
    def normalise(self, meta, val):
        class Options:
            force = False
            fresh = False

        if val is sb.NotSpecified:
            return Options

        val = [a.strip() for a in sb.string_spec().normalise(meta, val).split(",")]
        if "fresh" in val:
            Options.fresh = True
        if "force" in val:
            Options.force = True

        return Options


@task.register(task_group="Docs")
class build_docs(task.Task):
    """
    Build the documentation

    You can specify options using the reference option.

    fresh
        Remove the cache

    force
        Force the build

    For example

    ``build_docs fresh,force``
    """

    reference = task.Field(build_options_spec)

    @property
    def is_fresh(self):
        return self.reference.fresh

    @property
    def force_all(self):
        return self.reference.force

    async def execute_task(self, **kwargs):
        options = self.collector.configuration["documentation"]

        srcdir = options.src
        outdir = os.path.join(options.out, "result")

        confdir = str((importlib.resources.files("photons_docs") / "config").resolve())
        doctreedir = os.path.join(options.out, "doctree")

        if self.is_fresh and os.path.exists(options.out):
            shutil.rmtree(options.out)

        for d in (outdir, doctreedir):
            if not os.path.exists(d):
                os.makedirs(d)

        argv = [srcdir, outdir, "-c", confdir, "-d", doctreedir]
        if self.is_fresh:
            argv.append("-E")
        argv.extend(shlex.split(self.photons_app.extra))

        sys.exit(build_main(argv))


@task.register(task_group="Docs")
class view_docs(task.GracefulTask):
    """
    View the built docs in your webbrowser.

    This will start serving the built documentation under http://127.0.0.1:4202
    and open your webbrowser to this address
    """

    def make_server():
        async def hello(request):
            return web.Response(text="Hello, world")

    async def execute_task(self, graceful_final_future, **kwargs):
        directory = os.path.join(self.collector.configuration["documentation"].out, "result")
        port = int(os.environ.get("PHOTONS_DOCS_PORT", 0))

        app = web.Application()
        app.router.add_static("/", directory)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", port))
            port = s.getsockname()[1]

        task = self.task_holder.add(web._run_app(app, port=port, handle_signals=False, print=False))

        start = time.time()
        while not port_connected(port) and time.time() - start < 3:
            await asyncio.sleep(0.1)

        if not port_connected(port):
            raise PhotonsAppError("Failed to start the server")

        try:
            log.info(f"Running server on http://127.0.0.1:{port}")
            webbrowser.open(f"http://127.0.0.1:{port}/index.html")
            await graceful_final_future
        finally:
            await app.shutdown()
            task.cancel()
            await hp.wait_for_all_futures(task, name="view_docs::execute_task[wait_for_server]")
