"""
.. autofunction:: photons_control.multizone.zones_from_reference

.. autofunction:: photons_control.multizone.find_multizone

.. autofunction:: photons_control.multizone.SetZonesPlan

.. autofunction:: photons_control.multizone.SetZones

.. autofunction:: photons_control.multizone.SetZonesEffect
"""
from photons_control.attributes import make_colors

from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_messages import MultiZoneMessages, MultiZoneEffectType, LightMessages
from photons_control.planner import Gatherer, make_plans, Skip, Plan, NoMessages
from photons_control.planner.plans import CapabilityPlan
from photons_control.script import FromGenerator

from input_algorithms import spec_base as sb

async def find_multizone(target, reference, afr, gatherer=None, **kwargs):
    """
    Yield (serial, has_extended_multizone) for all multizone products found in this reference
    """
    if gatherer is None:
        gatherer = Gatherer(target)

    plans = make_plans("capability")
    async for serial, _, info in gatherer.gather(plans, reference, afr, **kwargs):
        if info["cap"].has_multizone:
            yield serial, info["has_extended_multizone"]

async def zones_from_reference(target, reference, afr, gatherer=None, **kwargs):
    """
    Yield (serial, [(zone, color), ...]) for each multizone device that is found
    """
    if gatherer is None:
        gatherer = Gatherer(target)

    plans = make_plans("zones")
    async for serial, _, info in gatherer.gather(plans, reference, afr, **kwargs):
        if info is not Skip:
            yield serial, info

class SetZonesPlan(Plan):
    """
    Return messages used to apply a color range to multizone devices

    Takes in:

    colors - [[color_specifier, length], ...]
        For example, [["red", 1], ["blue", 3], ["hue:100 saturation:0.5", 5]]

    zone_index - default 0
        An integer representing where on the strip to start the colors

    duration - default 1
        Application duration

    overrides - default None
        A dictionary containing hue, saturation, brightness and kelvin for
        overriding colors with

    For devices that aren't a multizone, info will be Skip, otherwise it'll be
    appropriate messages respective to the device supporting extended multizone
    or not.

    Usage is:

    .. code-block:: python

        from photons_control.planner import Gatherer, Skip

        gatherer = Gatherer(target)
        plans = {"set_zones": SetZonesPlan(colors)}

        async with target.session() as afr:
            async for serial, _, messages in g.gather(plans, reference, afr):
                if messages is not Skip:
                    await target.script(messages).run_with_all(serial, afr)

    Note that this example code will do one strip at a time, if you want to
    change all strips at the same time, just use the SetZones msg in a normal
    run_with script.
    """
    dependant_info = {"c": CapabilityPlan()}

    def setup(self, colors, zone_index=0, duration=1, overrides=None, **kwargs):
        colors = self.make_colors(colors, overrides)
        self.set_color_old = self.make_color_old_messages(zone_index, colors, duration)
        self.set_color_new = self.make_color_new_messages(zone_index, colors, duration)

    def make_color_old_messages(self, zone_index, colors, duration):
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
                    , ack_required = True
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
                , ack_required = True
                , res_required = False
                , **current
                ))

        return set_color_old

    def make_color_new_messages(self, zone_index, colors, duration):
        return MultiZoneMessages.SetExtendedColorZones(
              duration = duration
            , colors_count = len(colors)
            , colors = colors
            , zone_index = zone_index
            , ack_required = True
            , res_required = False
            )

    def make_colors(self, colors, overrides):
        results = list(make_colors(colors, overrides))

        if len(results) > 82:
            raise PhotonsAppError("colors can only go up to 82 colors", got=len(results))

        if not results:
            raise PhotonsAppError("No colors were specified")

        return results

    class Instance(Plan.Instance):
        @property
        def messages(self):
            if self.deps["c"]["cap"]["has_multizone"]:
                return NoMessages
            return Skip

        async def info(self):
            if self.deps["c"]["has_extended_multizone"]:
                msg = self.parent.set_color_new.clone()
                msg.target = self.serial
                return msg
            else:
                msgs = []
                ms = [m.clone() for m in self.parent.set_color_old]
                for m in ms:
                    m.target = self.serial
                    msgs.append(m)
                return msgs

