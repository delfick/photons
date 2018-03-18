# coding: spec

from photons_device_finder import DeviceFinder, InfoPoints, DeviceFinderWrap, Filter

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.registers import ProtocolRegister
from photons_app.test_helpers import AsyncTestCase

from photons_socket.fake import MemorySocketTarget, FakeDevice
from photons_socket.messages import DiscoveryMessages
from photons_device_messages import DeviceMessages
from photons_protocol.frame import LIFXPacket
from photons_colour import ColourMessages
from photons_script.script import ATarget

from input_algorithms.meta import Meta
import binascii
import asyncio
import uuid

class Device(FakeDevice):
    def __init__(self, *args, **kwargs):
        super(Device, self).__init__(*args, **kwargs)
        self.received = []

        self.hue = 120
        self.saturation = 0.4
        self.brightness = 0.3
        self.kelvin = 3500
        self.label = "LIFX {0}".format(self.serial)
        self.power = 65535

        self.group = ""
        self.group_label = ""
        self.group_updated_at = 0

        self.location = ""
        self.location_label = ""
        self.location_updated_at = 0

        self.firmware_version = 1.22
        self.firmware_build_time = 1508567297

        self.vendor_id = 1
        self.product_id = 22

        self.infrared = 0

    def change_infrared(self, level):
        self.infrared = level

    def change_label(self, label):
        self.label = label

    def change_power(self, power):
        self.power = power

    def change_hsbk(self, hue, saturation, brightness, kelvin):
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.kelvin = kelvin

    def change_group(self, group, label, updated_at):
        self.group = group
        self.group_label = label
        self.group_updated_at = updated_at

    def change_location(self, location, label, updated_at):
        self.location = location
        self.location_label = label
        self.location_updated_at = updated_at

    def change_firmware(self, version, build_time):
        self.firmware_version = version
        self.build_time = build_time

    def change_version(self, vendor_id, product_id):
        self.vendor_id = vendor_id
        self.product_id = product_id

    def make_response(self, pkt):
        self.received.append(pkt)

        if pkt | DeviceMessages.GetInfrared:
            return DeviceMessages.StateInfrared(level=self.infrared)

        if pkt | ColourMessages.GetColor:
            return ColourMessages.LightState(
                  hue = self.hue
                , saturation = self.saturation
                , brightness = self.brightness
                , kelvin = self.kelvin
                , label = self.label
                , power = self.power
                )

        elif pkt | DeviceMessages.GetVersion:
            return DeviceMessages.StateVersion(
                  vendor = self.vendor_id
                , product = self.product_id
                , version = 0
                )

        elif pkt | DeviceMessages.GetHostFirmware:
            return DeviceMessages.StateHostFirmware(
                  version = self.firmware_version
                , build = self.firmware_build_time
                )

        elif pkt | DeviceMessages.GetGroup:
            return DeviceMessages.StateGroup(
                  group = self.group
                , label = self.group_label
                , updated_at = self.group_updated_at
                )

        elif pkt | DeviceMessages.GetLocation:
            return DeviceMessages.StateLocation(
                  location = self.location
                , label = self.location_label
                , updated_at = self.location_updated_at
                )

