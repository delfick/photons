"""
A target encapsulates the logic for finding devices over a particular medium and
then talking to them over that medium.
"""

from delfick_project.norms import dictobj, sb

from photons_transport.retry_options import Gaps
from photons_transport.session.discovery_options import discovery_options_spec
from photons_transport.session.network import NetworkSession
from photons_transport.targets.base import Target


class LanTarget(Target):
    """
    Knows how to talk to a device over the local network. It's one configuration
    option is default_broadcast which says what address to broadcast discovery
    if broadcast is given to sender calls as True.
    """

    gaps = dictobj.Field(
        Gaps(
            gap_between_results=0.4,
            gap_between_ack_and_res=0.2,
            timeouts=[(0.2, 0.2), (0.1, 0.5), (0.2, 1), (1, 5)],
        )
    )

    default_broadcast = dictobj.Field(sb.defaulted(sb.string_spec(), "255.255.255.255"))
    discovery_options = dictobj.Field(discovery_options_spec)

    session_kls = NetworkSession


__all__ = ["LanTarget"]
