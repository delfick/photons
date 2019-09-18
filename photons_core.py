"""
Requiring this module will in turn require all the lifx-photons-core modules
"""
from delfick_project.addons import addon_hook

__shortdesc__ = "Requiring this module will in turn require all lifx-photons-core modules"

wanted = [
    "protocol",
    "transport",
    "control",
    "messages",
    "colour",
    "themes",
    "device_finder",
    "products_registry",
]


@addon_hook(extras=[("lifx.photons", comp) for comp in wanted])
def __lifx__(collector, *args, **kwargs):
    pass
