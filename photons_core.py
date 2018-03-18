"""
Requiring this module will in turn require all the lifx-photons-core modules
"""
from option_merge_addons import option_merge_addon_hook

__shortdesc__ = "Requiring this module will in turn require all lifx-photons-core modules"

wanted = [
      "protocol"
    , "script"
    , "socket"
    , "transform"
    , "attributes"
    , "colour"
    , "themes"
    , "device_messages"
    , "multizone"
    , "device_finder"
    , "tile_messages"
    , "products_registry"
    ]

@option_merge_addon_hook(extras=[("lifx.photons", comp) for comp in wanted])
def __lifx__(collector, *args, **kwargs):
    pass