def SetZones(colors, gatherer=None, power_on=True, reference=None, **options):
    """
    Set colors on all found multizone devices. Uses SetZonesPlan to generate the
    messages to set the zones on the device and so keyword arguments to this
    messages are passed directly to the plan.

    Usage looks like:

    .. code-block:: python

        msg = SetZones([["red", 10], ["blue", 10]], zone_index=1, duration=1)
        await target.script(msg).run_with_all(reference)

    You may also pass in a Gatherer instance to SetZones if you already have
    one of those.

    By default the devices will be powered on. If you don't want this to happen
    then pass in power_on=False

    If you want to target a particular device or devices, pass in reference as a
    run_with reference.
    """
    async def gen(ref, afr, **kwargs):
        plans = {"set_zones": SetZonesPlan(colors, **options)}

        g = gatherer
        if g is None:
            g = Gatherer(afr.transport_target)

        r = ref if reference is None else reference

        async for serial, _, messages in g.gather(plans, r, afr, **kwargs):
            if messages is not Skip:
                if power_on:
                    yield LightMessages.SetLightPower(
                          level = 65535
                        , target = serial
                        , duration = options.get("duration", 1)
                        , ack_required = True
                        , res_required = False
                        )

                yield messages

    return FromGenerator(gen)

def SetZonesEffect(effect, gatherer=None, power_on=True, power_on_duration=1, reference=None, **options):
    """
    Set an effect on your strips

    Where effect is one of the available effect types:

    OFF
        Turn the animation off

    MOVE
        A moving animation

    Options include:
    - offset
    - speed
    - duration

    Usage looks like:

    .. code-block:: python

        msg = SetZonesEffect("MOVE", speed=1)
        await target.script(msg).run_with_all(reference)

    By default the devices will be powered on. If you don't want this to happen
    then pass in power_on=False

    If you want to target a particular device or devices, pass in reference as a
    run_with reference.
    """
    typ = effect
    if type(effect) is str:
        for e in MultiZoneEffectType:
            if e.name.lower() == effect.lower():
                typ = e
                break

    if typ is None:
        available = [e.name for e in MultiZoneEffectType]
        raise PhotonsAppError("Please specify a valid type", wanted=effect, available=available)

    options["type"] = typ
    options["res_required"] = False
    set_effect = MultiZoneMessages.SetMultiZoneEffect.empty_normalise(**options)

    async def gen(ref, afr, **kwargs):
        plans = make_plans("capability")

        g = gatherer
        if g is None:
            g = Gatherer(afr.transport_target)

        r = ref if reference is None else reference

        async for serial, _, info in g.gather(plans, r, afr, **kwargs):
            if info["cap"]["has_multizone"]:
                if power_on:
                    yield LightMessages.SetLightPower(
                          level = 65535
                        , target = serial
                        , duration = power_on_duration
                        , ack_required = True
                        , res_required = False
                        )

                msg = set_effect.clone()
                msg.target = serial
                yield msg

    return FromGenerator(gen)

@an_action(needs_target=True, special_reference=True)
async def get_zones(collector, target, reference, artifact, **kwargs):
    """
    Get the zones colors from a light strip
    """
    async with target.session() as afr:
        async for serial, zones in zones_from_reference(target, reference, afr):
            print(serial)
            for zone, color in zones:
                print("\tZone {0}: {1}".format(zone, repr(color)))

@an_action(needs_target=True, special_reference=True)
async def set_zones(collector, target, reference, artifact, **kwargs):
    """
    Set the zones colors on a light strip

    Usage looks like::

        lifx lan:set_zones d073d5000001 -- '{"colors": [["red", 10], ["blue", 3], ["green", 5]]}'

    In that example the strip will have the first 10 zones set to red, then 3
    blue zones and then 5 green zones
    """
    options = collector.configuration["photons_app"].extra_as_json

    if "colors" not in options:
        raise PhotonsAppError("""Say something like ` -- '{"colors": [["red", 10], ["blue", 3]]}'`""")

    await target.script(SetZones(**options)).run_with_all(reference)

@an_action(needs_target=True, special_reference=True)
async def multizone_effect(collector, target, reference, artifact, **kwargs):
    """
    Set an animation on your strip!

    ``lan:multizone_effect d073d5000001 <type> -- '{<options>}'``

    Where type is one of the available effect types:

    OFF
        Turn the animation off

    MOVE
        A moving animation

    Options include:
    - offset
    - speed
    - duration
    """
    options = collector.configuration["photons_app"].extra_as_json

    if artifact in ("", None, sb.NotSpecified):
        raise PhotonsAppError("Please specify type of effect with --artifact")

    await target.script(SetZonesEffect(artifact, **options)).run_with_all(reference)
