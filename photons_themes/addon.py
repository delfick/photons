from photons_app.actions import an_action
from photons_app import helpers as hp

from photons_messages import LightMessages, DeviceMessages, MultiZoneMessages, TileMessages
from photons_control.orientation import Orientation as O, reorient
from photons_control.tile import tiles_from, orientations_from
from photons_products_registry import capability_for_ids
from photons_themes.appliers import types as appliers
from photons_control.script import Pipeline
from photons_themes.theme import Theme
from photons_colour import Parser

from option_merge_addons import option_merge_addon_hook
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta
from collections import defaultdict
import logging

@option_merge_addon_hook(extras=[
      ("lifx.photons", "products_registry")
    , ("lifx.photons", "messages")
    , ("lifx.photons", "colour")
    , ("lifx.photons", "control")
    ])
def __lifx__(collector, *args, **kwargs):
    pass

__shortdesc__ = "Determine how to apply themes to devices"

log = logging.getLogger("photons_themes")

class Color(dictobj.Spec):
    hue = dictobj.Field(sb.integer_spec(), wrapper=sb.required)
    saturation = dictobj.Field(sb.float_spec(), wrapper=sb.required)
    brightness = dictobj.Field(sb.float_spec(), wrapper=sb.required)
    kelvin = dictobj.Field(sb.integer_spec(), wrapper=sb.required)

class Options(dictobj.Spec):
    colors = dictobj.Field(sb.listof(Color.FieldSpec()), wrapper=sb.required)
    theme = dictobj.Field(sb.string_choice_spec(appliers.keys()), default="SPLOTCH")
    duration = dictobj.Field(sb.float_spec(), default=1)
    hue = dictobj.NullableField(sb.float_spec())
    saturation = dictobj.NullableField(sb.float_spec())
    brightness = dictobj.NullableField(sb.float_spec())
    kelvin = dictobj.NullableField(sb.float_spec())

    @property
    def overrides(self):
        o = {}
        for key in ("duration", "hue", "saturation", "brightness", "kelvin"):
            if self[key] is not None:
                o[key] = self[key]
        return o

@an_action(needs_target=True, special_reference=True)
async def apply_theme(collector, target, reference, artifact, **kwargs):
    """
    Apply a theme to specified device

    ``lan:apply_theme d073d5000001 -- `{"colors": <colors>, "theme": "SPLOTCH"}'``

    If you don't specify serials, then the theme will apply to all devices found on the network.

    colors must be an array of ``{"hue": <hue>, "saturation": <saturation>, "brightness": <brightness>, "kelvin": <kelvin>}``

    theme must be a valid theme type and defaults to SPLOTCH

    You may also specify ``duration`` which is how long to take to apply in seconds.

    And you may also supply ``hue``, ``saturation``, ``brightness`` and ``kelvin`` to override the specified colors.
    """
    options = Options.FieldSpec().normalise(Meta.empty(), collector.configuration["photons_app"].extra_as_json)

    async with target.session() as afr:
        await do_apply_theme(target, reference, afr, options)

async def do_apply_theme(target, reference, afr, options):
    aps = appliers[options.theme]

    theme = Theme()
    for color in options.colors:
        theme.add_hsbk(color.hue, color.saturation, color.brightness, color.kelvin)

    info = defaultdict(dict)
    async for pkt, _, _ in target.script([DeviceMessages.GetVersion(), DeviceMessages.GetHostFirmware()]).run_with(reference, afr):
        if pkt | DeviceMessages.StateVersion:
            info[pkt.serial]["capability"] = capability_for_ids(pkt.product, pkt.vendor)
        elif pkt | DeviceMessages.StateHostFirmware:
            info[pkt.serial]["firmware"] = (pkt.version_major, pkt.version_minor)

    tasks = []
    for serial, details in info.items():
        if "capability" not in details:
            continue

        firmware = details.get("firmware") or (None, None)
        capability = details["capability"]

        if capability.has_multizone:
            log.info(hp.lc("Found a strip", serial=serial))
            if firmware and capability.has_extended_multizone(*firmware):
                t = hp.async_as_background(apply_zone_extended(aps["1d"], target, afr, serial, theme, options.overrides))
            else:
                t = hp.async_as_background(apply_zone_old(aps["1d"], target, afr, serial, theme, options.overrides))
        elif capability.has_chain:
            log.info(hp.lc("Found a tile", serial=serial))
            t = hp.async_as_background(apply_tile(aps["2d"], target, afr, serial, theme, options.overrides))
        else:
            log.info(hp.lc("Found a light", serial=serial))
            t = hp.async_as_background(apply_light(aps["0d"], target, afr, serial, theme, options.overrides))

        tasks.append((serial, t))

    results = {}

    for serial, t in tasks:
        try:
            await t
        except Exception as error:
            results[serial] = error
        else:
            results[serial] = "ok"

    return results

