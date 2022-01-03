from photons_app.mimic.operator import Operator, operator
from photons_app.mimic.operators.device import power_spec

from photons_messages import RelayMessages

from delfick_project.norms import dictobj, sb


# Ensure Device operator comes before this one
__import__("photons_app.mimic.operators.device")


@operator
class Switch(Operator):
    class Options(dictobj.Spec):
        relays = dictobj.Field(
            sb.dictof(sb.integer_spec(), power_spec()), default={0: 0, 1: 0, 2: 0, 3: 0}
        )

    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store) and not device.cap.is_light:
            return kls(device, device.value_store)

    attrs = [
        Operator.Attr.Lambda(
            "relays",
            from_zero=lambda event, options: {},
            from_options=lambda event, options: options.relays,
        ),
    ]

    def get_relay_power(self, event):
        self.relay_index = event.pkt.relay_index

    async def set_relay_power(self, event):
        self.relay_index = event.pkt.relay_index
        self.device.attrs.relays[event.pkt.relay_index] = event.pkt.level
        await self.change_one(("relays", event.pkt.relay_index), event.pkt.level, event=event)

    async def respond(self, event):
        if event | RelayMessages.GetRPower:
            self.get_relay_power(event)
            event.add_replies(self.state_for(RelayMessages.StateRPower))

        elif event | RelayMessages.SetRPower:
            await self.set_relay_power(event)
            event.add_replies(self.state_for(RelayMessages.StateRPower))

    def make_state_for(self, kls, result):
        if kls | RelayMessages.StateRPower:
            result.append(
                kls(relay_index=self.relay_index, level=self.device.attrs.relays[self.relay_index])
            )
