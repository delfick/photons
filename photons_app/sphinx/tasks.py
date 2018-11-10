from photons_app.actions import available_actions

from docutils.parsers.rst import Directive
from collections import defaultdict
from docutils import statemachine
from textwrap import dedent
import inspect

class ShowModuleTasks(Directive):
    has_content = True

    def __init__(self, app):
        self.app = app

    def __call__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        return self

    def run(self):
        if self.content:
            wanted = self.content[0]
        else:
            source = self.state.document.current_source
            tail = source[source.rfind(":", 1) + 1:]
            if not tail.startswith("docstring of "):
                raise Exception(f"Couldn't determine module\tsource={source}")

            wanted = tail[13:].split(".")[0]

        available = defaultdict(list)

        for target, actions in available_actions.items():
            for name, action in actions.items():
                module = inspect.getmodule(action)
                parent_module = module.__name__.split(".")[0]
                if parent_module == "photons_docs":
                    continue
                equal = wanted == "*" or module.__name__ == wanted
                child = module.__name__.startswith(f"{wanted}.")
                if equal or child:
                    available[parent_module].append((name, target, action))

        template = []

        if len(available) == 1:
            actions = list(available.values())[0]
            for name, target, action in reversed(sorted(actions)):
                template.extend(lines_for_task(name, target, action))
        else:
            for module, actions in sorted(available.items()):
                template.append(f"From ``{module}``")

                for name, target, action in reversed(sorted(actions)):
                    for line in lines_for_task(name, target, action):
                        template.append(f"    {line}")

                template.append("")

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines("\n".join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)

        return []

def lines_for_task(task_name, target, action):
    def lines():
        yield (1, "")

        if target:
            yield (1, f"* needs a {target} type target")

        if action.needs_reference:
            yield (1, f"* Needs a reference to be specified")

        if action.special_reference:
            yield (1, f"* Can take in a special reference")

        if action.special_reference and not action.needs_reference:
            yield (1, f"* not specifying a reference will result in finding all devices on the network")

        if action.needs_target:
            yield (1, f"* Needs a target to be specified")

        if getattr(action, "__doc__"):
            for line in dedent(action.__doc__).lstrip().split("\n"):
                yield (2, line)

    ls = list(lines())
    mx = max(len(l) for _, l in ls)
    mx = max([mx, len(task_name)])

    current = 1

    yield ""
    yield f"+{'-' * (mx + 2)}+"
    yield f"| {task_name}{' ' * (mx - len(task_name))} |"
    yield f"+{'=' * (mx + 2)}+"

    for num, line in ls:
        if num != current:
            yield f"+{'-' * (mx + 2)}+"
            current = num
        yield f"| {line}{' ' * (mx - len(line))} |"
    yield f"+{'-' * (mx + 2)}+"
    yield ""

def setup(app):
    app.add_directive('photons_module_tasks', ShowModuleTasks(app))
