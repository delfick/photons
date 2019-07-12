"""
A target encapsulates the logic for finding devices over a particular medium and
then talking to them over that medium.
"""
from photons_transport.session.memory import makeMemorySession
from photons_transport.session.network import NetworkSession
from photons_transport.targets.base import Target

from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj

class LanTarget(Target):
    """
    Knows how to talk to a device over the local network. It's one configuration
    option is default_broadcast which says what address to broadcast discovery
    if broadcast is given to run_with calls as True.
    """
    default_broadcast = dictobj.Field(sb.defaulted(sb.string_spec(), "255.255.255.255"))

    session_kls = NetworkSession

class MemoryTarget(Target):
    """
    Knows how to talk to fake devices as if they were on the network.
    """
    devices = dictobj.Field(sb.listof(sb.any_spec()), wrapper=sb.required)
    default_broadcast = dictobj.Field(sb.defaulted(sb.string_spec(), "255.255.255.255"))

    session_kls = makeMemorySession(NetworkSession)

__all__ = ["LanTarget", "MemoryTarget"]
