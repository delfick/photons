from interactor.tasks.registered.circadian.circadian import Circadian
from interactor.tasks.time_specs import time_spec, time_range_spec
from interactor.tasks.registered.circadian.specs import days_spec
from interactor.tasks.register import DeviceTask

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from delfick_project.norms import dictobj, sb
from astral.geocoder import database, lookup
from astral.location import Location
from astral import LocationInfo
from datetime import datetime


class NoSuchLocation(PhotonsAppError):
    desc = "Couldn't find this location"


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
                latitude=sb.required(sb.integer_spec()),
                longitude=sb.required(sb.integer_spec()),
            ).normalise(meta, val)

            info = LocationInfo(
                options["name"],
                options["region"],
                options["timezone"],
                options["latitude"],
                options["longitude"],
            )

        return Location(info)


class Options(DeviceTask):
    days = dictobj.Field(
        days_spec,
        help="""
    The days of the week to run this task.
    """,
    )

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

    lights_on_range = dictobj.Field(
        time_range_spec(default_start="8:00", default_end="22:00"),
        help="""
    Specified as a tuple of ("HH:MM", "HH:MM"), all times starting as first time
    and ending at second time will result in telling the light to power on. Otherwise
    the light will always be told to turn off.
    """,
    )

    change_power = dictobj.Field(
        sb.boolean,
        default=True,
        help="""
    Set to false if you don't want the power of the lights to ever be changed
    """,
    )

    break_saturation_threshold = dictobj.Field(
        sb.float_spec,
        default=0.05,
        help="""
    Any device with a saturation greater than this amount will be ignored and let
    to continue as is. Defaults to 0.05 which means 5% saturation.
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

    min_kelvin = dictobj.Field(
        sb.integer_spec,
        default=1500,
        help="""
    The kelvin of the lights will never be set below this
    """,
    )

    max_kelvin = dictobj.Field(
        sb.integer_spec,
        default=9000,
        help="""
    The kelvin of the lights will never be set above this
    """,
    )

    min_brightness = dictobj.Field(
        sb.float_spec,
        default=0.5,
        help="""
    The brightness of the lights will never be set below this
    """,
    )

    max_brightness = dictobj.Field(
        sb.float_spec,
        default=1,
        help="""
    The brightness of the lights will never be set above this
    """,
    )

    @hp.memoized_property
    def circadian(self):
        return Circadian(self.location, sunrise_at=self.sunrise_at, sunset_at=self.sunset_at)

    async def status(self, name):
        status = await super().status(name)
        status.update(
            {
                "lights_on": datetime.now() in self.lights_on_range,
            }
        )
        return status
