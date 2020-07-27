from photons_app.formatter import MergedOptionStringFormatter

from delfick_project.norms import dictobj, sb
import os


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


class Options(dictobj.Spec):
    host = dictobj.Field(host_spec, help="The host to serve the server on")

    port = dictobj.Field(port_spec, help="The port to serve the server on")

    database = dictobj.Field(
        lambda: __import__("interactor.database.database").database.database.Database.FieldSpec(
            formatter=MergedOptionStringFormatter
        ),
        help="Database options",
    )
