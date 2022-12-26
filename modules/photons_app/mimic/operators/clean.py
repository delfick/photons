import time

from delfick_project.norms import dictobj, sb
from photons_app import helpers as hp
from photons_app.mimic.event import Events
from photons_app.mimic.operator import Operator, operator
from photons_messages import DeviceMessages, LightLastHevCycleResult, LightMessages
from photons_protocol.types import enum_spec

# Ensure Device operator comes before this one
__import__("photons_app.mimic.operators.device")


class CleanDetails(dictobj.Spec):
    def __init__(self, device, indication, last_result, default_duration_s):
        self.device = device

        self.indication = indication
        self.last_result = last_result
        self.default_duration_s = default_duration_s

        self.enabled = False
        self.duration_s = 0

        self.last_trigger = None
        self.triggered_at = None

    @property
    def remaining_s(self):
        if self.triggered_at is None:
            return 0
        return max([0, int(self.duration_s - (time.time() - self.triggered_at))])

    @property
    def last_power(self):
        if self.enabled:
            return self.device.attrs.power > 0
        else:
            return 0

    async def set_cycle(self, event):
        duration = event.pkt.duration_s
        if duration == 0:
            duration = self.default_duration_s

        if self.enabled and not event.pkt.enable:
            await self.stop_cycle(event, stopped=LightLastHevCycleResult.INTERRUPTED_BY_LAN)

        changes = [
            (("clean_details", "enabled"), bool(event.pkt.enable)),
            (("clean_details", "duration_s"), 0 if not event.pkt.enable else duration),
        ]

        if event.pkt.enable:
            changes.append((("clean_details", "last_result"), LightLastHevCycleResult.BUSY))

            if self.last_trigger is not None:
                self.last_trigger.cancel()
                self.last_trigger = None

            self.triggered_at = time.time()
            self.last_trigger = hp.get_event_loop().call_later(
                duration, lambda: self.device.io["MEMORY"].ts.add(self.stop_cycle(event))
            )

        await self.device.change(*changes, event=event)

    async def set_cycle_config(self, event):
        await self.device.change(
            (("clean_details", "indication"), bool(event.pkt.indication)),
            (("clean_details", "default_duration_s"), event.pkt.duration_s),
            event=event,
        )

    async def stop_cycle(self, event, stopped=LightLastHevCycleResult.SUCCESS):
        if self.last_trigger is not None:
            self.last_trigger.cancel()
            self.last_trigger = None

        await self.device.change(
            (("clean_details", "enabled"), False),
            (("clean_details", "last_result"), stopped),
            (("clean_details", "duration_s"), 0),
            event=event,
        )


class CleanDetailsAttr:
    async def __call__(self, event, options):
        if event.zerod:
            options = Clean.Options.FieldSpec().empty_normalise()

        details = CleanDetails(
            event.device,
            options.clean_indication,
            options.clean_last_result,
            options.clean_default_duration_s,
        )

        yield event.device.attrs.attrs_path("clean_details").changer_to(details)


@operator
class Clean(Operator):
    class Options(dictobj.Spec):
        clean_indication = dictobj.Field(sb.boolean, default=False)
        clean_last_result = dictobj.Field(
            enum_spec(None, LightLastHevCycleResult, unpacking=True),
            default=LightLastHevCycleResult.NONE,
        )
        clean_default_duration_s = dictobj.Field(sb.float_spec, default=7200)

    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store) and device.cap.has_hev:
            return kls(device, device.value_store)

    attrs = [CleanDetailsAttr()]

    async def respond(self, event):
        if event | Events.SHUTTING_DOWN:
            if self.device.attrs._started:
                await self.change(
                    (("clean_details", "enabled"), False),
                    (("clean_details", "duration_s"), 0),
                    (
                        ("clean_details", "last_result"),
                        LightLastHevCycleResult.INTERRUPTED_BY_RESET,
                    ),
                    event=event,
                )

        elif event | LightMessages.GetHevCycle:
            event.set_replies(self.state_for(LightMessages.StateHevCycle))

        elif event | LightMessages.GetHevCycleConfiguration:
            event.set_replies(self.state_for(LightMessages.StateHevCycleConfiguration))

        elif event | LightMessages.GetLastHevCycleResult:
            event.set_replies(self.state_for(LightMessages.StateLastHevCycleResult))

        elif event | LightMessages.SetHevCycle:
            event.set_replies(self.state_for(LightMessages.StateHevCycle))
            duration = event.pkt.duration_s
            if duration == 0:
                duration = self.device.attrs.clean_details.default_duration_s
            await self.device.attrs.clean_details.set_cycle(event)

        elif event | LightMessages.SetHevCycleConfiguration:
            await self.device.attrs.clean_details.set_cycle_config(event)
            event.set_replies(self.state_for(LightMessages.StateHevCycleConfiguration))

    def make_state_for(self, kls, result):
        if kls | DeviceMessages.StatePower:
            if result and self.device.attrs.clean_details.enabled:
                result[0].level = 65535

        elif kls | LightMessages.StateHevCycle:
            result.append(
                kls(
                    duration_s=self.device.attrs.clean_details.duration_s,
                    remaining_s=self.device.attrs.clean_details.remaining_s,
                    last_power=self.device.attrs.clean_details.last_power,
                )
            )

        elif kls | LightMessages.StateHevCycleConfiguration:
            result.append(
                kls(
                    indication=self.device.attrs.clean_details.indication,
                    duration_s=self.device.attrs.clean_details.default_duration_s,
                )
            )

        elif kls | LightMessages.StateLastHevCycleResult:
            result.append(kls(result=self.device.attrs.clean_details.last_result))
