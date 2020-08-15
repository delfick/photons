from photons_control.script import FromGenerator, Pipeline

from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_messages import LightMessages, DeviceMessages
from photons_control.colour import ColourParser

from delfick_project.norms import sb, Meta


def PowerToggle(duration=1, group=False, **kwargs):
    """
    Returns a valid message that will toggle the power of devices used against it.

    If group is True, then we return a PowerToggleGroup message and treat all
    lights in the reference as a group.

    For example:

    .. code-block:: python

        await target.send(PowerToggle(), ["d073d5000001", "d073d5000001"])
    """

    if group:
        return PowerToggleGroup(duration=duration, **kwargs)

    async def gen(reference, sender, **kwargs):
        get_power = DeviceMessages.GetPower()
        async for pkt in sender(get_power, reference, **kwargs):
            if pkt | DeviceMessages.StatePower:
                if pkt.level == 0:
                    yield LightMessages.SetLightPower(
                        level=65535, res_required=False, duration=duration, target=pkt.serial
                    )
                else:
                    yield LightMessages.SetLightPower(
                        level=0, res_required=False, duration=duration, target=pkt.serial
                    )

    return FromGenerator(gen)


def PowerToggleGroup(duration=1, **kwargs):
    """
    Returns a valid message that will toggle the power of devices used against it.

    This takes into account the whole group of lights so if any light is turned
    on then all lights are turned off, otherwise they are all turned on

    For example:

    .. code-block:: python

        await target.send(PowerToggle(group=True), ["d073d5000001", "d073d5000001"])
    """

    async def gen(reference, sender, **kwargs):
        get_power = DeviceMessages.GetPower()
        turn_on = True
        async with sender(get_power, reference, **kwargs) as pkts:
            async for pkt in pkts:
                if pkt | DeviceMessages.StatePower:
                    if pkt.level != 0:
                        turn_on = False
                        raise pkts.StopPacketStream()

        if turn_on:
            yield LightMessages.SetLightPower(level=65535, res_required=False, duration=duration)
        else:
            yield LightMessages.SetLightPower(level=0, res_required=False, duration=duration)

    return FromGenerator(gen, reference_override=True)


