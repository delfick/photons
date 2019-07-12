from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from photons_messages import (
      LightMessages, DeviceMessages, MultiZoneMessages, TileMessages
    , MultiZoneEffectType, TileEffectType
    , protocol_register
    )
from photons_products_registry import (
      capability_for_ids
    , ProductRegistries, VendorRegistry, LIFIProductRegistry
    )
from photons_transport.targets import MemoryTarget
from photons_protocol.types import enum_spec
from photons_transport.fake import Responder

from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta
import logging
import asyncio

log = logging.getLogger("photons_control.test_helpers")

class HSBKClose:
    """
    Used to compare hsbk dictionaries without caring too much about complete accuracy
    """
    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return repr(self.data)

    def __eq__(self, other):
        if any(k not in other for k in self.data):
            return False
        if any(k not in self.data for k in other):
            return False

        for k in other:
            diff = abs(other[k] - self.data[k])
            precision = 1 if k in ("hue", "kelvin") else 0.1
            if diff > precision:
                return False

        return True

class Color(dictobj):
    fields = ["hue", "saturation", "brightness", "kelvin"]

class LightStateResponder(Responder):
    _fields = [
          ("color", lambda: Color(0, 0, 1, 3500))
        , ("power", lambda: 0)
        , ("label", lambda: "")
        ]

    async def respond(self, device, pkt, source):
        if pkt | DeviceMessages.GetLabel:
            yield self.make_label_response(device)
        elif pkt | DeviceMessages.SetLabel:
            device.attrs.label = pkt.label
            yield self.make_label_response(device)

        elif pkt | DeviceMessages.GetPower:
            yield self.make_power_response(device)
        elif pkt | DeviceMessages.SetPower or pkt | LightMessages.SetLightPower:
            res = self.make_power_response(device)
            device.attrs.power = pkt.level
            yield res

        elif pkt | LightMessages.GetColor:
            yield self.make_light_response(device)
        elif pkt | LightMessages.SetColor or pkt | LightMessages.SetWaveform:
            res = self.make_light_response(device)
            device.attrs.color = Color(pkt.hue, pkt.saturation, pkt.brightness, pkt.kelvin)
            yield res
        elif pkt | LightMessages.SetWaveformOptional:
            res = self.make_light_response(device)

            color = Color(**device.attrs.color.as_dict())
            for p in ("hue", "saturation", "brightness", "kelvin"):
                if getattr(pkt, f"set_{p}"):
                    color[p] = pkt[p]

            device.attrs.color = color
            yield res

    def make_label_response(self, device):
        return DeviceMessages.StateLabel(label=device.attrs.label)

    def make_power_response(self, device):
        return DeviceMessages.StatePower(level=device.attrs.power)

    def make_light_response(self, device):
        return LightMessages.LightState.empty_normalise(
              label = device.attrs.label
            , power = device.attrs.power
            , **device.attrs.color.as_dict()
            )

class InfraredResponder(Responder):
    _fields = [("infrared", lambda: 0)]

    def has_infrared(self, device):
        return ProductResponder.capability(device)[0].has_ir

    async def reset(self, device, *, zero=False):
        if self.has_infrared(device):
            await super().reset(device, zero=zero)

    async def respond(self, device, pkt, source):
        if not self.has_infrared(device):
            return

        if pkt | LightMessages.GetInfrared:
            yield self.make_response(device)
        elif pkt | LightMessages.SetInfrared:
            res = self.make_response(device)
            device.attrs.infrared = pkt.brightness
            yield res

    def make_response(self, device):
        return LightMessages.StateInfrared(brightness=device.attrs.infrared)

class TilesResponder(Responder):
    _fields = [("tiles_effect", lambda: TileEffectType.OFF)]

    def has_chain(self, device):
        return ProductResponder.capability(device)[0].has_chain

    async def reset(self, device, *, zero=False):
        if self.has_chain(device):
            await super().reset(device, zero=zero)

    async def respond(self, device, pkt, source):
        if not self.has_chain(device):
            return

        if pkt | TileMessages.GetTileEffect:
            yield self.make_state_tile_effect(device)
        elif pkt | TileMessages.SetTileEffect:
            res = self.make_state_tile_effect(device)
            device.attrs.tiles_effect = pkt.type
            yield res

    def make_state_tile_effect(self, device):
        return TileMessages.StateTileEffect(type=device.attrs.tiles_effect)

