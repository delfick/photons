from docutils.parsers.rst import Directive
from docutils import statemachine

class Cache:
    @classmethod
    def protocol_register(kls, app):
        if hasattr(app.env, "protocol_register"):
            return app.env.protocol_register
        else:
            if not hasattr(kls, "_protocol_register"):
                from photons_app.sphinx.setup import collector
                kls._protocol_register = collector.configuration["protocol_register"]
            return kls._protocol_register

class ShowMessagesDirective(Directive):
    has_content = True

    def __init__(self, app):
        self.app = app

    def __call__(self, *args, **kwargs):
        super(ShowMessagesDirective, self).__init__(*args, **kwargs)
        return self

    def run(self):
        wanted = None
        protocol = 1024

        if len(self.content) > 0:
            wanted = self.content[0]

        if len(self.content) > 1:
            protocol = int(self.content[1])

        protocol_register = Cache.protocol_register(self.app)
        klses = protocol_register.message_register(protocol).message_classes

        if wanted and "." in wanted:
            want = wanted.split('.')
            mod = __import__('.'.join(want[:-1]), globals(), locals(), want[-1], 0)
            kls = getattr(mod, want[-1])
            klses = list(klses) + [kls]
            wanted = kls.__name__

        template = []
        for name, kls in sorted([(kls.__name__, kls) for kls in klses]):
            if name != "Messages" and wanted in (name, None):
                template.extend([name, "-" * len(name)])
                if getattr(kls, "__doc__", None):
                    template.extend([line for line in kls.__doc__.split("\n")])
                    template.append("")

                found = sorted(kls.by_type.items())
                if not found:
                    found = []
                    for attr in dir(kls):
                        msg = getattr(kls, attr)
                        if hasattr(msg, "Meta"):
                            found.append((None, msg))

                for num, msg in found:
                    if num is not None:
                        title = "{0} - {1}".format(num, msg.__name__)
                    else:
                        title = msg.__name__

                    template.extend([title, '+' * len(title)])
                    template.extend(["", "``{1}.{2}.{3}``".format(num, kls.__module__, kls.__name__, msg.__name__), ""])
                    template.extend(["", ".. code-block:: python", ""])
                    for line in msg.Meta.caller_source.split("\n"):
                        template.append("    {0}".format(line))
                    template.append("")

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
        lines = statemachine.string2lines('\n'.join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

def setup(app):
    app.add_directive('lifx_messages', ShowMessagesDirective(app))
