from docutils.parsers.rst import Directive
from docutils import statemachine
import inspect

class ShowCodeForDirective(Directive):
    has_content = True

    def run(self):
        buf = []
        want = self.content[0].split('.')
        if len(want) is 1:
            thing = __import__('.'.join(want))
        else:
            buf = []
            mod = __import__('.'.join(want[:-1]), globals(), locals(), want[-1], 0)
            thing = getattr(mod, want[-1])
            if not isinstance(thing, type):
                for line in inspect.getsource(mod).split('\n'):
                    if line[:line.find('=')].strip() == want[-1]:
                        buf.append(line)
                    elif buf:
                        buf.append(line)
                        if line == "":
                            break

        if not buf:
            buf = inspect.getsource(thing).split('\n')

        template = ["", ".. code-block:: python", ""] + ["    {0}".format(line) for line in buf]

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

def setup(app):
    app.add_directive('code_for', ShowCodeForDirective)
