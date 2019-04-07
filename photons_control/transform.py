"""
.. autoclass:: photons_control.transform.Transformer
"""
from photons_control.script import FromGenerator, Pipeline

from photons_app.errors import PhotonsAppError
from photons_app.actions import an_action

from photons_messages import LightMessages, DeviceMessages
from photons_colour import Parser

from input_algorithms import spec_base as sb

def PowerToggle(duration=1):
    """
    Returns a valid message that will toggle the power of devices used against it.

    For example:

    .. code-block:: python

        await target.script(PowerToggle()).run_with_all(["d073d5000001", "d073d5000001"])
    """
    async def gen(reference, afr, **kwargs):
        get_power = DeviceMessages.GetPower()
        async for pkt, _, _ in afr.transport_target.script(get_power).run_with(reference, afr, **kwargs):
            if pkt.level == 0:
                yield LightMessages.SetLightPower(level=65535, res_required=False, duration=duration, target=pkt.serial)
            else:
                yield LightMessages.SetLightPower(level=0, res_required=False, duration=duration, target=pkt.serial)

    return FromGenerator(gen)

class Transformer(object):
    """
    This is responsible for creating the messages to send to a device for a
    transformation

    .. code-block:: python

        msg = Transformer.using({"power": "on", "color": "red"}, keep_brightness=False)
        async for info in target.script(msg).run_with(references):
            ...

    If there are no color related attributes specified then we just generate a
    message to set the power on or off as specified.

    If we are turning the light on and have color options then we will first
    ask the device what it's current state is. Lights that are off will be set
    to brightness 0 on the new color and on, and then the brightness will be
    changed to match the end result.

    For the color options we use ``photons_colour.Parser`` to create the
    ``SetWaveformOptional`` message that is needed to change the device. This
    means that we support an ``effect`` option for setting different waveforms.

    If keep_brightness is True then we do not change the brightness of the device
    despite any brightness options in the color options.
    """
    @classmethod
    def using(kls, state, keep_brightness=False):
        transformer = kls()
        has_color_options = transformer.has_color_options(state)

        if "power" not in state and not has_color_options:
            return []

        if state.get("power") == "on" and has_color_options:
            return transformer.power_on_and_color(state, keep_brightness=keep_brightness)

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
            return DeviceMessages.SetPower(level=power_level, res_required=False)
        else:
            return LightMessages.SetLightPower(level=power_level, duration=state["duration"], res_required=False)

    def color_message(self, state, keep_brightness):
        msg = Parser.color_to_msg(state.get("color", None), overrides=state)
        msg.res_required = False
        if keep_brightness:
            msg.brightness = 0
            msg.set_brightness = False
        return msg

    def power_on_and_color(self, state, keep_brightness=False):
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
                clone.target = serial
                pipeline.append(clone)

                clone = power_message.clone()
                clone.target = serial
                pipeline.append(clone)

            set_color = color_message.clone()
            set_color.target = serial

            if currently_off:
                set_color.brightness = current_state.brightness if want_brightness is None else want_brightness
                set_color.set_brightness = True
            elif want_brightness is not None:
                set_color.brightness = want_brightness
                set_color.set_brightness = True

            pipeline.append(set_color)

            return Pipeline(*pipeline, synchronized=True)

        async def gen(reference, afr, **kwargs):
            get_color = LightMessages.GetColor(ack_required=False, res_required=True)

            async for pkt, _, _ in afr.transport_target.script(get_color).run_with(reference, afr, **kwargs):
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
    """
    msg = Transformer.using(collector.configuration["photons_app"].extra_as_json)
    if not msg:
        raise PhotonsAppError('Please specify valid options after --. For example ``transform -- \'{"power": "on", "color": "red"}\'``')
    await target.script(msg).run_with_all(reference)
