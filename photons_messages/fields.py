from photons_messages import enums

from photons_protocol.packets import dictobj
from photons_protocol.messages import T

from input_algorithms import spec_base as sb
from lru import LRU
import random

def tile_effect_parameters_for(typ):
    for i in range(8):
        yield ("parameter{0}".format(i), T.Reserved(32))

def multizone_effect_parameters_for(typ):
    if typ is enums.MultiZoneEffectType.MOVE:
        yield ("parameter1", T.Reserved(32))
        yield ("speed_direction", T.Uint32.enum(enums.Direction).default(enums.Direction.RIGHT))
        for i in range(6):
            yield ("parameter{0}".format(i + 2), T.Reserved(32))
    else:
        for i in range(8):
            yield ("parameter{0}".format(i), T.Reserved(32))

duration_type = T.Uint32.default(0).transform(
      lambda _, value: int(1000 * float(value))
    , lambda value: float(value) / 1000
    ).allow_float()

extended_duration_type = T.Uint64.default(0).transform(
      lambda _, value: int(1e9 * float(value))
    , lambda value: float(value) / 1e9
    ).allow_float()

scaled_hue = T.Uint16.transform(
      lambda _, v: int(65535 * (0 if v is sb.NotSpecified else float(v)) / 360)
    , lambda v: float(v) * 360 / 65535
    ).allow_float()

scaled_to_65535 = T.Uint16.transform(
      lambda _, v: int(65535 * (0 if v is sb.NotSpecified else float(v)))
    , lambda v: float(v) / 65535
    ).allow_float()

nano_to_seconds = T.Uint64.transform(
      lambda _, v: int(v * 1e9)
    , lambda v: v / 1e9
    ).allow_float()

waveform_period = T.Uint32.default(0).transform(
      lambda _, value: int(1000 * float(value))
    , lambda value: float(value) / 1000
    ).allow_float()

waveform_skew_ratio = T.Int16.default(0).transform(
      lambda _, v: int(65535 * (0 if v is sb.NotSpecified else float(v))) - 32768
    , lambda v: float(v + 32768) / 65535
    ).allow_float()

hsbk_with_optional = (
      ("hue", scaled_hue.optional())
    , ("saturation", scaled_to_65535.optional())
    , ("brightness", scaled_to_65535.optional())
    , ("kelvin", T.Uint16.optional())
    )

hsbk = (
      ("hue", scaled_hue)
    , ("saturation", scaled_to_65535)
    , ("brightness", scaled_to_65535)
    , ("kelvin", T.Uint16.default(3500))
    )

class Color(dictobj.PacketSpec):
    fields = hsbk
Color.Meta.cache = LRU(8000)

multi_zone_effect_settings = (
      ("instanceid", T.Uint32.default(lambda pkt: random.randrange(1, 1<<32)))
    , ("type", T.Uint8.enum(enums.MultiZoneEffectType, allow_unknown=True).default(enums.MultiZoneEffectType.MOVE))
    , ("reserved6", T.Reserved(16))
    , ("speed", duration_type.default(5))
    , ("duration", extended_duration_type)
    , ("reserved7", T.Reserved(32))
    , ("reserved8", T.Reserved(32))
    , ("parameters", T.Bytes(32 * 8).dynamic(lambda pkt: multizone_effect_parameters_for(pkt.type)))
    )

tile_state_device = (
      ("accel_meas_x", T.Int16)
    , ("accel_meas_y", T.Int16)
    , ("accel_meas_z", T.Int16)
    , ("reserved6", T.Reserved(16))
    , ("user_x", T.Float)
    , ("user_y", T.Float)
    , ("width", T.Uint8)
    , ("height", T.Uint8)
    , ("reserved7", T.Reserved(8))
    , ("device_version_vendor", T.Uint32)
    , ("device_version_product", T.Uint32)
    , ("device_version_version", T.Uint32)
    , ("firmware_build", T.Uint64)
    , ("reserved8", T.Reserved(64))
    , ("firmware_version_minor", T.Uint16)
    , ("firmware_version_major", T.Uint16)
    , ("reserved9", T.Reserved(32))
    )

class Tile(dictobj.PacketSpec):
    fields = tile_state_device

tile_buffer_rect = (
      ("reserved6", T.Reserved(8))
    , ("x", T.Uint8)
    , ("y", T.Uint8)
    , ("width", T.Uint8)
    )

tile_effect_settings = (
      ("instanceid", T.Uint32.default(lambda pkt: random.randrange(1, 1<<32)))
    , ("type", T.Uint8.enum(enums.TileEffectType, allow_unknown=True).default(enums.TileEffectType.OFF))
    , ("speed", duration_type.default(5))
    , ("duration", extended_duration_type)
    , ("reserved6", T.Reserved(32))
    , ("reserved7", T.Reserved(32))
    , ("parameters", T.Bytes(32 * 8).dynamic(lambda pkt: tile_effect_parameters_for(pkt.type)))
    , ("palette_count", T.Uint8)
    , ("palette", T.Bytes(64 * 16).many(lambda pkt: Color))
    )
