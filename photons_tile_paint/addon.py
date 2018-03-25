from photons_tile_paint.font.alphabet import characters as alphabet
from photons_tile_paint.pacman import state as pacman_state

from photons_app.actions import an_action
from photons_app import helpers as hp

from photons_themes.coords import user_coords_to_pixel_coords
from photons_tile_messages import TileMessages, tiles_from
from photons_products_registry import capability_for_ids
from photons_themes.theme import ThemeColor as Color
from photons_device_messages import DeviceMessages
from photons_script.script import ATarget
from photons_themes.canvas import Canvas

from option_merge_addons import option_merge_addon_hook
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from collections import defaultdict
import binascii
import logging
import asyncio
import time

log = logging.getLogger("photons_tile_paint.addon")

__shortdesc__ = "Utilities for painting on the tiles"

@option_merge_addon_hook(extras=[
      ("lifx.photons", "tile_messages"), ("lifx.photons", "themes"), ("lifx.photons", "device_messages")
    , ("lifx.photons", "products_registry")
    ])
def __lifx__(*args, **kwargs):
    pass

coords_for_horizontal_line = user_coords_to_pixel_coords(
      [ [(0, 0), (8, 8)]
      , [(1, 0), (8, 8)]
      , [(2, 0), (8, 8)]
      , [(3, 0), (8, 8)]
      , [(4, 0), (8, 8)]
      ]
    )

async def tile_serials_from_reference(target, reference, afr):
    """
    Given a reference, return all the serials that has a ``has_chain`` capability
    """
    serials = []

    async for pkt, _, _ in target.script(DeviceMessages.GetVersion()).run_with(reference, afr):
        if pkt | DeviceMessages.StateVersion:
            cap = capability_for_ids(pkt.product, pkt.vendor)
            if cap.has_chain:
                serials.append(binascii.hexlify(pkt.target[:6]).decode())

    return serials

def canvas_to_msgs(canvas, coords, duration=1, acks=True):
    for i, coord in enumerate(coords):
        colors = [c.as_dict() for c in canvas.points_for_tile(*coord[0], *coord[1])]

        yield TileMessages.SetTileState64(
              tile_index=i, length=1, x=0, y=0, width=coord[1][0], duration=duration, colors=colors
            , res_required = False
            , ack_required = acks
            )

def put_characters_on_canvas(canvas, chars, coords, fill_color=None):
    msgs = []
    for ch, coord in zip(chars, coords):
        if ch is None:
            continue

        canvas.set_all_points_for_tile(*coord[0], *coord[1], ch.get_color_func(fill_color))

    return msgs

class BackgroundOption(dictobj.Spec):
    type = dictobj.Field(sb.string_choice_spec(["specified", "current"]), default="specified")

    hue = dictobj.Field(sb.float_spec, default=0)
    saturation = dictobj.Field(sb.float_spec, default=0)
    brightness = dictobj.Field(sb.float_spec, default=0)
    kelvin = dictobj.Field(sb.float_spec, default=3500)

    @property
    def default_color(self):
        if self.type == "empty":
            return Color(0, 0, 0, 3500)
        else:
            return Color(self.hue, self.saturation, self.brightness, self.kelvin)

