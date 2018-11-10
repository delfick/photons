from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_colour import Parser

from input_algorithms import spec_base as sb

@an_action(needs_target=True, special_reference=True)
async def set_color(collector, target, reference, artifact, **kwargs):
    """
    Change specified bulb to specified colour

    ``target:set_color d073d50000 red -- '{"hue": 205}'``

    The format of this task is ``<reference> <color> -- <overrides>`` where
    overrides is optional.

    The color may be any valid color specifier.
    """
    overrides = {}
    if collector.configuration["photons_app"].extra:
        overrides = collector.configuration["photons_app"].extra_as_json

    if artifact in (None, "", sb.NotSpecified):
        raise PhotonsAppError("Please specify a color as artifact")

    msg = Parser.color_to_msg(artifact, overrides)
    await target.script(msg).run_with_all(reference)
