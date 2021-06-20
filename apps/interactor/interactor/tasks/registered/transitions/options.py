from interactor.tasks.location import NaturalLight, NoSuchNaturalLightPreset
from interactor.tasks.time_specs import duration_spec
from interactor.tasks.register import DeviceTask

from photons_app.formatter import MergedOptionStringFormatter

from delfick_project.norms import dictobj, sb, BadSpecValue


class natural_light_spec(sb.Spec):
    def __init__(self):
        self.spec = NaturalLight.FieldSpec(formatter=MergedOptionStringFormatter)

    def normalise(self, meta, val):
        if isinstance(val, str):
            try:
                return meta.everything["natural_light_presets"].find(val)
            except NoSuchNaturalLightPreset as error:
                raise BadSpecValue(str(error), **error.kwargs, meta=meta)
        else:
            return self.spec.normalise(meta, val)


class Options(DeviceTask):
    update_every = dictobj.Field(
        formatted_into=duration_spec,
        default=1,
        help="""
    The duration to wait between evaluating what to do next.
    """,
    )

    default_power = dictobj.NullableField(
        sb.boolean,
        help="""
        If set to True then every action will by default turn on the power. If
        set to False then every action will default to turning off the power.
        Otherwise if not filled or set as None the power will not be interfered
        with by default
    """,
    )

    natural_light = dictobj.NullableField(
        natural_light_spec,
        help="""

    Either:

    .. code-block:: yaml

        natural_light:
          location: Melbourne

    Which will use https://astral.readthedocs.io/en/latest/#geocoder

    Or you can specify all the options:

    .. code-block:: yaml

        natural_light:
          location:
            name: "Melbourne"
            region: "Australia"
            timezone: "Australia/Melbourne"
            latitude: -37.8
            longitude: 144.95
          # optionally specify exactly when sunrise and sunset are
          sunrise_at: "05:00"
          sunset_at: "17:00"
  
    Or you can specify a string that matches one of the natural_light settings under tasks:

    .. code-block:: yaml

        tasks:
          natural_light:
            home:
              location:
                name: "Melbourne"
                region: "Australia"
                timezone: "Australia/Melbourne"
                latitude: -37.8
                longitude: 144.95
              # optionally specify exactly when sunrise and sunset are
              sunrise_at: "05:00"
              sunset_at: "17:00"
    
          presets:
            my_task:
              type: transitions
              options:
                # refer to our preset for "home"
                natural_light: home
    """,
    )
