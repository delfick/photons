from interactor.commander.errors import NoSuchCommand
from interactor.commander import helpers as ihp
from interactor.commander.store import store

from delfick_project.norms import dictobj, sb
from textwrap import dedent


@store.command(name="help")
class HelpCommand(store.Command):
    """
    Display the documentation for the specified command
    """

    path = store.injected("path")
    store = store.injected("store")

    command = dictobj.Field(sb.string_spec, default="help", help="The command to show help for")

    @property
    def command_kls(self):
        available = self.store.paths[self.path]
        if self.command not in available:
            raise NoSuchCommand(wanted=self.command, available=sorted(available))
        return available[self.command]["kls"]

    async def execute(self):
        header = f"Command {self.command}"
        kls = self.command_kls
        doc = dedent(getattr(kls, "__help__", kls.__doc__))

        fields = ihp.fields_description(kls)
        fields_string = ""
        if fields:
            fields_string = ["", "Arguments\n---------", ""]
            for name, type_info, desc in fields:
                fields_string.append(f"{name}: {type_info}")
                for line in desc.split("\n"):
                    if not line.strip():
                        fields_string.append("")
                    else:
                        fields_string.append(f"\t{line}")
                fields_string.append("")
            fields_string = "\n".join(fields_string)

        extra = ""
        if self.command == "help":
            extra = "\nAvailable commands:\n{}".format(
                "\n".join(f" * {name}" for name in sorted(self.store.paths[self.path]))
            )

        return f"{header}\n{'=' * len(header)}\n{doc}{fields_string}{extra}"
