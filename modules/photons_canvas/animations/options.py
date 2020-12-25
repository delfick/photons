from photons_control.colour import make_hsbk

from delfick_project.norms import sb, BadSpecValue, Meta
import random


class ZeroColor:
    def __init__(self):
        self.color = None

    def __repr__(self):
        return "[ZeroColor]"


class OneColor:
    def __init__(self, hue, saturation, brightness, kelvin):
        self.color = (hue, saturation, brightness, kelvin)

    def __repr__(self):
        return str(self.color)


class OneColorRange:
    def __init__(self, hs, ss, bb, kk):
        self.hs = hs
        self.ss = ss
        self.bb = bb
        self.kk = kk

    @property
    def color(self):
        return (self.hue, self.saturation, self.brightness, int(self.kelvin))

    def __repr__(self):
        return str((self.hs, self.ss, self.bb, self.kk))

    @property
    def hue(self):
        h = self.hs
        if h[0] != h[1]:
            h = random.randrange(h[0], h[1])
        else:
            h = h[0]
        return h % 360

    @property
    def saturation(self):
        s = self.ss
        if s[0] != s[1]:
            s = random.randrange(s[0], s[1]) / 1000
        else:
            s = s[0] / 1000

        if s < 0:
            s = 0
        elif s > 1:
            s = 1
        return s

    @property
    def brightness(self):
        b = self.bb
        if b[0] != b[1]:
            b = random.randrange(b[0], b[1]) / 1000
        else:
            b = b[0] / 1000

        if b < 0:
            b = 0
        elif b > 1:
            b = 1
        return b

    @property
    def kelvin(self):
        k = self.kk
        if k[0] != k[1]:
            k = random.randrange(k[0], k[1])
        else:
            k = k[0]

        if k < 0:
            k = 0
        elif k > 0xFFFF:
            k = 0xFFFF
        return k


class ManyColor:
    def __init__(self, colors):
        if len(colors) == 0:
            colors = [ZeroColor()]
        self.colors = colors

    def __repr__(self):
        return f"<ManyColor:{self.colors}>"

    @property
    def color(self):
        return random.choice(self.colors).color


class color_option_spec(sb.Spec):
    def setup(self, h, s, b, k):
        self.default = (h, s, b, k)

    def normalise_empty(self, meta):
        return self.normalise_filled(meta, self.default)

    def normalise_filled(self, meta, val):
        h, s, b, k = make_hsbk(val)
        return OneColor(*make_hsbk(val))


class color_range_spec(sb.Spec):
    def setup(self, default):
        self.default = default

    def normalise_empty(self, meta):
        return self.normalise(meta, self.default)

    def normalise_filled(self, meta, val):
        if isinstance(val, str):
            val = val.split(":")

        colors = []
        for i, r in enumerate(val):
            colors.append(self.interpret(meta.indexed_at(i), r))

        return ManyColor([c for c in colors if c is not None])

    def interpret(self, meta, val):
        if not isinstance(val, (tuple, list, str)):
            raise BadSpecValue("Each color specifier must be a list or string", got=val, meta=meta)

        if isinstance(val, str):
            val = val.split(",")

        if len(val) == 0:
            return
        elif len(val) == 1:
            val = (*val, (1, 1), (1, 1), (3500, 3500))
        elif len(val) == 2:
            val = (*val, (1, 1), (3500, 3500))
            if val[0] == "rainbow":
                val[2] = (1, 1)
        elif len(val) == 3:
            val = (*val, (3500, 3500))
        elif len(val) > 4:
            raise BadSpecValue("Each color must be 4 or less specifiers", got=val, meta=meta)

        result = []
        for i, v in enumerate(val):
            m = meta.indexed_at(i)

            if not isinstance(v, (tuple, list, str)):
                raise BadSpecValue("Each color specifier must be a list or string", got=val, meta=m)

            if i != 0 and v == "rainbow":
                raise BadSpecValue("Only hue may be given as 'rainbow'", meta=m)

            if v == "rainbow":
                result.append((0, 360))
                continue

            if isinstance(v, str):
                v = v.split("-")

            if isinstance(v, (int, float)):
                v = [v]

            if len(v) > 2:
                raise BadSpecValue("A specifier must be two values", got=v, meta=m)

            if len(v) == 0:
                continue

            if len(v) == 1:
                v = v * 2

            if i in (1, 2):
                result.append((float(v[0]) * 1000, float(v[1]) * 1000))
            else:
                result.append((float(v[0]), float(v[1])))

        return OneColorRange(*result)


class ensure_integer_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        return int(sb.float_spec().normalise(meta, val))


class Range:
    default_multiplier = 1
    default_normaliser = ensure_integer_spec

    default_minimum_min = None
    default_maximum_max = None

    def __init__(self, mn, mx, minimum_mn=None, maximum_mx=None, spec=None, multiplier=None):
        self.mn = round(float(mn), 3)
        self.mx = round(float(mx), 3)
        self.spec = (spec or self.default_normaliser)()
        self.multiplier = multiplier if multiplier is not None else self.default_multiplier

        mmn = minimum_mn if minimum_mn is not None else self.default_minimum_min
        mmx = maximum_mx if maximum_mx is not None else self.default_maximum_max

        if mmn not in (None, False) and self.mn < mmn:
            self.mn = mmn
        if mmx not in (None, False) and self.mx > mmx:
            self.mx = mmx

        self.meta = Meta.empty()

        self.constant = None
        if self.mn == self.mx:
            self.constant = self.mn

    def __repr__(self):
        return f"<Range {self.mn} -> {self.mx}>"

    def choose_range(self):
        choice = random.randrange(self.mn * self.multiplier, self.mx * self.multiplier)
        return self.spec.normalise(self.meta, choice / self.multiplier)

    @property
    def rate(self):
        if self.constant is not None:
            return self.constant
        return self.choose_range()

    def __call__(self):
        return self.rate


class Rate(Range):
    default_multiplier = 1000
    default_normaliser = sb.float_spec

    default_minimum_min = 0.01
    default_maximum_max = 1

    def __repr__(self):
        return f"<Rate {self.mn} -> {self.mx}>"


class range_spec(sb.Spec):
    def setup(self, default, rate=False, **kwargs):
        self.rate = rate
        self.kwargs = kwargs
        self.default = default

    def normalise_empty(self, meta):
        return self.normalise_filled(meta, self.default)

    def normalise_filled(self, meta, value):
        if isinstance(value, str):
            value = value.split("-")
            if len(value) == 1:
                value *= 2
        elif isinstance(value, (int, float)):
            value = (value, value)

        if not isinstance(value, (list, tuple)):
            raise BadSpecValue("Speed option must be 'min-max' or [min, max]", got=value, meta=meta)

        kls = Rate if self.rate else Range
        return kls(value[0], value[1], **self.kwargs)
