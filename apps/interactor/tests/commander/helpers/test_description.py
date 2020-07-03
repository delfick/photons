# coding: spec

from interactor.commander import helpers as ihp

from delfick_project.norms import dictobj, sb

describe "fields_description":
    it "only gets fields that have help specified":

        class Thing(dictobj.Spec):
            one = dictobj.Field(sb.integer_spec)

            two = dictobj.Field(
                sb.integer_spec,
                default=20,
                help="""
                    two
                    is
                    good
                  """,
            )

            three = dictobj.Field(sb.string_spec, wrapper=sb.required, help="three")

        got = list(ihp.fields_description(Thing))

        assert got == [
            ("two", "integer (default 20)", "two\nis\ngood"),
            ("three", "string (required)", "three"),
        ]
