from delfick_project.addons import addon_hook


@addon_hook(extras=[("lifx.photons", "protocol")])
def __lifx__(collector, *args, **kwargs):
    pass
