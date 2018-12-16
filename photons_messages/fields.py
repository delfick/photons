from photons_protocol.packets import dictobj
from photons_protocol.messages import T

from input_algorithms import spec_base as sb
from lru import LRU

duration_type = T.Uint32.default(0).transform(
      lambda _, value: int(1000 * float(value))
    , lambda value: float(value) / 1000
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
      lambda _, value: int(32767 * float(value))
    , lambda value: float(value) / 32767
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

tile_state_device = (
      ("reserved6", T.Reserved(48))
    , ("reserved7", T.Reserved(16))
    , ("user_x", T.Float)
    , ("user_y", T.Float)
    , ("width", T.Uint8)
    , ("height", T.Uint8)
    , ("reserved8", T.Reserved(8))
    , ("device_version_vendor", T.Uint32)
    , ("device_version_product", T.Uint32)
    , ("device_version_version", T.Uint32)
    , ("firmware_build", T.Uint64)
    , ("reserved9", T.Reserved(64))
    , ("firmware_version", T.Uint32.version_number())
    , ("reserved10", T.Reserved(32))
    )

class Tile(dictobj.PacketSpec):
    fields = tile_state_device

tile_buffer_rect = (
      ("reserved6", T.Reserved(8))
    , ("x", T.Uint8)
    , ("y", T.Uint8)
    , ("width", T.Uint8)
    )
