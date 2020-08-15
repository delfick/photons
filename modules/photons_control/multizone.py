from photons_control.colour import make_hsbks

from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_messages import MultiZoneMessages, MultiZoneEffectType, LightMessages
from photons_control.planner import Skip, Plan, NoMessages
from photons_control.planner.plans import CapabilityPlan
from photons_control.script import FromGenerator

from delfick_project.norms import sb


async def find_multizone(reference, sender, **kwargs):
    """
    Yield (serial, capability) for all multizone products found in this reference
    """
    plans = sender.make_plans("capability")
    async for serial, _, info in sender.gatherer.gather(plans, reference, **kwargs):
        if info["cap"].has_multizone:
            yield serial, info["cap"]


async def zones_from_reference(reference, sender, **kwargs):
    """
    Yield (serial, [(zone, color), ...]) for each multizone device that is found
    """
    plans = sender.make_plans("zones")
    async for serial, _, info in sender.gatherer.gather(plans, reference, **kwargs):
        if info is not Skip:
            yield serial, info


class SetZonesPlan(Plan):
    """
    Return messages used to apply a color range to multizone devices

    Takes in:

    colors - ``[[color_specifier, length], ...]``
        For example, ``[["red", 1], ["blue", 3], ["hue:100 saturation:0.5", 5]]``
        will set one zone to red, followed by 3 zones to blue, followed by
        5 zones to half saturation green.

    zone_index - default 0
        An integer representing where on the device to start the colors

    duration - default 1
        Time it takes to apply.

    overrides - default None
        A dictionary containing hue, saturation, brightness and kelvin for
        overriding colors with

    For devices that don't have multizone capabilities, the ``info`` will be
    a ``Skip`` otherwise, you'll get the  appropriate messages to then send
    to the device to apply the change.

    Usage is:

    .. code-block:: python

        from photons_control.planner import Skip

        plans = {"set_zones": SetZonesPlan(colors)}

        async with target.session() as sender:
            async for serial, name, messages in sender.gatherer.gather(plans, reference):
                if name == "set_zones" and messages is not Skip:
                    await sender(messages, serial)

    Note that this example code will do one device at a time, If you want to
    change multiple devices at the same time then use
    :class:`photons_control.multizone.SetZones` message instead.
    """

    default_refresh = True
    dependant_info = {"c": CapabilityPlan()}

    def setup(self, colors, zone_index=0, duration=1, overrides=None, **kwargs):
        colors = self.make_hsbks(colors, overrides)
        self.set_color_old = self.make_hsbk_old_messages(zone_index, colors, duration)
        self.set_color_new = self.make_hsbk_new_messages(zone_index, colors, duration)

    def make_hsbk_old_messages(self, zone_index, colors, duration):
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
                set_color_old.append(
                    MultiZoneMessages.SetColorZones(
                        start_index=start,
                        end_index=end,
                        duration=duration,
                        ack_required=True,
                        res_required=False,
                        **current
                    )
                )
                start = i

            current = color
            end = i

        if not set_color_old or set_color_old[-1].end_index != i:
            set_color_old.append(
                MultiZoneMessages.SetColorZones(
                    start_index=start,
                    end_index=end,
                    duration=duration,
                    ack_required=True,
                    res_required=False,
                    **current
                )
            )

        return set_color_old

    def make_hsbk_new_messages(self, zone_index, colors, duration):
        return MultiZoneMessages.SetExtendedColorZones(
            duration=duration,
            colors_count=len(colors),
            colors=colors,
            zone_index=zone_index,
            ack_required=True,
            res_required=False,
        )

    def make_hsbks(self, colors, overrides):
        results = list(make_hsbks(colors, overrides))

        if len(results) > 82:
            raise PhotonsAppError("colors can only go up to 82 colors", got=len(results))

        if not results:
            raise PhotonsAppError("No colors were specified")

        return results

    class Instance(Plan.Instance):
        @property
        def messages(self):
            if self.deps["c"]["cap"].has_multizone:
                return NoMessages
            return Skip

        async def info(self):
            if self.deps["c"]["cap"].has_extended_multizone:
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


