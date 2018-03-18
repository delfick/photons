from photons_app.formatter import MergedOptionStringFormatter
from photons_app.actions import an_action, available_actions
from photons_app import actions as original_actions

from sphinx.util.docutils import docutils_namespace
from sphinx.cmdline import handle_exception
from sphinx.application import Sphinx

from option_merge_addons import option_merge_addon_hook
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta
from textwrap import dedent
import pkg_resources
import logging
import shutil
import sys
import os

log = logging.getLogger("photons_docs.addon")

__shortdesc__ = "Entry point for creating documentation"

class DocOptions(dictobj.Spec):
    out = dictobj.Field(wrapper=sb.required, format_into=sb.string_spec)
    src = dictobj.Field(wrapper=sb.required, format_into=sb.directory_spec)

@option_merge_addon_hook()
def __lifx__(collector, *args, **kwargs):
    collector.register_converters(
          { (0, ("documentation", )): DocOptions.FieldSpec(formatter=MergedOptionStringFormatter)
          }
        , Meta, collector.configuration, sb.NotSpecified
        )

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
                    desc = dedent(desc).strip().split('\n')[0]
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

    photons_app_symlink_location = os.path.join(out, "photons_app")
    if not os.path.exists(photons_app_symlink_location):
        os.symlink(pkg_resources.resource_filename("photons_app", "docs"), photons_app_symlink_location)

    app = None
    try:
        with docutils_namespace():
            app = Sphinx(
                  srcdir, confdir, outdir, doctreedir, builder
                , confoverrides, sys.stdout, sys.stderr, is_fresh
                , warningiserror, tags, verbosity, jobs
                )
            app.builder.env.protocol_register = collector.configuration["protocol_register"]
            app.builder.env.tasks = tasks
            app.build(force_all, [])
            if app.statuscode != 0:
                sys.exit(app.statuscode)
    except (Exception, KeyboardInterrupt) as exc:
        opts = type("opts", (object, ), {"pdb": False, "verbosity": verbosity, "traceback": True})
        handle_exception(app, opts, exc, sys.stderr)
        sys.exit(1)
