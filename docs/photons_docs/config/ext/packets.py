import enum
import inspect
from enum import EnumMeta
from textwrap import dedent

from delfick_project.norms import sb
from docutils import statemachine
from docutils.parsers.rst import Directive
from photons_messages import enums, protocol_register
from photons_messages.fields import (
    multizone_effect_parameters_for,
    tile_effect_parameters_for,
)
from photons_protocol.types import Type as T

enum_description = """
Some fields are enum values. This means the value on the binary packet is a
number, but Photons lets you interact with them as Enum values. This means
whenever you access an attribute that is an enum, you'll get back the enum
value rather than the number.

When you set a enum value you can use either the enum value itself, the number
that enum represents, or the name of the value. For example all of the following
do the same thing.

.. code-block:: python

    msg = TileMessages.SetTileEffect(...)

    # These are all valid ways of setting an enum value.
    msg.type = TileEffectType.MORPH
    msg.type = "MORPH"
    msg.type = 2

    # The value photons gives back to you is always an enum value
    assert msg.type is TileEffectType.MORPH

Photons will complain if the value you set is not a valid value for that type.
"""


class ShowPacketsDirective(Directive):
    has_content = True

    def run(self):
        template = [""]
        messages = protocol_register.message_register(1024)

        template.extend(list(self.messages_toc(messages)))
        template.append("")

        for kls in messages.message_classes:
            template.extend(list(self.message_group(kls)))

        title = "Message Objects"
        template.extend(["", ".. _message_objects:", "", title, "-" * len(title), ""])
        template.extend(list(self.message_objects(messages)))

        title = "Enums"
        template.extend(["", ".. _message_enums:", "", title, "-" * len(title), ""])
        template.extend(list(self.enums()))

        source = self.state_machine.input_lines.source(self.lineno - self.state_machine.input_offset - 1)
        tab_width = self.options.get("tab-width", self.state.document.settings.tab_width)
        lines = statemachine.string2lines("\n".join(template), tab_width, convert_whitespace=True)
        self.state_machine.insert_input(lines, source)
        return []

    def messages_toc(self, messages):
        for kls in messages.message_classes:
            name = kls.__name__
            if name in ("CoreMessages", "DiscoveryMessages"):
                continue

            yield f"* :ref:`{name}`"

        yield "* :ref:`message_objects`"
        yield "* :ref:`message_enums`"

    def message_group(self, kls):
        name = kls.__name__
        if name in ("CoreMessages", "DiscoveryMessages"):
            return

        yield from [f".. _{name}:", "", name, "-" * len(name), ""]

        for _, message in kls.by_type.items():
            message_name = f"{name}.{message.__name__}"
            yield f"* :ref:`{message_name}`"

        yield ""

        for _, message in kls.by_type.items():
            message_name = f"{name}.{message.__name__}"
            yield from self.for_message(message_name, message)

    def message_objects(self, messages):
        found = set()
        for kls in messages.message_classes:
            for _, message in kls.by_type.items():
                for typ in message.Payload.Meta.all_field_types_dict.values():
                    if typ._multiple and typ._multiple_kls:
                        name = typ._multiple_kls.__name__
                        if name in found:
                            continue
                        found.add(name)
                        yield f".. _message_type.{name}:"
                        yield ""
                        message_name = f"photons_messages.fields.{name}"
                        yield from self.for_message(message_name, typ._multiple_kls)
                        yield ""

    def enums(self):
        found = []
        services = None
        for name in dir(enums):
            thing = getattr(enums, name)
            if isinstance(thing, EnumMeta) and name != "Enum":
                if name == "Services":
                    services = thing
                else:
                    found.append((name, thing))
        found.insert(0, ("Services", services))

        yield from enum_description.split("\n")

        for name, e in found:
            enum_name = f"photons_messages.enums.{name}"
            yield from [f".. _enums.{name}:", "", enum_name, "+" * len(enum_name), ""]
            for value in e:
                if "reserved" not in value.name.lower():
                    yield f"* {str(value.value):3s}: {value.name}"
            yield ""

    def for_message(self, name, message):
        yield from [f".. _{name}:", "", name, "+" * len(name), ""]

        if hasattr(message, "Payload"):
            field_types = message.Payload.Meta.all_field_types
        else:
            field_types = message.Meta.all_field_types

        found = 0

        for attr, typ in field_types:
            if not isinstance(typ, T.Reserved.__class__):
                found += 1
                yield from self.explain_type(message, attr, typ)
                yield ""

        if not found:
            yield "This packet has no fields"
            yield ""
            return

    def explain_type(self, message, attr, typ):
        transformed = False
        type_name = typ.__class__.__name__.lower()
        if typ._allow_float:
            type_name = "float"

        if type_name in ("bytes", "string"):
            number = typ.size_bits // 8
            if typ._multiple:
                number = number * typ._multiple
            type_name = f"{type_name}[{number}]"

        line = f"{type_name} - {attr:12s}"

        yield line

        if typ._default:
            if typ._default is not sb.NotSpecified:
                if attr == "instanceid":
                    default = "``randomly generated number``"
                elif "set_" in attr:
                    default = f"``true only if {attr[4:]} is given a value``"
                elif callable(typ._default):
                    pkt = message.create(enabled=True)
                    default = typ._default(pkt)
                    if isinstance(default, enum.Enum):
                        enum_type, enum_name = str(default).rsplit(".", 1)
                        default = f":ref:`enums.{enum_type}`. **{enum_name}**"
                else:
                    default = f"``{typ._default}``"

                transformed = True
                yield f"    **default**: {default}"
                yield ""

        def get_func(func):
            s = inspect.getsource(func).strip()
            return s[s.find("lambda") :]

        if typ._optional and not message.__name__.startswith("State"):
            transformed = True
            yield "    **optional**: This attribute is optional"
            yield ""

        if typ._enum is not sb.NotSpecified:
            transformed = True
            e = typ._enum.__name__
            yield f"    **enum**: This attribute is a :ref:`enums.{e}`"
            yield ""

            if typ._unknown_enum_values:
                yield "    **unknown enums**: This attribute allows values that aren't part of the enum"

        if typ._transform is not sb.NotSpecified and message.__name__.startswith("Set"):
            transformed = True
            yield "    **transformed**: Value **you provide** is changed for the binary packet::"
            yield ""
            yield f"        {get_func(typ._transform)}"

        elif typ._unpack_transform is not sb.NotSpecified and message.__name__.startswith("State"):
            transformed = True
            yield "    **transformed**: value **from the packet** is changed for you::"
            yield ""
            yield f"        {get_func(typ._unpack_transform)}"

        if typ._dynamic is not sb.NotSpecified:
            transformed = True
            assert attr == "parameters"
            yield "    **dynamic**: This attribute turns into a packet like object with these fields::"
            yield ""

            if message.__name__.endswith("TileEffect"):
                func = tile_effect_parameters_for
            elif message.__name__.endswith("MultiZoneEffect"):
                func = multizone_effect_parameters_for
            else:
                assert False, f"unknown dymamic field {attr} for kls {message.__name__}"

            s = dedent(inspect.getsource(func))
            for line in s.split("\n"):
                yield f"        {line}"
            yield ""
            yield "    Using transformer::"
            yield ""
            yield f"        {get_func(typ._dynamic)}"
            yield ""
            yield "    You set parameters with a dictionary of fields"
            yield f"    and you can access the additional fields on ``{attr}``"
            yield f"    as if ``{attr}`` is it's own packet with those fields"

        if typ._multiple:
            transformed = True
            if typ._multiple_kls is not None:
                kls_name = typ._multiple_kls.__name__
                ref = f":ref:`{kls_name} <message_type.{kls_name}>`"
                yield f"    **multiple**: This attribute turns into an array of {typ._multiple} {ref} objects"
            else:
                yield f"    **multiple**: This attribute turns into an array of {typ._multiple} {typ.__class__.__name__}"

            yield ""

        if not transformed:
            yield "    This attribute has no transformations"


def setup(app):
    app.add_directive("show_packets", ShowPacketsDirective)
