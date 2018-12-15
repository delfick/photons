"""
.. autofunction:: photons_control.multizone.zones_from_reference
"""
from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_messages import MultiZoneMessages

from input_algorithms import spec_base as sb
from option_merge import MergedOptions
from collections import defaultdict

async def zones_from_reference(target, reference, afr=sb.NotSpecified, **kwargs):
    """
    Return a dictionary of {serial: [(zone_index, colors), ...]} for the provided reference

    We assume all the devices support multizone
    """
    final = {}

    msg = MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
    options = MergedOptions.using({"timeout": 5}, kwargs).as_dict()

    by_serial = defaultdict(list)
    async for pkt, _, _ in target.script(msg).run_with(reference, afr, **options):
        by_serial[pkt.serial].append(pkt)

    for serial, pkts in by_serial.items():
        final[serial] = []
        for p in pkts:
            if p | MultiZoneMessages.StateMultiZone:
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

    setter_kls = MultiZoneMessages.SetColorZones
    missing = []
    for field in setter_kls.Payload.Meta.all_names:
        if field not in options and field not in ("kelvin", "duration", "apply"):
            missing.append(field)

    if missing:
        raise PhotonsAppError("Missing options for the SetColorZones message", missing=missing)

    setter = setter_kls.empty_normalise(**options)
    setter.res_required = False
    setter.ack_required = True
    await target.script(setter).run_with_all(reference)
