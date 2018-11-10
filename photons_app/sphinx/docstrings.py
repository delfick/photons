from input_algorithms.dictobj import dictobj

def process_dictobj_signature(app, what, name, obj, options, signature, return_annotation):
    if what == "class" and issubclass(obj, dictobj):
        try:
            from photons_messages import LIFXPacket
        except ImportError:
            pass
        else:
            if obj in (LIFXPacket, ):
                return signature, return_annotation

        args = []
        for f in sorted(obj.fields):
            if type(f) is tuple:
                args.append("{0}={1}".format(f[0], repr(f[1])))
            else:
                args.append(f)
        return ("({0})".format(", ".join(args)), return_annotation)

def process_dictobj_docstring(pp, what, name, obj, options, lines):
    if what == "class" and issubclass(obj, dictobj):
        for index, line in enumerate(lines):
            if line.strip() == ".. dictobj_params::":
                lines[index] = ""
                for_adding = [""]
                for f in sorted(obj.fields):
                    name = f
                    if type(name) is tuple:
                        name = name[0]

                    hlp = obj.fields[f]
                    if type(hlp) is tuple:
                        hlp = hlp[0]
                    for_adding.extend([name, "   {0}".format(hlp), ""])
                for line in reversed(for_adding):
                    lines.insert(index, line)

def setup(app):
    app.connect('autodoc-process-signature', process_dictobj_signature)
    app.connect('autodoc-process-docstring', process_dictobj_docstring)
