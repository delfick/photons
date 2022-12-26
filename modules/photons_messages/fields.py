import random

from delfick_project.norms import sb
from lru import LRU
from photons_messages import enums
from photons_protocol.messages import T
from photons_protocol.packets import dictobj


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


# fmt: off


def union_fields_ButtonTarget(typ):
    if typ is enums.ButtonTargetType.RESERVED6:
        yield from (("reserved6", T.Reserved(128)), )
    if typ is enums.ButtonTargetType.RESERVED7:
        yield from (("reserved7", T.Reserved(128)), )
    if typ is enums.ButtonTargetType.RELAYS:
        yield from (*button_target_relays, )
    if typ is enums.ButtonTargetType.DEVICE:
        yield from (*button_target_device, )
    if typ is enums.ButtonTargetType.LOCATION:
        yield from (("location", T.Bytes(16 * 8)), )
    if typ is enums.ButtonTargetType.GROUP:
        yield from (("group", T.Bytes(16 * 8)), )
    if typ is enums.ButtonTargetType.SCENE:
        yield from (("scene", T.Bytes(16 * 8)), )
    if typ is enums.ButtonTargetType.DEVICE_RELAYS:
        yield from (*button_target_device_relays, )


duration_type = T.Uint32.default(0).transform(
      lambda _, value: int(1000 * float(value))
    , lambda _, value: float(value) / 1000
    ).allow_float()

extended_duration_type = T.Uint64.default(0).transform(
      lambda _, value: int(1e9 * float(value))
    , lambda _, value: float(value) / 1e9
    ).allow_float()

scaled_hue = T.Uint16.transform(
      lambda _, v: int(round(0x10000 * (0 if v is sb.NotSpecified else float(v)) / 360)) % 0x10000
    , lambda _, v: round(float(v) * 360 / 0x10000, 2)
    ).allow_float()

scaled_to_65535 = T.Uint16.transform(
      lambda _, v: int(round(0xFFFF * (0 if v is sb.NotSpecified else float(v))))
    , lambda _, v: round(float(v) / 0xFFFF, 4)
    ).allow_float()

nano_to_seconds = T.Uint64.transform(
      lambda _, v: int(v * 1e9)
    , lambda _, v: v / 1e9
    ).allow_float()

waveform_period = T.Uint32.default(0).transform(
      lambda _, value: int(1000 * float(value))
    , lambda _, value: float(value) / 1000
    ).allow_float()

waveform_skew_ratio = T.Int16.default(0).transform(
      lambda _, v: int(65535 * (0 if v is sb.NotSpecified else float(v))) - 32768
    , lambda _, v: float(v + 32768) / 65535
    ).allow_float()

hsbk_with_optional = [
      ("hue", scaled_hue.optional())
    , ("saturation", scaled_to_65535.optional())
    , ("brightness", scaled_to_65535.optional())
    , ("kelvin", T.Uint16.optional())
    ]

button_target_relays = [
      ("relays_count", T.Uint8)
    , ("relays", T.Uint8.multiple(15))
    ]

button_target_device = [
      ("serial", T.Bytes(6 * 8))
    , ("reserved6", T.Reserved(80))
    ]

button_target_device_relays = [
      ("serial", T.Bytes(6 * 8))
    , ("relays_count", T.Uint8)
    , ("relays", T.Uint8.multiple(9))
    ]

button_action = [
      ("gesture", T.Uint16.enum(enums.ButtonGesture))
    , ("target_type", T.Uint16.enum(enums.ButtonTargetType))
    , ("target", T.Bytes(16 * 8).dynamic(lambda pkt: fields.union_fields_ButtonTarget(pkt.target_value)))
    ]

class ButtonAction(dictobj.PacketSpec):
    fields = button_action

button = [
      ("actions_count", T.Uint8)
    , ("actions", T.Bytes(160).multiple(5, kls=ButtonAction))
    ]

class Button(dictobj.PacketSpec):
    fields = button

hsbk = [
      ("hue", scaled_hue)
    , ("saturation", scaled_to_65535)
    , ("brightness", scaled_to_65535)
    , ("kelvin", T.Uint16.default(3500))
    ]

class Color(dictobj.PacketSpec):
    fields = hsbk
Color.Meta.cache = LRU(8000)

multi_zone_effect_settings = [
      ("instanceid", T.Uint32.default(lambda pkt: random.randrange(1, 1<<32)))
    , ("type", T.Uint8.enum(enums.MultiZoneEffectType, allow_unknown=True).default(enums.MultiZoneEffectType.MOVE))
    , ("reserved6", T.Reserved(16))
    , ("speed", duration_type.default(5))
    , ("duration", extended_duration_type)
    , ("reserved7", T.Reserved(32))
    , ("reserved8", T.Reserved(32))
    , ("parameters", T.Bytes(32 * 8).dynamic(lambda pkt: multizone_effect_parameters_for(pkt.type)))
    ]

tile_state_device = [
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
    , ("reserved8", T.Reserved(32))
    , ("firmware_build", T.Uint64)
    , ("reserved9", T.Reserved(64))
    , ("firmware_version_minor", T.Uint16)
    , ("firmware_version_major", T.Uint16)
    , ("reserved10", T.Reserved(32))
    ]

class Tile(dictobj.PacketSpec):
    fields = tile_state_device

tile_buffer_rect = [
      ("reserved6", T.Reserved(8))
    , ("x", T.Uint8)
    , ("y", T.Uint8)
    , ("width", T.Uint8)
    ]

tile_effect_settings = [
      ("instanceid", T.Uint32.default(lambda pkt: random.randrange(1, 1<<32)))
    , ("type", T.Uint8.enum(enums.TileEffectType, allow_unknown=True).default(enums.TileEffectType.OFF))
    , ("speed", duration_type.default(5))
    , ("duration", extended_duration_type)
    , ("reserved6", T.Reserved(32))
    , ("reserved7", T.Reserved(32))
    , ("parameters", T.Bytes(32 * 8).dynamic(lambda pkt: tile_effect_parameters_for(pkt.type)))
    , ("palette_count", T.Uint8)
    , ("palette", T.Bytes(64).multiple(16, kls=Color))
    ]

# fmt: on
