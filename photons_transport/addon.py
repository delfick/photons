from option_merge_addons import option_merge_addon_hook
from input_algorithms import spec_base as sb

from photons_script.script import ATarget
from photons_app.actions import an_action

__shortdesc__ = "Core classes for creating Photons targets"

@option_merge_addon_hook(extras=[("lifx.photons", "script")])
def __lifx__(*args, **kwargs):
    pass

@an_action(needs_target=True)
async def find_devices(collector, target, reference, **kwargs):
    """Print the devices that can be found"""
    broadcast = sb.NotSpecified
    if reference not in (None, "", sb.NotSpecified):
        broadcast = reference

    async with ATarget(target) as afr:
        for device in await target.get_list(afr, broadcast=broadcast):
            print(device)