class ZonesResponder(Responder):
    _fields = ["zones", ("zones_effect", lambda: MultiZoneEffectType.OFF)]

    def has_multizone(self, device):
        return ProductResponder.capability(device)[0].has_multizone

    def has_extended_multizone(self, device):
        cap, major, minor = ProductResponder.capability(device)
        return cap.has_extended_multizone(major, minor)

    def validate_attr(self, device, field, val):
        if field == "zones" and len(val) > 82:
            raise PhotonsAppError("Can only have up to 82 zones!")

    async def reset(self, device, *, zero=False):
        if self.has_multizone(device):
            await super().reset(device, zero=zero)

    def effect_response(self, device):
        return MultiZoneMessages.StateMultiZoneEffect(type=device.attrs.zones_effect)

    def extended_multizone_response(self, device):
        return MultiZoneMessages.StateExtendedColorZones(
              zones_count = len(device.attrs.zones)
            , zone_index = 0
            , colors_count = len(device.attrs.zones)
            , colors = [z.as_dict() for z in device.attrs.zones]
            )

    def multizone_responses(self, device):
        buf = []
        bufs = []

        for i, zone in enumerate(device.attrs.zones):
            if len(buf) == 8:
                bufs.append(buf)
                buf = []

            buf.append((i, zone))

        if buf:
            bufs.append(buf)

        for buf in bufs:
            yield MultiZoneMessages.StateMultiZone(
                  zones_count = len(device.attrs.zones)
                , zone_index = buf[0][0]
                , colors = [b.as_dict() for _, b in buf]
                )

    def set_zone(self, device, index, hue, saturation, brightness, kelvin):
        if index >= len(device.attrs.zones):
            log.warning(hp.lc("Setting zone outside range of the device", number_zones=len(device.attrs.zones), want=index))
            return

        device.attrs.zones[index] = Color(hue, saturation, brightness, kelvin)

    async def respond(self, device, pkt, source):
        if not self.has_multizone(device):
            return

        if pkt | MultiZoneMessages.SetMultiZoneEffect:
            res = self.effect_response(device)
            device.attrs.zones_effect = pkt.type
            yield res
        elif pkt | MultiZoneMessages.GetMultiZoneEffect:
            yield self.effect_response(device)

        elif pkt | MultiZoneMessages.GetColorZones:
            if pkt.start_index != 0 or pkt.end_index != 255:
                raise PhotonsAppError("Fake device only supports getting all color zones", got=pkt.payload)

            for r in self.multizone_responses(device):
                yield r
        elif pkt | MultiZoneMessages.SetColorZones:
            res = []
            for r in self.multizone_responses(device):
                res.append(r)
            for i in range(pkt.start_index, pkt.end_index + 1):
                self.set_zone(device, i, pkt.hue, pkt.saturation, pkt.brightness, pkt.kelvin)

            for r in res:
                yield r

        if self.has_extended_multizone(device):
            if pkt | MultiZoneMessages.GetExtendedColorZones:
                yield self.extended_multizone_response(device)

            elif pkt | MultiZoneMessages.SetExtendedColorZones:
                res = self.extended_multizone_response(device)
                for i, c in enumerate(pkt.colors[:pkt.colors_count]):
                    self.set_zone(device, i + pkt.zone_index, c.hue, c.saturation, c.brightness, c.kelvin)
                yield res

class Firmware(dictobj):
    fields = ["major", "minor", "build"]

class ProductResponder(Responder):
    _fields = ["vendor_id", "product_id", "firmware"]

    @classmethod
    def from_enum(self, enum, firmware=Firmware(0, 0, 0)):
        vendor_id = None
        product_id = None
        for e in ProductRegistries.__members__.values():
            if enum.__class__ == e.value:
                vendor_id = VendorRegistry[e.name].value
                product_id = enum.value
                break

        if vendor_id is None or product_id is None:
            assert False, f"Couldn't determine vid and pid from product: {enum}"

        return ProductResponder(
              product_id = product_id
            , vendor_id = vendor_id
            , firmware = firmware
            )

    @classmethod
    def capability(kls, device):
        assert any(isinstance(r, kls) for r in device.responders)
        return capability_for_ids(device.attrs.product_id, device.attrs.vendor_id), device.attrs.firmware.major, device.attrs.firmware.minor

    async def respond(self, device, pkt, source):
        if pkt | DeviceMessages.GetVersion:
            yield DeviceMessages.StateVersion(
                  vendor = device.attrs.vendor_id
                , product = device.attrs.product_id
                , version = 0
                )

        elif pkt | DeviceMessages.GetHostFirmware:
            yield DeviceMessages.StateHostFirmware(
                  build = device.attrs.firmware.build
                , version_major = device.attrs.firmware.major
                , version_minor = device.attrs.firmware.minor
                )

        elif pkt | DeviceMessages.GetWifiFirmware:
            yield DeviceMessages.StateWifiFirmware(
                  build = 0
                , version_major = 0
                , version_minor = 0
                )

