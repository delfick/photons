from photons_app.executor import App

from docutils.parsers.rst import Directive
from docutils import statemachine
import pkg_resources
import os

class ShowPhotonsEnvVarsModulesDirective(Directive):
    has_content = True

    def run(self):
        template = []

        for name, val in sorted(App.cli_environment_defaults.items()):
            template.extend([
                  name
                , "    Sets a value for {0} and defaults to {1}".format(val[0], repr(val[1]))
                , ""
                ])

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

class ShowPhotonsCliArgsModulesDirective(Directive):
    has_content = True

    def run(self):
        app = App()
        cli_parser = app.make_cli_parser()
        _, _, defaults = cli_parser.split_args([])
        parser = cli_parser.make_parser(defaults)

        template = [".. code-block:: text", ""]
        for line in parser.format_help().split("\n"):
            template.append("    {0}".format(line))

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

def setup(app):
    app.add_directive('photons_app_cli_args', ShowPhotonsCliArgsModulesDirective)
    app.add_directive('photons_app_environment_defaults', ShowPhotonsEnvVarsModulesDirective)
