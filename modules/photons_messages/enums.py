from enum import Enum


class Direction(Enum):
    RIGHT = 0
    LEFT = 1
    BACKWARD = 0
    FORWARD = 1


class Services(Enum):
    UDP = 1
    RESERVED1 = 2
    RESERVED2 = 3
    RESERVED3 = 4
    RESERVED4 = 5


class Waveform(Enum):
    SAW = 0
    SINE = 1
    HALF_SINE = 2
    TRIANGLE = 3
    PULSE = 4


class LightLastHevCycleResult(Enum):
    SUCCESS = 0
    BUSY = 1
    INTERRUPTED_BY_RESET = 2
    INTERRUPTED_BY_HOMEKIT = 3
    INTERRUPTED_BY_LAN = 4
    INTERRUPTED_BY_CLOUD = 5
    NONE = 255


class MultiZoneApplicationRequest(Enum):
    NO_APPLY = 0
    APPLY = 1
    APPLY_ONLY = 2


class MultiZoneEffectType(Enum):
    OFF = 0
    MOVE = 1
    RESERVED1 = 2
    RESERVED2 = 3


class MultiZoneExtendedApplicationRequest(Enum):
    NO_APPLY = 0
    APPLY = 1
    APPLY_ONLY = 2


class TileEffectType(Enum):
    OFF = 0
    RESERVED1 = 1
    MORPH = 2
    FLAME = 3
    RESERVED2 = 4
