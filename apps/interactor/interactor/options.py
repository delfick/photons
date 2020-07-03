from interactor.database.database import Database

from photons_app.formatter import MergedOptionStringFormatter

from delfick_project.norms import dictobj, sb


class Options(dictobj.Spec):
    host = dictobj.Field(
        sb.string_spec, default="localhost", help="The host to serve the server on"
    )

    port = dictobj.Field(sb.integer_spec, default=6100, help="The port to serve the server on")

    fake_devices = dictobj.Field(
        sb.boolean,
        default=False,
        help=""""
            Whether to look at the lan or use fake devices

            This is useful for integration tests
          """,
    )

    database = dictobj.Field(
        Database.FieldSpec(formatter=MergedOptionStringFormatter), help="Database options",
    )
