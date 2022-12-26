import typing as tp

from delfick_project.norms import dictobj, sb
from photons_app.mimic.event import Event, Events
from photons_app.mimic.operator import Operator, operator
from photons_messages import DeviceMessages, RelayMessages

# Ensure Device operator comes before this one
__import__("photons_app.mimic.operators.device")


@Events.register("SET_RELAYS_POWER")
class SetRelaysPower(Event):
    """Used to change the power of zero or more relays"""

    def setup(self, *, relays: tp.Dict[int, int]):
        self.relays = relays

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:relays={self.relays}>"


class RelayPowerGetter:
    def __init__(self, index):
        self.index = index

    def __or__(self, other):
        return other == RelayPowerGetter


class Relay(dictobj.Spec):
    power = dictobj.Field(sb.integer_spec(), default=0)

    @classmethod
    def create(kls, **kwargs):
        return kls.FieldSpec().empty_normalise(**kwargs)


class RelaysAttr:
    async def __call__(self, event, options):
        if event.zerod:
            options = Relays.Options.FieldSpec().empty_normalise()

        relays = list(options.relays) if options.relays is not None else []
        relays_count = (
            options.relays_count
            if isinstance(options.relays_count, int) and options.relays_count > 0
            else 4
        )

        while len(relays) < relays_count:
            relays.append(Relay.FieldSpec().empty_normalise())

        yield event.device.attrs.attrs_path("relays").changer_to([r.clone() for r in relays])


@operator
class Relays(Operator):
    class Options(dictobj.Spec):
        relays = dictobj.NullableField(sb.listof(Relay.FieldSpec()))
        relays_count = dictobj.NullableField(sb.integer_spec())

    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store) and device.cap.has_relays:
            return kls(device, device.value_store)

    async def apply(self):
        self.device.operators.insert(0, self)

    attrs = [RelaysAttr()]

    async def respond(self, event):
        if event | RelayMessages.GetRPower:
            event.add_replies(self.state_for(RelayPowerGetter(event.pkt.relay_index)))

        elif event | RelayMessages.SetRPower:
            event.add_replies(self.state_for(RelayPowerGetter(event.pkt.relay_index)))
            await self.respond(
                SetRelaysPower(self.device, relays={event.pkt.relay_index: event.pkt.level})
            )

        elif event | DeviceMessages.SetPower:
            event.set_replies(self.state_for(DeviceMessages.StatePower))
            await self.respond(
                SetRelaysPower(
                    self.device,
                    relays={
                        index: event.pkt.level for index in range(len(self.device.attrs.relays))
                    },
                )
            )

        elif event | SetRelaysPower:
            changes = []
            powers = {index: r.power for index, r in enumerate(self.device.attrs.relays)}

            for index, power in event.relays.items():
                if 0 <= index < len(self.device.attrs.relays):
                    new_power = 0 if power == 0 else 65535
                    changes.append(
                        self.device.attrs.attrs_path("relays", index, "power").changer_to(new_power)
                    )
                    powers[index] = new_power

            # On a real switch this changes depending on how you've setup your switch
            # But the public protocol doesn't expose that information
            power = 0
            if any(p > 0 for p in powers.values()):
                power = 65535
            changes.append(self.device.attrs.attrs_path("power").changer_to(power))

            await self.device.attrs.attrs_apply(*changes, event=event)

    def make_state_for(self, kls, result):
        if kls | RelayPowerGetter:
            if 0 < kls.index < len(self.device.attrs.relays):
                result.append(
                    RelayMessages.StateRPower(
                        relay_index=kls.index, level=self.device.attrs.relays[kls.index].power
                    )
                )
