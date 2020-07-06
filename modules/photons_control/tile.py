from photons_canvas.orientation import nearest_orientation
from photons_control.script import FromGenerator
from photons_control.colour import make_hsbks

from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_messages import TileMessages, TileEffectType, LightMessages

from delfick_project.norms import BadSpecValue, sb, Meta
import logging

log = logging.getLogger(name="photons_control.tiles")

default_tile_palette = [
    {"hue": hue, "brightness": 1, "saturation": 1, "kelvin": 3500}
    for hue in [0, 40, 60, 122, 239, 271, 294]
]


def tiles_from(state_pkt):
    """
    Given a Tile State packet, return the tile devices that are valid.

    This works by taking into account ``tile_devices_count`` and ``start_index``
    on the packet.
    """
    amount = state_pkt.tile_devices_count - state_pkt.start_index
    return state_pkt.tile_devices[:amount]


def orientations_from(pkt):
    orientations = {}
    for i, tile in enumerate(tiles_from(pkt)):
        orientations[i] = nearest_orientation(
            tile.accel_meas_x, tile.accel_meas_y, tile.accel_meas_z
        )
    return orientations


def SetTileEffect(effect, power_on=True, power_on_duration=1, reference=None, **options):
    """
    Set an effect on your tiles

    Where effect is one of the available effect types:

    OFF
        Turn the animation off

    FLAME
        A flame effect

    MORPH
        A Morph effect

    Options include:

    * speed
    * duration
    * palette

    Usage looks like:

    .. code-block:: python

        msg = SetTileEffect("MORPH", palette=["red", "blue", "green"])
        await target.send(msg, reference)

    By default the devices will be powered on. If you don't want this to happen
    then pass in ``power_on=False``.

    If you want to target a particular device or devices, pass in reference.
    """
    typ = effect
    if type(effect) is str:
        for e in TileEffectType:
            if e.name.lower() == effect.lower():
                typ = e
                break

    if typ is None:
        available = [e.name for e in TileEffectType]
        raise PhotonsAppError("Please specify a valid type", wanted=effect, available=available)

    options["type"] = typ
    options["res_required"] = False

    if "palette" not in options:
        options["palette"] = default_tile_palette

    if len(options["palette"]) > 16:
        raise PhotonsAppError("Palette can only be up to 16 colors", got=len(options["palette"]))

    options["palette"] = list(make_hsbks([c, 1] for c in options["palette"]))
    options["palette_count"] = len(options["palette"])

    set_effect = TileMessages.SetTileEffect.create(**options)

    async def gen(ref, sender, **kwargs):
        r = ref if reference is None else reference

        ps = sender.make_plans("capability")
        async for serial, _, info in sender.gatherer.gather(ps, r, **kwargs):
            if info["cap"].has_matrix:
                if power_on:
                    yield LightMessages.SetLightPower(
                        level=65535,
                        target=serial,
                        duration=power_on_duration,
                        ack_required=True,
                        res_required=False,
                    )

                msg = set_effect.clone()
                msg.target = serial
                yield msg

    return FromGenerator(gen)


@an_action(needs_target=True, special_reference=True)
async def get_device_chain(collector, target, reference, **kwargs):
    """
    Get the devices in your chain
    """

    async def gen(reference, sender, **kwargs):
        ps = sender.make_plans("capability")
        async for serial, _, info in sender.gatherer.gather(ps, reference, **kwargs):
            if info["cap"].has_matrix:
                yield TileMessages.GetDeviceChain(target=serial)

    async for pkt in target.send(FromGenerator(gen), reference):
        print(pkt.serial)
        for tile in tiles_from(pkt):
            print("    ", repr(tile))


@an_action(needs_target=True, special_reference=True)
async def get_chain_state(collector, target, reference, **kwargs):
    """
    Get the colors of the tiles in your chain
    """

    async with target.session() as sender:
        plans = sender.make_plans("parts_and_colors")

        def error(e):
            log.error(e)

        async for serial, _, parts in sender.gatherer.gather(plans, reference, error_catcher=error):
            if not parts or not parts[0].device.cap.has_matrix:
                continue

            print(serial)
            for part in parts:
                print(f"    Tile {part.part_number}")
                for i, color in enumerate(part.colors):
                    color = (round(color[0], 3), round(color[1], 3), round(color[2], 3), color[3])
                    print(f"        color {i:<2d}", repr(color))
                print("")


