from photons_app.actions import an_action
from photons_app import helpers as hp

from photons_control.script import FromGeneratorPerSerial
from photons_messages import LightMessages, TileMessages
from photons_control.planner import Gatherer, make_plans
from photons_themes.appliers import types as appliers
from photons_control.multizone import SetZonesPlan
from photons_control.attributes import make_colors
from photons_messages.fields import Color
from photons_themes.theme import Theme
from photons_colour import Parser

from delfick_project.norms import sb, dictobj, Meta
from delfick_project.addons import addon_hook
import logging


@addon_hook(
    extras=[
        ("lifx.photons", "products"),
        ("lifx.photons", "messages"),
        ("lifx.photons", "colour"),
        ("lifx.photons", "control"),
    ]
)
def __lifx__(collector, *args, **kwargs):
    pass


__shortdesc__ = "Determine how to apply themes to devices"

log = logging.getLogger("photons_themes")

default_colors = [
    (0, 1, 0.3, 3500),
    (40, 1, 0.3, 3500),
    (60, 1, 0.3, 3500),
    (127, 1, 0.3, 3500),
    (239, 1, 0.3, 3500),
    (271, 1, 0.3, 3500),
    (294, 1, 0.3, 3500),
]


class colors_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        overrides = meta.everything.get("overrides", {})
        return [
            Color(**color) for i, color in enumerate(make_colors([[c, 1] for c in val], overrides))
        ]


class Options(dictobj.Spec):
    colors = dictobj.Field(colors_spec, wrapper=sb.required)
    theme = dictobj.Field(sb.string_choice_spec(appliers.keys()), default="SPLOTCH")
    duration = dictobj.Field(sb.float_spec(), default=1)
    overrides = dictobj.Field(sb.dictionary_spec)


@an_action(needs_target=True, special_reference=True)
async def apply_theme(collector, target, reference, artifact, **kwargs):
    """
    Apply a theme to specified device

    ``lan:apply_theme d073d5000001 -- `{"colors": [<color>, <color>, ...], "theme": "SPLOTCH", "overrides": {<hsbk dictionary>}}'``

    If you don't specify serials, then the theme will apply to all devices found
    on the network.

    Colors may be words like "red", "blue", etc. Or may be [h, s, b, k] arrays
    where each part is optional.

    theme must be a valid theme type and defaults to SPLOTCH

    You may also specify ``duration`` which is how long to take to apply in
    seconds.

    And you may also supply ``overrides`` with ``hue``, ``saturation``,
    ``brightness`` and ``kelvin`` to override the specified colors.
    """
    extra = collector.configuration["photons_app"].extra_as_json
    everything = {}
    if "overrides" in extra:
        everything["overrides"] = extra["overrides"]

    if "colors" not in extra:
        extra["colors"] = default_colors

    options = Options.FieldSpec().normalise(Meta(everything, []), extra)

    gatherer = Gatherer(target)

    def errors(e):
        log.error(e)

    await target.script(ApplyTheme.script(options, gatherer=gatherer)).run_with_all(
        reference, error_catcher=errors
    )


class ApplyTheme:
    @classmethod
    def script(kls, options, gatherer=None):
        aps = appliers[options.theme]

        theme = Theme()
        for color in options.colors:
            theme.add_hsbk(color.hue, color.saturation, color.brightness, color.kelvin)

        async def gen(reference, afr, **kwargs):
            g = gatherer
            if g is None:
                g = Gatherer(afr.transport_target)

            instance = kls(g, reference, afr, kwargs, aps, theme, options)

            # Turn on the device
            yield LightMessages.SetLightPower(level=65535, duration=options.duration)

            # Yield messages to turn on the theme for this device
            async for serial, _, info in instance.gather(make_plans("capability")):
                async for m in instance.apply(info["cap"]):
                    yield m

        # Use gen per device to apply the theme
        return FromGeneratorPerSerial(gen)

    def __init__(self, gatherer, serial, afr, kwargs, aps, theme, options):
        self.afr = afr
        self.aps = aps
        self.theme = theme
        self.kwargs = kwargs
        self.serial = serial
        self.options = options
        self.gatherer = gatherer

    async def gather(self, plans):
        async for info in self.gatherer.gather(plans, self.serial, self.afr, **self.kwargs):
            yield info

    async def apply(self, cap):
        if cap.has_multizone:
            if cap.has_extended_multizone:
                log.info(hp.lc("found a strip with extended multizone", serial=self.serial))
            else:
                log.info(hp.lc("found a strip without extended multizone", serial=self.serial))
            async for m in self.zone_msgs():
                yield m

        elif cap.has_matrix:
            log.info(hp.lc("found a device with matrix zones", serial=self.serial))
            async for m in self.tile_msgs():
                yield m

        else:
            log.info(hp.lc("found a light with a single zone", serial=self.serial))
            async for m in self.light_msgs():
                yield m

    async def zone_msgs(self):
        colors = []

        length = 82
        async for _, _, zones in self.gather(make_plans("zones")):
            length = len(zones)

        for (start_index, end_index), hsbk in self.aps["1d"](length).apply_theme(self.theme):
            for _ in range(0, end_index - start_index + 1):
                colors.append(hsbk.as_dict())

        # SetZonesPlan knows when to use extended multizone vs old multizone messages
        plans = {"set_zones": SetZonesPlan([c, 1] for c in colors)}

        async for _, _, messages in self.gather(plans):
            yield messages

    async def tile_msgs(self):
        coords_and_sizes = None
        async for _, _, info in self.gather(make_plans("chain")):
            reorient = info["reorient"]
            coords_and_sizes = info["coords_and_sizes"]

        if not coords_and_sizes:
            log.warning(
                hp.lc("Couldn't work out how many zones the device had", serial=self.serial)
            )
            return

        applied = self.aps["2d"].from_user_coords(coords_and_sizes).apply_theme(self.theme)
        for i, (hsbks, coords_and_size) in enumerate(zip(applied, coords_and_sizes)):
            colors = reorient(
                i,
                [
                    {
                        "hue": self.options.overrides.get("hue", hsbk.hue),
                        "saturation": self.options.overrides.get("saturation", hsbk.saturation),
                        "brightness": self.options.overrides.get("brightness", hsbk.brightness),
                        "kelvin": self.options.overrides.get("kelvin", hsbk.kelvin),
                    }
                    for hsbk in hsbks
                ],
            )

            yield TileMessages.Set64(
                tile_index=i,
                length=1,
                x=0,
                y=0,
                width=coords_and_size[1][0],
                duration=self.options.duration,
                colors=colors,
                res_required=False,
                ack_required=True,
            )

    async def light_msgs(self):
        color = self.aps["0d"]().apply_theme(self.theme)
        s = "kelvin:{} hue:{} saturation:{} brightness:{}".format(
            color.kelvin, color.hue, color.saturation, color.brightness
        )
        yield Parser.color_to_msg(s, overrides={"duration": self.options.duration})
