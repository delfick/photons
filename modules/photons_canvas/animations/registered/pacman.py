# Characters borrowed from https://github.com/devonbeckett/LifxTile2DEngine

from photons_canvas.animations.registered.marquee import (
    MarqueeAnimation,
    MarqueeDirection,
    direction_spec,
    State,
    Options,
)

from photons_app import helpers as hp

from photons_canvas.font import Character, Characters, Space
from photons_canvas.animations import an_animation

from delfick_project.norms import dictobj, sb


class PacmanCharacter(Character):
    colors = {
        "c": (207, 0.47, 1, 3500),  # cyan
        "y": (60, 1, 1, 3500),  # yellow
        "w": (0, 0, 1, 3500),  # white
        "p": (345, 0.25, 1, 3500),  # pink
        "o": (24, 1, 1, 3500),  # orange
        "r": (0, 1, 1, 3500),  # red
        "b": (240, 1, 0.5, 3500),  # blue
    }


PacmanR2LOpen = PacmanCharacter(
    """
        __yyyy__
        _yyyyyy_
        __yyyyyy
        ___yyyyy
        ____yyyy
        __yyyyyy
        _yyyyyy_
        __yyyy__
    """
)

PacmanClosed = PacmanCharacter(
    """
        __yyyy__
        _yyyyyy_
        yyyyyyyy
        yyyyyyyy
        yyyyyyyy
        yyyyyyyy
        _yyyyyy_
        __yyyy__
    """
)

PacmanL2ROpen = PacmanCharacter(
    """
        __yyyy__
        _yyyyyy_
        yyyyyy__
        yyyyy___
        yyyy____
        yyyyyy__
        _yyyyyy_
        __yyyy__
    """
)

Blinky = PacmanCharacter(
    """
        __rrrr__
        _rrrrrr_
        _wwrwwr_
        rbwrbwrr
        rrrrrrrr
        rrrrrrrr
        rrrrrrrr
        _r_rr_r_
    """
)

Pinky = PacmanCharacter(
    """
        __pppp__
        _pppppp_
        _wwpwwp_
        pbwpbwpp
        pppppppp
        pppppppp
        pppppppp
        _p_pp_p_
    """
)

Inky = PacmanCharacter(
    """
        __cccc__
        _cccccc_
        _wwcwwc_
        cbwcbwcc
        cccccccc
        cccccccc
        cccccccc
        _c_cc_c_
    """
)

Clyde = PacmanCharacter(
    """
        __oooo__
        _oooooo_
        _wwowwo_
        obwobwoo
        oooooooo
        oooooooo
        oooooooo
        _o_oo_o_
    """
)

Ghost = PacmanCharacter(
    """
        __bbbb__
        _bbbbbb_
        _bbwbwb_
        bbbwbwbb
        bbbbbbbb
        bwbwbwbb
        bbwbwbwb
        _b_bb_b_
    """
)


class Options(Options):
    direction = dictobj.Field(direction_spec(MarqueeDirection.RIGHT))
    switch_directions = dictobj.Field(sb.boolean, default=True)


class State(State):
    def setup(self):
        self.num = 0
        self.pacman = PacmanL2ROpen

    @hp.memoized_property
    def characters(self):
        if self.direction == MarqueeDirection.RIGHT:
            return Characters(
                self.make_pacman(),
                Space(2),
                Ghost,
                Space(2),
                Ghost,
                Space(2),
                Ghost,
                Space(2),
                Ghost,
            )
        else:
            return Characters(
                self.make_pacman(),
                Space(2),
                Blinky,
                Space(2),
                Pinky,
                Space(2),
                Inky,
                Space(2),
                Clyde,
            )

    def make_pacman(self):
        if self.direction == MarqueeDirection.RIGHT:
            if self.pacman is PacmanL2ROpen:
                self.pacman = PacmanClosed
            else:
                self.pacman = PacmanL2ROpen
        else:
            if self.pacman is PacmanR2LOpen:
                self.pacman = PacmanClosed
            else:
                self.pacman = PacmanR2LOpen

        return self.pacman

    def add_iteration(self):
        self.num = 0
        del self.characters
        super().add_iteration()

    @property
    def next_layer(self):
        self.num += 1
        if self.num == 4:
            del self.characters
            self.num = 0

        return super().next_layer


@an_animation("pacman", Options)
class PacmanAnimation(MarqueeAnimation):
    """
    Make pacman and his "friends" go back and forth across your tiles

    Tiles are aligned vertically, and so each row of tiles will have a duplicate
    of the animation.
    """

    make_state = State
