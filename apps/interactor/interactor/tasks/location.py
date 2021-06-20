from interactor.tasks.time_specs import time_spec

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import PhotonsAppError

from delfick_project.norms import dictobj, sb
from astral.geocoder import database, lookup
from astral.location import Location
from astral import LocationInfo


class NoSuchLocation(PhotonsAppError):
    desc = "Couldn't find this location"


class NoSuchNaturalLightPreset(PhotonsAppError):
    desc = "There is no configuration for natural light with this name"


class NaturalLightPresets:
    @classmethod
    def spec(kls):
        return sb.container_spec(
            kls,
            sb.dictof(
                sb.string_spec(), NaturalLight.FieldSpec(formatter=MergedOptionStringFormatter)
            ),
        )

    def __init__(self, presets):
        self.presets = presets

    def find(self, name):
        if name not in self.presets:
            raise NoSuchNaturalLightPreset(wanted=name, available=sorted(self.presets))

        return self.presets[name]


class location_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        if isinstance(val, str):
            try:
                info = Location(lookup(val, database()))
            except KeyError:
                raise NoSuchLocation(want=val, meta=meta)
        else:
            options = sb.set_options(
                name=sb.required(sb.string_spec()),
                region=sb.required(sb.string_spec()),
                timezone=sb.required(sb.string_spec()),
                latitude=sb.required(sb.float_spec()),
                longitude=sb.required(sb.float_spec()),
            ).normalise(meta, val)

            info = LocationInfo(
                options["name"],
                options["region"],
                options["timezone"],
                options["latitude"],
                options["longitude"],
            )

        return Location(info)


class NaturalLight(dictobj.Spec):
    location = dictobj.Field(
        location_spec,
        wrapper=sb.required,
        help="""
    Either the name of your city, i.e. "Melbourne" or a dictionary of {name, region, timezone, latitude, longitude}

    For example:

    .. code-block:: yaml

        location:
            name: "Melbourne"
            region: "Australia"
            timezone: "Australia/Melbourne"
            latitude: -37.8
            longitude: 144.95

    If you specify a name we'll use https://astral.readthedocs.io/en/latest/#geocoder
    """,
    )

    sunset_at = dictobj.NullableField(
        time_spec(default=""),
        help="""
    You may set a static sunset time as "HH:MM" or leave this option out for it to
    be determined dynamically
    """,
    )
    sunrise_at = dictobj.NullableField(
        time_spec(default=""),
        help="""
    You may set a static sunset time as "HH:MM" or leave this option out for it to
    be determined dynamically
    """,
    )

    def sunrise(self, date):
        if self.sunrise_at is not None:
            return date.replace(hour=self.sunrise_at[0], minute=self.sunrise_at[1])
        else:
            return self.location.sunrise(date)

    def sunset(self, date):
        if self.sunset_at is not None:
            return date.replace(hour=self.sunset_at[0], minute=self.sunset_at[1])
        else:
            return self.location.sunset(date)

    def solar_noon(self, date):
        return self.location.noon(date)

    def solar_midnight(self, date):
        return self.location.midnight(date)
