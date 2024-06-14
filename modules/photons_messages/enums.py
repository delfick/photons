from enum import Enum


class Direction(Enum):
    RIGHT = 0
    LEFT = 1
    BACKWARD = 0
    FORWARD = 1


class ButtonGesture(Enum):
    PRESS = 1
    HOLD = 2
    PRESS_PRESS = 3
    PRESS_HOLD = 4
    HOLD_HOLD = 5


class ButtonTargetType(Enum):
    RESERVED1 = 0
    RESERVED2 = 1
    RELAYS = 2
    DEVICE = 3
    LOCATION = 4
    GROUP = 5
    SCENE = 6
    DEVICE_RELAYS = 7


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


class TileEffectSkyPalette(Enum):
    CLOUDS_SKY = 0
    NIGHT_SKY = 1
    DAWN_SKY = 2
    DAWN_SUN = 3
    FULL_SUN = 4
    FINAL_SUN = 5
    NUM_COLOURS = 6


class TileEffectSkyType(Enum):
    SUNRISE = 0
    SUNSET = 1
    CLOUDS = 2


class TileEffectType(Enum):
    OFF = 0
    RESERVED1 = 1
    MORPH = 2
    FLAME = 3
    RESERVED2 = 4
    SKY = 5
