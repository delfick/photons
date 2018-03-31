from photons_app.actions import an_action

from photons_script.script import ATarget

from option_merge_addons import option_merge_addon_hook
from input_algorithms.meta import Meta

__shortdesc__ = "Utilities for painting on the tiles"

@option_merge_addon_hook(extras=[
      ("lifx.photons", "tile_messages"), ("lifx.photons", "themes"), ("lifx.photons", "device_messages")
    , ("lifx.photons", "products_registry")
    ])
def __lifx__(*args, **kwargs):
    pass

@an_action(needs_target=True, special_reference=True)
async def tile_time(collector, target, reference, **kwargs):
    """
    Print time to the tiles

    ``lifx lan:tile_time <reference>``
    """
    from photons_tile_paint.time.animation import TileTimeAnimation
    from photons_tile_paint.time.options import TileTimeOptions

    extra = collector.configuration["photons_app"].extra_as_json
    options = TileTimeOptions.FieldSpec().normalise(Meta.empty(), extra)
    async with ATarget(target) as afr:
        await TileTimeAnimation(target, afr, options).animate(reference)

@an_action(needs_target=True, special_reference=True)
async def tile_marquee(collector, target, reference, **kwargs):
    """
    Print scrolling text to the tiles

    ``lifx lan:tile_marquee <reference> -- '{"text": "hello there"}'``
    """
    from photons_tile_paint.marquee.animation import TileMarqueeAnimation
    from photons_tile_paint.marquee.options import TileMarqueeOptions

    extra = collector.configuration["photons_app"].extra_as_json
    options = TileMarqueeOptions.FieldSpec().normalise(Meta.empty(), extra)
    async with ATarget(target) as afr:
        await TileMarqueeAnimation(target, afr, options).animate(reference)

@an_action(needs_target=True, special_reference=True)
async def tile_pacman(collector, target, reference, **kwargs):
    """
    Make pacman go back and forth across your tiles

    ``lifx lan:tile_pacman <reference>``
    """
    from photons_tile_paint.pacman.animation import TilePacmanAnimation
    from photons_tile_paint.pacman.options import TilePacmanOptions

    extra = collector.configuration["photons_app"].extra_as_json
    options = TilePacmanOptions.FieldSpec().normalise(Meta.empty(), extra)
    async with ATarget(target) as afr:
        await TilePacmanAnimation(target, afr, options).animate(reference)
