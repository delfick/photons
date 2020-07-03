# coding: spec

from interactor.commander.spec_description import signature

from delfick_project.norms import sb

describe "signature":

    def assertSignature(self, spec, want):
        assert " ".join(signature(spec)) == want

    it "knows about integer_spec":
        self.assertSignature(sb.integer_spec(), "integer")

    it "knows about float_spec":
        self.assertSignature(sb.float_spec(), "float")

    it "knows about string_spec":
        self.assertSignature(sb.string_spec(), "string")

    it "knows about boolean":
        self.assertSignature(sb.boolean(), "boolean")

    it "knows about dictionary_spec":
        self.assertSignature(sb.dictionary_spec(), "dictionary")

    it "knows about string_choice_spec":
        self.assertSignature(sb.string_choice_spec(["one", "two"]), "choice of (one | two)")

    it "knows about optional_spec":
        self.assertSignature(sb.optional_spec(sb.integer_spec()), "integer (optional)")
        self.assertSignature(sb.optional_spec(sb.any_spec()), "(optional)")

    it "knows about defaulted":
        self.assertSignature(sb.defaulted(sb.integer_spec(), 20), "integer (default 20)")
        self.assertSignature(sb.defaulted(sb.any_spec(), True), "(default True)")

    it "knows about required":
        self.assertSignature(sb.required(sb.integer_spec()), "integer (required)")
        self.assertSignature(sb.required(sb.any_spec()), "(required)")

    it "knows about listof":
        self.assertSignature(sb.listof(sb.integer_spec()), "[ integer , ... ]")
        self.assertSignature(sb.listof(sb.any_spec()), "[ <item> , ... ]")

    it "knows about dictof":
        self.assertSignature(sb.dictof(sb.string_spec(), sb.integer_spec()), "{ string : integer }")
        self.assertSignature(sb.dictof(sb.string_spec(), sb.any_spec()), "{ string : <item> }")

    it "knows about container_spec":

        class Container:
            def __init__(self, value):
                pass

        self.assertSignature(sb.container_spec(Container, sb.string_spec()), "string")

    it "knows about formatted":
        self.assertSignature(sb.formatted(sb.string_spec(), formatter=None), "string")

    it "knows about or_spec":
        self.assertSignature(
            sb.or_spec(sb.string_spec(), sb.dictionary_spec()), "string or dictionary"
        )
        self.assertSignature(sb.or_spec(), "")
        self.assertSignature(sb.or_spec(sb.string_spec()), "string")
        self.assertSignature(sb.or_spec(sb.string_spec(), sb.any_spec()), "string or <item>")
        self.assertSignature(
            sb.or_spec(sb.string_spec(), sb.any_spec(), sb.boolean()), "string or <item> or boolean"
        )
