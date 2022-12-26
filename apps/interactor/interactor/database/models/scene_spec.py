import json

from delfick_project.norms import BadSpecValue, dictobj, sb
from photons_messages import LightMessages, MultiZoneMessages, TileMessages


class range_spec(sb.Spec):
    def __init__(self, minimum, maximum, spec=None):
        self.minimum = minimum
        self.maximum = maximum
        self.spec = spec or sb.float_spec()

    def normalise_filled(self, meta, val):
        val = self.spec.normalise(meta, val)
        if val < self.minimum or val > self.maximum:
            raise BadSpecValue(
                "Number must be between min and max",
                minimum=self.minimum,
                maximum=self.maximum,
                got=val,
                meta=meta,
            )
        return val


class sized_list_spec(sb.Spec):
    def __init__(self, spec, length):
        self.spec = spec
        self.length = length

    def normalise_filled(self, meta, val):
        val = sb.listof(self.spec).normalise(meta, val)
        if len(val) != self.length:
            raise BadSpecValue(
                "Expected certain number of parts", want=self.length, got=len(val), meta=meta
            )
        return val


class hsbk(sb.Spec):
    def __init__(self):
        self.specs = [
            range_spec(0, 360),
            range_spec(0, 1),
            range_spec(0, 1),
            range_spec(1500, 9000, spec=sb.integer_spec()),
        ]

    def normalise_filled(self, meta, val):
        val = sized_list_spec(sb.any_spec(), 4).normalise(meta, val)
        res = []
        for i, (v, s) in enumerate(zip(val, self.specs)):
            res.append(s.normalise(meta.at(i), v))
        return res


chain_spec = sb.listof(hsbk())


class json_string_spec(sb.Spec):
    def __init__(self, spec, storing):
        self.spec = spec
        self.storing = storing

    def normalise_filled(self, meta, val):
        if type(val) is str:
            try:
                v = json.loads(val)
            except (TypeError, ValueError) as error:
                raise BadSpecValue("Value was not valid json", error=error, meta=meta)
            else:
                normalised = self.spec.normalise(meta, v)
                if not self.storing:
                    return normalised

                return json.dumps(normalised, default=lambda o: repr(o))
        else:
            v = self.spec.normalise(meta, val)
            if not self.storing:
                return v
            return json.dumps(v)


def make_spec(storing=True):
    class Fields(dictobj.Spec):
        uuid = dictobj.Field(sb.string_spec, wrapper=sb.required)
        matcher = dictobj.Field(
            json_string_spec(sb.dictionary_spec(), storing), wrapper=sb.required
        )
        power = dictobj.NullableField(sb.boolean)
        color = dictobj.NullableField(sb.string_spec)
        zones = dictobj.NullableField(json_string_spec(sb.listof(hsbk()), storing))
        chain = dictobj.NullableField(json_string_spec(sb.listof(chain_spec), storing))
        duration = dictobj.NullableField(sb.integer_spec)

    if not storing:

        class Fields(Fields):
            @property
            def transform_options(self):
                power = None
                if self.power is not None:
                    power = "on" if self.power else "off"
                dct = {"power": power, "color": self.color, "duration": self.duration}
                return {k: v for k, v in dct.items() if v is not None}

            def colors_from_hsbks(self, hsbks, overrides):
                return [
                    {
                        "hue": overrides.get("hue", h),
                        "saturation": overrides.get("saturation", s),
                        "brightness": overrides.get("brightness", b),
                        "kelvin": overrides.get("kelvin", k),
                    }
                    for h, s, b, k in hsbks
                ]

            def power_message(self, overrides):
                power = overrides.get("power", self.power)
                duration = overrides.get("duration", self.duration) or 0

                if power is not None:
                    level = 0 if power not in (True, "on") else 65535
                    return LightMessages.SetLightPower(level=level, duration=duration)

            def determine_duration(self, overrides):
                return overrides.get("duration", self.duration) or 0

            def zone_msgs(self, overrides):
                power_message = self.power_message(overrides)
                if power_message:
                    yield power_message

                colors = self.colors_from_hsbks(self.zones, overrides)
                duration = self.determine_duration(overrides)

                start = 0
                color = None
                i = -1
                while i < len(colors) - 1:
                    i += 1
                    if color is None:
                        color = colors[i]
                        continue
                    if colors[i] != color:
                        yield MultiZoneMessages.SetColorZones(
                            start_index=start,
                            end_index=i - 1,
                            **color,
                            duration=duration,
                            res_required=False,
                        )
                        color = colors[i]
                        start = i

                color = colors[i]
                yield MultiZoneMessages.SetColorZones(
                    start_index=start, end_index=i, **color, duration=duration, res_required=False
                )

            def chain_msgs(self, overrides):
                power_message = self.power_message(overrides)
                if power_message:
                    yield power_message

                duration = self.determine_duration(overrides)
                for i, lst in enumerate(self.chain):
                    colors = self.colors_from_hsbks(lst, overrides)

                    width = 8
                    if len(colors) == 30:
                        width = 5

                    yield TileMessages.Set64(
                        tile_index=i,
                        length=1,
                        x=0,
                        y=0,
                        width=width,
                        duration=duration,
                        colors=colors,
                        res_required=False,
                    )

    return Fields.FieldSpec()
