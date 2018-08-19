from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_protocol.messages import Messages, msg, MultiOptions, T
from photons_colour import hsbk, duration_typ
from photons_protocol.packets import dictobj
from photons_script.script import ATarget

from option_merge_addons import option_merge_addon_hook
from input_algorithms.errors import BadSpecValue
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from collections import defaultdict
from lru import LRU
import logging

__shortdesc__ = "LIFX binary protocol messages for Tiles"

__doc__ = """
.. photons_task:: get_device_chain

.. photons_task:: get_chain_state

.. photons_task:: set_chain_state

.. photons_task:: set_tile_positions

.. lifx_messages:: TileMessages
"""

log = logging.getLogger(name="photons_tile_messages")

@option_merge_addon_hook(extras=[("lifx.photons", "protocol"), ("lifx.photons", "colour"), ("lifx.photons", "script")])
def __lifx__(collector, *args, **kwargs):
    pass

@option_merge_addon_hook(post_register=True)
def __lifx_post__(collector, *args, **kwargs):
    collector.configuration["protocol_register"].message_register(1024).add(TileMessages)

def tiles_from(state_pkt):
    amount = state_pkt.total_count - state_pkt.start_index
    return state_pkt.tile_devices[:amount]

@an_action(needs_target=True, special_reference=True)
async def get_device_chain(collector, target, reference, **kwargs):
    """
    Get the devices in your chain
    """
    async for pkt, _, _ in target.script(TileMessages.GetDeviceChain()).run_with(reference):
        if pkt | TileMessages.StateDeviceChain:
            print(pkt.serial)
            for tile in tiles_from(pkt):
                print("   ", repr(tile))

@an_action(needs_target=True, special_reference=True)
async def get_chain_state(collector, target, reference, **kwargs):
    """
    Get the colors of the tiles in your chain
    """
    options = collector.configuration['photons_app'].extra_as_json

    missing = []
    for field in TileMessages.GetTileState64.Payload.Meta.all_names:
        if field not in options and field not in ("reserved", ):
            missing.append(field)

    if missing:
        raise PhotonsAppError("Missing options for the GetTileState message", missing=missing)

    response_kls = TileMessages.StateTileState64

    got = defaultdict(list)

    msg = TileMessages.GetTileState64.empty_normalise(**options)

    async for pkt, _, _ in target.script(msg).run_with(reference):
        if pkt | response_kls:
            got[pkt.serial].append((pkt.tile_index, pkt))

    for serial, states in got.items():
        print(serial)
        for i, state in sorted(states):
            print("    Tile {0}".format(i))
            for index, color in enumerate(pkt.colors):
                print("        color {0}".format(index), repr(color))
            print("")

class list_spec(sb.Spec):
    def setup(self, *specs):
        self.specs = specs

    def normalise(self, meta, val):
        if type(val) not in (tuple, list):
            raise BadSpecValue("Expected a list", got=type(val), meta=meta)

        if len(val) != len(self.specs):
            raise BadSpecValue("Expected a value with certain number of items", wanted=len(self.specs), got=len(val), meta=meta)

        res = []
        for i, v in enumerate(val):
            res.append(self.specs[i].normalise(meta.indexed_at(i), v))

        return res

@an_action(needs_target=True, special_reference=True)
async def set_chain_state(collector, target, reference, artifact, **kwargs):
    """
    Set the state of colors on your tile

    ``lan:set_chain_state d073d5f09124 -- '{"colors": [[[0, 0, 0, 3500], [0, 0, 0, 3500], ...], [[0, 0, 1, 3500], ...], ...], "tile_index": 1, "length": 1, "x": 0, "y": 0, "width": 8}'``

    Where the colors is a grid of 8 rows of 8 ``[h, s, b, k]`` values.
    """
    options = collector.configuration["photons_app"].extra_as_json

    if "colors" in options:
        spec = sb.listof(sb.listof(list_spec(sb.integer_spec(), sb.float_spec(), sb.float_spec(), sb.integer_spec())))
        colors = spec.normalise(Meta.empty().at("colors"), options["colors"])

        row_lengths = [len(row) for row in colors]
        if len(set(row_lengths)) != 1:
            raise PhotonsAppError("Please specify colors as a grid with the same length rows", got=row_lengths)

        num_cells = sum(len(row) for row in colors)
        if num_cells != 64:
            raise PhotonsAppError("Please specify 64 colors", got=num_cells)

        cells = []
        for row in colors:
            for col in row:
                cells.append({"hue": col[0], "saturation": col[1], "brightness": col[2], "kelvin": col[3]})

        options["colors"] = cells
    else:
        raise PhotonsAppError("Please specify colors in options after -- as a grid of [h, s, b, k]")

    missing = []
    for field in TileMessages.SetTileState64.Payload.Meta.all_names:
        if field not in options and field not in ("duration", "reserved"):
            missing.append(field)

    if missing:
        raise PhotonsAppError("Missing options for the SetTileState message", missing=missing)

    options["res_required"] = False
    msg = TileMessages.SetTileState64.empty_normalise(**options)
    await target.script(msg).run_with_all(reference)

