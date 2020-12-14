"""
This is where the mainline sits and is responsible for setting up the logging,
the argument parsing and for starting up the App.

This class is extended in Photons Apps to provide custom startup functionalities.
"""

from photons_app.collector import Collector
from photons_app import VERSION

from delfick_project.app import App, OptionalFileType
from delfick_project.norms import sb
import sys
import os


def library_setup(
    config_filename="lifx.yml", photons_modules=True, extra_files=None, photons_app_options=None
):
    """
    Get us a setup photons Collector instance.

    config_filename
        Optionally provide the filename of configuration to read in and parse

    photons_modules
        If this is set to True then all photons modules in your environment will
        be activated. If it is an array, then only the modules in that array
        will be activated.

        If you only want modules from photons-core then say photons_modules=["core"]

    extra_files
        Optionally provide extra configuration files to load in

    photons_app_options
        Options to instantiate the photons_app object with.

    This function returns :ref:`photons_app_collector`.
    """
    photons_app = photons_app_options if photons_app_options is not None else {}

    def init_addons(adns):
        if "addons" not in photons_app:
            photons_app["addons"] = {}

        if "lifx.photons" not in photons_app["addons"]:
            photons_app["addons"]["lifx.photons"] = adns

    if photons_modules is True:
        init_addons(["__all__"])
    elif type(photons_modules) is str:
        init_addons([photons_modules])
    elif type(photons_modules) is list:
        init_addons(photons_modules)

    collector = Collector()
    collector.prepare(config_filename, {"photons_app": photons_app}, extra_files=extra_files)
    collector.configuration["target_register"].add_targets(collector.configuration["targets"])
    return collector


class App(App):
    """
    The app is based on `delfick-project App <https://delfick-project.readthedocs.io/en/latest/api/app.html>`_
    and is responsible for several things:

    * Reading in environment variables
    * Reading in positional and keyword commandline arguments
    * Getting a target from the task argument
    * Making photons silent for the ``list_tasks`` and ``help`` tasks
    * Setting up logging
    * Creating and starting the ``Collector``
    * Starting the chosen task
    * Cleanly stopping the asyncio event loop

    Environment variables we look at are:

    .. photons_app_environment_defaults::
    """

    VERSION = VERSION
    cli_categories = ["photons_app"]
    cli_description = "Photons server!"
    cli_environment_defaults = {"LIFX_CONFIG": ("--config", "./lifx.yml")}
    cli_positional_replacements = [
        ("--task", "list_tasks"),
        ("--reference", sb.NotSpecified),
        ("--artifact", sb.NotSpecified),
    ]

    silent_by_default_environ_name = "PHOTONS_SILENT_BY_DEFAULT"

    def mainline(self, argv=None, print_errors_to=sys.stdout, **execute_args):
        original_argv = argv
        if argv is None:
            argv = sys.argv[1:]

        if len(argv) == 0:
            os.environ["PHOTONS_SILENT_BY_DEFAULT"] = "1"

        elif len(argv) >= 1:
            task = argv[0]
            if ":" in task:
                task = task.split(":", 1)[1]

            if task in ("list_tasks", "help"):
                os.environ["PHOTONS_SILENT_BY_DEFAULT"] = "1"

        super(App, self).mainline(original_argv, print_errors_to, **execute_args)

    def setup_collector(self, args_dict, logging_handler, extra_files):
        """Create and initialize a collector"""
        config_name = None
        if args_dict["photons_app"]["config"] is not sb.NotSpecified:
            config_name = args_dict["photons_app"]["config"].name

        collector = Collector()
        collector.prepare(config_name, args_dict, extra_files=extra_files)
        if "term_colors" in collector.configuration:
            self.setup_logging_theme(logging_handler, colors=collector.configuration["term_colors"])

        collector.configuration["target_register"].add_targets(collector.configuration["targets"])

        return collector

    def execute(
        self,
        args_obj,
        args_dict,
        extra_args,
        logging_handler,
        extra_files=None,
        default_activate=None,
    ):
        args_dict["photons_app"]["config"] = args_dict["photons_app"]["config"] or sb.NotSpecified
        args_dict["photons_app"]["extra"] = extra_args
        args_dict["photons_app"]["debug"] = args_dict["debug"] or args_obj.debug
        args_dict["photons_app"]["default_activate"] = default_activate

        collector = self.setup_collector(args_dict, logging_handler, extra_files)

        task_runner = collector.configuration["task_runner"]

        target, task = collector.photons_app.task_specifier()
        collector.run_coro_as_main(task_runner(target, task), catch_delfick_error=False)

    def specify_other_args(self, parser, defaults):
        parser.add_argument(
            "--dry-run",
            help="Should we take any real action or print out what is intends to do",
            dest="photons_app_dry_run",
            action="store_true",
        )

        parser.add_argument(
            "--task",
            help="The task to run",
            dest="photons_app_task_specifier",
            **defaults["--task"]
        )

        parser.add_argument(
            "--artifact",
            help="Extra information",
            dest="photons_app_artifact",
            **defaults["--artifact"]
        )

        parser.add_argument(
            "--reference",
            help="A selector for the lights",
            dest="photons_app_reference",
            **defaults["--reference"]
        )

        parser.add_argument(
            "--config",
            help="Config file to read from",
            dest="photons_app_config",
            type=OptionalFileType("r"),
            **defaults["--config"]
        )

        return parser


main = App.main


def lifx_main(*args, **kwargs):
    """
    Used by the lifx script

    If there is no configuration, or the configuration doesn't specify addons
    then we default to activating all photons modules in the environment.
    """
    kwargs["default_activate"] = ["__all__"]
    return main(*args, **kwargs)


if __name__ == "__main__":
    main()
