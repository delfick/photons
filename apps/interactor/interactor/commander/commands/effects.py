from interactor.commander.command import DeviceChangeMixin
from interactor.commander import helpers as ihp
from interactor.commander.store import store

from photons_messages.enums import TileEffectType, MultiZoneEffectType
from photons_control.script import FromGeneratorPerSerial
from photons_control.multizone import SetZonesEffect
from photons_control.tile import SetTileEffect
from photons_protocol.types import enum_spec
from photons_canvas.theme import ApplyTheme
from photons_control.planner import Skip

from delfick_project.norms import dictobj, sb
import enum


class EffectCommand(store.Command, DeviceChangeMixin):
    apply_theme = dictobj.Field(
        sb.boolean,
        default=False,
        help="Whether to apply a theme to the devices before running an animation",
    )
    theme_options = dictobj.Field(
        sb.dictionary_spec, help="Any options to give to applying a theme"
    )

    def theme_msg(self):
        return ApplyTheme.msg(self.theme_options)


@store.command(name="effects/run")
class RunEffectCommand(EffectCommand):
    """
    Start or stop a firmware animation on devices that support them
    """

    matrix_animation = dictobj.NullableField(
        enum_spec(None, TileEffectType, unpacking=True),
        help="""
            The animation to run for matrix devices.

            This can be FLAME, MORPH or OFF.

            If you don't supply this these devices will not run any animation"
        """,
    )
    matrix_options = dictobj.Field(
        sb.dictionary_spec,
        help="""
                Any options to give to the matrix animation. For example duration
            """,
    )

    linear_animation = dictobj.NullableField(
        enum_spec(None, MultiZoneEffectType, unpacking=True),
        help="""
            The animation to run for linear devices.

            Currently only MOVE or OFF are supported

            If you don't supply this these devices will not run any animation"
        """,
    )
    linear_options = dictobj.Field(
        sb.dictionary_spec,
        help="""
                Any options to give to the linear animation. For example duration
            """,
    )

    async def execute(self):
        async def gen(reference, afr, **kwargs):
            if self.apply_theme:
                yield self.theme_msg()

            if self.matrix_animation:
                yield SetTileEffect(self.matrix_animation, **self.matrix_options)

            if self.linear_animation:
                yield SetZonesEffect(self.linear_animation, **self.linear_options)

        return await self.send(FromGeneratorPerSerial(gen), add_replies=False)


@store.command(name="effects/stop")
class StopEffectCommand(EffectCommand):
    """
    Stop any firmware effects on devices.
    """

    stop_matrix = dictobj.Field(
        sb.boolean, default=True, help="Whether to stop any matrix animations"
    )
    stop_linear = dictobj.Field(
        sb.boolean, default=True, help="Whether to stop any linear animations"
    )

    async def execute(self):
        async def gen(reference, afr, **kwargs):
            if self.apply_theme:
                yield self.theme_msg()

            if self.stop_matrix:
                yield SetTileEffect(TileEffectType.OFF, palette=[])

            if self.stop_linear:
                yield SetZonesEffect(MultiZoneEffectType.OFF)

        return await self.send(FromGeneratorPerSerial(gen), add_replies=False)


@store.command(name="effects/status")
class StatusEffectCommand(store.Command, DeviceChangeMixin):
    """
    Returns the current status of effects on devices that support them
    """

    async def execute(self):
        plans = self.sender.make_plans("capability", "firmware_effects")
        self.sender.gatherer.clear_cache()

        serials = await self.serials
        result = ihp.ResultBuilder()
        result.add_serials(serials)

        def convert(d):
            for k, v in d.items():
                if isinstance(v, enum.Enum):
                    d[k] = v.name
            return d

        async for serial, complete, info in self.sender.gatherer.gather_per_serial(
            plans, serials, error_catcher=result.error, message_timeout=self.timeout
        ):
            if not complete:
                continue

            cap = info["capability"]["cap"]
            final = {
                "product": {
                    "pid": cap.product.pid,
                    "vid": cap.product.vendor.vid,
                    "cap": convert(cap.as_dict()),
                    "name": cap.product.name,
                },
                "effect": {"type": "SKIP"},
            }

            effects = info["firmware_effects"]
            if effects is not Skip:
                final["effect"]["type"] = effects["type"].name
                final["effect"]["options"] = convert(effects["options"])

            result.result["results"][serial] = final

        return result
