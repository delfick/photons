from photons_app.actions import an_action

from photons_messages import Services

from delfick_project.addons import addon_hook
from delfick_project.norms import sb, Meta
import ipaddress
import binascii
import json

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

    Options include:

    cli_output - default True
        Print "{serial}: {ip}" for each device found

        Note that if you choose settings_output or env_output then this will
        default to False. Explicitly setting it to true will turn it on.

    settings_output - default False
        Print yaml output that you can copy into a lifx.yml

    env_output - default False
        Print an ENV variable you can copy into your terminal to set these
        ips as a HARDCODED_DISCOVERY for future commands.
    """
    broadcast = True
    if artifact not in (None, "", sb.NotSpecified):
        broadcast = artifact

    options = sb.set_options(
        cli_output=sb.defaulted(sb.boolean(), None),
        env_output=sb.defaulted(sb.boolean(), False),
        settings_output=sb.defaulted(sb.boolean(), False),
    ).normalise(Meta.empty(), collector.photons_app.extra_as_json)

    if options["env_output"] is False and options["settings_output"] is False:
        if options["cli_output"] is None:
            options["cli_output"] = True

    env_output = options["env_output"]
    cli_output = options["cli_output"]
    settings_output = options["settings_output"]

    ips = {}

    async with target.session() as sender:
        found, serials = await reference.find(sender, timeout=20, broadcast=broadcast)
        for serial in serials:
            services = found[binascii.unhexlify(serial)]
            if Services.UDP in services:
                ip = services[Services.UDP].host
                ips[serial] = ip

    sorted_ips = sorted(ips.items(), key=lambda item: ipaddress.ip_address(item[1]))

    if cli_output:
        for serial, ip in sorted_ips:
            print(f"{serial}: {ip}")

    if cli_output and (env_output or settings_output):
        print()

    if env_output:
        print(f"export HARDCODED_DISCOVERY='{json.dumps(sorted_ips)}'")
        if settings_output:
            print()

    if settings_output:
        print("discovery_options:")
        print("  hardcoded_discovery:")

        for serial, ip in sorted_ips:
            print(f'    {serial}: "{ip}"')