class TileStateGetter:
    class Info:
        def __init__(self, coords, default_color):
            self.states = []
            self.coords = coords
            self.default_color = default_color

        @hp.memoized_property
        def default_color_func(self):
            if not self.states:
                def get_empty(x, y):
                    return self.default_color
                return get_empty

            canvas = self.canvas

            def default_color_func(i, j):
                return canvas.get((i, j), dflt=Color(0, 0, 0, 3500))
            return default_color_func

        @property
        def canvas(self):
            canvas = Canvas()
            for i, state in sorted(self.states):
                colors = state.colors
                coords = self.coords

                if not coords:
                    continue

                if i >= len(coords):
                    continue

                (user_x, user_y), (width, height) = coords[i]

                rows = []
                pos = 0
                for j in range(height):
                    nxt = []
                    for i in range(width):
                        nxt.append(colors[pos])
                        pos += 1
                    rows.append(nxt)

                def get_color(x, y):
                    color = rows[y][x]
                    return Color(color.hue, color.saturation, color.brightness, color.kelvin)
                canvas.set_all_points_for_tile(user_x, user_y, width, height, get_color)
            return canvas

    def __init__(self, target, afr, serials, background_option, coords=None):
        self.afr = afr
        self.target = target
        self.coords = coords
        self.serials = serials
        self.background_option = background_option

        self.info_by_serial = defaultdict(lambda: self.Info(self.coords, self.background_option.default_color))

    @property
    def default_color_funcs(self):
        funcs = {}
        for serial in self.serials:
            funcs[serial] = self.info_by_serial[serial].default_color_func
        return funcs

    async def fill(self):
        msgs = []
        if self.background_option.type == "current":
            msgs.append(TileMessages.GetTileState64.empty_normalise(tile_index=0, length=255, x=0, y=0, width=8))

        if self.coords is None:
            msgs.append(TileMessages.GetDeviceChain())

        if not msgs:
            return

        async for pkt, _, _ in self.target.script(msgs).run_with(self.serials, self.afr, multiple_replies=True, first_wait=1):
            serial = binascii.hexlify(pkt.target[:6]).decode()

            if pkt | TileMessages.StateTileState64:
                self.info_by_serial[serial].states.append((pkt.tile_index, pkt))

            elif pkt | TileMessages.StateDeviceChain:
                coords = []
                for tile in tiles_from(pkt):
                    coords.append(((tile.user_x, tile.user_y), (tile.width, tile.height)))
                self.info_by_serial[serial].coords = user_coords_to_pixel_coords(coords)

class Animation:
    coords = None
    every = 1.5
    duration = 1
    acks = True

    def __init__(self, target, afr, options):
        self.afr = afr
        self.target = target
        self.options = options
        self.setup()

    def setup(self):
        pass

    def next_state(self, prev_state, coords):
        raise NotImplementedError()

    def make_canvas(self, state, coords):
        raise NotImplementedError()

    async def animate(self, reference):
        def errors(e):
            log.error(e)

        serials = await tile_serials_from_reference(self.target, reference, self.afr)
        state = TileStateGetter(self.target, self.afr, serials, self.options.background, coords=self.coords)
        await state.fill()

        coords_to_state = {}
        coords_to_serials = {}
        for serial in serials:
            coords = tuple(state.info_by_serial[serial].coords)
            if coords not in coords_to_serials:
                coords_to_serials[coords] = []
            coords_to_serials[coords].append(serial)
            coords_to_state[coords] = None

        log.info("Starting!")

        while True:
            start = time.time()

            msgs = []
            for coords, serials in coords_to_serials.items():
                coords_to_state[coords] = self.next_state(coords_to_state[coords], coords)
                canvas = self.make_canvas(coords_to_state[coords], coords)
                for serial in serials:
                    canvas.set_default_color_func(state.info_by_serial[serial].default_color_func)
                    for msg in canvas_to_msgs(canvas, coords, duration=self.duration, acks=self.acks):
                        msg.target = serial
                        msgs.append(msg)

            await self.target.script(msgs).run_with_all(None, self.afr, error_catcher=errors)

            diff = time.time() - start
            if diff < self.every:
                await asyncio.sleep(self.every - diff)

def ColorOption(h, s, b, k):
    class C(dictobj.Spec):
        hue = dictobj.Field(sb.float_spec, default=h)
        saturation = dictobj.Field(sb.float_spec, default=s)
        brightness = dictobj.Field(sb.float_spec, default=b)
        kelvin = dictobj.Field(sb.integer_spec, default=k)

        @property
        def color(self):
            return Color(self.hue, self.saturation, self.brightness, self.kelvin)
    return C.FieldSpec()

class TileTimeOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    hour24 = dictobj.Field(sb.boolean, default=True)
    number_color = dictobj.Field(ColorOption(200, 0.24, 0.5, 3500))
    progress_bar_color = dictobj.Field(ColorOption(0, 1, 0.4, 3500))
    full_height_progress = dictobj.Field(sb.boolean, default=False)

class TileMarqueeOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    text_color = dictobj.Field(ColorOption(200, 0.24, 0.5, 3500))
    text = dictobj.Field(sb.string_spec, wrapper=sb.required)
    user_coords = dictobj.Field(sb.boolean, default=False)

    @property
    def text_width(self):
        return len(self.text) * 8

class TilePacmanOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    user_coords = dictobj.Field(sb.boolean, default=False)

