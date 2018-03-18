from photons_app.actions import available_actions

from docutils.parsers.rst import Directive
from docutils import statemachine
from textwrap import dedent

class Cache:
    @classmethod
    def tasks(kls, app):
        if hasattr(app.env, "tasks"):
            return app.env.tasks
        else:
            if not hasattr(kls, "_tasks"):
                from photons_app.sphinx import setup
                from photons_app.actions import all_tasks
                kls._tasks = all_tasks
            return kls._tasks

class ShowPhotonsTasksDirective(Directive):
    has_content = True

    def __init__(self, app):
        self.app = app

    def __call__(self, *args, **kwargs):
        super(ShowPhotonsTasksDirective, self).__init__(*args, **kwargs)
        return self

    def run(self):
        want = self.content[0]
        task = Cache.tasks(self.app)[want]

        template = ["TASK:: {0}".format(want)]
        target = None
        if len(self.content) > 1:
            target = self.content[1]

        action = available_actions[target][task.action]

        if action.target:
            template.extend(["    ``Uses {0} target by default``".format(action.target), ""])

        if action.needs_reference:
            template.extend(["    ``Needs a reference to be specified``", ""])

        if getattr(action, "__doc__"):
            for line in dedent(action.__doc__).lstrip().split("\n"):
                template.append("    {0}".format(line))

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

def setup(app):
    app.add_directive('photons_task', ShowPhotonsTasksDirective(app))
