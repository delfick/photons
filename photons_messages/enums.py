from enum import Enum

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

class MultiZoneApplicationRequest(Enum):
    NO_APPLY = 0
    APPLY = 1
    APPLY_ONLY = 2
