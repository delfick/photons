import enum

from docutils import statemachine
from docutils.parsers.rst import Directive
from photons_products import Products


class ShowProductsDirective(Directive):
    has_content = True

    def run(self):
        template = []
        for _, product in sorted(Products.by_pair.items()):
            template.append(f"* :ref:`product_{product.name}`")

        template.append("")

        for _, product in sorted(Products.by_pair.items()):
            template.extend(
                [f".. _product_{product.name}:", "", product.name, "-" * len(product.name), ""]
                + [f"    {line}" for line in list(self.fields_for(product))]
                + [""],
            )

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
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

        def make_table(found, max_value=None, extra_name=""):
            max_name = max(len(n) for n, _ in found)
            if max_value is None:
                max_value = max(len(v) for _, v in found)

            border = f"{extra_name}{'=' * max_name} {'=' * max_value}"
            yield border
            for n, v in found:
                yield f"{n}{' ' * len(extra_name)}{' ' * (max_name - len(n))} {v}"
            yield border
            yield ""

        yield from make_table(found)

        found = []
        max_value = 0
        for attr, val in sorted(product.cap.Meta.capabilities.items()):
            found.append((f"cap.{attr}", val._value))
            max_value = max([max_value, len(str(val._value))])

            for ma, mi, becomes, conds in val.upgrades:
                if all(c(product.cap) for c in conds):
                    found.append((f"cap({ma}, {mi}).{attr}", becomes))
                    max_value = max([max_value, len(str(becomes))])

        yield from make_table(found, max_value=max_value, extra_name="====")


def setup(app):
    app.add_directive("show_products", ShowProductsDirective)
