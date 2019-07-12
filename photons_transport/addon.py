from photons_transport.targets import LanTarget

from photons_app.formatter import MergedOptionStringFormatter

from option_merge_addons import option_merge_addon_hook

__shortdesc__ = "The logic for communicating with devices"

@option_merge_addon_hook()
def __lifx__(collector, *args, **kwargs):
    if "targets.lan" not in collector.configuration:
        collector.configuration[["targets", "lan"]] = {"type": "lan"}

@option_merge_addon_hook(post_register=True)
def __lifx_post__(collector, **kwargs):
    collector.configuration["target_register"].register_type("lan", LanTarget.FieldSpec(formatter=MergedOptionStringFormatter))
