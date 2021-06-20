from photons_app.errors import PhotonsAppError

from delfick_project.norms import BadSpecValue, sb
from datetime import datetime
import re


class UnexpectedUnits(PhotonsAppError):
    pass


class time_spec(sb.Spec):
    pattern = re.compile(r"(?P<hour>\d?\d):(?P<minutes>\d\d)")

    def __init__(self, *, default):
        self.default = default

    def normalise(self, meta, val):
        if val in ("", None, sb.NotSpecified):
            val = self.default

        m = self.pattern.match(val)
        if m is None:
            raise BadSpecValue("Must be of the form 'HH:MM' in 24 hours clock", got=val, meta=meta)

        return tuple(int(g) for g in m.groups())


class time_range_spec(sb.Spec):
    def __init__(self, *, default_start, default_end):
        self.spec = sb.tuple_spec(time_spec(default=default_start), time_spec(default=default_end))

    def normalise(self, meta, val):
        if val is sb.NotSpecified:
            val = (sb.NotSpecified, sb.NotSpecified)
        if isinstance(val, list):
            val = tuple(val)
        return TimeRange(*self.spec.normalise(meta, val))


class TimeRange:
    def __init__(self, start_hhmm, end_hhmm):
        endh, endm = end_hhmm
        starth, startm = start_hhmm

        self.end = (endh, endm)
        self.start = (starth, startm)

        begin = datetime(year=2020, month=1, day=1, hour=starth, minute=startm)
        nextday = starth > endh or (starth == endh and startm > endm)
        finish = datetime(year=2020, month=1, day=2 if nextday else 1, hour=endh, minute=endm)
        self.diff = (finish - begin).seconds / 60

    def __contains__(self, now):
        hhmm = (int(now.strftime("%H")), int(now.strftime("%M")))

        diff = (hhmm[0] * 60) + hhmm[1] - (self.start[0] * 60) - self.start[1]
        if diff < 0:
            diff += 24 * 60

        return diff <= self.diff


class Duration:
    def __init__(self, seconds, *, raw):
        self.raw = raw
        self.seconds = seconds


class duration_spec(sb.Spec):
    def __init__(self, *, units_from_meta):
        self.units_from_meta = units_from_meta

    def normalise(self, meta, val):
        if isinstance(val, (int, float)):
            return Duration(val, raw=val)
        elif isinstance(val, str):
            raise BadSpecValue(
                "Sorry, I couldn't find a python module that could parse natural language durations!",
                wanted=val,
                meta=meta,
            )
        elif isinstance(val, dict):
            units = {}
            if self.units_from_meta:
                units.update(meta.everything.units)

            expected = ["seconds", "minutes", "hours", "days"]
            for unit in units:
                expected.append(f"unit_{unit}")

            unexpected = set(val) - set(expected)
            if unexpected:
                if self.units_from_meta:
                    raise UnexpectedUnits(
                        "Can only specify known units and at this stage custom units are unavailable",
                        available=expected,
                        missing=sorted(unexpected),
                    )
                else:
                    raise UnexpectedUnits(
                        "Can only specify known units",
                        available=expected,
                        missing=sorted(unexpected),
                    )

            final = 0
            for name, amount in val.items():
                if name == "seconds":
                    final += amount
                elif name == "minutes":
                    final += amount * 60
                elif name == "hours":
                    final += amount * 3600
                elif name == "days":
                    final += amount * 3600 * 24
                elif name.startswith("unit_"):
                    name = name[len("unit_") :]
                    final += units[name].seconds()

            return Duration(final, raw=(val, units))
        else:
            raise BadSpecValue(
                "Duration must be seconds as a number, or english phrase as a string, or dictionary of unit to amount",
                got=val,
                meta=meta,
            )
