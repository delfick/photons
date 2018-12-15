"""
This module contains the definition of the LIFX binary protocol messages.

This includes the frame of the packet that is common to all messages.
"""

# Get the parent packet
from photons_messages.frame import LIFXPacket

# Get the messages
from photons_messages.messages import *
from photons_messages import messages

# Make the enums available straight from photons_messages
from photons_messages.enums import *

# Make this explicitly part of this module
LIFXPacket = LIFXPacket

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
