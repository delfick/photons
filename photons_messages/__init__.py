"""
This module contains the definition of the LIFX binary protocol messages.

This includes the frame of the packet that is common to all messages.

See :ref:`lifx_binary_protocol` for the messages.
"""

# Get the parent packet
from photons_messages.frame import LIFXPacket

# Get the messages
from photons_messages.messages.lan import (
      CoreMessages, DiscoveryMessages
    , DeviceMessages, ColourMessages
    , MultiZoneMessages, TileMessages
    )

# Make the enums available straight from photons_messages
from photons_messages.enums import *

# Make this explicitly part of this module
LIFXPacket = LIFXPacket

def make_protocol_register():
    from photons_app.registers import ProtocolRegister

    protocol_register = ProtocolRegister()

    protocol_register.add(1024, LIFXPacket)
    message_register = protocol_register.message_register(1024)

    message_register.add(CoreMessages)
    message_register.add(DiscoveryMessages)
    message_register.add(DeviceMessages)
    message_register.add(ColourMessages)
    message_register.add(MultiZoneMessages)
    message_register.add(TileMessages)

    return protocol_register

protocol_register = make_protocol_register()