@an_action(needs_target=True, special_reference=True)
async def tile_effect(collector, target, reference, artifact, **kwargs):
    """
    Set an animation on your tile!

    ``lan:tile_effect d073d5000001 <type> -- '{<options>}'``

    Where type is one of the available effect types:

    OFF
        Turn of the animation off

    MORPH
        Move through a perlin noise map, assigning pixel values from a
        16-color palette

    FLAME
        A flame effect

    For effects that take in a palette option, you may specify palette as
    ``[{"hue": 0, "saturation": 1, "brightness": 1, "kelvin": 2500}, ...]``

    or as ``[[0, 1, 1, 2500], ...]`` or as ``[[0, 1, 1], ...]``

    or as ``["red", "hue:100 saturation:1", "blue"]``
    """
    options = collector.photons_app.extra_as_json

    if artifact in ("", None, sb.NotSpecified):
        raise PhotonsAppError("Please specify type of effect with --artifact")

    await target.send(SetTileEffect(artifact, **options), reference)


class list_spec(sb.Spec):
    def setup(self, *specs):
        self.specs = specs

    def normalise(self, meta, val):
        if type(val) not in (tuple, list):
            raise BadSpecValue("Expected a list", got=type(val), meta=meta)

        if len(val) != len(self.specs):
            raise BadSpecValue(
                "Expected a value with certain number of items",
                wanted=len(self.specs),
                got=len(val),
                meta=meta,
            )

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
    """  # noqa
    options = collector.photons_app.extra_as_json

    if "colors" in options:
        spec = sb.listof(
            sb.listof(
                list_spec(sb.integer_spec(), sb.float_spec(), sb.float_spec(), sb.integer_spec())
            )
        )
        colors = spec.normalise(Meta.empty().at("colors"), options["colors"])

        row_lengths = [len(row) for row in colors]
        if len(set(row_lengths)) != 1:
            raise PhotonsAppError(
                "Please specify colors as a grid with the same length rows", got=row_lengths
            )

        num_cells = sum(len(row) for row in colors)
        if num_cells != 64:
            raise PhotonsAppError("Please specify 64 colors", got=num_cells)

        cells = []
        for row in colors:
            for col in row:
                cells.append(
                    {"hue": col[0], "saturation": col[1], "brightness": col[2], "kelvin": col[3]}
                )

        options["colors"] = cells
    else:
        raise PhotonsAppError("Please specify colors in options after -- as a grid of [h, s, b, k]")

    missing = []
    for field in TileMessages.Set64.Payload.Meta.all_names:
        if field not in options and field not in ("duration", "reserved6"):
            missing.append(field)

    if missing:
        raise PhotonsAppError("Missing options for the SetTileState message", missing=missing)

    options["res_required"] = False
    msg = TileMessages.Set64.create(**options)
    await target.send(msg, reference)


@an_action(needs_target=True, special_reference=True)
async def set_tile_positions(collector, target, reference, **kwargs):
    """
    Set the positions of the tiles in your chain.

    ``lan:set_tile_positions d073d5f09124 -- '[[0, 0], [-1, 0], [-1, 1]]'``
    """
    extra = collector.photons_app.extra_as_json
    positions = sb.listof(sb.listof(sb.float_spec())).normalise(Meta.empty(), extra)
    if any(len(position) != 2 for position in positions):
        raise PhotonsAppError(
            "Please enter positions as a list of two item lists of user_x, user_y"
        )

    async def gen(reference, sender, **kwargs):
        ps = sender.make_plans("capability")
        async for serial, _, info in sender.gatherer.gather(ps, reference, **kwargs):
            if info["cap"].has_matrix:
                for i, (user_x, user_y) in enumerate(positions):
                    yield TileMessages.SetUserPosition(
                        tile_index=i,
                        user_x=user_x,
                        user_y=user_y,
                        res_required=False,
                        target=serial,
                    )

    await target.send(FromGenerator(gen), reference)


@an_action(needs_target=True, special_reference=True)
async def get_tile_positions(collector, target, reference, **kwargs):
    """
    Get the positions of the tiles in your chain.

    ``lan:get_tile_positions d073d5f09124``
    """

    async def gen(reference, sender, **kwargs):
        ps = sender.make_plans("capability")
        async for serial, _, info in sender.gatherer.gather(ps, reference, **kwargs):
            if info["cap"].has_matrix:
                yield TileMessages.GetDeviceChain(target=serial)

    async for pkt in target.send(FromGenerator(gen), reference):
        print(pkt.serial)
        for tile in tiles_from(pkt):
            print(f"\tuser_x: {tile.user_x}, user_y: {tile.user_y}")
        print("")