async def apply_zone_extended(applier, target, afr, serial, theme, overrides):
    length = None
    async for pkt, _, _ in target.script(MultiZoneMessages.GetExtendedColorZones()).run_with(serial, afr):
        if pkt | MultiZoneMessages.StateExtendedColorZones:
            length = pkt.zones_count

    if length is None:
        log.warning(hp.lc("Couldn't work out how many zones the light had", serial=serial))
        return

    colors = []
    for (start_index, end_index), hsbk in applier(length).apply_theme(theme):
        for _ in range(0, end_index - start_index + 1):
            colors.append(hsbk.as_dict())

    set_zones = MultiZoneMessages.SetExtendedColorZones(
          zone_index = 0
        , colors_count = len(colors)
        , colors = colors
        , duration = overrides.get("duration", 1)
        , res_required = False
        , ack_required = True
        )

    set_power = LightMessages.SetLightPower(level=65535, duration=overrides.get("duration", 1))

    await target.script([set_power, set_zones]).run_with_all(serial, afr)

async def apply_zone_old(applier, target, afr, serial, theme, overrides):
    length = None
    msg = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
    async for pkt, _, _ in target.script(msg).run_with(serial, afr):
        if pkt | MultiZoneMessages.StateMultiZone:
            length = pkt.zones_count

    if length is None:
        log.warning(hp.lc("Couldn't work out how many zones the light had", serial=serial))
        return

    messages = []
    for (start_index, end_index), hsbk in applier(length).apply_theme(theme):
        messages.append(MultiZoneMessages.SetColorZones(
              start_index=start_index
            , end_index=end_index
            , hue = hsbk.hue
            , saturation = hsbk.saturation
            , brightness = hsbk.brightness
            , kelvin = hsbk.kelvin
            , duration = overrides.get("duration", 1)
            , res_required = False
            , ack_required = True
            ))

    set_power = LightMessages.SetLightPower(level=65535, duration=overrides.get("duration", 1))
    pipeline = Pipeline(*messages, spread=0.005)
    await target.script([set_power, pipeline]).run_with_all(serial, afr)

async def apply_light(applier, target, afr, serial, theme, overrides):
    color = applier().apply_theme(theme)
    s = "kelvin:{} hue:{} saturation:{} brightness:{}".format(color.kelvin, color.hue, color.saturation, color.brightness)
    set_power = LightMessages.SetLightPower(level=65535, duration=overrides.get("duration", 1))
    await target.script([set_power, Parser.color_to_msg(s, overrides=overrides)]).run_with_all(serial, afr)

async def apply_tile(applier, target, afr, serial, theme, overrides):
    chain = []
    orientations = {}
    async for pkt, _, _ in target.script(TileMessages.GetDeviceChain()).run_with(serial, afr):
        if pkt | TileMessages.StateDeviceChain:
            for tile in tiles_from(pkt):
                chain.append(tile)
            orientations = orientations_from(pkt)

    if chain is None:
        log.warning(hp.lc("Couldn't work out how many tiles the light had", serial=serial))
        return

    coords_and_sizes = [((t.user_x, t.user_y), (t.width, t.height)) for t in chain]

    messages = []
    for i, (hsbks, coords_and_size) in enumerate(zip(applier.from_user_coords(coords_and_sizes).apply_theme(theme), coords_and_sizes)):
        colors = [
            { "hue": overrides.get("hue", hsbk.hue)
            , "saturation": overrides.get("saturation", hsbk.saturation)
            , "brightness": overrides.get("brightness", hsbk.brightness)
            , "kelvin": overrides.get("kelvin", hsbk.kelvin)
            } for hsbk in hsbks
        ]

        colors = reorient(colors, orientations.get(i, O.RightSideUp))

        messages.append(TileMessages.Set64(
              tile_index=i, length=1, x=0, y=0, width=coords_and_size[1][0], duration=overrides.get("duration", 1), colors=colors
            , res_required = False
            , ack_required = True
            ))

    set_power = LightMessages.SetLightPower(level=65535, duration=overrides.get("duration", 1))
    pipeline = Pipeline(*messages, spread=0.005)
    await target.script([set_power, pipeline]).run_with_all(serial, afr)
