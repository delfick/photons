from photons_messages.enums import Waveform

from photons_protocol.packets import dictobj
from photons_protocol.messages import T

from input_algorithms import spec_base as sb
from lru import LRU

scaled_to_65535 = T.Uint16.transform(
      lambda _, v: int(65535 * (0 if v is sb.NotSpecified else float(v)))
    , lambda v: float(v) / 65535
    ).allow_float()

nano_to_seconds = T.Uint64.transform(
      lambda _, v: int(v * 1e9)
    , lambda v: v / 1e9
    ).allow_float()

hsbk = (
      ('hue', T.Uint16.transform(
              lambda _, v: int(65535 * (0 if v is sb.NotSpecified else float(v)) / 360)
            , lambda v: float(v) * 360 / 65535
            ).allow_float()
          )
    , ('saturation', scaled_to_65535)
    , ('brightness', scaled_to_65535)
    , ('kelvin', T.Uint16.default(3500))
    )

hsbk_with_optional = (
      ('hue', hsbk[0][1].optional())
    , ('saturation', hsbk[1][1].optional())
    , ('brightness', hsbk[2][1].optional())
    , ('kelvin', T.Uint16.optional())
    )

duration_typ = T.Uint32.default(0).transform(
      lambda _, value: int(1000 * float(value))
    , lambda value: float(value) / 1000
    ).allow_float()

color_and_duration = (
      ('setcolor_reserved1', T.Reserved(8))
    , *hsbk
    , ('duration', duration_typ)
    )

waveform_opts = (
      ('period', T.Uint32.default(0).transform(
              lambda _, value: int(1000 * float(value))
            , lambda value: float(value) / 1000
            ).allow_float()
          )
    , ('cycles', T.Float.default(1))
    , ('skew_ratio', T.Int16.default(0).transform(
              lambda _, value: int(32767 * float(value))
            , lambda value: float(value) / 32767
            ).allow_float()
          )
    , ('waveform', T.Uint8.enum(Waveform).default(Waveform.SAW))
    )

tile_buffer_rect = (
      ("reserved", T.Uint8.default(0))
    , ("x", T.Uint8)
    , ("y", T.Uint8)
    , ("width", T.Uint8)
    )

class Color(dictobj.PacketSpec):
    fields = hsbk
# Give Color a cache for 25 sets of tiles all containing different colors in every pixel
# Which completely filled is only 4mb
# The cache is used by photons-protocol so that we don't have to Color().pack() 64 times for every SetState64
#   which is very slow...
Color.Meta.cache = LRU(8000)

class Tile(dictobj.PacketSpec):
    fields = [
          ("reserved6", T.Int16.default(0))
        , ("reserved7", T.Int16.default(0))
        , ("reserved8", T.Int16.default(0))
        , ("reserved9", T.Uint16.default(0))
        , ("user_x", T.Float)
        , ("user_y", T.Float)
        , ("width", T.Uint8)
        , ("height", T.Uint8)
        , ("reserved10", T.Uint8.default(50))
        , ("device_version_vendor", T.Uint32)
        , ("device_version_product", T.Uint32)
        , ("device_version_version", T.Uint32)
        , ("firmware_build", T.Uint64)
        , ("reserved11", T.Uint64.default(0))
        , ("firmware_version", T.Uint32.transform(
                lambda _, v: v if type(v) is int else (int(str(v).split(".")[0]) << 0x10) + int(str(v).split(".")[1])
              , lambda v: float("{0}.{1:02d}".format(v >> 0x10, v & 0xFF))
              ).allow_float()
            )
        , ("reserved12", T.Uint32.default(0))
        ]