class TileTimeAnimation(Animation):
    every = 1.5
    duration = 1
    coords = coords_for_horizontal_line

    class State:
        def __init__(self, time_string, second):
            self.time_string = time_string
            self.second = second

    def next_state(self, prev_state, coords):
        localtime = time.localtime(time.time())
        second = localtime.tm_sec
        minute = localtime.tm_min
        hour = localtime.tm_hour
        if not self.options.hour24 and (hour > 12):
            hour = hour - 12
        if not self.options.hour24 and hour == 0:
            hour = 12

        return self.State("{:02d}:{:02d}".format(hour, minute), second)

    def make_canvas(self, state, coords):
        canvas = Canvas()

        line_length = (8 * 5) * (state.second / 60)
        (user_x, user_y), (width, height) = coords[0]
        if not self.options.full_height_progress:
            user_y  = user_y - height + 1
            height = 1

        def get_color(x, y):
            if x < line_length:
                return self.options.progress_bar_color.color
        canvas.set_all_points_for_tile(user_x, user_y, width * 5, height, get_color)

        put_characters_on_canvas(canvas, list(state.time_string), coords, self.options.number_color.color)
        return canvas

class TileMarqueeAnimation(Animation):
    every = 0.1
    acks = False
    coords = coords_for_horizontal_line
    duration = 0

    def setup(self):
        if self.options.user_coords:
            self.coords = None

    class State:
        def __init__(self, x):
            self.x = x

        def move_left(self, amount):
            return self.__class__(self.x - amount)

        def coords_for(self, original, characters):
            coords = []

            (left_x, top_y), (width, height) = original[0]
            left_x = left_x + self.x

            for char in characters:
                coords.append(((left_x, top_y), (char.width, height)))
                left_x += char.width

            return coords

    def next_state(self, prev_state, coords):
        right_x = 0
        left_x = 0
        for (user_x, top_y), (width, height) in coords:
            if user_x + width > right_x:
                right_x = user_x + width
            if user_x - self.options.text_width < left_x:
                left_x = user_x - self.options.text_width

        if prev_state is None:
            return self.State(right_x)

        nxt = prev_state.move_left(1)
        if nxt.x < left_x:
            nxt = self.State(right_x)

        return nxt

    @hp.memoized_property
    def characters(self):
        characters = []
        for ch in self.options.text:
            characters.append(alphabet[ch])
        return characters

    def make_canvas(self, state, coords):
        canvas = Canvas()
        put_characters_on_canvas(canvas, self.characters, state.coords_for(coords, self.characters), self.options.text_color.color)
        return canvas

class TilePacmanAnimation(Animation):
    every = 0.075
    acks = False
    coords = coords_for_horizontal_line
    duration = 0

    def setup(self):
        if self.options.user_coords:
            self.coords = None

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return pacman_state.start(coords)

        if prev_state.finished:
            return prev_state.swap_state(coords)

        return prev_state.move(1)

    def make_canvas(self, state, coords):
        canvas = Canvas()
        put_characters_on_canvas(canvas, state.characters, state.coords_for(coords))
        return canvas

@an_action(needs_target=True, special_reference=True)
async def tile_time(collector, target, reference, **kwargs):
    """Print time to the tiles"""
    extra = collector.configuration["photons_app"].extra_as_json
    options = TileTimeOptions.FieldSpec().normalise(Meta.empty(), extra)
    async with ATarget(target) as afr:
        await TileTimeAnimation(target, afr, options).animate(reference)

@an_action(needs_target=True, special_reference=True)
async def tile_marquee(collector, target, reference, **kwargs):
    """Print scrolling text to the tiles"""
    extra = collector.configuration["photons_app"].extra_as_json
    options = TileMarqueeOptions.FieldSpec().normalise(Meta.empty(), extra)
    async with ATarget(target) as afr:
        await TileMarqueeAnimation(target, afr, options).animate(reference)

@an_action(needs_target=True, special_reference=True)
async def tile_pacman(collector, target, reference, **kwargs):
    """Print scrolling text to the tiles"""
    extra = collector.configuration["photons_app"].extra_as_json
    options = TilePacmanOptions.FieldSpec().normalise(Meta.empty(), extra)
    async with ATarget(target) as afr:
        await TilePacmanAnimation(target, afr, options).animate(reference)
