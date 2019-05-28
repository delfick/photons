from photons_app.formatter import MergedOptionStringFormatter
from photons_app.actions import an_action

from option_merge_addons import option_merge_addon_hook
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta

# Get us our actions
import photons_control.attributes
import photons_control.multizone
import photons_control.transform
import photons_control.payloads
import photons_control.colour
import photons_control.tile

__shortdesc__ = "Tasks and code for control of the devices"

@option_merge_addon_hook(extras=[
      ("lifx.photons", "messages")
    , ("lifx.photons", "colour")
    , ("lifx.photons", "products_registry")
    ])
def __lifx__(collector, *args, **kwargs):
    pass

@an_action(needs_target=True, special_reference=True)
async def find_devices(collector, target, reference, artifact, **kwargs):
    """
    List the devices that can be found on the network::

        lifx lan:find_devices

    You can specify a different broadcast address by saying::

        lifx lan:find_devices _ 192.168.0.255

    Otherwise it will use the default broadcast address for the target you are
    using. (i.e. the lan target by default broadcasts to 255.255.255.255)

    You can find specific devices by specifying a reference::

        lifx lan:find_devices match:label=kitchen
    """
    broadcast = True
    if artifact not in (None, "", sb.NotSpecified):
        broadcast = artifact

    async with target.session() as afr:
        _, serials = await reference.find(afr, timeout=20, broadcast=broadcast)
        for serial in serials:
            print(serial)