@an_action(needs_target=True, special_reference=True)
async def set_tile_positions(collector, target, reference, **kwargs):
    """
    Set the positions of the tiles in your chain.

    ``lan:set_tile_positions d073d5f09124 -- '[[0, 0], [-1, 0], [-1, 1]]'``
    """
    extra = collector.configuration["photons_app"].extra_as_json
    positions = sb.listof(sb.listof(sb.float_spec())).normalise(Meta.empty(), extra)
    if any(len(position) != 2 for position in positions):
        raise PhotonsAppError("Please enter positions as a list of two item lists of user_x, user_y")

    async with ATarget(target) as afr:
        for i, (user_x, user_y) in enumerate(positions):
            msg = TileMessages.SetUserPosition(tile_index=i, user_gravity_vector=0, user_x=user_x, user_y=user_y, res_required=False)
            await target.script(msg).run_with_all(reference, afr)

class Color(dictobj.PacketSpec):
    fields = hsbk
# Give Color a cache for 25 sets of tiles all containing different colors in every pixel
# Which completely filled is only 4mb
# The cache is used by photons-protocol so that we don't have to Color().pack() 64 times for every SetState64
#   which is very slow...
Color.Meta.cache = LRU(8000)

class Tile(dictobj.PacketSpec):
    fields = [
          ("reserved6", T.Int16.default(0))
        , ("reserved7", T.Int16.default(0))
        , ("reserved8", T.Int16.default(0))
        , ("reserved9", T.Uint16.default(0))
        , ("user_x", T.Float)
        , ("user_y", T.Float)
        , ("width", T.Uint8)
        , ("height", T.Uint8)
        , ("reserved10", T.Uint8.default(50))
        , ("device_version_vendor", T.Uint32)
        , ("device_version_product", T.Uint32)
        , ("device_version_version", T.Uint32)
        , ("firmware_build", T.Uint64)
        , ("reserved11", T.Uint64.default(0))
        , ("firmware_version", T.Uint32.transform(
                lambda _, v: v if type(v) is int else (int(str(v).split(".")[0]) << 0x10) + int(str(v).split(".")[1])
              , lambda v: float("{0}.{1:02d}".format(v >> 0x10, v & 0xFF))
              ).allow_float()
            )
        , ("reserved12", T.Uint32.default(0))
        ]

tile_buffer_rect = (
      ("reserved", T.Uint8.default(0))
    , ("x", T.Uint8)
    , ("y", T.Uint8)
    , ("width", T.Uint8)
    )

get_tile_state = (
      ("tile_index", T.Uint8)
    , ("length", T.Uint8)
    , *tile_buffer_rect
    )

def set_tile_state(num_colors):
    return (
          ("tile_index", T.Uint8)
        , ("length", T.Uint8)
        , *tile_buffer_rect
        , ("duration", duration_typ)
        , ("colors", T.Bytes(64 * num_colors).many(lambda pkt: Color))
        )

def tile_state(num_colors):
    return (
          ("tile_index", T.Uint8)
        , *tile_buffer_rect
        , ("colors", T.Bytes(64 * num_colors).many(lambda pkt: Color))
        )

class TileMessages(Messages):
    GetDeviceChain = msg(701)

    StateDeviceChain = msg(702
        , ("start_index", T.Uint8)
        , ("tile_devices", T.Bytes(440 * 16).many(lambda pkt: Tile))
        , ("total_count", T.Uint8)
        )

    SetUserPosition = msg(703
        , ("tile_index", T.Uint8)
        , ("reserved6", T.Uint16.default(0))
        , ("user_x", T.Float)
        , ("user_y", T.Float)
        )

    GetTileState64 = msg(707, *get_tile_state
        , multi = MultiOptions(
              lambda req: TileMessages.StateTileState64
            , lambda req, res: MultiOptions.Max(req.length)
            )
        )

    SetTileState64 = msg(715, *set_tile_state(64))

    StateTileState64 = msg(711, *tile_state(64))
