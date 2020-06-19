from photons_app.actions import an_action

from photons_messages import Services

from delfick_project.addons import addon_hook
from delfick_project.norms import sb
import binascii

# Get us our actions
from photons_control.device_finder import DeviceFinder
import photons_control.attributes  # noqa
import photons_control.multizone  # noqa
import photons_control.transform  # noqa
import photons_control.payloads  # noqa
import photons_control.tile  # noqa


@addon_hook(extras=[("lifx.photons", "transport")])
def __lifx__(collector, *args, **kwargs):
    pass


@addon_hook(post_register=True)
def __lifx_post__(collector, **kwargs):
    def resolve(s):
        return DeviceFinder.from_url_str(s)

    collector.configuration["reference_resolver_register"].add("match", resolve)


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

    async with target.session() as sender:
        _, serials = await reference.find(sender, timeout=20, broadcast=broadcast)
        for serial in serials:
            print(serial)


@an_action(needs_target=True, special_reference=True)
async def find_ips(collector, target, reference, artifact, **kwargs):
    """
    List the ips of the devices that can be found on the network

        lifx lan:find_ips

    You can specify a different broadcast address by saying::

        lifx lan:find_ips 192.168.0.255
    """
    broadcast = True
    if artifact not in (None, "", sb.NotSpecified):
        broadcast = artifact

    async with target.session() as sender:
        found, serials = await reference.find(sender, timeout=20, broadcast=broadcast)
        for serial in serials:
            services = found[binascii.unhexlify(serial)]
            if Services.UDP in services:
                print(f"{serial}: {services[Services.UDP].host}")
