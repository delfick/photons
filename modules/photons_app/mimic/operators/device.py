from delfick_project.norms import BadSpecValue, dictobj, sb
from photons_app.mimic.operator import Operator, operator
from photons_messages import DeviceMessages
from photons_protocol.types import bytes_spec


class identity_spec(sb.Spec):
    def __init__(self):
        self.spec = bytes_spec(None, 16 * 8)

    def normalise(self, meta, val):
        val = self.spec.normalise(meta, val)
        return val.tobytes()


class Collection(dictobj.Spec):
    label = dictobj.Field(sb.string_spec, default="")
    identity = dictobj.Field(identity_spec, default=b"")
    updated_at = dictobj.Field(sb.integer_spec, default=0)

    @classmethod
    def create(
        self, *, identity=sb.NotSpecified, label=sb.NotSpecified, updated_at=sb.NotSpecified
    ):
        return Collection.FieldSpec().empty_normalise(
            identity=identity, label=label, updated_at=updated_at
        )


class power_spec(sb.Spec):
    def normalise(self, meta, val):
        if val is sb.NotSpecified:
            return 0

        if isinstance(val, bool):
            return 0 if val is False else 0xFFFF
        elif isinstance(val, int):
            return 0 if val == 0 else 0xFFFF
        elif val in ("on", "off"):
            return 0 if val == "off" else 0xFFFF
        else:
            raise BadSpecValue("Unknown value for power", got=val, meta=meta)


@operator
class Device(Operator):
    class Options(dictobj.Spec):
        power = dictobj.Field(power_spec)
        label = dictobj.Field(sb.string_spec(), default="")

    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store):
            return kls(device, device.value_store)

    attrs = [
        Operator.Attr.Lambda(
            "power",
            from_zero=lambda event, options: 0,
            from_options=lambda event, options: options.power,
        ),
        Operator.Attr.Lambda(
            "label",
            from_zero=lambda event, options: "",
            from_options=lambda event, options: options.label,
        ),
    ]

    async def respond(self, event):
        if event | DeviceMessages.GetLabel:
            event.add_replies(self.state_for(DeviceMessages.StateLabel))

        elif event | DeviceMessages.GetPower:
            event.add_replies(self.state_for(DeviceMessages.StatePower))

        elif event | DeviceMessages.SetLabel:
            await self.change_one("label", event.pkt.label, event=event)
            event.add_replies(self.state_for(DeviceMessages.StateLabel))

        elif event | DeviceMessages.SetPower:
            event.add_replies(self.state_for(DeviceMessages.StatePower))
            await self.change_one("power", event.pkt.level, event=event)

        elif event | DeviceMessages.EchoRequest:
            event.add_replies(DeviceMessages.EchoResponse(echoing=event.pkt.echoing))

    def make_state_for(self, kls, result):
        if kls | DeviceMessages.StateLabel:
            result.append(kls(label=self.device.attrs.label))

        elif kls | DeviceMessages.StatePower:
            result.append(kls(level=self.device.attrs.power))


@operator
class Grouping(Operator):
    class Options(dictobj.Spec):
        group = dictobj.Field(Collection.FieldSpec())
        location = dictobj.Field(Collection.FieldSpec())

    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store):
            return kls(device, device.value_store)

    attrs = [
        Operator.Attr.Lambda(
            "group",
            from_zero=lambda event, options: Collection.FieldSpec().empty_normalise(),
            from_options=lambda event, options: options.group.clone(),
        ),
        Operator.Attr.Lambda(
            "location",
            from_zero=lambda event, options: Collection.FieldSpec().empty_normalise(),
            from_options=lambda event, options: options.location.clone(),
        ),
    ]

    async def respond(self, event):
        if event | DeviceMessages.GetGroup:
            event.add_replies(self.state_for(DeviceMessages.StateGroup))

        elif event | DeviceMessages.GetLocation:
            event.add_replies(self.state_for(DeviceMessages.StateLocation))

        elif event | DeviceMessages.SetGroup:
            await self.change(
                (("group", "identity"), event.pkt.group),
                (("group", "label"), event.pkt.label),
                (("group", "updated_at"), event.pkt.updated_at),
                event=event,
            )
            event.add_replies(self.state_for(DeviceMessages.StateGroup))

        elif event | DeviceMessages.SetLocation:
            await self.change(
                (("location", "identity"), event.pkt.location),
                (("location", "label"), event.pkt.label),
                (("location", "updated_at"), event.pkt.updated_at),
                event=event,
            )
            event.add_replies(self.state_for(DeviceMessages.StateLocation))

    def make_state_for(self, kls, result):
        if kls | DeviceMessages.StateGroup:
            result.append(
                kls(
                    group=self.device.attrs.group.identity,
                    label=self.device.attrs.group.label,
                    updated_at=self.device.attrs.group.updated_at,
                )
            )

        elif kls | DeviceMessages.StateLocation:
            result.append(
                kls(
                    location=self.device.attrs.location.identity,
                    label=self.device.attrs.location.label,
                    updated_at=self.device.attrs.location.updated_at,
                )
            )


@operator
class Product(Operator):
    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store):
            return kls(device, device.value_store)

    async def respond(self, event):
        if event | DeviceMessages.GetVersion:
            event.add_replies(self.state_for(DeviceMessages.StateVersion))

        elif event | DeviceMessages.GetHostFirmware:
            event.add_replies(self.state_for(DeviceMessages.StateHostFirmware))

        elif event | DeviceMessages.GetWifiFirmware:
            event.add_replies(self.state_for(DeviceMessages.StateWifiFirmware))

    def make_state_for(self, kls, result):
        if kls | DeviceMessages.StateWifiFirmware:
            result.append(kls(build=0, version_major=0, version_minor=0))

        elif kls | DeviceMessages.StateVersion:
            result.append(
                kls(vendor=self.device.cap.product.vendor.vid, product=self.device.cap.product.pid)
            )

        elif kls | DeviceMessages.StateHostFirmware:
            result.append(
                kls(
                    build=self.device.firmware.build,
                    version_major=self.device.firmware.major,
                    version_minor=self.device.firmware.minor,
                )
            )
