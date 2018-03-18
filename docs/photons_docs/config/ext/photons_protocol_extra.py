from photons_protocol.types import Type as T

from docutils.parsers.rst import Directive
from docutils import statemachine

import json
import re

class ShowProtocolTypesDirective(Directive):
    has_content = True

    def run(self):
        template = []

        found = []
        for name in dir(T):
            thing = getattr(T, name)
            if isinstance(thing, T):
                found.append((name, thing))

        for name, thing in sorted(found):
            template.append("T.{0}".format(name))

            for line in self.describe(thing):
                template.append("    {0}".format(line))

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

    def describe(self, typ):
        if typ.size_bits is not NotImplemented:
            yield "``{0}`` bits of data".format(typ.size_bits)
            yield ""

        if typ.struct_format is not NotImplemented:
            if typ.struct_format is bool:
                yield "1 bit as a boolean"
            else:
                yield "``{0}`` struct format".format(typ.struct_format)
            yield ""

        converter = re.compile("<(?:class|built-in function) '?(\w+)'?>")
        if typ.conversion is json:
            yield "Converts as ``json``"
        else:
            yield "Converts as ``{0}``".format(converter.sub(r"\1", repr(typ.conversion)))
        yield ""

def setup(app):
    app.add_directive('photons_protocol_types', ShowProtocolTypesDirective)
