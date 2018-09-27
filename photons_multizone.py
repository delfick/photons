from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_protocol.messages import Messages, msg, MultiOptions, T
from photons_colour import hsbk, duration_typ
from photons_protocol.packets import dictobj

from option_merge_addons import option_merge_addon_hook
from input_algorithms import spec_base as sb
from option_merge import MergedOptions
from collections import defaultdict
from enum import Enum

__shortdesc__ = "LIFX Binary protocol messages related to multizone capabilities"

__doc__ = """
.. photons_task:: get_zones

.. photons_task:: set_zones

.. lifx_messages:: MultiZoneMessages
"""

@option_merge_addon_hook(extras=[("lifx.photons", "protocol"), ("lifx.photons", "script")])
def __lifx__(collector, *args, **kwargs):
    pass

@option_merge_addon_hook(post_register=True)
def __lifx_post__(collector, *args, **kwargs):
    collector.configuration["protocol_register"].message_register(1024).add(MultiZoneMessages)

async def zones_from_reference(target, reference, afr=sb.NotSpecified, **kwargs):
    """
    Return a dictionary of {serial: [(zone_index, colors), ...]} for the provided reference

    We assume all the devices support multizone
    """
    final = {}

    msg = MultiZoneMessages.GetMultiZoneColorZones(start_index=0, end_index=255)
    options = MergedOptions.using({"timeout": 5}, kwargs).as_dict()

    by_serial = defaultdict(list)
    async for pkt, _, _ in target.script(msg).run_with(reference, afr, **options):
        by_serial[pkt.serial].append(pkt)

    for serial, pkts in by_serial.items():
        final[serial] = []
        for p in pkts:
            if p | MultiZoneMessages.StateMultiZoneStateMultiZones:
                for i, color in enumerate(p.colors):
                    final[serial].append((p.zone_index + i, color))

    return final

@an_action(needs_target=True, special_reference=True)
async def get_zones(collector, target, reference, artifact, **kwargs):
    """
    Get the zones colors from a light strip
    """
    results = await zones_from_reference(target, reference)
    for serial, zones in results.items():
        print(serial)
        for zone, color in zones:
            print("\tZone {0}: {1}".format(zone, repr(color)))

@an_action(needs_target=True, special_reference=True)
async def set_zones(collector, target, reference, artifact, **kwargs):
    """
    Set the zones colors on a light strip
    """
    options = collector.configuration["photons_app"].extra_as_json

    setter_kls = MultiZoneMessages.SetMultiZoneColorZones
    missing = []
    for field in setter_kls.Payload.Meta.all_names:
        if field not in options and field not in ("kelvin", "duration", "type"):
            missing.append(field)

    if missing:
        raise PhotonsAppError("Missing options for the SetMultiZoneColorZones message", missing=missing)

    setter = setter_kls.empty_normalise(**options)
    setter.res_required = False
    setter.ack_required = True
    await target.script(setter).run_with_all(reference)

class ApplicationRequestType(Enum):
    NO_APPLY = 0
    APPLY = 1
    APPLY_ONLY = 2

class ZoneCountScanType(Enum):
    NONE = 0
    RESCAN = 1

class Color(dictobj.PacketSpec):
    fields = hsbk

class MultiZoneMessages(Messages):
    """
    Messages related to multizone functionality (i.e. light strips)

    Uses:

    .. code_for:: photons_multizone.ApplicationRequestType

    .. code_for:: photons_multizone.ZoneCountScanType
    """
    SetMultiZoneColorZones = msg(501
        , ("start_index", T.Uint8)
        , ("end_index", T.Uint8)
        , *hsbk
        , ("duration", duration_typ)
        , ("type", T.Uint8.enum(ApplicationRequestType).default(ApplicationRequestType.APPLY))
        )

    GetMultiZoneColorZones = msg(502
        , ("start_index", T.Uint8)
        , ("end_index", T.Uint8)

        , multi = MultiOptions(
              lambda req: [MultiZoneMessages.StateMultiZoneStateMultiZones, MultiZoneMessages.StateMultiZoneStateZones]
            , lambda req, res: min((req.end_index // 8) + 1, res.num_zones // 8)
            )
        )

    StateMultiZoneStateZones = msg(503
        , ("num_zones", T.Uint8)
        , ("zone_index", T.Uint8)
        , *hsbk
        )

    GetMultiZoneZoneCount = msg(504
        , ("scan", T.Uint8.enum(ZoneCountScanType).default(ZoneCountScanType.RESCAN))
        )

    StateMultiZoneStateZoneCount = msg(505
        , ("time", T.Uint64)
        , ("num_zones", T.Uint8)
        )

    StateMultiZoneStateMultiZones = msg(506
        , ("num_zones", T.Uint8)
        , ("zone_index", T.Uint8)
        , ("colors", T.Bytes(64 * 8).many(lambda pkt: Color))
        )
