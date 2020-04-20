from photons_transport.session.discovery_options import DiscoveryOptions
from photons_transport.targets import LanTarget

from photons_app.formatter import MergedOptionStringFormatter

from delfick_project.addons import addon_hook


@addon_hook()
def __lifx__(collector, *args, **kwargs):
    if "targets.lan" not in collector.configuration:
        collector.configuration[["targets", "lan"]] = {"type": "lan"}


@addon_hook(post_register=True)
def __lifx_post__(collector, **kwargs):
    collector.configuration["target_register"].register_type(
        "lan", LanTarget.FieldSpec(formatter=MergedOptionStringFormatter)
    )
    collector.register_converters(
        {"discovery_options": DiscoveryOptions.FieldSpec(formatter=MergedOptionStringFormatter)}
    )
