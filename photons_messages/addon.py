from delfick_project.addons import addon_hook

__shortdesc__ = "The LIFX binary message classes"

__doc__ = """
This module knows about all the messages in the LIFX binary protocol.
"""


@addon_hook(extras=[("lifx.photons", "protocol")])
def __lifx__(collector, *args, **kwargs):
    pass
