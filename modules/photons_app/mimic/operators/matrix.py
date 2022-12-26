from delfick_project.norms import dictobj, sb
from photons_app import helpers as hp
from photons_app.mimic.operator import Operator, operator
from photons_app.mimic.operators.light import color_spec
from photons_messages import TileEffectType, TileMessages
from photons_protocol.types import enum_spec


class TileChild(dictobj.Spec):
    accel_meas_x = dictobj.Field(sb.integer_spec, default=0)
    accel_meas_y = dictobj.Field(sb.integer_spec, default=0)
    accel_meas_z = dictobj.Field(sb.integer_spec, default=0)
    user_x = dictobj.Field(sb.float_spec, default=0)
    user_y = dictobj.Field(sb.float_spec, default=0)
    width = dictobj.Field(sb.integer_spec, default=8)
    height = dictobj.Field(sb.integer_spec, default=8)
    device_version_vendor = dictobj.Field(sb.integer_spec, default=1)
    device_version_product = dictobj.Field(sb.integer_spec, default=55)
    device_version_version = dictobj.Field(sb.integer_spec, default=0)
    firmware_version_minor = dictobj.Field(sb.integer_spec, default=50)
    firmware_version_major = dictobj.Field(sb.integer_spec, default=3)
    firmware_build = dictobj.Field(sb.integer_spec, default=0)
    colors = dictobj.Field(sb.listof(color_spec()))


class ChainAttr:
    async def __call__(self, event, options):
        chain_length = options.chain_length
        if not options.chain and not options.chain_length:
            chain_length = 5
        elif not options.chain_length:
            chain_length = len(options.chain)

        spec = TileChild.FieldSpec()

        if event.zerod:
            chain = [spec.empty_normalise() for _ in range(chain_length)]

        else:
            chain = [ch.clone() for ch in options.chain]
            while len(chain) < chain_length:
                chain.append(spec.empty_normalise())

            chain = chain[:chain_length]

        for ch in chain:
            ch.firmware_build = event.device.firmware.build
            ch.firmware_version_minor = event.device.firmware.minor
            ch.firmware_version_major = event.device.firmware.major

            if "candle" in event.device.cap.product.name.lower():
                ch.width = 5
                ch.height = 6
            else:
                ch.width = 8
                ch.height = 8

            ch.device_version_vendor = event.device.cap.product.vendor.vid
            ch.device_version_product = event.device.cap.product.pid

            while len(ch.colors) < ch.height * ch.width:
                ch.colors.append(hp.Color(0, 1, 1, 3500))

        yield event.device.attrs.attrs_path("chain").changer_to(chain)


class PaletteAttr:
    async def __call__(self, event, options):
        palette_count = options.palette_count
        if not options.palette and not options.palette_count:
            palette_count = 0
        elif not options.palette_count:
            palette_count = len(options.palette)

        if event.zerod:
            palette = [hp.Color(0, 0, 0, 0) for _ in range(palette_count)]

        else:
            palette = [p.clone() for p in options.palette]
            while len(palette) < palette_count:
                palette.append(hp.Color(0, 0, 0, 0))

            palette = palette[:palette_count]

        yield event.device.attrs.attrs_path("palette").changer_to(palette)


