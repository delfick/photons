"""
``photons_socket.messages.Services``
    .. code_for:: photons_socket.messages.Services

.. lifx_messages:: DiscoveryMessages
"""
from photons_protocol.messages import Messages, msg, T

from enum import Enum

class Services(Enum):
    """The different services a device exposes"""
    UDP       = 1
    RESERVED1 = 2
    RESERVED2 = 3
    RESERVED3 = 4
    RESERVED4 = 5

class DiscoveryMessages(Messages):
    """
    Messages related to Discovery
    """
    Acknowledgment = msg(45)

    GetService = msg(2)
    StateService = msg(3
        , ("service", T.Uint8.enum(Services))
        , ("port", T.Uint32)
        )