def SetZones(colors, power_on=True, reference=None, **options):
    """
    Set colors on all found multizone devices. This will use the extended
    multizone messages if they are supported by the device to increase
    reliability and speed of application.

    Usage looks like:

    .. code-block:: python

        msg = SetZones([["red", 10], ["blue", 10]], zone_index=1, duration=1)
        await target.send(msg, reference)

    By default the devices will be powered on. If you don't want this to happen
    then pass in power_on=False

    If you want to target a particular device or devices, pass in a reference.

    The options to this helper include:

    colors - [[color_specifier, length], …]
        For example, ``[[“red”, 1], [“blue”, 3], [“hue:100 saturation:0.5”, 5]]``

    zone_index - default 0
        An integer representing where on the device to start the colors

    duration - default 1
        Application duration

    overrides - default None
        A dictionary containing hue, saturation, brightness and kelvin for overriding colors with
    """

    async def gen(ref, sender, **kwargs):
        r = ref if reference is None else reference

        plans = {"set_zones": SetZonesPlan(colors, **options)}
        async for serial, _, messages in sender.gatherer.gather(plans, r, **kwargs):
            if messages is not Skip:
                if power_on:
                    yield LightMessages.SetLightPower(
                        level=65535,
                        target=serial,
                        duration=options.get("duration", 1),
                        ack_required=True,
                        res_required=False,
                    )

                yield messages

    return FromGenerator(gen)


def SetZonesEffect(effect, power_on=True, power_on_duration=1, reference=None, **options):
    """
    Set an effect on your multizone devices

    Where effect is one of the available effect types:

    OFF
        Turn the animation off

    MOVE
        A moving animation

    Options include:

    * offset
    * speed
    * duration

    Usage looks like:

    .. code-block:: python

        msg = SetZonesEffect("MOVE", speed=1)
        await target.send(msg, reference)

    By default the devices will be powered on. If you don't want this to happen
    then pass in ``power_on=False``

    If you want to target a particular device or devices, pass in reference.
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
    set_effect = MultiZoneMessages.SetMultiZoneEffect.create(**options)

    async def gen(ref, sender, **kwargs):
        r = ref if reference is None else reference

        plans = sender.make_plans("capability")
        async for serial, _, info in sender.gatherer.gather(plans, r, **kwargs):
            if info["cap"].has_multizone:
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
async def get_zones(collector, target, reference, artifact, **kwargs):
    """
    Get the zones colors from a multizone device
    """
    async with target.session() as sender:
        async for serial, zones in zones_from_reference(reference, sender):
            print(serial)
            for zone, color in zones:
                print("\tZone {0}: {1}".format(zone, repr(color)))


@an_action(needs_target=True, special_reference=True)
async def set_zones(collector, target, reference, artifact, **kwargs):
    """
    Set the zones colors on a multizone device

    Usage looks like::

        lifx lan:set_zones d073d5000001 -- '{"colors": [["red", 10], ["blue", 3], ["green", 5]]}'

    In that example the device will have the first 10 zones set to red, then 3
    blue zones and then 5 green zones
    """
    options = collector.photons_app.extra_as_json

    if "colors" not in options:
        raise PhotonsAppError(
            """Say something like ` -- '{"colors": [["red", 10], ["blue", 3]]}'`"""
        )

    await target.send(SetZones(**options), reference)


@an_action(needs_target=True, special_reference=True)
async def multizone_effect(collector, target, reference, artifact, **kwargs):
    """
    Set an animation on your multizone device

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
    options = collector.photons_app.extra_as_json

    if artifact in ("", None, sb.NotSpecified):
        raise PhotonsAppError("Please specify type of effect with --artifact")

    await target.send(SetZonesEffect(artifact, **options), reference)
