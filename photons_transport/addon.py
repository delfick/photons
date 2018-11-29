from option_merge_addons import option_merge_addon_hook
from input_algorithms import spec_base as sb

from photons_app.actions import an_action

__shortdesc__ = "Core classes for creating Photons targets"

@option_merge_addon_hook()
def __lifx__(*args, **kwargs):
    pass

@an_action(needs_target=True)
async def find_devices(collector, target, reference, **kwargs):
    """
    List the devices that can be found on the network

    ``target:find_devices <broadcast>``

    If you specify a broadcast (i.e. 192.168.0.255) then it will broadcast the
    discovery messages to that address.

    Otherwise it will use the default broadcast address for the target you are
    using. (i.e. the lan target by default broadcasts to 255.255.255.255)
    """
    broadcast = sb.NotSpecified
    if reference not in (None, "", sb.NotSpecified):
        broadcast = reference

    async with target.session() as afr:
        for device in await target.get_list(afr, broadcast=broadcast):
            print(device)
