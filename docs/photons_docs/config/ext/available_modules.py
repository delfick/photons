from docutils.parsers.rst import Directive
from docutils import statemachine
import pkg_resources
import os

class ShowAvailableModulesDirective(Directive):
    has_content = True

    def run(self):
        template = [".. toctree::", "    :hidden:", ""]

        deps = [e for e in pkg_resources.iter_entry_points("lifx.photons")]
        folder = os.path.dirname(self.state_machine.input_lines.source(0))

        found = []
        for e in deps:
            module_name = e.module_name.split(".")[0]
            found.append((module_name, e))

        for module_name, e in sorted(found):
            template.append("    modules/{0}".format(module_name))
            with open(os.path.join(folder, "modules", "{0}.rst".format(module_name)), 'w') as fle:
                lines = []
                lines.append(".. _{0}:".format(module_name))
                lines.append("")
                lines.append(module_name)
                lines.append("=" * len(module_name))
                lines.append("")
                lines.append(".. automodule:: {0}".format(module_name))
                fle.write("\n".join(lines))

        template.append("")

        for module_name, e in sorted(found):
            template.append(":ref:`{0}`".format(module_name))
            shortdesc = getattr(e.resolve(), "__shortdesc__", "This module has no __shortdesc__ property")
            template.append("    {0}".format(shortdesc))

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

def setup(app):
    app.add_directive('available_modules', ShowAvailableModulesDirective)
