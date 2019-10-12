import enum


class Vendor:
    def __init__(self, vid):
        self.vid = vid
        self.name = "UNKNOWN"
        self._name_set = False

    def __eq__(self, other):
        return other == self.vid or (isinstance(other, Vendor) and other.vid == self.vid)

    def __set_name__(self, owner, name):
        if not self._name_set:
            self.name = name
            self._name_set = True

    def __lt__(self, other):
        return self.vid < other.vid

    def __repr__(self):
        return f"<Vendor {self.vid}:{self.name}>"

    def __hash__(self):
        return hash(self.vid)


class VendorRegistry:
    LIFX = Vendor(1)
    QUALCOMM = Vendor(2)
    MAXUS = Vendor(3)

    @classmethod
    def choose(kls, vid):
        for attr in dir(kls):
            if not attr.startswith("_"):
                val = getattr(kls, attr)
                if isinstance(val, Vendor):
                    if val == vid:
                        return val
        v = Vendor(vid)
        v._name_set = True
        return v


class Zones(enum.Enum):
    SINGLE = "single"
    LINEAR = "linear"
    MATRIX = "matrix"


class Family(enum.Enum):
    UNKNOWN = "unknown"

    LMB = "lmb"
    LMBG = "lmbg"
    LCM1 = "lcm1"
    LCM2 = "lcm2"
    LCM3 = "lcm3"
