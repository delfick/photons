from photons_tile_paint.marquee.animation import TileMarqueeAnimation, MarqueeDirection
from photons_tile_paint.options import BackgroundOption
from photons_tile_paint.font.base import Character

from photons_app import helpers as hp

from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

class TileNyanOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    user_coords = dictobj.Field(sb.boolean, default=False)
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)

    @property
    def direction(self):
        return MarqueeDirection.RIGHT

    @property
    def text_width(self):
        return 11

    @property
    def text_color(self):
        class Color:
            color = None
        return Color

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration

class NyanCharacter(Character):
    colors = {
          'c': Color(207, 0.47, 0.14, 3500)  # cyan
        , 'y': Color(60, 1, 0.11, 3500)  # yellow
        , 'w': Color(0, 0, 0.3, 3500)  # white
        , 'p': Color(345, 0.25, 0.12, 3500)  # pink
        , 'o': Color(24, 1, 0.07, 3500)  # orange
        , 'r': Color(0, 1, 0.15, 3500)  # red
        , 'b': Color(240, 1, 0.15, 3500)  # blue
        , 'g': Color(110, 1, 0.15, 3500)  # green
        }

Nyan1 = NyanCharacter("""
        ___________
        _oo________
        oyyoorppwpw
        yggywpppbwb
        gccggpppwww
        c__ccrpppr_
        ______w__w_
        ___________
    """)

Nyan2 = NyanCharacter("""
        ___________
        ___________
        o__oorpppr_
        yooyypppwpw
        gyygwpppbwb
        cggccrppwww
        _cc__w__w__
        ___________
    """)

class TileNyanAnimation(TileMarqueeAnimation):
    def characters(self, state):
        if state.x % 6 in (0, 1, 2):
            return [Nyan1]
        else:
            return [Nyan2]
