from option_merge_addons import option_merge_addon_hook

__shortdesc__ = "The LIFX binary message classes"

__doc__ = """
This module knows about all the messages in the LIFX binary protocol.
"""

@option_merge_addon_hook(extras=[
      ("lifx.photons", "protocol")
    ])
def __lifx__(collector, *args, **kwargs):
    pass
