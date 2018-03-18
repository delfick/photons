from photons_app.errors import PhotonsAppError
from photons_app import errors

from docutils.parsers.rst import Directive
from docutils import statemachine
import pkg_resources
import os

class ShowPhotonsErrorsModulesDirective(Directive):
    has_content = True

    def run(self):
        template = []

        for name in dir(errors):
            thing = getattr(errors, name)
            if thing is PhotonsAppError:
                continue

            if isinstance(thing, type) and issubclass(thing, PhotonsAppError):
                template.extend([
                      ".. autoclass:: photons_app.errors.{0}".format(name)
                    , ""
                    , "    {0}".format(thing.desc)
                    , ""]
                    )

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

def setup(app):
    app.add_directive('photons_errors', ShowPhotonsErrorsModulesDirective)
