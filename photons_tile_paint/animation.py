from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from photons_themes.coords import user_coords_to_pixel_coords
from photons_tile_messages import TileMessages, tiles_from
from photons_products_registry import capability_for_ids
from photons_themes.theme import ThemeColor as Color
from photons_device_messages import DeviceMessages
from photons_themes.canvas import Canvas

from collections import defaultdict
import logging
import asyncio
import time

log = logging.getLogger("photons_tile_paint.animation")

class Finish(PhotonsAppError):
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
                serials.append(pkt.serial)

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

        async for pkt, _, _ in self.target.script(msgs).run_with(self.serials, self.afr):
            serial = pkt.serial

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

        await self.target.script(DeviceMessages.SetLightPower(level=65535, duration=1)).run_with_all(serials, self.afr)

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
