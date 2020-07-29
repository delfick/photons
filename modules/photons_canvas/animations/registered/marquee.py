from photons_canvas.animations import Animation, an_animation, options, Finish
from photons_canvas.font import alphabet_8, Characters

from photons_app import helpers as hp

from photons_protocol.types import enum_spec

from delfick_project.norms import dictobj, sb
import enum


class MarqueeDirection(enum.Enum):
    LEFT = "left"
    RIGHT = "right"


class direction_spec(sb.Spec):
    def setup(self, dflt):
        self.dflt = dflt

    def normalise_empty(self, meta):
        return self.dflt

    def normalise_filled(self, meta, val):
        return enum_spec(None, MarqueeDirection, unpacking=True).normalise(meta, val)


class Options(dictobj.Spec):
    text = dictobj.Field(sb.string_spec, default="LIFX is awesome!")
    speed = dictobj.Field(options.range_spec(1, rate=True))
    text_color = dictobj.Field(options.color_range_spec("rainbow"))

    num_iterations = dictobj.Field(sb.integer_spec, default=-1)

    direction = dictobj.Field(direction_spec(MarqueeDirection.LEFT))
    switch_directions = dictobj.Field(sb.boolean, default=False)


class State:
    def __init__(self, options):
        self.options = options

        self._bounds = None

        self.left = None
        self.far_left = None
        self.far_right = None

        self.speed = options.speed()
        self.iteration = 0
        self.direction = self.options.direction

        self.setup()

    def setup(self):
        pass

    @hp.memoized_property
    def characters(self):
        return Characters(*[alphabet_8[ch] for ch in self.options.text])

    def add_iteration(self):
        self.iteration += 1

    @hp.memoized_property
    def color(self):
        return self.options.text_color.color

    @property
    def bounds(self):
        return self._bounds

    @bounds.setter
    def bounds(self, value):
        (left, right), _, _ = value

        self.far_left = left
        self.far_right = right

        self._bounds = value

    @property
    def next_layer(self):
        characters = self.characters

        if self.direction is MarqueeDirection.LEFT:
            if self.left is None:
                self.left = self.far_right
            else:
                self.left -= self.speed

            if self.left + characters.width == self.far_left:
                del self.color
                self.add_iteration()

                if self.options.switch_directions:
                    self.direction = MarqueeDirection.RIGHT
                else:
                    self.left = self.far_right

        else:
            if self.left is None:
                self.left = self.far_left - characters.width
            else:
                self.left += self.speed

            if self.left == self.far_right:
                del self.color
                self.add_iteration()

                if self.options.switch_directions:
                    self.direction = MarqueeDirection.LEFT
                else:
                    self.left = self.far_left - characters.width

        return characters.layer(self.left, 0, self.color)


@an_animation("marquee", Options)
class MarqueeAnimation(Animation):
    """
    Scrolling text over the tiles.

    Tiles are aligned vertically, and so each row of tiles will have a duplicate
    of the animation.

    The following options are recognised:

    text - string - default "LIFX is awesome!"
        The text to animate

    speed - :range: pixels to move per tick - default to 1
        The smaller the number, the slower the movement

    text_color - :color_range: - default to rainbow
        The colour to choose for each iteration.

    num_iterations - integer - default -1 (no limit)
        The number of times the text goes across the tiles before the animation
        ends.

    direction - "LEFT" or "RIGHT" - default LEFT
        Whether to move "LEFT" or to move "RIGHT"

    switch_directions - boolean - default False
        Whether to change direction when the text finishes an iteration.
    """

    switch_directions = False
    align_parts_vertically = True

    make_state = State

    async def process_event(self, event):
        if event.state is None:
            event.state = self.make_state(self.options)

        if event.is_new_device:
            event.state.bounds = event.canvas.bounds

        elif event.is_tick:

            if (
                self.options.num_iterations > 0
                and event.state.iteration >= self.options.num_iterations
            ):
                raise Finish("Reached maximum iterations")

            return event.state.next_layer
