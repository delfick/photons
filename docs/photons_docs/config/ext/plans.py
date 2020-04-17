from photons_control.planner.plans import Plan, plan_by_key

from docutils.parsers.rst import Directive
from docutils import statemachine
import inspect


def plans():
    work = [Plan]
    subclasses = set()

    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)

    return subclasses


plans = plans()
plan_labels = {v: k for k, v in plan_by_key.items()}


class ShowPlansDirective(Directive):
    has_content = True

    def run(self):
        template = []

        ps = []
        ps_no_label = []

        for plan in plans:
            name = plan_labels.get(plan, plan.__name__)
            sig = f'``"{name}"``' if plan in plan_labels else f"{name}(...)"
            if plan in plan_labels:
                ps.append((name, sig, plan))
            else:
                ps_no_label.append((name, sig, plan))

        ps = sorted(ps, key=lambda i: i[0])
        ps.extend(sorted(ps_no_label, key=lambda i: i[-1].__name__))

        for name, sig, plan in ps:
            template.append(f"* :ref:`{name} <plan_{name}>`")

        template.append("")

        for name, sig, plan in ps:
            template.extend(list(self.explain_plan(name, sig, plan)))
            template.append("")

        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1
        )
        tab_width = self.options.get("tab-width", self.state.document.settings.tab_width)
        lines = statemachine.string2lines("\n".join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

    def explain_plan(self, name, sig, plan):
        yield from [f".. _plan_{name}:", "", sig, "+" * len(sig), ""]

        setup = plan.setup
        if setup is Plan.setup:
            sig = f"(refresh={plan.default_refresh})"
        else:
            sig = []
            for param in inspect.signature(setup).parameters.values():
                if param.kind is inspect.Parameter.VAR_KEYWORD:
                    param = param.replace(
                        name="refresh",
                        kind=inspect.Parameter.KEYWORD_ONLY,
                        default=plan.default_refresh,
                    )
                sig.append(str(param))
            sig = f"({', '.join(sig)})"

        yield f".. autoclass:: {plan.__module__}.{plan.__name__}{sig}"


def setup(app):
    app.add_directive("show_plans", ShowPlansDirective)