def default_responders(
      product = LIFIProductRegistry.LCM2_A19
    , *, power = 0
    , label = ""
    , color = Color(0, 1, 1, 3500)
    , infrared = 0
    , zones = None
    , firmware = Firmware(0, 0, 0)
    , zones_effect = MultiZoneEffectType.OFF
    , tiles_effect = TileEffectType.OFF
    , **kwargs
    ):
    product_responder = ProductResponder.from_enum(product, firmware)

    responders = [
          product_responder
        , LightStateResponder(power=power, color=color, label=label)
        ]

    cap = capability_for_ids(product_responder._attr_default_product_id, product_responder._attr_default_vendor_id)

    if cap.has_ir:
        responders.append(InfraredResponder(infrared=infrared))

    meta = Meta.empty()

    if cap.has_multizone:
        if zones is None:
            assert False, "Product has multizone capability but no zones specified"
        zones_effect = enum_spec(None, MultiZoneEffectType, unpacking=True).normalise(meta, zones_effect)
        responders.append(ZonesResponder(zones=zones, zones_effect=zones_effect))

    if cap.has_chain:
        tiles_effect = enum_spec(None, TileEffectType, unpacking=True).normalise(meta, tiles_effect)
        responders.append(TilesResponder(tiles_effect=tiles_effect))

    return responders

class MemoryTargetRunner:
    def __init__(self, final_future, devices):
        options = {
              "devices": devices
            , "final_future": final_future
            , "protocol_register": protocol_register
            }
        self.target = MemoryTarget.create(options)
        self.devices = devices

    async def __aenter__(self):
        await self.start()

    async def start(self):
        for device in self.devices:
            await device.start()
        self.afr = await self.target.args_for_run()

    async def __aexit__(self, typ, exc, tb):
        await self.close()

    async def close(self):
        await self.target.close_args_for_run(self.afr)
        for device in self.target.devices:
            await device.finish()

    async def reset_devices(self):
        for device in self.devices:
            await device.reset()

    @property
    def serials(self):
        return [device.serial for device in self.devices]

def with_runner(func):
    async def test(s, **kwargs):
        final_future = asyncio.Future()
        try:
            runner = MemoryTargetRunner(final_future, s.devices, **kwargs)
            async with runner:
                await s.wait_for(func(s, runner))
        finally:
            final_future.cancel()
            await runner.reset_devices()
    test.__name__ = func.__name__
    return test

class ModuleLevelRunner:
    def __init__(self, *args, **kwargs):
        self.loop = asyncio.new_event_loop()

        self.args = args
        self.kwargs = kwargs

    async def server_runner(self, devices, **kwargs):
        final_future = asyncio.Future()
        runner = MemoryTargetRunner(final_future, devices, **kwargs)
        await runner.start()

        async def close():
            final_future.cancel()
            await runner.close()

        return runner, close

    def setUp(self):
        """
        Set the loop to our loop and use ``serve_runner`` to get a runner and
        closer
        """
        asyncio.set_event_loop(self.loop)
        self.runner, self.closer = self.loop.run_until_complete(self.server_runner(*self.args, **self.kwargs))

    def tearDown(self):
        """
        Call our closer function returned from ``server_runner`` and set close
        our loop
        """
        if self.closer is not None:
            self.loop.run_until_complete(self.closer())
        self.loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())

    def test(self, func):
        async def test(s):
            await self.runner.reset_devices()
            await s.wait_for(func(s, self.runner), timeout=10)
        test.__name__ = func.__name__
        return test
