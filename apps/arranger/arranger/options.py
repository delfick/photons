import os
import shutil
import socket
import subprocess

from delfick_project.norms import dictobj, sb
from photons_app.errors import PhotonsAppError
from photons_app.formatter import MergedOptionStringFormatter


class port_spec(sb.Spec):
    def normalise_empty(self, meta):
        port = os.environ.get("ARRANGER_PORT", None)
        if port is not None and port != "0":
            return int(port)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            return s.getsockname()[1]

    def normalise_filled(self, meta, val):
        return sb.integer_spec().normalise(meta, val)


class host_spec(sb.Spec):
    def normalise_empty(self, meta):
        return os.environ.get("ARRANGER_HOST", "127.0.0.1")

    def normalise_filled(self, meta, val):
        return sb.string_spec().normalise(meta, val)


class Assets(dictobj.Spec):
    src = dictobj.Field(
        sb.overridden("{arranger/static:resource}"),
        formatted=True,
        help="Folder where we can find the source of the assets",
    )

    @property
    def dist(self):
        if os.environ.get("NODE_ENV", "production") == "development":
            return os.path.join(self.src, "dist", "dev")
        else:
            return os.path.join(self.src, "dist", "prod")

    def ensure_npm(self):
        if not shutil.which("npm"):
            raise PhotonsAppError("Couldn't find npm, I suggest you use nvm")

    @property
    def needs_install(self):
        return (
            not os.path.exists(os.path.join(self.src, "node_modules"))
            or os.environ.get("REBUILD") == 1
        )

    def run(self, *args, no_node_env=False):
        env = None
        if no_node_env:
            env = dict(os.environ)
            if "NODE_ENV" in env:
                del env["NODE_ENV"]
        subprocess.check_call(["npm", *args], cwd=self.src, **({} if env is None else {"env": env}))


class get_animation_options(sb.Spec):
    def normalise(self, meta, val):
        return meta.everything.get("animation_options", {})


class Options(dictobj.Spec):
    host = dictobj.Field(host_spec, default="127.0.0.1", help="The host to serve the server on")

    port = dictobj.Field(
        port_spec,
        help="The port to serve the server on. Not Specifying this will result in choosing a port on your computer that isn't currently in use",
    )

    assets = dictobj.Field(
        Assets.FieldSpec(formatter=MergedOptionStringFormatter),
        help="Options for where assets can be found",
    )

    animation_options = dictobj.Field(get_animation_options)
