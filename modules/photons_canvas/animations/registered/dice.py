from photons_canvas.animations import Animation, Finish, an_animation, options
from photons_canvas import font

from delfick_project.norms import dictobj, sb
import itertools
import random


class Options(dictobj.Spec):
    num_iterations = dictobj.Field(sb.integer_spec, default=1)

    roll_time = dictobj.Field(sb.float_spec, default=2)
    dice_color = dictobj.Field(options.color_range_spec("rainbow"))

    num_rolls = dictobj.Field(sb.integer_spec, default=20)


class State:
    def __init__(self, num_rolls, color):
        self.rolls = num_rolls
        self.color = color

        self.dice = list(font.dice_8.values())
        self.cycle = iter(itertools.cycle(self.dice))

    def numbers(self, parts):
        chars = [char for char, _ in zip(self.cycle, parts)]
        random.shuffle(chars)
        return font.Characters(*chars)

    def result(self, parts):
        return font.Characters(*[random.choice(self.dice)] * len(parts))


@an_animation("dice", Options)
class TileDiceRollAnimation(Animation):
    """A dice roll"""

    align_parts_straight = True

    def setup(self):
        self.remaining = self.options.num_iterations

    async def process_event(self, event):
        if event.state is None and not event.is_sent_messages:
            self.every = TileDiceRollAnimation.every
            self.duration = TileDiceRollAnimation.duration
            self.acks = False
            event.state = State(self.options.num_rolls, self.options.dice_color.color)

        if not event.is_tick:
            return

        if self.options.num_iterations > 0 and self.remaining == 0:
            raise Finish("No more dice")

        rolls = event.state.rolls
        event.state.rolls -= 1

        if rolls == 0:
            self.every = 1
            self.acks = True
            return event.state.result(event.canvas.parts).layer(0, 0, event.state.color)

        if rolls == -1:
            self.every = 0.5
            self.duration = 0.5
            event.state = None
            self.remaining -= 1
            return lambda point, canvas: None

        return event.state.numbers(event.canvas.parts).layer(0, 0, event.state.color)
