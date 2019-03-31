from photons_tile_paint.set_64 import set_64_maker

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from photons_messages import LightMessages, DeviceMessages, TileMessages
from photons_control.tile import tiles_from, orientations_from
from photons_themes.coords import user_coords_to_pixel_coords
from photons_control.orientation import Orientation as O
from photons_products_registry import capability_for_ids
from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas
from photons_control import orientation

from collections import defaultdict
import logging
import asyncio
import random
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

def canvas_to_msgs(canvas, coords, duration=1, acks=True, orientations=None):
    for i, coord in enumerate(coords):
        colors = canvas.points_for_tile(*coord[0], *coord[1])
        if orientations:
            colors = orientation.reorient(colors, orientations.get(i, O.RightSideUp))

        yield set_64_maker(
              tile_index = i
            , width = coord[1][0]
            , duration = duration
            , colors = colors
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
            self.orientations = {}
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
                o = orientation.reverse_orientation(self.orientations.get(i, O.RightSideUp))
                colors = orientation.reorient(colors, o)

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

    async def fill(self, random_orientations=False):
        msgs = []
        if self.background_option.type == "current":
            msgs.append(TileMessages.Get64.empty_normalise(tile_index=0, length=255, x=0, y=0, width=8))

        msgs.append(TileMessages.GetDeviceChain())

        async for pkt, _, _ in self.target.script(msgs).run_with(self.serials, self.afr):
            serial = pkt.serial

            if pkt | TileMessages.State64:
                self.info_by_serial[serial].states.append((pkt.tile_index, pkt))

            elif pkt | TileMessages.StateDeviceChain:
                if self.coords is None:
                    coords = []
                    for tile in tiles_from(pkt):
                        coords.append(((tile.user_x, tile.user_y), (tile.width, tile.height)))
                    self.info_by_serial[serial].coords = user_coords_to_pixel_coords(coords)

                orientations = orientations_from(pkt)
                if random_orientations:
                    self.info_by_serial[serial].orientations = {i: random.choice(list(O.__members__.values())) for i in orientations}
                else:
                    self.info_by_serial[serial].orientations = orientations

class Animation:
    acks = False
    every = 0.075
    coords = None
    duration = 0
    random_orientations = False

    def __init__(self, target, afr, options):
        self.afr = afr
        self.target = target
        self.options = options

        if getattr(self.options, "user_coords", False) or getattr(self.options, "combine_tiles", False):
            self.coords = None

        self.setup()

    def setup(self):
        pass

    def next_state(self, prev_state, coords):
        raise NotImplementedError()

    def make_canvas(self, state, coords):
        raise NotImplementedError()

    async def animate(self, reference, final_future, pauser=None):
        if pauser is None:
            pauser = asyncio.Condition()

        def errors(e):
            log.error(e)

        serials = await tile_serials_from_reference(self.target, reference, self.afr)
        state = TileStateGetter(self.target, self.afr, serials, self.options.background, coords=self.coords)
        await state.fill(random_orientations=self.random_orientations)

        by_serial = {}
        for serial in serials:
            by_serial[serial] = {
                  "state": None
                , "coords": tuple(state.info_by_serial[serial].coords)
                }

        log.info("Starting!")

        await self.target.script(LightMessages.SetLightPower(level=65535, duration=1)).run_with_all(serials, self.afr)

        combined_coords = []
        for info in by_serial.values():
            combined_coords.extend(info["coords"])
        combined_info = {"state": None}

        while True:
            start = time.time()

            combined_canvas = None
            if getattr(self.options, "combine_tiles", False):
                combined_state = combined_info["state"] = self.next_state(combined_info["state"], combined_coords)
                combined_canvas = self.make_canvas(combined_state, combined_coords)

            msgs = []
            for serial, info in by_serial.items():
                coords = info["coords"]

                canvas = combined_canvas
                if canvas is None:
                    info["state"] = self.next_state(info["state"], coords)
                    canvas = self.make_canvas(info["state"], coords)

                canvas.set_default_color_func(state.info_by_serial[serial].default_color_func)
                orientations = state.info_by_serial[serial].orientations
                for msg in canvas_to_msgs(canvas, coords, duration=self.duration, acks=self.acks, orientations=orientations):
                    msg.target = serial
                    msgs.append(msg)

            async with pauser:
                if final_future.done():
                    break
                await self.target.script(msgs).run_with_all(None, self.afr, error_catcher=errors, limit=None)

            if final_future.done():
                break

            diff = time.time() - start
            if diff < self.every:
                await asyncio.sleep(self.every - diff)
