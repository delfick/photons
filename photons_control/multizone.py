"""
.. autofunction:: photons_control.multizone.zones_from_reference

.. autofunction:: photons_control.multizone.find_multizone
"""
from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_messages import MultiZoneMessages, MultiZoneEffectType, DeviceMessages
from photons_products_registry import capability_for_ids
from photons_colour import Parser

from input_algorithms import spec_base as sb
from collections import defaultdict

async def find_multizone(target, reference, afr):
    """
    Yield (serial, has_extended_multizone) for all multizone products found in this reference
    """
    info = defaultdict(dict)

    msgs = [DeviceMessages.GetVersion(), DeviceMessages.GetHostFirmware()]
    async for pkt, _, _ in target.script(msgs).run_with(reference, afr):
        if pkt | DeviceMessages.StateVersion:
            info[pkt.serial]["capability"] = capability_for_ids(pkt.product, pkt.vendor)
        elif pkt | DeviceMessages.StateHostFirmware:
            info[pkt.serial]["firmware"] = pkt.build

    for serial, details in sorted(info.items()):
        capability = details.get("capability")
        firmware = details.get("firmware")
        if not capability or not capability.has_multizone:
            continue

        yield serial, capability.has_extended_multizone(firmware)

async def zones_from_reference(target, reference, afr, **kwargs):
    """
    Yield {serial: [(zone, color), ...]} for each multizone device that is found
    """
    msgs = []
    async for serial, has_extended_multizone in find_multizone(target, reference, afr):
        if has_extended_multizone:
            msg = MultiZoneMessages.GetExtendedColorZones(target=serial)
        else:
            msg = MultiZoneMessages.GetColorZones(target=serial, start_index=0, end_index=255)
        msgs.append(msg)

    by_serial = defaultdict(list)
    async for pkt, _, _ in target.script(msgs).run_with(None, afr, **kwargs):
        by_serial[pkt.serial].append(pkt)

    staging = defaultdict(list)

    for serial, pkts in by_serial.items():
        for p in pkts:
            if p | MultiZoneMessages.StateMultiZone:
                for i, color in enumerate(p.colors):
                    staging[serial].append((p.zone_index + i, color))
            elif p | MultiZoneMessages.StateExtendedColorZones:
                for i, color in enumerate(p.colors[:p.colors_count]):
                    staging[serial].append((p.zone_index + i, color))

    return dict(staging)

@an_action(needs_target=True, special_reference=True)
async def get_zones(collector, target, reference, artifact, **kwargs):
    """
    Get the zones colors from a light strip
    """
    async with target.session() as afr:
        results = await zones_from_reference(target, reference, afr)
        for serial, zones in results.items():
            print(serial)
            for zone, color in zones:
                print("\tZone {0}: {1}".format(zone, repr(color)))

@an_action(needs_target=True, special_reference=True)
async def set_zones(collector, target, reference, artifact, **kwargs):
    """
    Set the zones colors on a light strip

    Usage looks like::
        
        lifx lan:set_zones d073d5000001 -- '{"color_ranges": [["red", 10], ["blue", 3], ["green", 5]]}'

    In that example the strip will have the first 10 zones set to red, then 3
    blue zones and then 5 green zones
    """
    options = collector.configuration["photons_app"].extra_as_json
    zone_index = options.get("zone_index", 0)

    if "colors" not in options:
        raise PhotonsAppError("""Say something like ` -- '{"color_ranges": [["red", 10], ["blue", 3]]}'`""")

    colors = []
    for color in options["colors"]:
        if not isinstance(color, list) or len(color) != 2:
            raise PhotonsAppError("Each color_range must be [color, length]")

        color, length = color

        if isinstance(color, str):
            h, s, b, k = Parser.hsbk(color)
            b = 1
        elif isinstance(color, list):
            h, s, b, k = 0, 0, 1, 3500
            if len(color) > 0: h = color[0]
            if len(color) > 1: s = color[1]
            if len(color) > 2: b = color[2]
            if len(color) > 3: k = color[3]
        elif isinstance(color, dict):
            h = color.get("hue", 0)
            s = color.get("saturation", 0)
            b = color.get("brightness", 1)
            k = color.get("kelvin", 3500)

        result = {"hue": h or 0, "saturation": s or 0, "brightness": b or 1, "kelvin": k or 3500}
        if "overrides" in options:
            for k in result:
                if k in options["overrides"]:
                    result[k] = options["overrides"][k]

        for _ in range(length):
            colors.append(result)

    if len(colors) > 82:
        raise PhotonsAppError("colors can only go up to 82 colors", got=len(colors))

    if not colors:
        raise PhotonsAppError("No colors were specified")

    duration = options.get("duration", 1)

    set_color_old = []

    end = zone_index
    start = zone_index
    current = None

    for i, color in enumerate(colors):
        i = i + zone_index

        if current is None:
            current = color
            continue

        if current != color:
            set_color_old.append(MultiZoneMessages.SetColorZones(
                  start_index = start
                , end_index = end
                , duration = duration
                , res_required = False
                , **current
                ))
            start = i

        current = color
        end = i

    if not set_color_old or set_color_old[-1].end_index != i:
        set_color_old.append(MultiZoneMessages.SetColorZones(
              start_index = start
            , end_index = end
            , duration = duration
            , res_required = False
            , **current
            ))

    set_color_new = MultiZoneMessages.SetExtendedColorZones(
          duration = duration
        , colors_count = len(colors)
        , colors = colors
        , zone_index = zone_index
        , res_required = False
        )

    async with target.session() as afr:
        msgs = []
        async for serial, has_extended_multizone in find_multizone(target, reference, afr):
            if has_extended_multizone:
                m = set_color_new.clone()
                m.target = serial
                msgs.append(m)
            else:
                ms = [m.clone() for m in set_color_old]
                for m in ms:
                    m.target = serial
                    msgs.append(m)

    await target.script(msgs).run_with_all(reference)

@an_action(needs_target=True, special_reference=True)
async def multizone_effect(collector, target, reference, artifact, **kwargs):
    """
    Set an animation on your strip!

    ``lan:multizone_effect d073d5000001 <type> -- '{<options>}'``

    Where type is one of the available effect types:

    OFF
        Turn of the animation off

    MOVE
        A moving animation

    Options include:
    - offset
    - speed
    - duration
    """
    if artifact in ("", None, sb.NotSpecified):
        raise PhotonsAppError("Please specify type of effect with --artifact")

    typ = None
    for e in MultiZoneEffectType:
        if e.name.lower() == artifact.lower():
            typ = e
            break

    if typ is None:
        available = [e.name for e in MultiZoneEffectType]
        raise PhotonsAppError("Please specify a valid type", wanted=artifact, available=available)

    options = collector.configuration["photons_app"].extra_as_json or {}

    options["type"] = typ
    options["res_required"] = False
    msg = MultiZoneMessages.SetMultiZoneEffect.empty_normalise(**options)
    await target.script(msg).run_with_all(reference)
