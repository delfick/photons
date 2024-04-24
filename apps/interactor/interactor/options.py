import os
import pathlib
import shutil
import subprocess

from delfick_project.norms import dictobj, sb
from interactor.zeroconf import Zeroconf
from photons_app.errors import PhotonsAppError
from photons_app.formatter import MergedOptionStringFormatter


class host_spec(sb.Spec):
    def normalise_empty(self, meta):
        return os.environ.get("INTERACTOR_HOST", "127.0.0.1")

    def normalise_filled(self, meta, val):
        return sb.string_spec().normalise(meta, val)


class port_spec(sb.Spec):
    def normalise_empty(self, meta):
        return int(os.environ.get("INTERACTOR_PORT", 6100))

    def normalise_filled(self, meta, val):
        return sb.integer_spec().normalise(meta, val)


class Assets(dictobj.Spec):
    src = dictobj.Field(
        sb.overridden("{interactor/../interactor_webapp/interactor:resource}"),
        formatted=True,
        help="Folder where we can find the source of the assets",
    )

    @property
    def dist(self) -> pathlib.Path:
        return pathlib.Path(self.src) / "build"

    def ensure_npm(self):
        if not shutil.which("npm"):
            raise PhotonsAppError("Couldn't find npm, I suggest you use nvm")

    @property
    def needs_install(self) -> bool:
        return (
            not os.path.exists(os.path.join(self.src, "node_modules"))
            or os.environ.get("REBUILD") == 1
        )

    def run(self, *args) -> None:
        subprocess.check_call(["npm", *args], cwd=self.src)


class Options(dictobj.Spec):
    host = dictobj.Field(host_spec, help="The host to serve the server on")

    port = dictobj.Field(port_spec, help="The port to serve the server on")

    assets = dictobj.Field(
        Assets.FieldSpec(formatter=MergedOptionStringFormatter),
        help="Options for where assets can be found",
    )

    zeroconf = dictobj.Field(
        Zeroconf.FieldSpec(formatter=MergedOptionStringFormatter),
        help="Options for zeroconf dns discovery",
    )

    database = dictobj.Field(
        lambda: __import__("interactor.database.database").database.database.Database.FieldSpec(
            formatter=MergedOptionStringFormatter
        ),
        help="Database options",
    )

    daemon_options = dictobj.Field(
        sb.dictionary_spec(),
        default={
            "search_interval": 30 * 60,
            "time_between_queries": {
                "LIGHT_STATE": 10 * 60,
                "GROUP": 13 * 60,
                "LOCATION": 16 * 60,
                "FIRMWARE": 24 * 3600,
            },
        },
        help="""
        Options for the device finder daemon. Defaults are::

            { "search_interval": 1800 # do a discovery every 30 minutes
            , "limit": 30 # Limit of 30 messages inflight at any one time
            , "time_between_queries": <shown below>
            }

        The time_between_queries is used to determine how long to between asking devices
        for particular information. It is a dictionary like the following::

            { "LIGHT_STATE": 10 * 60 # label, power, hsbk every 10 minutes
            , "VERSION": None # The type of product can be cached forever
            , "FIRMWARE": 24 * 3600 # Cache the firmware version for a day
            , "GROUP": 13 * 60 # Cache group information for 13 minutes
            , "LOCATION": 16 * 600 # Cache location information for 16 minutes
            }
    """,
    )
