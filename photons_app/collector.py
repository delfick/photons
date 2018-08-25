"""
The collector is responsible for collecting configuration and photons_app
modules.

.. autoclass:: photons_app.collector.Collector
"""

from photons_app.option_spec.photons_app_spec import PhotonsAppSpec
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import BadYaml, BadConfiguration
from photons_app.task_finder import TaskFinder

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta

from option_merge_addons import Result, Addon, Register, AddonGetter
from option_merge.collector import Collector
from option_merge import MergedOptions

import pkg_resources
import asyncio
import logging
import yaml
import os

log = logging.getLogger("photons_app.collector")

class Collector(Collector):
    """
    This is based off
    http://option-merge.readthedocs.io/en/latest/docs/api/collector.html

    It overrides the following:

    .. automethod:: photons_app.collector.Collector.extra_prepare

    .. automethod:: photons_app.collector.Collector.extra_configuration_collection

    .. automethod:: photons_app.collector.Collector.extra_prepare_after_activation

    .. automethod:: photons_app.collector.Collector.add_configuration
    """
    _merged_options_formattable = True

    BadFileErrorKls = BadYaml
    BadConfigurationErrorKls = BadConfiguration

    def alter_clone_args_dict(self, new_collector, new_args_dict, options=None):
        return MergedOptions.using(
              new_args_dict
            , {"photons_app": self.configuration["photons_app"].as_dict()}
            , options or {}
            )

    def extra_prepare(self, configuration, args_dict):
        """
        Called before the configuration.converters are activated

        Here we make sure that we have photons_app options from ``args_dict`` in
        the configuration.

        We also load in ``__main__`` as if it were a photons_module. This means
        scripts can use ``option_merge_addon_hook`` and that will be used.

        We then load all the photons_app modules as specified by the
        ``photons_app.addons`` setting.

        Finally we inject into the configuration:

        $@
            The ``photons_app.extra`` setting

        collector
            This instance

        photons_app
            The photons_app settings

        final_future
            A future representing the end of the program.
        """
        photons_app = self.find_photons_app_options(configuration, args_dict)
        __main__ = self.determine_mainline_module()
        self.register = self.setup_addon_register(photons_app, __main__)

        # Add our special stuff to the configuration
        configuration.update(
            { "$@": photons_app.get("extra", "")
            , "collector": self
            , "photons_app": photons_app
            , "final_future": asyncio.Future()
            }
        , source = "<args_dict>"
        )

    def find_photons_app_options(self, configuration, args_dict):
        """Return us all the photons_app options"""
        d = lambda r: {} if r in (None, "", NotSpecified) else r
        return MergedOptions.using(
              dict(d(configuration.get('photons_app')).items())
            , dict(d(args_dict.get("photons_app")).items())
            ).as_dict()

    def determine_mainline_module(self):
        """Find us the __main__ module and add it to pkg_resources"""
        # Register __main__ as an entry point
        __main__ = None
        try:
            __main__ = __import__("__main__")
        except ImportError:
            pass
        else:
            if any(hasattr(getattr(__main__, attr, None), "_option_merge_addon_entry") for attr in dir(__main__)):
                working_set = pkg_resources.working_set
                dist = pkg_resources.Distribution("__main__")
                mp = pkg_resources.EntryPoint.parse_group("lifx.photons", ["__main__ = __main__"])

                def get_entry_map(group=None):
                    if group == "lifx.photons":
                        return mp
                    return {}
                dist.get_entry_map = get_entry_map
                working_set.add(dist, entry="__main__")
            else:
                __main__ = None

        return __main__

    def setup_addon_register(self, photons_app, __main__):
        """Setup our addon register"""
        # Create the addon getter and register the crosshair namespace
        self.addon_getter = AddonGetter()
        self.addon_getter.add_namespace("lifx.photons", Result.FieldSpec(), Addon.FieldSpec())

        # Initiate the addons from our configuration
        register = Register(self.addon_getter, self)

        if "addons" in photons_app:
            addons = photons_app["addons"]
            if type(addons) in (MergedOptions, dict) or getattr(addons, "is_dict", False):
                spec = sb.dictof(sb.string_spec(), sb.listof(sb.string_spec()))
                meta = Meta(photons_app, []).at("addons")
                for namespace, adns in spec.normalise(meta, addons).items():
                    register.add_pairs(*[(namespace, adn) for adn in adns])
        elif photons_app.get("default_activate_all_modules"):
            register.add_pairs(("lifx.photons", "__all__"))

        if __main__ is not None:
            register.add_pairs(("lifx.photons", "__main__"))

        # Import our addons
        register.recursive_import_known()

        # Resolve our addons
        register.recursive_resolve_imported()

        return register

    def extra_prepare_after_activation(self, configuration, args_dict):
        """
        Called after the configuration.converters are activated

        We also put a ``task_runner`` in the configuration for running tasks.

        .. code-block:: python

            await collector.configuration["task_runner"]("lan:find_devices", "d073d500000")

        This will determine the target and artifact for you given the
        configuration in the collector.
        """
        # Post register our addons
        extra_args = {"lifx.photons": {}}
        self.register.post_register(extra_args)

        # Make the task finder
        task_finder = TaskFinder(self)
        configuration["task_runner"] = task_finder.task_runner

    def home_dir_configuration_location(self):
        return os.path.expanduser("~/.photons_apprc.yml")

    def start_configuration(self):
        """Create the base of the configuration"""
        return MergedOptions(dont_prefix=[dictobj])

    def read_file(self, location):
        """Read in a yaml file and return as a python object"""
        with open(location) as fle:
            try:
                return yaml.load(fle)
            except (yaml.parser.ParserError, yaml.scanner.ScannerError) as error:
                raise self.BadFileErrorKls("Failed to read yaml"
                    , location = location
                    , error_type = error.__class__.__name__
                    , error = "{0}{1}".format(error.problem, error.problem_mark)
                    )

    def add_configuration(self, configuration, collect_another_source, done, result, src):
        """
        Used to add a file to the configuration, result here is the yaml.load
        of the src.

        If the configuration we're reading in has ``photons_app.extra_files``
        then this is treated as a list of strings of other files to collect.
        """
        # Make sure to maintain the original config_root
        if "config_root" in configuration:
            # if we already have a config root then we only keep new config root if it's not the home location
            # i.e. if it is the home configuration, we don't delete the new config_root
            if configuration["config_root"] != os.path.dirname(self.home_dir_configuration_location()):
                if "config_root" in result:
                    del result["config_root"]

        config_root = configuration.get("config_root")
        if config_root and src.startswith(config_root):
            src = "{{config_root}}/{0}".format(src[len(config_root) + 1:])

        configuration.update(result, source=src)

        if "photons_app" in result:
            if "extra_files" in result["photons_app"]:
                spec = sb.listof(sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter))
                config_root = {"config_root": result.get("config_root", configuration.get("config_root"))}
                meta = Meta(MergedOptions.using(result, config_root), []).at("photons_app").at("extra_files")
                for extra in spec.normalise(meta, result["photons_app"]["extra_files"]):
                    if os.path.abspath(extra) not in done:
                        if not os.path.exists(extra):
                            raise BadConfiguration("Specified extra file doesn't exist", extra=extra, source=src)
                        collect_another_source(extra)

    def extra_configuration_collection(self, configuration):
        """
        Hook to do any extra configuration collection or converter registration

        Here we register our base configuration converters:

        photons_app
            .. autoattribute:: photons_app.option_spec.photons_app_spec.PhotonsAppSpec.photons_app_spec

        targets
            .. autoattribute:: photons_app.option_spec.photons_app_spec.PhotonsAppSpec.targets_spec

        target_register
            .. autoattribute:: photons_app.option_spec.photons_app_spec.PhotonsAppSpec.target_register_spec

        protocol_register
            .. autoattribute:: photons_app.option_spec.photons_app_spec.PhotonsAppSpec.protocol_register_spec
        """
        photons_app_spec = PhotonsAppSpec()

        self.register_converters(
              { (0, ("targets", )): photons_app_spec.targets_spec
              , (0, ("photons_app", )): photons_app_spec.photons_app_spec
              , (0, ("target_register", )): photons_app_spec.target_register_spec
              , (0, ("protocol_register", )): photons_app_spec.protocol_register_spec
              , (0, ("reference_resolver_register", )): photons_app_spec.reference_resolver_register_spec
              }
            , Meta, configuration, sb.NotSpecified
            )
