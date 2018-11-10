from photons_socket.target import SocketTarget

from photons_app.formatter import MergedOptionStringFormatter

from option_merge_addons import option_merge_addon_hook

__shortdesc__ = "A target for talking to devices over a socket"

@option_merge_addon_hook(extras=[
      ('lifx.photons', 'protocol')
    , ('lifx.photons', 'transport')
    , ('lifx.photons', 'messages')
    ])
def __lifx__(collector, *args, **kwargs):
    if "targets.lan" not in collector.configuration:
        collector.configuration[["targets", "lan"]] = {"type": "lan"}

@option_merge_addon_hook(post_register=True)
def __lifx_post__(collector, **kwargs):
    collector.configuration["target_register"].register_type("lan", SocketTarget.FieldSpec(formatter=MergedOptionStringFormatter))
