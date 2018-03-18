from docutils.parsers.rst import Directive
from docutils import statemachine
from textwrap import dedent

class ShowPhotonsTargetDirective(Directive):
    has_content = True

    def run(self):
        want = self.content[0]
        parts = want.split('.')
        template = []

        if len(parts) is 1:
            thing = __import__(want)
        else:
            thing = getattr(__import__('.'.join(parts[:-1]), globals(), locals(), [parts[-1]], 0), parts[-1])

        for field in sorted(thing.fields):
            options = thing.fields[field]
            if type(options) is tuple:
                template.extend([field] + ["    {0}".format(line) for line in dedent(options[0]).strip().split('\n')] + [""])

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

def setup(app):
    app.add_directive('photons_target_fields', ShowPhotonsTargetDirective)
