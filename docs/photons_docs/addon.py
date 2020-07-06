from photons_app.formatter import MergedOptionStringFormatter
from photons_app.actions import an_action, available_actions
from photons_app import actions as original_actions
from photons_app.errors import PhotonsAppError

from sphinx.util.docutils import docutils_namespace
from sphinx.cmdline import handle_exception
from sphinx.application import Sphinx

from tornado.web import StaticFileHandler, Application
from delfick_project.addons import addon_hook
from delfick_project.norms import dictobj, sb
from tornado.httpserver import HTTPServer
from textwrap import dedent
import pkg_resources
import webbrowser
import logging
import asyncio
import socket
import shutil
import time
import sys
import os

log = logging.getLogger("photons_docs")

this_dir = os.path.abspath(os.path.dirname(__file__))


class DocOptions(dictobj.Spec):
    out = dictobj.Field(wrapper=sb.required, format_into=sb.string_spec)
    src = dictobj.Field(wrapper=sb.required, format_into=sb.directory_spec)


@addon_hook()
def __lifx__(collector, *args, **kwargs):
    collector.register_converters(
        {"documentation": DocOptions.FieldSpec(formatter=MergedOptionStringFormatter)}
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


@an_action()
async def list_tasks(collector, tasks, reference=sb.NotSpecified, full_desc=False, **kwargs):
    if "for_docs" not in collector.configuration:
        return await original_actions.list_tasks(collector, tasks=tasks, **kwargs)

    print("To use, just use the executable with the name of the task you wish to run")
    print("")
    for name, task in tasks.items():
        if reference in ("", sb.NotSpecified, name):
            if task.label == "Docs":
                func = available_actions[None][name]
                desc = func.__doc__ or ""
                if not full_desc:
                    desc = dedent(desc).strip().split("\n")[0]
                    print(name, " - ", desc)
                else:
                    print(name)
                    print("-" * len(name))
                    print("\n".join("    {0}".format(line) for line in desc.split("\n")))


@an_action()
async def help(collector, *args, **kwargs):
    if "for_docs" not in collector.configuration:
        return await original_actions.help(collector, **kwargs)

    kwargs["full_desc"] = True
    return await list_tasks(collector, *args, **kwargs)


@an_action(label="Docs")
async def build_docs(collector, reference, tasks, **kwargs):
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
    options = collector.configuration["documentation"]

    reference_opts = [thing.strip() for thing in reference.split(",")]
    is_fresh = "fresh" in reference_opts
    force_all = "force" in reference_opts

    out = options.out
    tags = []
    jobs = 1
    srcdir = options.src
    confdir = pkg_resources.resource_filename("photons_docs", "config")
    builder = "html"
    verbosity = 0
    confoverrides = {}
    warningiserror = False

    outdir = os.path.join(out, "result")
    doctreedir = os.path.join(out, "doctree")

    if is_fresh and os.path.exists(out):
        shutil.rmtree(out)

    for d in (outdir, doctreedir):
        if not os.path.exists(d):
            os.makedirs(d)

    app = None
    try:
        with docutils_namespace():
            app = Sphinx(
                srcdir,
                confdir,
                outdir,
                doctreedir,
                builder,
                confoverrides,
                sys.stdout,
                sys.stderr,
                is_fresh,
                warningiserror,
                tags,
                verbosity,
                jobs,
            )
            app.builder.env.protocol_register = collector.configuration["protocol_register"]
            app.builder.env.tasks = tasks
            app.build(force_all, [])
            if app.statuscode != 0:
                sys.exit(app.statuscode)
    except (Exception, KeyboardInterrupt) as exc:
        opts = type("opts", (object,), {"pdb": False, "verbosity": verbosity, "traceback": True})
        handle_exception(app, opts, exc, sys.stderr)
        sys.exit(1)


@an_action(label="Docs")
async def view_docs(collector, reference, tasks, **kwargs):
    """
    View the built docs in your webbrowser.

    This will start serving the built documentation under http://127.0.0.1:4202
    and open your webbrowser to this address
    """
    directory = os.path.join(collector.configuration["documentation"].out, "result")
    http_server = HTTPServer(
        Application(
            [(r"/(.*)", StaticFileHandler, {"path": directory, "default_filename": "index.html"})]
        )
    )

    port = int(os.environ.get("PHOTONS_DOCS_PORT", 0))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", port))
        port = s.getsockname()[1]

    photons_app = collector.configuration["photons_app"]
    with photons_app.using_graceful_future() as final_future:
        http_server.listen(port, "127.0.0.1")

        start = time.time()
        while not port_connected(port) and time.time() - start < 3:
            await asyncio.sleep(0.1)

        if not port_connected(port):
            raise PhotonsAppError("Failed to start the server")

        try:
            log.info(f"Running server on http://127.0.0.1:{port}")
            webbrowser.open(f"http://127.0.0.1:{port}")
            await final_future
        finally:
            http_server.stop()
