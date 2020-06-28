"""
Requiring this module will in turn require all the lifx-photons-core modules
"""
from photons_app.executor import main

from delfick_project.option_merge import MergedOptionStringFormatter
from delfick_project.addons import addon_hook
import shlex
import sys
import os


wanted = [
    "control",
    "canvas",
    "transport",
]


@addon_hook(extras=[("lifx.photons", comp) for comp in wanted])
def __lifx__(collector, *args, **kwargs):
    pass


class CommandSplitter(MergedOptionStringFormatter):
    """
    This class let's you format a string into an array that can be used
    like sys.argv.

    For example:

    .. code-block:: python

        command = "{TARGET|lan:env}:{@:1} {@:2:}"
        result = CommandSplitter({"argv": ["my_script", "get_attr", "--silent"]}, command).split()
        assert result == ["lan:get_attr", "--silent"]

    Note that if when running that there was a ``TARGET`` variable in your
    environment then it would use that instead of the default ``lan`` specified.

    If you require the environment variable to exist then you can just say ``{TARGET:env}``

    Anything that is specified after a ``--`` will not be formatted. For example

    .. code-block:: python

        command = 'lan:transform {@:1:} -- {"power": "off"}'
        result = CommandSplitter({"argv": ["my_script", "match:cap=kitchen", "--silent"]}, command).split()
        assert result == ["lan:transform", "match:cap=kitchen", "--silent", "--", '{"power": "off"}']

    If the string after the ``--`` is wrapped with single quotes then the quotes
    will be stripped in the result.

    .. code-block:: python

        command = 'lan:transform {@:1:} -- '{"power": "off"}''
        result = CommandSplitter({"argv": ["my_script", "match:cap=kitchen", "--silent"]}, command).split()
        assert result == ["lan:transform", "match:cap=kitchen", "--silent", "--", '{"power": "off"}']
    """

    def get_string(self, key):
        return key

    def split(self):
        after = None
        if " -- " in self.value:
            self.value, after = self.value.split(" -- ", 1)
            self.value = self.value.strip()

        command = shlex.split(self.format())

        if after:
            after = after.strip()
            if after.startswith("'"):
                after = after[1:]
            if after.endswith("'"):
                after = after[:-1]
            command.extend(["--", after.strip()])

        return command

    def format_field(self, obj, format_spec):
        result = super().format_field(obj, format_spec)
        if result == " ":
            result = ""
        return result

    def special_get_field(self, value, args, kwargs, format_spec=None):
        return value, ()

    def special_format_field(self, obj, format_spec):
        """Know about any special formats"""
        if format_spec == "env":
            if not obj:
                raise Exception("env specifier used without saying what variable is needed")

            parts = obj.split("|")

            name = parts[0]
            if len(parts) == 1:
                if name not in os.environ:
                    raise sys.exit(
                        f"This script requires you have a '{name}' variable in your environment"
                    )
                return os.environ[name] or " "
            else:
                return os.environ.get(name, parts[1]) or " "

        elif obj == "@":
            if format_spec.isdigit():
                num = int(format_spec)
                if num > len(self.all_options["argv"]):
                    sys.exit(f"Needed greater than {num} arguments to the script")
                result = self.all_options["argv"][num]
            else:
                s = slice(*[None if not i else int(i) for i in format_spec.split(":")])
                result = self.all_options["argv"][s]

            if isinstance(result, list):
                result = " ".join(shlex.quote(arg) for arg in self.all_options["argv"][s])

            return result or " "


def run(command, *, argv=None, default_activate=None, **kwargs):
    """
    Run the photons mainline with arguments as specified by the command.

    This will enable the "core" module and all it's dependencies by default. To
    load no modules by default use ``default_activate=[]``. If you want only
    specific modules, then use ``default_activate=["transport"]``. If you want
    all available photons modules to be activated, use
    ``default_activate=["__all__"]``.

    The command may look something like::

        run("{TARGET|lan:env}:{@:1} {@:2:}")

    Which is the same as saying:

    .. code-block:: python

        target = os.environ.get("TARGET", "lan")
        main([f"{target}:{sys.argv[1]}"] + sys.argv[2:]])

    Note that if you have something like::

        "{TARGET:env}:transform -- '{"power": "on"}'"

    We will not try to format everything after the ``--``
    """
    if argv is not None:
        argv.insert(0, sys.argv[0])

    if isinstance(command, str):
        command = CommandSplitter({"argv": argv or sys.argv}, command).split()

    if default_activate is None:
        default_activate = ["core"]

    return main(command, default_activate=default_activate, **kwargs)
