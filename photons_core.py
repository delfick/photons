"""
Requiring this module will in turn require all the lifx-photons-core modules
"""
from option_merge_addons import option_merge_addon_hook

__shortdesc__ = "Requiring this module will in turn require all lifx-photons-core modules"

wanted = [
      "protocol"
    , "socket"
    , "control"
    , "messages"
    , "colour"
    , "themes"
    , "device_finder"
    , "products_registry"
    ]

@option_merge_addon_hook(extras=[("lifx.photons", comp) for comp in wanted])
def __lifx__(collector, *args, **kwargs):
    pass
