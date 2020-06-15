from photons_protocol.messages import Messages
from photons_messages.frame import LIFXPacket

from photons_messages.messages import *  # noqa
from photons_messages import messages

from photons_messages.enums import *  # noqa
from photons_messages import enums

from enum import Enum


def make_protocol_register():
    from photons_app.registers import ProtocolRegister

    protocol_register = ProtocolRegister()

    protocol_register.add(1024, LIFXPacket)
    message_register = protocol_register.message_register(1024)

    for kls in messages.__all__:
        kls = getattr(messages, kls)
        message_register.add(kls)

    return protocol_register


protocol_register = make_protocol_register()


def make_all_list():
    lst = ["protocol_register", "LIFXPacket", "messages"]

    for thing in dir(messages):
        if isinstance(getattr(messages, thing), Messages):
            lst.append(thing)

    for thing in dir(enums):
        if isinstance(getattr(enums, thing), Enum):
            lst.append(thing)

    return lst


__all__ = make_all_list()
