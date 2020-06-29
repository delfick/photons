from photons_canvas.animations.registered.marquee import (
    MarqueeAnimation,
    MarqueeDirection,
    direction_spec,
    State,
    Options,
)

from photons_app import helpers as hp

from photons_canvas.font import Character, Characters
from photons_canvas.animations import an_animation

from delfick_project.norms import dictobj


class Options(Options):
    direction = dictobj.Field(direction_spec(MarqueeDirection.RIGHT))


class NyanCharacter(Character):
    colors = {
        "c": (207, 0.47, 1, 3500),  # cyan
        "y": (60, 1, 1, 3500),  # yellow
        "w": (0, 0, 1, 3500),  # white
        "p": (345, 0.25, 1, 3500),  # pink
        "o": (24, 1, 1, 3500),  # orange
        "r": (0, 1, 1, 3500),  # red
        "b": (240, 1, 0.5, 3500),  # blue
        "g": (110, 1, 1, 3500),  # green
    }


Nyan1 = NyanCharacter(
    """
        ___________
        _oo________
        oyyoorppwpw
        yggywpppbwb
        gccggpppwww
        c__ccrpppr_
        ______w__w_
        ___________
    """
)

Nyan2 = NyanCharacter(
    """
        ___________
        ___________
        o__oorpppr_
        yooyypppwpw
        gyygwpppbwb
        cggccrppwww
        _cc__w__w__
        ___________
    """
)


class State(State):
    def setup(self):
        self.num = 0
        self.nyan = Nyan1

    @hp.memoized_property
    def characters(self):
        if self.nyan is Nyan1:
            self.nyan = Nyan2
        else:
            self.nyan = Nyan1

        return Characters(self.nyan)

    @property
    def next_layer(self):
        self.num += 1
        if self.num == 3:
            del self.characters
            self.num = 0

        return super().next_layer


@an_animation("nyan", Options)
class NyanAnimation(MarqueeAnimation):
    """
    Make a nyan cat like image keep going from left to right across your tiles.

    Tiles are aligned vertically, and so each row of tiles will have a duplicate
    of the animation.
    """

    make_state = State
