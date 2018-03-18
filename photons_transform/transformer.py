from photons_script.script import Decider, Pipeline
from photons_device_messages import DeviceMessages
from photons_colour import ColourMessages, Parser

from input_algorithms import spec_base as sb

class Transformer(object):
    """
    This is responsible for creating the messages to send to a device for a
    transformation

    .. code-block:: python

        msg = Transformer.using({"power": "on"}, keep_brightness=False)
        async for info in target.script(msg).run_with(references):
            ...

    If there are no color related attributes specified then we just generate a
    message to set the power on or off as specified.

    If we do have colour related options, then we return a script that will
    first do a ``GetColor`` for each reference and create messages based on the
    result.

    It will have a look at the current power on the device and what is wanted
    and set the difference.

    Finally, it'll use ``photons_colour.Parser`` to create the
    ``SetWaveformOptional`` message that is needed to change the device.
    """
    @classmethod
    def using(kls, state, keep_brightness=False):
        power_level = None
        power_message = None
        if "power" in state:
            power_level = 65535 if state["power"] == "on" else 0

        if "power" in state and state.get("duration") in (sb.NotSpecified, "", 0, None):
            power_message = DeviceMessages.SetPower(level=power_level)
        elif "power" in state:
            power_message = DeviceMessages.SetLightPower(level=power_level, duration=state["duration"])

        if all(k not in state for k in ["hue", "brightness", "saturation", "kelvin", "color"]) and power_message is not None:
            return power_message

        if "color" not in state:
            state["color"] = None

        def receiver(reference, *states):
            if not states:
                return

            current_state = states[0].as_dict()["payload"]

            msg_dict = dict(state)
            h, s, b, k = Parser.hsbk(state["color"], overrides=state)
            msg_dict.update({"hue": h, "saturation": s, "brightness": b, "kelvin": k})

            final_overrides = dict(msg_dict)

            pipeline = []

            reset = None
            if current_state["power"] in (None, 0):
                overrides = dict(msg_dict)
                overrides["brightness"] = 0
                if "duration" in overrides:
                    del overrides["duration"]
                msg = Parser.color_to_msg(None, overrides=overrides)
                msg.target = reference
                msg.ack_required = True
                msg.res_required = False
                reset = msg
                pipeline.append(reset)

            if power_message is not None:
                if (power_level == 65535 and current_state["power"] in (None, 0)) or (power_level == 0 and current_state["power"] == 65535):
                    power = power_message.clone()
                    power.target = reference
                    power.ack_required = True
                    power.res_required = False
                    pipeline.append(power)

            if keep_brightness or (reset is not None and "brightness" not in state):
                final_overrides["brightness"] = current_state["brightness"]

            msg = Parser.color_to_msg(None, overrides=final_overrides)
            msg.target = reference
            msg.ack_required = True
            msg.res_required = False
            pipeline.append(msg)

            yield Pipeline(*pipeline)

        getter = ColourMessages.GetColor(ack_required=False, res_required=True)
        return Decider(getter, receiver, [ColourMessages.LightState])
