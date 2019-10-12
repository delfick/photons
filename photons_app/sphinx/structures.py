from photons_products import Products

from docutils.parsers.rst import Directive
from docutils import statemachine
import enum


class ShowListDirective(Directive):
    has_content = True

    def run(self):
        want = self.content[0]
        parts = want.split(".")

        if len(parts) == 1:
            thing = __import__(want)
        else:
            thing = getattr(
                __import__(".".join(parts[:-1]), globals(), locals(), [parts[-1]], 0), parts[-1]
            )

        if len(self.content) > 1:
            thing = getattr(thing, self.content[1])

        template = []
        for name in sorted(repr(t) for t in thing):
            template.append("``{0}``".format(name))

        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1
        )
        tab_width = self.options.get("tab-width", self.state.document.settings.tab_width)
        lines = statemachine.string2lines("\n".join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []


class ShowDictionaryDirective(Directive):
    has_content = True

    def run(self):
        want = self.content[0]
        parts = want.split(".")

        if len(parts) == 1:
            thing = __import__(want)
        else:
            thing = getattr(
                __import__(".".join(parts[:-1]), globals(), locals(), [parts[-1]], 0), parts[-1]
            )

        if len(self.content) > 1:
            thing = getattr(thing, self.content[1])

        template = []
        for name in sorted(thing):
            template.extend([name, "    {0}".format(repr(thing[name])), ""])

        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1
        )
        tab_width = self.options.get("tab-width", self.state.document.settings.tab_width)
        lines = statemachine.string2lines("\n".join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []


class ShowRegexesDirective(Directive):
    has_content = True

    def run(self):
        want = self.content[0]
        parts = want.split(".")

        if len(parts) == 1:
            thing = __import__(want)
        else:
            thing = getattr(
                __import__(".".join(parts[:-1]), globals(), locals(), [parts[-1]], 0), parts[-1]
            )

        if len(self.content) > 1:
            thing = getattr(thing, self.content[1])

        template = []
        for name in sorted(thing):
            template.extend([name, "    ``{0}``".format(thing[name].pattern), ""])

        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1
        )
        tab_width = self.options.get("tab-width", self.state.document.settings.tab_width)
        lines = statemachine.string2lines("\n".join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []


class ShowCapabilitiesDirective(Directive):
    has_content = True

    def run(self):
        template = []
        for _, product in sorted(Products.by_pair.items()):
            template.extend(
                [product.name] + [f"    {line}" for line in list(self.fields_for(product))] + [""]
            )

        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1
        )
        tab_width = self.options.get("tab-width", self.state.document.settings.tab_width)
        lines = statemachine.string2lines("\n".join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

    def fields_for(self, product):
        def rr(v):
            if isinstance(v, str):
                return v
            elif isinstance(v, enum.Enum):
                return v.name
            else:
                return repr(v)

        found = []
        for attr, val in product.as_dict().items():
            if attr != "cap":
                found.append((attr, rr(val)))

        def make_table(found):
            max_name = max(len(n) for n, _ in found)
            max_value = max(len(v) for _, v in found)

            border = "{0} {1}".format("=" * max_name, "=" * max_value)
            yield border
            yield "attr{0} value{1}".format(" " * (max_name - 4), " " * (max_value - 5))
            yield border
            for n, v in found:
                yield "{0}{1} {2}".format(n, " " * (max_name - len(n)), v)
            yield border

        yield from make_table(found)

        found = []
        for attr, val in product.cap.items():
            found.append((attr, rr(val)))

        yield ""
        yield "Capabilities"
        yield ""
        yield from make_table(found)


def setup(app):
    app.add_directive("show_list", ShowListDirective)
    app.add_directive("show_regexes", ShowRegexesDirective)
    app.add_directive("show_dictionary", ShowDictionaryDirective)
    app.add_directive("show_capabilities", ShowCapabilitiesDirective)
