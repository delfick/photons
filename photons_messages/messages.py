from photons_messages import enums, fields
from photons_messages.frame import msg

from photons_protocol.messages import T, Messages, MultiOptions
from photons_protocol.types import Optional

from input_algorithms import spec_base as sb
import math

def empty(pkt, attr):
    return pkt.actual(attr) in (Optional, sb.NotSpecified)

########################
###   CORE
########################

class CoreMessages(Messages):
    Acknowledgement = msg(45)

########################
###   DISCOVERY
########################

class DiscoveryMessages(Messages):
    GetService = msg(2
        , multi = -1
        )

    StateService = msg(3
        , ("service", T.Uint8.enum(enums.Services))
        , ("port", T.Uint32)
        )

########################
###   DEVICE
########################

class DeviceMessages(Messages):
    GetHostInfo = msg(12)

    StateHostInfo = msg(13
        , ("signal", T.Float)
        , ("tx", T.Uint32)
        , ("rx", T.Uint32)
        , ("reserved6", T.Reserved(16))
        )

    GetHostFirmware = msg(14)

    StateHostFirmware = msg(15
        , ("build", T.Uint64)
        , ("reserved6", T.Reserved(64))
        , ("version_minor", T.Uint16)
        , ("version_major", T.Uint16)
        )

    GetWifiInfo = msg(16)

    StateWifiInfo = msg(17
        , ("signal", T.Float)
        , ("tx", T.Uint32)
        , ("rx", T.Uint32)
        , ("reserved6", T.Reserved(16))
        )

    GetWifiFirmware = msg(18)

    StateWifiFirmware = msg(19
        , ("build", T.Uint64)
        , ("reserved6", T.Reserved(64))
        , ("version_minor", T.Uint16)
        , ("version_major", T.Uint16)
        )

    GetPower = msg(20)

    SetPower = msg(21
        , ("level", T.Uint16)
        )

    StatePower = msg(22
        , ("level", T.Uint16)
        )

    GetLabel = msg(23)

    SetLabel = msg(24
        , ("label", T.String(32 * 8))
        )

    StateLabel = SetLabel.using(25)

    GetVersion = msg(32)

    StateVersion = msg(33
        , ("vendor", T.Uint32)
        , ("product", T.Uint32)
        , ("version", T.Uint32)
        )

    GetInfo = msg(34)

    StateInfo = msg(35
        , ("time", T.Uint64)
        , ("uptime", fields.nano_to_seconds)
        , ("downtime", fields.nano_to_seconds)
        )

    GetLocation = msg(48)

    SetLocation = msg(49
        , ("location", T.Bytes(16 * 8))
        , ("label", T.String(32 * 8))
        , ("updated_at", T.Uint64)
        )

    StateLocation = SetLocation.using(50)

    GetGroup = msg(51)

    SetGroup = msg(52
        , ("group", T.Bytes(16 * 8))
        , ("label", T.String(32 * 8))
        , ("updated_at", T.Uint64)
        )

    StateGroup = SetGroup.using(53)

    EchoRequest = msg(58
        , ("echoing", T.Bytes(64 * 8))
        )

    EchoResponse = EchoRequest.using(59)

########################
###   LIGHT
########################

class LightMessages(Messages):
    GetColor = msg(101)

    SetColor = msg(102
        , ("reserved6", T.Reserved(8))
        , *fields.hsbk
        , ("duration", fields.duration_type)
        )

    SetWaveform = msg(103
        , ("reserved6", T.Reserved(8))
        , ("transient", T.BoolInt.default(0))
        , *fields.hsbk
        , ("period", fields.waveform_period)
        , ("cycles", T.Float.default(1))
        , ("skew_ratio", fields.waveform_skew_ratio)
        , ("waveform", T.Uint8.enum(enums.Waveform).default(enums.Waveform.SAW))
        )

    LightState = msg(107
        , *fields.hsbk
        , ("reserved6", T.Reserved(16))
        , ("power", T.Uint16)
        , ("label", T.String(32 * 8))
        , ("reserved7", T.Reserved(64))
        )

    GetLightPower = msg(116)

    SetLightPower = msg(117
        , ("level", T.Uint16)
        , ("duration", fields.duration_type)
        )

    StateLightPower = msg(118
        , ("level", T.Uint16)
        )

    SetWaveformOptional = msg(119
        , ("reserved6", T.Reserved(8))
        , ("transient", T.BoolInt.default(0))
        , *fields.hsbk_with_optional
        , ("period", fields.waveform_period)
        , ("cycles", T.Float.default(1))
        , ("skew_ratio", fields.waveform_skew_ratio)
        , ("waveform", T.Uint8.enum(enums.Waveform).default(enums.Waveform.SAW))
        , ("set_hue", T.BoolInt.default(lambda pkt: 0 if empty(pkt, "hue") else 1))
        , ("set_saturation", T.BoolInt.default(lambda pkt: 0 if empty(pkt, "saturation") else 1))
        , ("set_brightness", T.BoolInt.default(lambda pkt: 0 if empty(pkt, "brightness") else 1))
        , ("set_kelvin", T.BoolInt.default(lambda pkt: 0 if empty(pkt, "kelvin") else 1))
        )

    GetInfrared = msg(120)

    StateInfrared = msg(121
        , ("brightness", T.Uint16)
        )

    SetInfrared = msg(122
        , ("brightness", T.Uint16)
        )

