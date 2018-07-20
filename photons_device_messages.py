from photons_protocol.messages import Messages, msg, T

from option_merge_addons import option_merge_addon_hook

__shortdesc__ = "LIFX binary protocol messages related to devices"

__doc__ = """
.. lifx_messages:: DeviceMessages
"""

@option_merge_addon_hook(extras=(("lifx.photons", "protocol")))
def __lifx__(collector, *args, **kwargs):
    pass

@option_merge_addon_hook(post_register=True)
def __lifx_post__(collector, *args, **kwargs):
    collector.configuration["protocol_register"].message_register(1024).add(DeviceMessages)

duration_typ = T.Uint32.default(0).transform(
      lambda _, value: int(1000 * float(value))
    , lambda value: float(value) / 1000
    ).allow_float()

class DeviceMessages(Messages):
    GetLabel = msg(23)
    SetLabel = msg(24
        , ('label', T.String(32 * 8))
        )
    StateLabel = SetLabel.using(25)

    GetPower = msg(20)
    SetPower = msg(21
        , ('level', T.Uint16)
        )
    StatePower = msg(22
        , ('level', T.Uint16)
        )

    # Light Power! Like Device Power, but with duration
    GetLightPower = msg(116)
    SetLightPower = msg(117
        , ('level', T.Uint16)
        , ('duration', duration_typ)
        )
    StateLightPower = msg(118
        , ('level', T.Uint16)
        )

    GetHostFirmware = msg(14)
    StateHostFirmware = msg(15
        , ("build", T.Uint64)
        , ("reserved", T.Uint64.default(0))
        , ("version", T.Uint32.version_number())
        )

    GetWifiInfo = msg(16)
    StateWifiInfo = msg(17
        , ("signal", T.Float)
        , ("tx", T.Uint32)
        , ("rx", T.Uint32)
        , ("reserved", T.Int16)
        )

    GetWifiFirmware = msg(18)
    StateWifiFirmware = msg(19
        , ("build", T.Uint64)
        , ("reserved", T.Uint64)
        , ("version", T.Uint32.version_number())
        )

    GetVersion = msg(32)
    StateVersion = msg(33
        , ("vendor", T.Uint32)
        , ("product", T.Uint32)
        , ("version", T.Uint32)
        )

    GetLocation = msg(48)
    SetLocation = msg(49
        , ("location", T.Bytes(16 * 8))
        , ("label", T.String(32 * 8))
        , ("updated_at", T.Uint64)
        )
    StateLocation = msg(50
        , ("location", T.Bytes(16 * 8))
        , ("label", T.String(32 * 8))
        , ("updated_at", T.Uint64)
        )

    GetGroup = msg(51)
    SetGroup = msg(52
        , ("group", T.Bytes(16 * 8))
        , ("label", T.String(32 * 8))
        , ("updated_at", T.Uint64)
        )
    StateGroup = msg(53
        , ("group", T.Bytes(16 * 8))
        , ("label", T.String(32 * 8))
        , ("updated_at", T.Uint64)
        )

    GetInfrared = msg(120)
    SetInfrared = msg(122
        , ('level', T.Uint16)
        )
    StateInfrared = SetInfrared.using(121)

    GetHostInfo = msg(12)
    StateHostInfo = msg(13
        , ("signal", T.Float)
        , ("tx", T.Uint32)
        , ("rx", T.Uint32)
        , ("reserved", T.Int16)
        )

    EchoRequest = msg(58
        , ("echoing", T.Bytes(64 * 8))
        )
    EchoResponse = EchoRequest.using(59)

    GetInfo = msg(34)
    StateInfo = msg(35
        , ("time", T.Uint64)
        , ("uptime", T.Uint64.transform(
              lambda _, v: v * 1e9
            , lambda v: v / 1e9
            ).allow_float()
          )
        , ("downtime", T.Uint64.transform(
              lambda _, v: v * 1e9
            , lambda v: v / 1e9
            ).allow_float()
          )
        )
