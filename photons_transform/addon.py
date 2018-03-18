from photons_transform.transformer import Transformer

from photons_app.actions import an_action

from option_merge_addons import option_merge_addon_hook

__shortdesc__ = "Helpers for creating messages for transforming the state of a device"

@option_merge_addon_hook(extras=[("lifx.photons", "colour")])
def __lifx__(collector, *args, **kwargs):
    pass

@an_action(needs_target=True, special_reference=True)
async def transform(collector, target, reference, **kwargs):
    """
    Do a http-api like transformation over whatever target you specify

    For example:

    ``transform d073d5000000 -- '{"color": "red", "effect": "pulse"}'``

    It takes in ``color``, ``effect``, ``power`` and valid options for a
    ``SetWaveformOptional``.
    """
    msg = Transformer.using(collector.configuration["photons_app"].extra_as_json)
    await target.script(msg).run_with_all(reference)