########################
###   MULTI_ZONE
########################

class MultiZoneMessages(Messages):
    SetColorZones = msg(501
        , ("start_index", T.Uint8)
        , ("end_index", T.Uint8)
        , *fields.hsbk
        , ("duration", fields.duration_type)
        , ("apply", T.Uint8.enum(enums.MultiZoneApplicationRequest).default(enums.MultiZoneApplicationRequest.APPLY))
        )

    GetColorZones = msg(502
        , ("start_index", T.Uint8)
        , ("end_index", T.Uint8)

        , multi = MultiOptions(
              lambda req: [MultiZoneMessages.StateZone, MultiZoneMessages.StateMultiZone]
            , lambda req, res: min((req.end_index // 8) + 1, math.ceil(res.zones_count / 8))
            )
        )

    StateZone = msg(503
        , ("zones_count", T.Uint8)
        , ("zone_index", T.Uint8)
        , *fields.hsbk
        )

    StateMultiZone = msg(506
        , ("zones_count", T.Uint8)
        , ("zone_index", T.Uint8)
        , ("colors", T.Bytes(64 * 8).many(lambda pkt: fields.Color))
        )

    GetMultiZoneEffect = msg(507)

    SetMultiZoneEffect = msg(508
        , *fields.multi_zone_effect_settings
        )

    StateMultiZoneEffect = SetMultiZoneEffect.using(509)

    SetExtendedColorZones = msg(510
        , ("duration", fields.duration_type)
        , ("apply", T.Uint8.enum(enums.MultiZoneExtendedApplicationRequest).default(enums.MultiZoneExtendedApplicationRequest.APPLY))
        , ("zone_index", T.Uint16)
        , ("colors_count", T.Uint8)
        , ("colors", T.Bytes(64 * 82).many(lambda pkt: fields.Color))
        )

    GetExtendedColorZones = msg(511)

    StateExtendedColorZones = msg(512
        , ("zones_count", T.Uint16)
        , ("zone_index", T.Uint16)
        , ("colors_count", T.Uint8)
        , ("colors", T.Bytes(64 * 82).many(lambda pkt: fields.Color))
        )

########################
###   TILE
########################

class TileMessages(Messages):
    GetDeviceChain = msg(701)

    StateDeviceChain = msg(702
        , ("start_index", T.Uint8)
        , ("tile_devices", T.Bytes(440 * 16).many(lambda pkt: fields.Tile))
        , ("tile_devices_count", T.Uint8)
        )

    SetUserPosition = msg(703
        , ("tile_index", T.Uint8)
        , ("reserved6", T.Reserved(16))
        , ("user_x", T.Float)
        , ("user_y", T.Float)
        )

    Get64 = msg(707
        , ("tile_index", T.Uint8)
        , ("length", T.Uint8)
        , *fields.tile_buffer_rect

        , multi = MultiOptions(
              lambda req: TileMessages.State64
            , lambda req, res: MultiOptions.Max(req.length)
            )
        )

    State64 = msg(711
        , ("tile_index", T.Uint8)
        , *fields.tile_buffer_rect
        , ("colors", T.Bytes(64 * 64).many(lambda pkt: fields.Color))
        )

    Set64 = msg(715
        , ("tile_index", T.Uint8)
        , ("length", T.Uint8)
        , *fields.tile_buffer_rect
        , ("duration", fields.duration_type)
        , ("colors", T.Bytes(64 * 64).many(lambda pkt: fields.Color))
        )

    GetTileEffect = msg(718
        , ("reserved6", T.Reserved(8))
        , ("reserved7", T.Reserved(8))
        )

    SetTileEffect = msg(719
        , ("reserved8", T.Reserved(8))
        , ("reserved9", T.Reserved(8))
        , *fields.tile_effect_settings
        )

    StateTileEffect = msg(720
        , ("reserved8", T.Reserved(8))
        , *fields.tile_effect_settings
        )

__all__ = ["CoreMessages", "DiscoveryMessages", "DeviceMessages", "LightMessages", "MultiZoneMessages", "TileMessages"]
