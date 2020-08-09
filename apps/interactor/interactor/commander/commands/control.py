from interactor.commander.command import DeviceChangeMixin
from interactor.commander import helpers as ihp
from interactor.commander.store import store

from photons_control.transform import Transformer, PowerToggle
from photons_canvas.theme import ApplyTheme

from delfick_project.norms import dictobj, sb

pkt_type_field = dictobj.Field(
    sb.or_spec(sb.integer_spec(), sb.string_spec()),
    wrapper=sb.required,
    help="""
        The type of packet to send to the lights. This can be a number or
        the name of the packet as known by the photons framework.

        A list of what's available can be found at
        https://photons.delfick.com/interacting/packets.html
      """,
)

pkt_args_field = dictobj.NullableField(
    sb.dictionary_spec(),
    help="""
        A dictionary of fields that make up the payload of the packet we
        are sending to the lights.
      """,
)


@store.command(name="status")
class StatusCommand(store.Command):
    async def execute(self):
        return {"on": True}


@store.command(name="discover")
class DiscoverCommand(store.Command, DeviceChangeMixin):
    """
    Display information about all the devices that can be found on the network
    """

    just_serials = dictobj.Field(
        sb.boolean,
        default=False,
        help="Just return a list of serials instead of all the information per device",
    )

    async def execute(self):
        if self.just_serials:
            return await self.serials
        else:
            return {device.serial: device.info for device in await self.devices}


@store.command(name="query")
class QueryCommand(store.Command, DeviceChangeMixin):
    """
    Send a pkt to devices and return the result
    """

    pkt_type = pkt_type_field
    pkt_args = pkt_args_field

    async def execute(self):
        msg = ihp.make_message(self.pkt_type, self.pkt_args)
        return await self.send(msg)


@store.command(name="power_toggle")
class PowerToggleCommand(store.Command, DeviceChangeMixin):
    """
    Toggle the power of the lights you specify
    """

    duration = dictobj.NullableField(sb.float_spec, help="Duration of the toggle")

    group = dictobj.NullableField(sb.boolean, help="Whether to treat the lights as a group")

    async def execute(self):
        kwargs = {}
        if self.duration:
            kwargs["duration"] = self.duration
        if self.group is not None:
            kwargs["group"] = self.group
        msg = PowerToggle(**kwargs)
        return await self.send(msg, add_replies=False)


@store.command(name="transform")
class TransformCommand(store.Command, DeviceChangeMixin):
    """
    Apply a http api like transformation to the lights
    """

    transform = dictobj.Field(
        sb.dictionary_spec(),
        wrapper=sb.required,
        help="""
            A dictionary of what options to use to transform the lights with.

            For example,
            ``{"power": "on", "color": "red"}``

            Or,
            ``{"color": "blue", "effect": "breathe", "cycles": 5}``
          """,
    )

    transform_options = dictobj.Field(
        sb.dictionary_spec(),
        help="""
            A dictionay of options that modify the way the tranform
            is performed:

            keep_brightness
                Ignore brightness options in the request

            transition_color
                If the light is off and we power on, setting this to True will mean the
                color of the light is not set to the new color before we make it appear
                to be on. This defaults to False, which means it will appear to turn on
                with the new color
            """,
    )

    async def execute(self):
        msg = Transformer.using(self.transform, **self.transform_options)
        return await self.send(msg, add_replies=False)


@store.command(name="set")
class SetCommand(store.Command, DeviceChangeMixin):
    """
    Send a pkt to devices. This is the same as query except res_required is False
    and results aren't returned
    """

    pkt_type = pkt_type_field
    pkt_args = pkt_args_field

    async def execute(self):
        msg = ihp.make_message(self.pkt_type, self.pkt_args)
        msg.res_required = False
        return await self.send(msg)


@store.command(name="apply_theme")
class ApplyThemeCommand(store.Command, DeviceChangeMixin):
    theme_options = dictobj.Field(
        sb.dictionary_spec, help="Any options to give to applying a theme"
    )

    async def execute(self):
        return await self.send(ApplyTheme.msg(self.theme_options), add_replies=False)