describe AsyncTestCase, "Memory target":
    def expect_received(self, device, *msgs):
        if not msgs:
            self.assertEqual(device.received, [])

        # De-duplicate to not fail on retries
        typs = []
        for m in device.received:
            if type(m) not in typs:
                typs.append(type(m))

        self.assertEqual(len(typs), len(msgs), typs)
        for t, m in zip(typs, msgs):
            assert t == m, "expected {0} to be {1}".format(t, m)

        while device.received:
            device.received.pop()

    async it "works":
        protocol_register = ProtocolRegister()
        protocol_register.add(1024, LIFXPacket)
        protocol_register.message_register(1024).add(DeviceMessages)
        protocol_register.message_register(1024).add(ColourMessages)
        protocol_register.message_register(1024).add(DiscoveryMessages)

        final_future = asyncio.Future()
        everything = {
              "final_future": lambda: final_future
            , "protocol_register": protocol_register
            }
        meta = Meta(everything, []).at("target")
        target = MemorySocketTarget.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, {})

        device1 = Device("d073d5000001", protocol_register)
        device2 = Device("d073d5000002", protocol_register)
        device3 = Device("d073d5000003", protocol_register)

        device1.change_group("1234", "one", 1)
        device2.change_group("1234", "two", 2)
        device3.change_group("4567", "three", 1)

        device1.change_location("7890", "one", 1)
        device2.change_location("1234", "two", 2)
        device3.change_location("7890", "four", 4)

        device1.change_version(1, 20)
        device3.change_version(1, 29)

        device1.change_label("kitchen")
        device2.change_label("bathroom")
        device3.change_label("hallway")

        device2.change_power(0)

        async with ATarget(target) as afr:
            async with target.with_devices(device1, device2, device3):
                finder = DeviceFinder(target)
                try:
                    serials = await finder.serials()
                    self.assertEqual(sorted(serials), sorted([device1.serial, device2.serial, device3.serial]))
                finally:
                    await finder.finish()

        async def test_wrap():
            wrap = DeviceFinderWrap(Filter.from_kwargs(), target)
            try:
                async with ATarget(target) as afr:
                    found = await wrap.find(afr, True, 5)
                    expected = {t: d.services for t, d in target.devices.items()}
                    serials = [d.serial for d in target.devices.values()]
                    self.assertEqual(found, (expected, serials))
            finally:
                await wrap.finish()
        await self.wait_for(test_wrap())

        finder = DeviceFinder(target
            , service_search_interval = 1
            , information_search_interval = 2
            , repeat_spread = 0.1
            )
        try:
            async with ATarget(target) as afr:
                async with target.with_devices(device1, device2, device3):
                    await finder.start()
                    info = await finder.info_for()
                    expected = {
                          'd073d5000001':
                          { 'label': 'kitchen'
                          , 'power': 'on'
                          , 'hue': 120.0
                          , 'saturation': 0.4
                          , 'brightness': 0.29999237048905164
                          , 'kelvin': 3500
                          , 'firmware_version': 1.22
                          , 'product_id': 20
                          , 'product_identifier': 'lifx_br30_color'
                          , 'group_id': '12340000000000000000000000000000'
                          , 'group_name': 'two'
                          , 'location_name': 'four'
                          , 'location_id': '78900000000000000000000000000000'
                          , "cap": ["color", "not_chain", "not_ir", "not_multizone", "variable_color_temp"]
                          }
                        , 'd073d5000002':
                          { 'label': 'bathroom'
                          , 'power': 'off'
                          , 'hue': 120.0
                          , 'saturation': 0.4
                          , 'brightness': 0.29999237048905164
                          , 'kelvin': 3500
                          , 'firmware_version': 1.22
                          , 'product_id': 22
                          , 'product_identifier': 'lifx_a19_color'
                          , 'group_id': '12340000000000000000000000000000'
                          , 'group_name': 'two'
                          , 'location_name': 'two'
                          , 'location_id': '12340000000000000000000000000000'
                          , "cap": ["color", "not_chain", "not_ir", "not_multizone", "variable_color_temp"]
                          }
                        , 'd073d5000003':
                          { 'label': 'hallway'
                          , 'power': 'on'
                          , 'hue': 120.0
                          , 'saturation': 0.4
                          , 'brightness': 0.29999237048905164
                          , 'kelvin': 3500
                          , 'firmware_version': 1.22
                          , 'product_id': 29
                          , "product_identifier": "lifx_a19_plus"
                          , 'group_id': '45670000000000000000000000000000'
                          , 'group_name': 'three'
                          , 'location_name': 'four'
                          , 'location_id': '78900000000000000000000000000000'
                          , "cap": ["color", "ir", "not_chain", "not_multizone", "variable_color_temp"]
                          }
                        }

                    self.maxDiff = None
                    self.assertEqual(info, expected)

                    self.expect_received(device1, *[type(e.value.msg) for e in InfoPoints])
                    self.expect_received(device2, *[type(e.value.msg) for e in InfoPoints])
                    self.expect_received(device3, *[type(e.value.msg) for e in InfoPoints])

                    serials = await finder.serials(label="kitchen", force_refresh=True)
                    self.expect_received(device1, ColourMessages.GetColor)
                    self.expect_received(device2, ColourMessages.GetColor)
                    self.expect_received(device3, ColourMessages.GetColor)
                    self.assertEqual(serials, [device1.serial])

                    serials = await finder.serials(group_name="two", force_refresh=True)
                    self.expect_received(device1, DeviceMessages.GetGroup)
                    self.expect_received(device2, DeviceMessages.GetGroup)
                    self.expect_received(device3, DeviceMessages.GetGroup)
                    self.assertEqual(set(serials), set([device1.serial, device2.serial]))

                    device1.change_hsbk(hue=72, saturation=0.8, brightness=0.6, kelvin=2500)
                    device2.change_label("blah")
                    device3.change_group("1111", "oneoneone", 7)

                    await asyncio.sleep(2)
                    self.expect_received(device1, *[type(e.value.msg) for e in InfoPoints])
                    self.expect_received(device2, *[type(e.value.msg) for e in InfoPoints])
                    self.expect_received(device3, *[type(e.value.msg) for e in InfoPoints])

                    info = await finder.info_for()
                    expected = {
                          'd073d5000001':
                          { 'label': 'kitchen'
                          , 'power': 'on'
                          , 'hue': 72
                          , 'saturation': 0.8
                          , 'brightness': 0.6
                          , 'kelvin': 2500
                          , 'firmware_version': 1.22
                          , 'product_id': 20
                          , 'product_identifier': 'lifx_br30_color'
                          , 'group_id': '12340000000000000000000000000000'
                          , 'group_name': 'two'
                          , 'location_name': 'four'
                          , 'location_id': '78900000000000000000000000000000'
                          , "cap": ["color", "not_chain", "not_ir", "not_multizone", "variable_color_temp"]
                          }
                        , 'd073d5000002':
                          { 'label': 'blah'
                          , 'power': 'off'
                          , 'hue': 120.0
                          , 'saturation': 0.4
                          , 'brightness': 0.29999237048905164
                          , 'kelvin': 3500
                          , 'firmware_version': 1.22
                          , 'product_id': 22
                          , 'product_identifier': 'lifx_a19_color'
                          , 'group_id': '12340000000000000000000000000000'
                          , 'group_name': 'two'
                          , 'location_name': 'two'
                          , 'location_id': '12340000000000000000000000000000'
                          , "cap": ["color", "not_chain", "not_ir", "not_multizone", "variable_color_temp"]
                          }
                        , 'd073d5000003':
                          { 'label': 'hallway'
                          , 'power': 'on'
                          , 'hue': 120.0
                          , 'saturation': 0.4
                          , 'brightness': 0.29999237048905164
                          , 'kelvin': 3500
                          , 'firmware_version': 1.22
                          , 'product_id': 29
                          , "product_identifier": "lifx_a19_plus"
                          , 'group_id': '11110000000000000000000000000000'
                          , 'group_name': 'oneoneone'
                          , 'location_name': 'four'
                          , 'location_id': '78900000000000000000000000000000'
                          , "cap": ["color", "ir", "not_chain", "not_multizone", "variable_color_temp"]
                          }
                        }

                    self.maxDiff = None
                    self.assertEqual(info, expected)

                    self.expect_received(device1)
                    self.expect_received(device2)
                    self.expect_received(device3)

                    device1.change_infrared(22)
                    device2.change_infrared(25)
                    device3.change_infrared(67)

                    script = target.script(DeviceMessages.GetInfrared())
                    found = []
                    async for pkt, _, _ in script.run_with(finder.find(), afr):
                        assert pkt | DeviceMessages.StateInfrared
                        found.append((binascii.hexlify(pkt.target[:6]).decode(), pkt.payload.level))

                    self.expect_received(device1, DeviceMessages.GetInfrared)
                    self.expect_received(device2, DeviceMessages.GetInfrared)
                    self.expect_received(device3, DeviceMessages.GetInfrared)

                    self.assertEqual(sorted(found)
                        , sorted([(device1.serial, 22), (device2.serial, 25), (device3.serial, 67)])
                        )

                    found = []
                    async for pkt, _, _ in script.run_with(finder.find(location_name="four"), afr):
                        assert pkt | DeviceMessages.StateInfrared
                        found.append((binascii.hexlify(pkt.target[:6]).decode(), pkt.payload.level))

                    self.assertEqual(sorted(found)
                        , sorted([(device1.serial, 22), (device3.serial, 67)])
                        )

                    self.expect_received(device1, DeviceMessages.GetInfrared)
                    self.expect_received(device3, DeviceMessages.GetInfrared)

                    serials = await finder.serials(product_identifier="*a19*")
                    self.assertEqual(sorted(serials), sorted([device2.serial, device3.serial]))
        finally:
            await finder.finish()
