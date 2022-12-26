from delfick_project.norms import dictobj, sb
from photons_app import helpers as hp
from photons_app.mimic.event import Event, Events
from photons_app.mimic.operator import Operator, operator
from photons_app.mimic.operators.light import color_spec
from photons_messages import MultiZoneEffectType, MultiZoneMessages
from photons_protocol.types import enum_spec


class ZonesAttr:
    async def __call__(self, event, options):
        zones_count = options.zones_count
        if not options.zones and not options.zones_count:
            zones_count = 16
        elif not options.zones_count:
            zones_count = len(options.zones)

        if zones_count > 82:
            zones_count = 82
        if zones_count < 0:
            zones_count = 0

        if event.zerod:
            zones = [hp.Color(0, 1, 1, 3500) for _ in range(zones_count)]

        else:
            zones = [c.clone() for c in options.zones]
            while len(zones) < zones_count:
                zones.append(hp.Color(0, 0, 1, 3500))

            zones = zones[:zones_count]

        yield event.device.attrs.attrs_path("zones").changer_to(zones)


@Events.register("SET_ZONES")
class SetZones(Event):
    """
    Used to say the device should change a zone to something
    """

    def setup(self, *, zones):
        self.zones = zones
        self.log_kwargs = {"num_changed_zones": len(zones)}


class GetZonesCallable:
    def __or__(self, other):
        return other == GetZonesCallable


@operator
class Multizone(Operator):
    class Options(dictobj.Spec):
        zones = dictobj.Field(sb.listof(color_spec()))
        zones_count = dictobj.NullableField(sb.integer_spec)

        zones_effect = dictobj.Field(
            enum_spec(None, MultiZoneEffectType, unpacking=True), default=MultiZoneEffectType.OFF
        )

    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store) and device.cap.has_multizone:
            return kls(device, device.value_store)

    attrs = [
        ZonesAttr(),
        Operator.Attr.Lambda(
            "zones_effect",
            from_zero=lambda event, options: MultiZoneEffectType.OFF,
            from_options=lambda event, options: options.zones_effect,
        ),
    ]

    async def respond(self, event):
        if event | Events.SET_ZONES:
            changes = []
            for index, color in event.zones:
                if index >= len(self.device.attrs.zones):
                    continue
                changes.append(self.device.attrs.attrs_path("zones", index).changer_to(color))
            await self.device.attrs.attrs_apply(*changes, event=event)

        elif event | MultiZoneMessages.GetMultiZoneEffect:
            event.add_replies(self.state_for(MultiZoneMessages.StateMultiZoneEffect))

        elif event | MultiZoneMessages.GetColorZones:
            getter = self.state_for(GetZonesCallable())
            for state in getter(event.pkt.start_index, event.pkt.end_index):
                event.add_replies(state)

        elif event | MultiZoneMessages.SetMultiZoneEffect:
            state = self.state_for(MultiZoneMessages.StateMultiZoneEffect)
            await self.change_one("zones_effect", event.pkt.type, event=event)
            event.add_replies(state)

        elif event | MultiZoneMessages.SetColorZones:
            getter = self.state_for(GetZonesCallable())
            state = getter(event.pkt.start_index, event.pkt.end_index)
            event.add_replies(*state)

            zones = []
            color = hp.Color(
                event.pkt.hue, event.pkt.saturation, event.pkt.brightness, event.pkt.kelvin
            )
            for i in range(event.pkt.start_index, event.pkt.end_index + 1):
                zones.append((i, color))
            await self.respond(Events.SET_ZONES(self.device, zones=zones))

    def make_state_for(self, kls, result):
        if kls | MultiZoneMessages.StateMultiZoneEffect:
            result.append(kls(type=self.device.attrs.zones_effect))

        elif kls | GetZonesCallable:
            result.append(self.get_zones)

    def get_zones(self, start_index=0, end_index=255):
        buf = []
        bufs = []

        for i, zone in enumerate(self.device.attrs.zones):
            if i < start_index or i > end_index:
                continue

            if len(buf) == 8:
                bufs.append(buf)
                buf = []

            buf.append((i, zone))

        if buf:
            bufs.append(buf)

        for buf in bufs:
            if len(buf) == 1:
                yield MultiZoneMessages.StateZone(
                    zones_count=len(self.device.attrs.zones),
                    zone_index=buf[0][0],
                    **buf[0][1].as_dict(),
                )
                continue

            yield MultiZoneMessages.StateMultiZone(
                zones_count=len(self.device.attrs.zones),
                zone_index=buf[0][0],
                colors=[b.as_dict() for _, b in buf],
            )


@operator
class ExtendedMultizone(Operator):
    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store) and device.cap.has_multizone:
            return kls(device, device.value_store)

    async def respond(self, event):
        if not self.device.cap.has_extended_multizone:
            return

        if event | MultiZoneMessages.GetExtendedColorZones:
            event.add_replies(self.state_for(MultiZoneMessages.StateExtendedColorZones))

        elif event | MultiZoneMessages.SetExtendedColorZones:
            event.add_replies(self.state_for(MultiZoneMessages.StateExtendedColorZones))

            zones = []
            for i, color in enumerate(event.pkt.colors[: event.pkt.colors_count]):
                zones.append((i + event.pkt.zone_index, color))

            zones = zones[: len(self.device.attrs.zones)]
            await self.device.event_with_options(
                Events.SET_ZONES, args=(), kwargs={"zones": zones}, visible=False
            )

    def make_state_for(self, kls, result):
        if not self.device.cap.has_extended_multizone:
            return

        if kls | MultiZoneMessages.StateExtendedColorZones:
            result.append(
                kls(
                    zones_count=len(self.device.attrs.zones),
                    zone_index=0,
                    colors_count=len(self.device.attrs.zones),
                    colors=[z.as_dict() for z in self.device.attrs.zones],
                )
            )
