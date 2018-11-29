from photons_app.formatter import MergedOptionStringFormatter

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
    ])
def __lifx__(collector, *args, **kwargs):
    pass
