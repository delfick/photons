from photons_app.errors import PhotonsAppError

from photons_messages import (
      LightMessages, DeviceMessages, MultiZoneMessages, TileMessages
    , MultiZoneEffectType, TileEffectType
    , protocol_register
    )
from photons_socket.fake import FakeDevice, MemorySocketTarget, MemoryTarget
from photons_products_registry import capability_for_ids
from photons_protocol.types import Type as T

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
from contextlib import contextmanager
from collections import defaultdict
import asyncio

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
            if round(diff) > precision:
                return False

        return True

def pktkeys(msgs, keep_duplicates=False):
    keys = []
    for msg in msgs:
        clone = msg.payload.clone()
        if hasattr(clone, "instanceid"):
            clone.instanceid = 0
        for name, typ in clone.Meta.field_types:
            if clone.actual(name) is sb.NotSpecified and isinstance(typ, type(T.Reserved)):
                clone[name] = None

        key = (msg.protocol, msg.pkt_type, repr(clone))
        if key not in keys or keep_duplicates:
            keys.append(key)
    return keys

class Color(dictobj):
    fields = ["hue", "saturation", "brightness", "kelvin"]

class Device(FakeDevice):
    def __init__(self, serial, *
        , label = ""
        , power = 0
        , infrared = 0
        , product_id = 22
        , firmware_major = 1
        , firmware_minor = 22
        , firmware_build = 1502237570000000000
        , color = Color(0, 0, 1, 3500)
        , zones = [Color(0, 0, 0, 3500)] * 8
        , **kwargs
        ):
        super().__init__(serial, protocol_register, **kwargs)

        self.product_id = product_id
        self.capability = capability_for_ids(self.product_id, 1)

        def reset():
            self.online = True
            self.label = label
            self.set_replies = defaultdict(list)

            self.received = []
            self.received_processing = None

            self.change_hsbk(color)
            self.change_power(power)
            self.change_zones(zones)
            self.change_infrared(infrared)
            self.change_zones_effect(MultiZoneEffectType.OFF)
            self.change_tile_effect(TileEffectType.OFF)

            self.change_firmware(firmware_build, firmware_major, firmware_minor)

            self._no_reply_to = ()

        self.reset = reset
        reset()

    def set_reply(self, kls, msg):
        self.set_replies[kls].append(msg)

    @property
    def has_extended_multizone(self):
        return self.capability.has_multizone and self.capability.has_extended_multizone(self.firmware_major, self.firmware_minor)

    def set_received_processing(self, processor):
        if self.use_sockets:
            assert False, "Setting received_processing callback on a device that won't ever use it"
        self.received_processing = processor

    def change_power(self, power):
        self.power = power

    def change_infrared(self, infrared):
        self.infrared = infrared

    def change_label(self, label):
        self.label = label

    def change_zones(self, zones):
        if len(zones) > 82:
            raise PhotonsAppError("Can only have up to 82 zones!")
        self.zones = zones

    def change_zones_effect(self, effect):
        if self.capability.has_multizone:
            self.zones_effect = effect

    def change_tile_effect(self, effect):
        if self.capability.has_chain:
            self.tile_effect = effect

    def change_hsbk(self, color):
        self.hue = color.hue
        self.saturation = color.saturation
        self.brightness = color.brightness
        self.kelvin = color.kelvin

    def change_firmware(self, firmware_build, firmware_major, firmware_minor):
        self.firmware_build = firmware_build
        self.firmware_major = firmware_major
        self.firmware_minor = firmware_minor

    def compare_received(self, expected, keep_duplicates=False):
        expect_keys = pktkeys(expected, keep_duplicates)
        got_keys = pktkeys(self.received, keep_duplicates)

        def do_print():
            print(self.serial)
            print("GOT:")
            for key in got_keys:
                print(f"\t{key}")
            print()
            print("EXPECTED:")
            for key in expect_keys:
                print(f"\t{key}")
            print()

        if len(expect_keys) != len(got_keys):
            do_print()
            assert False, "Expected a different number of messages to what we got"

        different = False
        for i, (got, expect) in enumerate(zip(got_keys, expect_keys)):
            if got != expect:
                print(f"{self.serial} Message {i} is different\n\tGOT:\n\t\t{got}\n\tEXPECT:\n\t\t{expect}")
                different = True

        if different:
            print("=" * 80)
            do_print()
            assert False, "Expected messages to be the same"

    def compare_received_klses(self, expected, keep_duplicates=False):
        got = self.received
        got_keys = pktkeys(self.received, keep_duplicates)

        def do_print():
            print(self.serial)
            print("GOT:")
            for key in got_keys:
                print(f"\t{key}")
            print()
            print("EXPECTED:")
            for kls in expected:
                print(f"\t{kls}")
            print()

        if len(expected) != len(got):
            do_print()
            assert False, "Expected a different number of messages to what we got"

        different = False
        for i, (got, expect) in enumerate(zip(got, expected)):
            if not got | expect:
                print(f"{self.serial} Message {i} is different\n\tGOT:\n\t\t{got}\n\tEXPECT:\n\t\t{expect}")
                different = True

        if different:
            print("=" * 80)
            do_print()
            assert False, "Expected messages to be the same"

    def reset_received(self):
        self.received = []

    async def async_got_message(self, pkt):
        if self.received_processing:
            if await self.received_processing(pkt) is False:
                return

        async for msg in super().async_got_message(pkt):
            yield msg

    @contextmanager
    def no_reply_to(self, *types):
        previous_no_reply_to = self._no_reply_to
        try:
            self._no_reply_to = self._no_reply_to + types
            yield
        finally:
            self._no_reply_to = previous_no_reply_to

    def ack_for(self, pkt, protocol):
        if not any(pkt | t for t in self._no_reply_to):
            return super().ack_for(pkt, protocol)

    def response_for(self, pkt, protocol):
        for res in super().response_for(pkt, protocol):
            if not any(pkt | t for t in self._no_reply_to):
                yield res

    def make_response(self, pkt, protocol):
        self.received.append(pkt)

        for kls, msgs in self.set_replies.items():
            if msgs and pkt | kls:
                return msgs.pop()

        if pkt | LightMessages.GetColor:
            return self.light_state_message()

        elif pkt | DeviceMessages.SetPower or pkt | LightMessages.SetLightPower:
            res = DeviceMessages.StatePower(level=pkt.level)
            self.change_power(pkt.level)
            return res

        elif pkt | DeviceMessages.GetPower:
            return DeviceMessages.StatePower(level=self.power)

        elif pkt | LightMessages.GetInfrared:
            return LightMessages.StateInfrared(brightness=self.infrared)

        elif pkt | LightMessages.SetInfrared:
            self.change_infrared(pkt.brightness)
            return LightMessages.StateInfrared(brightness=self.infrared)

        elif pkt | LightMessages.SetWaveformOptional or pkt | LightMessages.SetColor:
            self.change_hsbk(Color(pkt.hue, pkt.saturation, pkt.brightness, pkt.kelvin))
            return self.light_state_message()

        elif pkt | DeviceMessages.SetLabel:
            self.change_label(pkt.label)
            return DeviceMessages.StateLabel(label=self.label)

        elif pkt | DeviceMessages.GetLabel:
            return DeviceMessages.StateLabel(label=self.label)

        elif pkt | DeviceMessages.GetVersion:
            return DeviceMessages.StateVersion(vendor=1, product=self.product_id, version=0)

        elif pkt | DeviceMessages.GetHostFirmware:
            return DeviceMessages.StateHostFirmware(build=self.firmware_build, version_major=self.firmware_major, version_minor=self.firmware_minor)

        elif pkt | MultiZoneMessages.GetColorZones:
            if self.capability.has_multizone:
                if pkt.start_index != 0 or pkt.end_index != 255:
                    raise PhotonsAppError("Fake device only supports getting all color zones", got=pkt.payload)

                buf = []
                bufs = []

                for i, zone in enumerate(self.zones):
                    if len(buf) == 8:
                        bufs.append(buf)
                        buf = []

                    buf.append((i, zone))

                if buf:
                    bufs.append(buf)

                return [
                      MultiZoneMessages.StateMultiZone(zones_count=len(self.zones), zone_index=buf[0][0], colors=[b.as_dict() for _, b in buf])
                      for buf in bufs
                    ]

        elif pkt | MultiZoneMessages.SetColorZones:
            if self.capability.has_multizone:
                for i in range(pkt.start_index, pkt.end_index + 1):
                    self.zones[i] = {
                          "hue": pkt.hue
                        , "saturation": pkt.saturation
                        , "brightness": pkt.brightness
                        , "kelvin": pkt.kelvin
                        }

        elif pkt | MultiZoneMessages.GetExtendedColorZones:
            if self.has_extended_multizone:
                return MultiZoneMessages.StateExtendedColorZones(
                      zones_count = len(self.zones)
                    , zone_index = 0
                    , colors_count = len(self.zones)
                    , colors = [z.as_dict() for z in self.zones]
                    )

        elif pkt | MultiZoneMessages.SetExtendedColorZones:
            if self.has_extended_multizone:
                for i, c in enumerate(pkt.colors[:pkt.colors_count]):
                    self.zones[i + pkt.zone_index] = c.as_dict()

        elif pkt | MultiZoneMessages.SetMultiZoneEffect:
            if self.capability.has_multizone:
                self.change_zones_effect(pkt.type)

        elif pkt | TileMessages.SetTileEffect:
            if self.capability.has_chain:
                self.change_tile_effect(pkt.type)

    def light_state_message(self):
        return LightMessages.LightState(
              hue = self.hue
            , saturation = self.saturation
            , brightness = self.brightness
            , kelvin = self.kelvin
            , power = self.power
            , label = self.label
            )

class MemoryTargetRunner:
    def __init__(self, final_future, devices, use_sockets=True):
        options = {
              "final_future": final_future
            , "protocol_register": protocol_register
            }
        if use_sockets:
            self.target = MemorySocketTarget.create(options)
        else:
            self.target = MemoryTarget.create(options)

        self.devices = devices

    async def __aenter__(self):
        await self.start()

    async def start(self):
        for device in self.devices:
            await device.start()
            self.target.add_device(device)
        self.afr = await self.target.args_for_run()

    async def __aexit__(self, typ, exc, tb):
        await self.close()

    async def close(self):
        await self.target.close_args_for_run(self.afr)
        for device in self.target.devices.values():
            await device.finish()

    def reset_devices(self):
        for device in self.devices:
            device.reset()

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
            runner.reset_devices()
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
            self.runner.reset_devices()
            await s.wait_for(func(s, self.runner), timeout=10)
        test.__name__ = func.__name__
        return test
