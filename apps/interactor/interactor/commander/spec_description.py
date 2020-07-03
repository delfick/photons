from delfick_project.norms import sb


def signature(spec, default=None):
    """
    yield parts of a type information for this spec

    i.e. sb.integer_spec yields "integer"

    and sb.listof yields "[", <signature for child spec>, ", ... ]"

    Implemented for common specs.
    """
    if isinstance(spec, sb.integer_spec):
        yield "integer"
    elif isinstance(spec, sb.float_spec):
        yield "float"
    elif isinstance(spec, sb.boolean):
        yield "boolean"

    elif isinstance(spec, sb.string_choice_spec):
        choices = " | ".join(spec.choices)
        yield f"choice of ({choices})"
    elif isinstance(spec, sb.string_spec):
        yield "string"

    elif isinstance(spec, sb.dictof):
        yield "{"
        yield from signature(spec.name_spec, default="<item>")
        yield ":"
        yield from signature(spec.value_spec, default="<item>")
        yield "}"
    elif isinstance(spec, sb.dictionary_spec):
        yield "dictionary"

    elif isinstance(spec, sb.or_spec):
        specs = spec.specs
        if not specs:
            if default is not None:
                yield default
        else:
            for s in spec.specs[:-1]:
                yield from signature(s, default="<item>")
                yield "or"
            yield from signature(spec.specs[-1], default="<item>")

    elif isinstance(spec, sb.optional_spec):
        yield from signature(spec.spec)
        yield "(optional)"
    elif isinstance(spec, sb.defaulted):
        yield from signature(spec.spec)
        dflt = spec.default(None)
        if isinstance(dflt, str):
            dflt = f'"{dflt}"'
        yield f"(default {dflt})"
    elif isinstance(spec, sb.required):
        yield from signature(spec.spec)
        yield "(required)"
    elif isinstance(spec, sb.listof):
        yield "["
        yield from signature(spec.spec, default="<item>")
        yield ", ... ]"
    elif isinstance(spec, (sb.container_spec, sb.formatted)):
        yield from signature(spec.spec)
    elif default is not None:
        yield default