@operator
class Matrix(Operator):
    class Options(dictobj.Spec):
        chain = dictobj.Field(sb.listof(TileChild.FieldSpec()))
        chain_length = dictobj.NullableField(sb.integer_spec)

        palette = dictobj.Field(sb.listof(color_spec()))
        palette_count = dictobj.NullableField(sb.integer_spec)

        matrix_effect = dictobj.Field(
            enum_spec(None, TileEffectType, unpacking=True), default=TileEffectType.OFF
        )

    @classmethod
    def select(kls, device):
        if not kls.only_io_and_viewer_operators(device.value_store) and device.cap.has_matrix:
            return kls(device, device.value_store)

    attrs = [
        ChainAttr(),
        PaletteAttr(),
        Operator.Attr.Lambda(
            "matrix_effect",
            from_zero=lambda event, options: TileEffectType.OFF,
            from_options=lambda event, options: options.matrix_effect,
        ),
    ]

    async def respond(self, event):
        if event | TileMessages.GetTileEffect:
            event.add_replies(self.state_for(TileMessages.StateTileEffect))

        elif event | TileMessages.SetTileEffect:
            state = self.state_for(TileMessages.StateTileEffect)
            state.instanceid = event.pkt.instanceid
            event.add_replies(state)

            palette_count = max([len(self.device.attrs.palette), len(event.pkt.palette)])

            changes = []
            for i, palette in enumerate(self.device.attrs.palette):
                if i >= palette_count:
                    changes.append(
                        self.device.attrs.attrs_path("palette", i).changer_to(hp.Color(0, 0, 0, 0))
                    )
                else:
                    if self.device.attrs.palette[i] != event.pkt.palette[i]:
                        changes.append(
                            self.device.attrs.attrs_path("palette", i).changer_to(
                                event.pkt.palette[i]
                            )
                        )

            for i in range(palette_count):
                if i >= len(self.device.attrs.palette):
                    changes.append(
                        self.device.attrs.attrs_path("palette", i).changer_to(event.pkt.palette[i])
                    )

            if event.pkt.palette_count > len(self.device.attrs.palette):
                changes.append(
                    self.device.attrs.attrs_path("palette").reduce_length_to(
                        event.pkt.palette_count
                    )
                )

            changes.append(self.device.attrs.attrs_path("matrix_effect").changer_to(event.pkt.type))
            await self.device.attrs.attrs_apply(*changes, event=event)

        elif event | TileMessages.GetDeviceChain:
            event.add_replies(self.state_for(TileMessages.StateDeviceChain))

        elif event | TileMessages.Get64:
            state = []
            res = {
                ch.tile_index: ch for ch in self.state_for(TileMessages.State64, expect_one=False)
            }
            for i in range(event.pkt.tile_index, event.pkt.tile_index + event.pkt.length):
                if i in res:
                    state.append(res[i])
            event.add_replies(*state)

        if event | TileMessages.SetUserPosition:
            if event.pkt.tile_index < len(self.device.attrs.chain):
                await self.device.change(
                    (("chain", event.pkt.tile_index, "user_x"), event.pkt.user_x),
                    (("chain", event.pkt.tile_index, "user_y"), event.pkt.user_y),
                    event=event,
                )
            event.set_replies()

        elif event | TileMessages.Set64:

            state = []
            res = {
                ch.tile_index: ch for ch in self.state_for(TileMessages.State64, expect_one=False)
            }
            for i in range(event.pkt.tile_index, event.pkt.tile_index + event.pkt.length):
                if i in res:
                    state.append(res[i])
            event.add_replies(*state)

            for i in range(event.pkt.tile_index, event.pkt.tile_index + event.pkt.length):
                if i < len(self.device.attrs.chain):
                    # For efficiency, not gonna make events for this
                    chain = self.device.attrs.chain[i]
                    chain.colors.clear()
                    chain.colors.extend(
                        [
                            hp.Color(c.hue, c.saturation, c.brightness, c.kelvin)
                            for c in event.pkt.colors
                        ]
                    )

    def make_state_for(self, kls, result):
        if kls | TileMessages.StateTileEffect:
            palette = []
            if self.device.attrs.matrix_effect is not TileEffectType.OFF:
                palette = self.device.attrs.palette

            result.append(
                kls(
                    type=self.device.attrs.matrix_effect,
                    palette_count=len(palette),
                    palette=palette,
                    parameters={},
                )
            )

        elif kls | TileMessages.StateDeviceChain:
            result.append(
                kls(
                    start_index=0,
                    tile_devices_count=len(self.device.attrs.chain),
                    tile_devices=[c.as_dict() for c in self.device.attrs.chain],
                )
            )

        elif kls | TileMessages.State64:
            for i, ch in enumerate(self.device.attrs.chain):
                result.append(kls(tile_index=i, x=0, y=0, width=ch.width, colors=list(ch.colors)))
