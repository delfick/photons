from delfick_project.addons import addon_hook

__shortdesc__ = "A registry of LIFX products"


@addon_hook()
def __lifx__(collector, *args, **kwargs):
    pass
