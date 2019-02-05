from photons_tile_paint.animation import Animation, Finish
from photons_tile_paint.options import AnimationOptions
from photons_themes.theme import ThemeColor as Color
from photons_tile_paint.addon import Animator
from photons_themes.canvas import Canvas

from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from delfick_logging import setup_logging
import asyncio
import logging
import random

log = logging.getLogger("tile_animation")

class Options(AnimationOptions):
    pass

class State:
    def __init__(self, coords):
        self.color = Color(random.randrange(0, 360), 1, 1, 3500)

        self.wait = 0
        self.filled = {}
        self.remaining = {}

        for (left, top), (width, height) in coords:
            for i in range(left, left + width):
                for j in range(top, top - height, -1):
                    self.remaining[(i, j)] = True

    def progress(self):
        next_selection = random.sample(list(self.remaining), k=min(len(self.remaining), 10))

        for point in next_selection:
            self.filled[point] = True
            del self.remaining[point]

class Animation(Animation):
    def setup(self):
        """This method can be used to do any extra setup for all tiles under the animation"""

    def next_state(self, prev_state, coords):
        """
        This is called for each tile set every time we refresh the light

        It takes in the previous state and the coords for the tiles
        we return the state that's passed in the next time this is called
        which is used in the make_canvas method
        """
        state = prev_state
        if state is None:
            state = State(coords)

        state.progress()

        if not state.remaining:
            self.acks = True
            state.wait += 1

        if state.wait == 2:
            self.every = 1
            self.duration = 1

        if state.wait == 3:
            raise Finish("Transition complete")

        return state

    def make_canvas(self, state, coords):
        """
        This is called for each tile set every time we want to refresh the state
        photons handles turning the points on the canvas into light on the tiles
        """
        canvas = Canvas()

        color = state.color
        if state.wait > 1:
            color = Color(0, 0, 0, 3500)

        for point in state.filled:
            canvas[point] = color

        return canvas

async def doit(collector):
    # Get the object that can talk to the devices over the lan
    lan_target = collector.configuration['target_register'].resolve("lan")

    # reference can be a single d073d5000001 string representing one device
    # Or a list of strings specifying multiple devices
    # Or a special reference like we have below
    # More information on special references can be found at https://delfick.github.io/photons-core/photons_app/special.html#photons-app-special
    reference = FoundSerials()

    # Create the animation from our classes defined ab ove
    animation = Animator(Animation, Options, "Example animation")

    # final_future is used for cleanup purposes
    final_future = asyncio.Future()

    # Options for our animation
    # In this example there aren't any extra options
    # The options has these two options by default https://github.com/delfick/photons-core/blob/master/photons_tile_paint/options.py#L32
    # See existing animations for an example of adding options, like https://github.com/delfick/photons-core/blob/master/photons_tile_paint/dice.py#L24
    options = {}

    try:
        # Run the animation
        async with lan_target.session() as afr:
            await animation.animate(lan_target, afr, final_future, reference, options)
    except Finish:
        pass
    except Exception as error:
        log.exception(error)
    finally:
        final_future.cancel()

if __name__ == '__main__':
    # Setup the logging
    setup_logging()

    # setup photons and get back the configuration
    collector = library_setup()

    # Get our asyncio loop
    loop = collector.configuration["photons_app"].loop

    # Run the animation!
    loop.run_until_complete(doit(collector))