class Transformer:
    """
    This is responsible for creating the messages to send to a device for a
    transformation

    .. code-block:: python

        msg = Transformer.using({"power": "on", "color": "red"}, keep_brightness=False)
        async for info in target.send(msg, references):
            ...

    If there are no color related attributes specified then we just generate a
    message to set the power on or off as specified.

    If we are turning the light on and have color options then we will first
    ask the device what it's current state is. Lights that are off will be set
    to brightness 0 on the new color and on, and then the brightness will be
    changed to match the end result.

    For the color options we use
    :class:`ColourParser <photons_control.colour.ColourParser>` to create the
    :ref:`SetWaveformOptional <LightMessages.SetWaveformOptional>` message that
    is needed to change the device. This means that we support an ``effect``
    option for setting different waveforms.

    If ``keep_brightness=True`` then we do not change the brightness of the
    device despite any brightness options in the color options.

    If ``transition_color=True`` then we do not change the color of the device
    prior to turning it on, so that it transitions with the brightness.
    """

    @classmethod
    def using(kls, state, keep_brightness=False, transition_color=False, **kwargs):
        transformer = kls()
        has_color_options = transformer.has_color_options(state)

        if "power" not in state and not has_color_options:
            return []

        if state.get("power") == "on" and has_color_options:
            return transformer.power_on_and_color(
                state, keep_brightness=keep_brightness, transition_color=transition_color
            )

        msgs = []
        if "power" in state:
            msgs.append(transformer.power_message(state))

        if has_color_options:
            msgs.append(transformer.color_message(state, keep_brightness))

        if len(msgs) == 1:
            return msgs[0]

        return Pipeline(*msgs)

    def has_color_options(self, state):
        return any(k in state for k in ["hue", "brightness", "saturation", "kelvin", "color"])

    def power_message(self, state):
        power_level = 65535 if state["power"] == "on" else 0

        if state.get("duration") in (sb.NotSpecified, "", 0, None):
            s = dict(state)
            s["level"] = power_level
            s["res_required"] = False
            return DeviceMessages.SetPower.create(**s)
        else:
            s = dict(state)
            s["level"] = power_level
            s["res_required"] = False
            return LightMessages.SetLightPower.create(**s)

    def color_message(self, state, keep_brightness):
        msg = ColourParser.msg(state.get("color", None), overrides=state)
        msg.res_required = False
        if keep_brightness:
            msg.brightness = 0
            msg.set_brightness = False
        return msg

    def power_on_and_color(self, state, keep_brightness=False, transition_color=False):
        power_message = self.power_message(state)
        color_message = self.color_message(state, keep_brightness)

        def receiver(serial, current_state):
            want_brightness = color_message.brightness if color_message.set_brightness else None

            pipeline = []
            currently_off = current_state.power == 0

            if currently_off:

                clone = color_message.clone()
                clone.period = 0
                clone.brightness = 0
                clone.set_brightness = True

                clone.set_hue = 0 if transition_color else clone.set_hue
                clone.set_saturation = 0 if transition_color else clone.set_saturation
                clone.set_kelvin = 0 if transition_color else clone.set_kelvin

                clone.target = serial
                pipeline.append(clone)

                clone = power_message.clone()
                clone.target = serial
                pipeline.append(clone)

            set_color = color_message.clone()
            set_color.target = serial

            if currently_off:
                set_color.brightness = (
                    current_state.brightness if want_brightness is None else want_brightness
                )
                set_color.set_brightness = True
            elif want_brightness is not None:
                set_color.brightness = want_brightness
                set_color.set_brightness = True

            pipeline.append(set_color)

            return Pipeline(*pipeline, synchronized=True)

        async def gen(reference, sender, **kwargs):
            get_color = LightMessages.GetColor(ack_required=False, res_required=True)

            async for pkt in sender(get_color, reference, **kwargs):
                if pkt | LightMessages.LightState:
                    yield receiver(pkt.serial, pkt.payload)

        return FromGenerator(gen)


@an_action(needs_target=True, special_reference=True)
async def transform(collector, target, reference, **kwargs):
    """
    Do a http-api like transformation over whatever target you specify

    ``target:transform d073d5000000 -- '{"color": "red", "effect": "pulse"}'``

    It takes in ``color``, ``effect``, ``power`` and valid options for a
    ``SetWaveformOptional``.

    You may also specify ``transform_options`` that change how the transform works.

    keep_brightness
        Ignore brightness options in the request

    transition_color
        If the light is off and we power on, setting this to True will mean the
        color of the light is not set to the new color before we make it appear
        to be on. This defaults to False, which means it will appear to turn on
        with the new color
    """
    extra = collector.photons_app.extra_as_json
    extra = sb.dictionary_spec().normalise(Meta.empty(), extra)

    transform_options = sb.set_options(transform_options=sb.dictionary_spec()).normalise(
        Meta.empty(), extra
    )["transform_options"]

    msg = Transformer.using(extra, **transform_options)

    if not msg:
        raise PhotonsAppError(
            'Please specify valid options after --. For example ``transform -- \'{"power": "on", "color": "red"}\'``'
        )

    await target.send(msg, reference)


@an_action(needs_target=True, special_reference=True)
async def power_toggle(collector, target, reference, **kwargs):
    """
    Toggle the power of devices.

    ``target:power_toggle match:group_label=kitchen -- '{"duration": 2}'``

    It takes in a ``duration`` field that is the seconds of the duration. This defaults
    to 1 second.
    """
    extra = collector.photons_app.extra_as_json
    msg = PowerToggle(**extra)
    await target.send(msg, reference)
