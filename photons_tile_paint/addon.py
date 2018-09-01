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

def animation_action(name, animationkls, optionskls, __doc__):
    """
    Return an action that will create our options and provide them to the animation kls
    before running the animation
    """
    async def action(collector, target, reference, **kwargs):
        extra = collector.configuration["photons_app"].extra_as_json
        options = optionskls.FieldSpec().normalise(Meta.empty(), extra)
        async with ATarget(target) as afr:
            await animationkls(target, afr, options).animate(reference)

    action.__name__ = name
    action.__doc__ = __doc__

    return action

from photons_tile_paint.time.animation import TileTimeAnimation
from photons_tile_paint.time.options import TileTimeOptions
tile_time = an_action(needs_target=True, special_reference=True)(animation_action(
      "tile_time"
    , TileTimeAnimation, TileTimeOptions
    , """
      Print time to the tiles

      ``lifx lan:tile_time <reference>``
      """
    ))

from photons_tile_paint.marquee.animation import TileMarqueeAnimation
from photons_tile_paint.marquee.options import TileMarqueeOptions
tile_marquee = an_action(needs_target=True, special_reference=True)(animation_action(
      "tile_marquee"
    , TileMarqueeAnimation, TileMarqueeOptions
    , """
      Print scrolling text to the tiles

      ``lifx lan:tile_marquee <reference> -- '{"text": "hello there"}'``
      """
    ))

from photons_tile_paint.pacman.animation import TilePacmanAnimation
from photons_tile_paint.pacman.options import TilePacmanOptions
tile_pacman = an_action(needs_target=True, special_reference=True)(animation_action(
      "tile_pacman"
    , TilePacmanAnimation, TilePacmanOptions
    , """
      Make pacman go back and forth across your tiles

      ``lifx lan:tile_pacman <reference>``
      """
    ))

from photons_tile_paint.nyan import TileNyanAnimation
from photons_tile_paint.nyan import TileNyanOptions
tile_nyan = an_action(needs_target=True, special_reference=True)(animation_action(
      "tile_nyan"
    , TileNyanAnimation, TileNyanOptions
    , """
      Make nyan go back and forth across your tiles

      ``lifx lan:tile_nyan <reference>``
      """
    ))

from photons_tile_paint.gameoflife.animation import TileGameOfLifeAnimation
from photons_tile_paint.gameoflife.options import TileGameOfLifeOptions
tile_gameoflife = an_action(needs_target=True, special_reference=True)(animation_action(
      "tile_gameoflife"
    , TileGameOfLifeAnimation, TileGameOfLifeOptions
    , """
      Run a Conway's game of life simulation on the tiles

      ``lifx lan:tile_gameoflife <reference>``
      """
    ))
