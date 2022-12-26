from docutils import statemachine
from docutils.parsers.rst import Directive


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


def setup(app):
    app.add_directive("show_list", ShowListDirective)
