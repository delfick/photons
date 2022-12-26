from delfick_project.norms import BadSpecValue, dictobj, sb
from photons_app import helpers as hp
from photons_app.mimic.operator import Operator, operator
from photons_messages import DeviceMessages, LightMessages
from photons_products import Family


class color_spec(sb.Spec):
    def normalise(self, meta, val):
        if val is sb.NotSpecified:
            return hp.Color(0, 0, 1, 3500)

        keys = ("hue", "saturation", "brightness", "kelvin")

        if isinstance(val, (list, tuple)):
            while len(val) < 4:
                val = (*val, 0)
        elif isinstance(val, dict):
            for k in keys:
                if k not in val:
                    val = {**val, k: 0}
            val = tuple(val[k] for k in keys)
        elif any(hasattr(val, k) for k in keys):
            val = tuple(getattr(val, k, 0) for k in keys)
        else:
            raise BadSpecValue("Unknown value for color", got=val, meta=meta)

        return hp.Color(*val[:4])


class infrared_spec(sb.Spec):
    def normalise(self, meta, val):
        if val is sb.NotSpecified:
            return 0

        if isinstance(val, bool):
            return 0 if val is False else 0xFFFF
        elif isinstance(val, int):
            return val
        elif val in ("on", "off"):
            return 0 if val == "off" else 0xFFFF
        else:
            raise BadSpecValue("Unknown value for infrared", got=val, meta=meta)


@operator
class LightState(Operator):
    class Options(dictobj.Spec):
        color = dictobj.Field(color_spec)

    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store) and device.cap.is_light:
            return kls(device, device.value_store)

    attrs = [
        Operator.Attr.Lambda(
            "color",
            from_zero=lambda event, options: hp.Color(0, 1, 1, 3500),
            from_options=lambda event, options: options.color,
        )
    ]

    async def respond(self, event):
        if event | LightMessages.GetColor:
            event.add_replies(self.state_for(LightMessages.LightState))

        elif event | LightMessages.GetLightPower:
            event.add_replies(self.state_for(DeviceMessages.StatePower))

        elif event | LightMessages.SetLightPower:
            event.add_replies(self.state_for(LightMessages.StateLightPower))
            await self.change_one("power", event.pkt.level, event=event)

        elif event | LightMessages.SetColor or event | LightMessages.SetWaveform:
            event.add_replies(self.state_for(LightMessages.LightState))
            await self.change(
                (("color", "hue"), event.pkt.hue),
                (("color", "saturation"), event.pkt.saturation),
                (("color", "brightness"), event.pkt.brightness),
                (("color", "kelvin"), event.pkt.kelvin),
                event=event,
            )
        elif event | LightMessages.SetWaveformOptional:
            event.add_replies(self.state_for(LightMessages.LightState))

            changes = []

            for k in ("hue", "saturation", "brightness", "kelvin"):
                if getattr(event.pkt, f"set_{k}"):
                    changes.append(
                        self.device.attrs.attrs_path("color", k).changer_to(event.pkt[k])
                    )

            if changes:
                await self.device.attrs.attrs_apply(*changes, event=event)

    def make_state_for(self, kls, result):
        if kls | LightMessages.StateLightPower:
            result.append(kls(level=self.device.attrs.power))

        elif kls | LightMessages.LightState:
            result.append(
                kls(
                    label=self.device.attrs.label,
                    power=self.device.attrs.power,
                    **self.device.attrs.color.as_dict(),
                )
            )


@operator
class Infrared(Operator):
    class Options(dictobj.Spec):
        infrared = dictobj.Field(infrared_spec)

    @classmethod
    def select(kls, device):
        # Some products respond to IR even though they don't have those LEDs
        has_ir = device.cap.has_ir or device.cap.product.family is Family.LCM3
        if not kls.only_io_and_viewer_operators(device.value_store) and has_ir:
            return kls(device, device.value_store)

    attrs = [
        Operator.Attr.Lambda(
            "infrared",
            from_zero=lambda event, options: 0,
            from_options=lambda event, options: options.infrared,
        )
    ]

    async def respond(self, event):
        if event | LightMessages.GetInfrared:
            event.add_replies(self.state_for(LightMessages.StateInfrared))

        elif event | LightMessages.SetInfrared:
            event.add_replies(self.state_for(LightMessages.StateInfrared))
            await self.change_one("infrared", event.pkt.brightness, event=event)

    def make_state_for(self, kls, result):
        if kls | LightMessages.StateInfrared:
            result.append(kls(brightness=self.device.attrs.infrared))
