from photons_script.script import Decider, Pipeline
from photons_device_messages import DeviceMessages
from photons_colour import ColourMessages, Parser

from input_algorithms import spec_base as sb

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

    If we have ``keep_brightness=True`` or ``power=on``; and ``color`` options
    then we first ask the devices what their current colour is and use that to
    make the transition to the new state smooth. Essentially when turning a
    light on from off we first set it's brightness to 0 in the new color, then
    turn the light on, then turn the brightness up to the desired level. The
    ``keep_brightness`` option will ensure the light stays the same brightness
    regardless of the ``color`` options.

    For the color options we use ``photons_colour.Parser`` to create the
    ``SetWaveformOptional`` message that is needed to change the device. This
    means that we support an ``effect`` option for setting different waveforms.
    """
    @classmethod
    def using(kls, state, keep_brightness=False):
        transformer = kls()
        has_color_options = transformer.has_color_options(state)

        if "power" not in state and not has_color_options:
            return []

        if keep_brightness or (state.get("power") == "on" and has_color_options):
            return transformer.transition(state, keep_brightness=keep_brightness)

        msgs = []
        if "power" in state:
            msgs.append(transformer.power_message(state))

        if has_color_options:
            msgs.append(transformer.color_message(state))

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
            return DeviceMessages.SetLightPower(level=power_level, duration=state["duration"], res_required=False)

    def color_message(self, state):
        msg = Parser.color_to_msg(state.get("color", None), overrides=state)
        msg.res_required = False
        return msg

    def transition(self, state, keep_brightness=False):
        def receiver(reference, *states):
            if not states:
                return

            current_state = states[0].as_dict()["payload"]
            power_message = None if "power" not in state else self.power_message(state)

            msg_dict = dict(state)
            h, s, b, k = Parser.hsbk(state.get("color", None), overrides=state)
            msg_dict.update({"hue": h, "saturation": s, "brightness": b, "kelvin": k})

            final_overrides = dict(msg_dict)

            pipeline = []

            reset = False

            now_off = current_state["power"] in (None, 0)

            if now_off:
                overrides = dict(msg_dict)
                overrides["brightness"] = 0
                if "duration" in overrides:
                    del overrides["duration"]
                msg = Parser.color_to_msg(None, overrides=overrides)
                msg.target = reference
                msg.ack_required = True
                msg.res_required = False
                reset = True
                pipeline.append(msg)

            if power_message is not None:
                want_off = power_message.level == 0

                if now_off ^ want_off:
                    power_message.target = reference
                    pipeline.append(power_message)

            if keep_brightness or (reset and "brightness" not in state):
                final_overrides["brightness"] = current_state["brightness"]

            msg = Parser.color_to_msg(None, overrides=final_overrides)
            msg.target = reference
            msg.ack_required = True
            msg.res_required = False
            pipeline.append(msg)

            yield Pipeline(*pipeline)

        getter = ColourMessages.GetColor(ack_required=False, res_required=True)
        return Decider(getter, receiver, [ColourMessages.LightState])
