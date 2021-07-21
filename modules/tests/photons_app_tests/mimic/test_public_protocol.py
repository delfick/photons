# coding: spec

from photons_app.mimic.operators.device import Collection
from photons_app.mimic.event import Events
from photons_app import helpers as hp

from photons_products import Products, Family
from photons_messages import (
    DeviceMessages,
    LightMessages,
    TileMessages,
    MultiZoneMessages,
    Waveform,
    TileEffectType,
    MultiZoneEffectType,
    LightLastHevCycleResult,
)

import pytest

devices = pytest.helpers.mimic()

devices.add("a19")(
    next(devices.serial_seq),
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(
        group={"label": "gl", "identity": "abcd", "updated_at": 1},
        location={"label": "ll", "identity": "efef", "updated_at": 2},
    ),
)

devices.add("color1000")(next(devices.serial_seq), Products.LCMV4_A19_COLOR, hp.Firmware(1, 23))

devices.add("lcm3a19")(next(devices.serial_seq), Products.LCM3_A19, hp.Firmware(3, 60))

devices.add("ir")(next(devices.serial_seq), Products.LCM2_A19_PLUS, hp.Firmware(2, 80))

devices.add("tile")(next(devices.serial_seq), Products.LCM3_TILE, hp.Firmware(3, 50))

devices.add("clean")(next(devices.serial_seq), Products.LCM3_A19_CLEAN, hp.Firmware(3, 50))

devices.add("striplcm1")(next(devices.serial_seq), Products.LCM1_Z, hp.Firmware(1, 22))

devices.add("striplcm2noextended")(next(devices.serial_seq), Products.LCM2_Z, hp.Firmware(2, 70))

devices.add("striplcm2extended")(next(devices.serial_seq), Products.LCM2_Z, hp.Firmware(2, 77))


@pytest.fixture(scope="module")
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


@pytest.fixture(scope="module")
async def sender(final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture(autouse=True)
async def reset_devices(sender):
    for device in devices:
        await device.reset()
        devices.store(device).clear()


def makeAssertResponse(device):
    async def assertResponse(send, expected, **attrs):
        send = send.clone()
        send.update(source=2, sequence=2, target=device.serial)
        event = await device.event(Events.INCOMING, device.io["MEMORY"], pkt=send)
        assert event.handled or event.replies
        if expected is not True:
            pytest.helpers.assertSamePackets(event.replies, *expected)
        if attrs:
            devices.store(device).assertAttrs(**attrs)

    return assertResponse


def makeAssertUnhandled(device):
    async def assertUnhandled(send):
        send = send.clone()
        send.update(source=2, sequence=2, target=device.serial)
        event = await device.event(Events.INCOMING, device.io["MEMORY"], pkt=send)
        assert not event.handled and not event.replies

    return assertUnhandled


describe "Device":

    @pytest.fixture()
    def device(self):
        device = devices["a19"]
        devices.store(device).assertAttrs(label="", power=0, color=hp.Color(0, 0, 1, 3500))
        return device

    @pytest.fixture()
    def assertResponse(self, device, **attrs):
        return makeAssertResponse(device, **attrs)

    async it "responds to label messages", device, assertResponse:
        await assertResponse(DeviceMessages.GetLabel(), [DeviceMessages.StateLabel(label="")])
        await assertResponse(
            DeviceMessages.SetLabel(label="sam"),
            [DeviceMessages.StateLabel(label="sam")],
            label="sam",
        )
        await assertResponse(
            DeviceMessages.GetLabel(), [DeviceMessages.StateLabel(label="sam")], label="sam"
        )

    async it "responds to power messages", device, assertResponse:
        await assertResponse(DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=0)])
        await assertResponse(
            DeviceMessages.SetPower(level=200), [DeviceMessages.StatePower(level=0)], power=200
        )
        await assertResponse(
            DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=200)], power=200
        )


describe "LightState":

    @pytest.fixture()
    def device(self):
        device = devices["a19"]
        devices.store(device).assertAttrs(label="", power=0, color=hp.Color(0, 0, 1, 3500))
        return device

    @pytest.fixture()
    def assertResponse(self, device, **attrs):
        return makeAssertResponse(device, **attrs)

    async it "responds to light power messages", device, assertResponse:
        await assertResponse(DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=0)])
        await assertResponse(
            LightMessages.SetLightPower(level=200),
            [LightMessages.StateLightPower(level=0)],
            power=200,
        )
        await assertResponse(
            DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=200)], power=200
        )
        await assertResponse(
            LightMessages.GetLightPower(), [DeviceMessages.StatePower(level=200)], power=200
        )

    @pytest.mark.async_timeout(1e9)
    async it "responds to Color messages", device, assertResponse:

        def light_state(label, power, hue, saturation, brightness, kelvin):
            return LightMessages.LightState.create(
                label=label,
                power=power,
                hue=hue,
                saturation=saturation,
                brightness=brightness,
                kelvin=kelvin,
            )

        await assertResponse(LightMessages.GetColor(), [light_state("", 0, 0, 0, 1, 3500)])

        await assertResponse(
            DeviceMessages.SetLabel(label="bob"),
            [DeviceMessages.StateLabel(label="bob")],
            label="bob",
        )
        await assertResponse(LightMessages.GetColor(), [light_state("bob", 0, 0, 0, 1, 3500)])

        await assertResponse(
            DeviceMessages.SetPower(level=300), [DeviceMessages.StatePower(level=0)], power=300
        )
        await assertResponse(LightMessages.GetColor(), [light_state("bob", 300, 0, 0, 1, 3500)])

        await assertResponse(
            LightMessages.SetColor(hue=100, saturation=0.5, brightness=0.5, kelvin=4500),
            [light_state("bob", 300, 0, 0, 1, 3500)],
        )
        await assertResponse(
            LightMessages.GetColor(), [light_state("bob", 300, 100, 0.5, 0.5, 4500)]
        )

        await assertResponse(
            LightMessages.SetWaveform(
                hue=200, saturation=0.6, brightness=0.4, kelvin=9000, waveform=Waveform.SAW
            ),
            [light_state("bob", 300, 100, 0.5, 0.5, 4500)],
        )
        await assertResponse(
            LightMessages.GetColor(), [light_state("bob", 300, 200, 0.6, 0.4, 9000)]
        )

        await assertResponse(
            LightMessages.SetWaveformOptional(hue=333),
            [light_state("bob", 300, 200, 0.6, 0.4, 9000)],
        )
        await assertResponse(
            LightMessages.GetColor(), [light_state("bob", 300, 333, 0.6, 0.4, 9000)]
        )

        await assertResponse(
            LightMessages.SetWaveformOptional(saturation=0),
            [light_state("bob", 300, 333, 0.6, 0.4, 9000)],
        )
        await assertResponse(LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 0.4, 9000)])

        await assertResponse(
            LightMessages.SetWaveformOptional(brightness=1),
            [light_state("bob", 300, 333, 0, 0.4, 9000)],
        )
        await assertResponse(LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 1, 9000)])

        await assertResponse(
            LightMessages.SetWaveformOptional(kelvin=6789),
            [light_state("bob", 300, 333, 0, 1, 9000)],
        )
        await assertResponse(LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 1, 6789)])

describe "Infrared":

    @pytest.fixture()
    def device(self):
        device = devices["ir"]
        assert device.cap.has_ir
        devices.store(device).assertAttrs(infrared=0)
        return device

    @pytest.fixture()
    def assertResponse(self, device, **attrs):
        return makeAssertResponse(device, **attrs)

    async it "responds to infrared messages", device, assertResponse:
        await assertResponse(
            LightMessages.GetInfrared(), [LightMessages.StateInfrared(brightness=0)]
        )
        await assertResponse(
            LightMessages.SetInfrared(brightness=100),
            [LightMessages.StateInfrared(brightness=0)],
            infrared=100,
        )
        await assertResponse(
            LightMessages.GetInfrared(),
            [LightMessages.StateInfrared(brightness=100)],
            infrared=100,
        )

    async it "doesn't respond to infrared if the product doesn't have infrared":
        device = devices["a19"]
        assert not device.cap.has_ir
        assert device.cap.product.family is Family.LCM2
        assert "infrared" not in device.attrs

        assertUnhandled = makeAssertUnhandled(device)

        await assertUnhandled(LightMessages.GetInfrared())
        await assertUnhandled(LightMessages.SetInfrared(brightness=100))

    async it "does respond to infrared if the product doesn't have infrared but is LCM3":
        device = devices["lcm3a19"]
        assert device.cap.product.family is Family.LCM3
        assert not device.cap.has_ir
        assert "infrared" in device.attrs

        assertResponse = makeAssertResponse(device)

        await assertResponse(
            LightMessages.GetInfrared(), [LightMessages.StateInfrared(brightness=0)]
        )
        await assertResponse(
            LightMessages.SetInfrared(brightness=100),
            [LightMessages.StateInfrared(brightness=0)],
            infrared=100,
        )
        await assertResponse(
            LightMessages.GetInfrared(),
            [LightMessages.StateInfrared(brightness=100)],
            infrared=100,
        )

describe "Matrix":

    @pytest.fixture
    def device(self):
        device = devices["tile"]
        devices.store(device).assertAttrs(matrix_effect=TileEffectType.OFF)
        return device

    @pytest.fixture()
    def assertResponse(self, device, **attrs):
        return makeAssertResponse(device, **attrs)

    async it "responds to changing user position", device, assertResponse:
        await assertResponse(
            TileMessages.SetUserPosition(tile_index=1, user_x=0, user_y=1),
            [],
        )
        assert device.attrs.chain[1].user_x == 0
        assert device.attrs.chain[1].user_y == 1

        await assertResponse(
            TileMessages.SetUserPosition(tile_index=1, user_x=3, user_y=4),
            [],
        )
        assert device.attrs.chain[1].user_x == 3
        assert device.attrs.chain[1].user_y == 4

        await assertResponse(
            TileMessages.SetUserPosition(tile_index=2, user_x=4, user_y=5),
            [],
        )
        assert device.attrs.chain[2].user_x == 4
        assert device.attrs.chain[2].user_y == 5

        # And can be out of range
        await assertResponse(
            TileMessages.SetUserPosition(tile_index=20, user_x=3, user_y=4),
            [],
        )

    async it "responds to tile effect messages", device, assertResponse:
        await assertResponse(
            TileMessages.GetTileEffect(),
            [
                TileMessages.StateTileEffect.create(
                    type=TileEffectType.OFF, speed=0.005, palette_count=0, parameters={}
                )
            ],
        )
        await assertResponse(
            TileMessages.SetTileEffect(
                type=TileEffectType.FLAME,
                palette_count=1,
                palette=[hp.Color(1, 0, 1, 3500)],
            ),
            [
                TileMessages.StateTileEffect.create(
                    type=TileEffectType.OFF, speed=0.005, palette_count=0, parameters={}, palette=[]
                )
            ],
            matrix_effect=TileEffectType.FLAME,
        )
        await assertResponse(
            TileMessages.GetTileEffect(),
            [
                TileMessages.StateTileEffect.create(
                    type=TileEffectType.FLAME,
                    palette_count=1,
                    speed=0.005,
                    parameters={},
                    palette=[hp.Color(1, 0, 1, 3500)] + [hp.Color(0, 0, 0, 0)] * 15,
                )
            ],
            matrix_effect=TileEffectType.FLAME,
        )

    async it "doesn't respond to tile messages if the product doesn't have chain":
        device = devices["a19"]
        assert "matrix_effect" not in device.attrs

        assertUnhandled = makeAssertUnhandled(device)

        await assertUnhandled(TileMessages.GetTileEffect())
        await assertUnhandled(
            TileMessages.SetTileEffect.create(
                type=TileEffectType.FLAME, parameters={}, palette=[hp.Color(0, 0, 0, 3500)]
            )
        )

describe "Zones":

    async def make_device(self, name, zones=None):
        device = devices[name]
        if zones is not None:
            await device.change_one("zones", zones, event=None)
        return device

    async it "doesn't respond if we aren't a multizone device":
        device = devices["a19"]
        assert "zones_effect" not in device.attrs
        assert "zones" not in device.attrs

        assertUnhandled = makeAssertUnhandled(device)

        await assertUnhandled(MultiZoneMessages.GetMultiZoneEffect())
        await assertUnhandled(
            MultiZoneMessages.SetMultiZoneEffect.create(
                type=MultiZoneEffectType.MOVE, parameters={}
            )
        )

        await assertUnhandled(MultiZoneMessages.GetColorZones(start_index=0, end_index=255))
        await assertUnhandled(
            MultiZoneMessages.SetColorZones(
                start_index=0, end_index=1, hue=0, saturation=1, brightness=1, kelvin=3500
            )
        )

        await assertUnhandled(MultiZoneMessages.GetExtendedColorZones())
        await assertUnhandled(
            MultiZoneMessages.SetExtendedColorZones(colors=[hp.Color(0, 0, 0, 0)], colors_count=1)
        )

    async it "doesn't respond to extended multizone if we aren't extended multizone":
        for case in ["striplcm1", "striplcm2noextended"]:
            device = await self.make_device(case, zones=[hp.Color(0, 0, 0, 0)])
            devices.store(device).assertAttrs(
                zones_effect=MultiZoneEffectType.OFF, zones=[hp.Color(0, 0, 0, 0)]
            )

            assertResponse = makeAssertResponse(device)

            await assertResponse(MultiZoneMessages.GetMultiZoneEffect(), True)
            await assertResponse(
                MultiZoneMessages.SetMultiZoneEffect.create(
                    type=MultiZoneEffectType.MOVE, parameters={}
                ),
                True,
            )

            await assertResponse(
                MultiZoneMessages.GetColorZones(start_index=0, end_index=255), True
            )
            await assertResponse(
                MultiZoneMessages.SetColorZones(
                    start_index=0,
                    end_index=1,
                    hue=0,
                    saturation=1,
                    brightness=1,
                    kelvin=3500,
                ),
                True,
            )

            assertUnhandled = makeAssertUnhandled(device)
            await assertUnhandled(MultiZoneMessages.GetExtendedColorZones())
            await assertUnhandled(
                MultiZoneMessages.SetExtendedColorZones(
                    colors=[hp.Color(0, 0, 0, 0)], colors_count=1
                )
            )

    async it "responds to all messages if we have extended multizone":
        device = await self.make_device("striplcm2extended", zones=[hp.Color(0, 0, 0, 0)])
        devices.store(device).assertAttrs(
            zones_effect=MultiZoneEffectType.OFF, zones=[hp.Color(0, 0, 0, 0)]
        )

        assertResponse = makeAssertResponse(device)

        await assertResponse(MultiZoneMessages.GetMultiZoneEffect(), True)
        await assertResponse(
            MultiZoneMessages.SetMultiZoneEffect.create(
                type=MultiZoneEffectType.MOVE, parameters={}
            ),
            True,
        )

        await assertResponse(MultiZoneMessages.GetColorZones(start_index=0, end_index=255), True)
        await assertResponse(
            MultiZoneMessages.SetColorZones(
                start_index=0, end_index=1, hue=0, saturation=1, brightness=1, kelvin=3500
            ),
            True,
        )

        await assertResponse(MultiZoneMessages.GetExtendedColorZones(), True)
        await assertResponse(
            MultiZoneMessages.SetExtendedColorZones(
                colors_count=1, zone_index=0, colors=[hp.Color(0, 0, 0, 0)]
            ),
            True,
        )

    async it "responds to effect messages":
        device = await self.make_device("striplcm2extended", zones=[hp.Color(0, 0, 0, 0)])
        devices.store(device).assertAttrs(
            zones_effect=MultiZoneEffectType.OFF, zones=[hp.Color(0, 0, 0, 0)]
        )

        assertResponse = makeAssertResponse(device)

        await assertResponse(
            MultiZoneMessages.GetMultiZoneEffect(),
            [MultiZoneMessages.StateMultiZoneEffect(type=MultiZoneEffectType.OFF)],
        )
        await assertResponse(
            MultiZoneMessages.SetMultiZoneEffect.create(
                type=MultiZoneEffectType.MOVE, parameters={}
            ),
            [MultiZoneMessages.StateMultiZoneEffect(type=MultiZoneEffectType.OFF)],
            zones_effect=MultiZoneEffectType.MOVE,
        )
        await assertResponse(
            MultiZoneMessages.GetMultiZoneEffect(),
            [MultiZoneMessages.StateMultiZoneEffect(type=MultiZoneEffectType.MOVE)],
        )

    async it "responds to old multizone":
        zones = [
            hp.Color(0, 0, 0, 0),
            hp.Color(1, 0.1, 0.1, 3500),
            hp.Color(2, 0.2, 0.1, 3500),
            hp.Color(3, 0.2, 0.3, 3500),
            hp.Color(3, 0.2, 0.3, 3500),
            hp.Color(3, 0.2, 0.3, 3500),
            hp.Color(6, 0.6, 0.5, 3500),
            hp.Color(7, 0.6, 0.7, 3500),
            hp.Color(8, 0.8, 0.7, 3500),
            hp.Color(9, 0.8, 0.9, 3500),
            hp.Color(10, 1.0, 0.9, 3500),
        ]

        device = await self.make_device("striplcm2extended", zones=zones)
        devices.store(device).assertAttrs(zones_effect=MultiZoneEffectType.OFF, zones=zones)

        assertResponse = makeAssertResponse(device)

        await assertResponse(
            MultiZoneMessages.GetColorZones(start_index=0, end_index=255),
            [
                MultiZoneMessages.StateMultiZone(zones_count=11, zone_index=0, colors=zones[0:8]),
                MultiZoneMessages.StateMultiZone(zones_count=11, zone_index=8, colors=zones[8:]),
            ],
        )

        await assertResponse(
            MultiZoneMessages.GetColorZones(start_index=0, end_index=9),
            [
                MultiZoneMessages.StateMultiZone(zones_count=11, zone_index=0, colors=zones[0:8]),
                MultiZoneMessages.StateMultiZone(zones_count=11, zone_index=8, colors=zones[8:10]),
            ],
        )

        await assertResponse(
            MultiZoneMessages.GetColorZones(start_index=0, end_index=0),
            [MultiZoneMessages.StateZone(zones_count=11, zone_index=0, **zones[0].as_dict())],
        )

        await assertResponse(
            MultiZoneMessages.SetColorZones(
                start_index=7,
                end_index=8,
                hue=100,
                saturation=0,
                brightness=0.1,
                kelvin=6500,
            ),
            [
                MultiZoneMessages.StateMultiZone(zones_count=11, zone_index=7, colors=zones[7:9]),
            ],
        )

        zones[7] = hp.Color(100, 0, 0.1, 6500)
        zones[8] = hp.Color(100, 0, 0.1, 6500)
        await assertResponse(
            MultiZoneMessages.GetColorZones(start_index=0, end_index=255),
            [
                MultiZoneMessages.StateMultiZone(zones_count=11, zone_index=0, colors=zones[0:8]),
                MultiZoneMessages.StateMultiZone(zones_count=11, zone_index=8, colors=zones[8:]),
            ],
        )

    async it "responds to extended multizone":
        zones = [
            hp.Color(0, 0, 0, 0),
            hp.Color(1, 0.1, 0.1, 3500),
            hp.Color(2, 0.2, 0.1, 3500),
            hp.Color(3, 0.2, 0.3, 3500),
            hp.Color(3, 0.2, 0.3, 3500),
            hp.Color(3, 0.2, 0.3, 3500),
            hp.Color(6, 0.6, 0.5, 3500),
            hp.Color(7, 0.6, 0.7, 3500),
            hp.Color(8, 0.8, 0.7, 3500),
            hp.Color(9, 0.8, 0.9, 3500),
            hp.Color(10, 1.0, 0.9, 3500),
        ]

        device = await self.make_device("striplcm2extended", zones=zones)
        devices.store(device).assertAttrs(zones_effect=MultiZoneEffectType.OFF, zones=zones)

        assertResponse = makeAssertResponse(device)

        await assertResponse(
            MultiZoneMessages.GetExtendedColorZones(),
            [
                MultiZoneMessages.StateExtendedColorZones(
                    zones_count=11, zone_index=0, colors_count=11, colors=zones
                )
            ],
        )

        new_colors = [
            hp.Color(100, 0.2, 0.3, 9000),
            hp.Color(200, 0.3, 0.4, 8000),
            hp.Color(300, 0.5, 0.6, 7000),
        ]
        await assertResponse(
            MultiZoneMessages.SetExtendedColorZones(
                zone_index=3, colors_count=3, colors=new_colors
            ),
            [
                MultiZoneMessages.StateExtendedColorZones(
                    zones_count=11, zone_index=0, colors_count=11, colors=zones
                )
            ],
        )

        zones[3] = new_colors[0]
        zones[4] = new_colors[1]
        zones[5] = new_colors[2]
        await assertResponse(
            MultiZoneMessages.GetExtendedColorZones(),
            [
                MultiZoneMessages.StateExtendedColorZones(
                    zones_count=11, zone_index=0, colors_count=11, colors=zones
                )
            ],
        )

describe "Product":

    def make_device(self, name, product, firmware):
        device = devices[name]
        assert device.cap.product is product
        assert device.firmware == firmware
        return device, makeAssertResponse(device)

    async it "responds to GetVersion":
        device, assertResponse = self.make_device("a19", Products.LCM2_A19, hp.Firmware(2, 80))
        await assertResponse(
            DeviceMessages.GetVersion(),
            [DeviceMessages.StateVersion(vendor=1, product=27)],
        )

        device, assertResponse = self.make_device("tile", Products.LCM3_TILE, hp.Firmware(3, 50))
        await assertResponse(
            DeviceMessages.GetVersion(),
            [DeviceMessages.StateVersion(vendor=1, product=55)],
        )

    async it "responds to GetHostFirmware":
        device, assertResponse = self.make_device(
            "color1000", Products.LCMV4_A19_COLOR, hp.Firmware(1, 23)
        )
        device.firmware.build = 2
        await assertResponse(
            DeviceMessages.GetHostFirmware(),
            [DeviceMessages.StateHostFirmware(build=2, version_major=1, version_minor=23)],
        )

        device, assertResponse = self.make_device("tile", Products.LCM3_TILE, hp.Firmware(3, 50))
        device.firmware.build = 4
        await assertResponse(
            DeviceMessages.GetHostFirmware(),
            [DeviceMessages.StateHostFirmware(build=4, version_major=3, version_minor=50)],
        )

    async it "responds to GetWifiFirmware":
        device, assertResponse = self.make_device(
            "color1000", Products.LCMV4_A19_COLOR, hp.Firmware(1, 23)
        )
        await assertResponse(
            DeviceMessages.GetWifiFirmware(),
            [DeviceMessages.StateWifiFirmware(build=0, version_major=0, version_minor=0)],
        )

        device, assertResponse = self.make_device("tile", Products.LCM3_TILE, hp.Firmware(3, 50))
        await assertResponse(
            DeviceMessages.GetWifiFirmware(),
            [DeviceMessages.StateWifiFirmware(build=0, version_major=0, version_minor=0)],
        )

describe "Grouping":

    @pytest.fixture()
    def device(self):
        return devices["a19"]

    @pytest.fixture()
    def assertResponse(self, device, **attrs):
        return makeAssertResponse(device, **attrs)

    async it "responds to group", device, assertResponse:
        getter = DeviceMessages.GetGroup()
        state = DeviceMessages.StateGroup(group="abcd", label="gl", updated_at=1)
        await assertResponse(getter, [state])

        setter = DeviceMessages.SetGroup.create(group="dcba", label="gl2", updated_at=3)
        state = DeviceMessages.StateGroup(group=setter.group, label="gl2", updated_at=3)
        await assertResponse(
            setter, [state], group=Collection(label="gl2", identity=setter.group, updated_at=3)
        )
        await assertResponse(
            setter,
            [state],
            group=Collection(label="gl2", identity=setter.group, updated_at=3),
        )
        await assertResponse(getter, [state])

    async it "responds to location", device, assertResponse:
        getter = DeviceMessages.GetLocation()
        state = DeviceMessages.StateLocation(location="efef", label="ll", updated_at=2)
        await assertResponse(getter, [state])

        setter = DeviceMessages.SetLocation.create(location="fefe", label="ll2", updated_at=6)
        state = DeviceMessages.StateLocation(location=setter.location, label="ll2", updated_at=6)
        await assertResponse(
            setter,
            [state],
            location=Collection(label="ll2", identity=setter.location, updated_at=6),
        )
        await assertResponse(getter, [state])

describe "Clean":

    @pytest.fixture()
    def device(self):
        return devices["clean"]

    @pytest.fixture()
    def assertResponse(self, device, **attrs):
        return makeAssertResponse(device, **attrs)

    @pytest.fixture(autouse=True)
    async def fake_the_time(self, FakeTime, MockedCallLater):
        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                yield (t, m)

    @pytest.fixture()
    def m(self, fake_the_time):
        return fake_the_time[1]

    async it "responds to starting a cycle when light is off", device, assertResponse, m:
        await device.change_one("power", 0, event=None)

        assert device.attrs.clean_details.enabled is False
        assert device.attrs.clean_details.duration_s == 0
        assert device.attrs.clean_details.remaining_s == 0
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.NONE
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        getter = LightMessages.GetHevCycleConfiguration()
        state = LightMessages.StateHevCycleConfiguration(indication=False, duration_s=7200)
        await assertResponse(getter, [state])
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        getter = LightMessages.GetLightPower()
        state = DeviceMessages.StatePower(level=0)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0
        getter = DeviceMessages.GetPower()
        state = DeviceMessages.StatePower(level=0)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0

        setter = LightMessages.SetHevCycle(enable=True, duration_s=0, res_required=False)
        await assertResponse(setter, True)
        getter = LightMessages.GetHevCycle()
        state = LightMessages.StateHevCycle(duration_s=7200, remaining_s=7200, last_power=0)
        await assertResponse(getter, [state])
        assert device.attrs.clean_details.enabled is True
        assert device.attrs.clean_details.duration_s == 7200
        assert device.attrs.clean_details.remaining_s == 7200
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.BUSY
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        # Reports as on even though it's actually not
        assert device.attrs.power == 0
        getter = DeviceMessages.GetPower()
        state = DeviceMessages.StatePower(level=0xFFFF)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0
        getter = LightMessages.GetLightPower()
        state = DeviceMessages.StatePower(level=0xFFFF)
        await assertResponse(getter, [state])

        await m.add(250)
        getter = LightMessages.GetHevCycle()
        state = LightMessages.StateHevCycle(duration_s=7200, remaining_s=6950, last_power=0)
        await assertResponse(getter, [state])
        assert device.attrs.clean_details.enabled is True
        assert device.attrs.clean_details.duration_s == 7200
        assert device.attrs.clean_details.remaining_s == 6950
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.BUSY
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        await m.add(7200)
        getter = LightMessages.GetHevCycle()
        state = LightMessages.StateHevCycle(duration_s=0, remaining_s=0, last_power=0)
        await assertResponse(getter, [state])
        assert device.attrs.clean_details.enabled is False
        assert device.attrs.clean_details.duration_s == 0
        assert device.attrs.clean_details.remaining_s == 0
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.SUCCESS
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        # Reports to back as off
        getter = LightMessages.GetLightPower()
        state = DeviceMessages.StatePower(level=0)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0
        getter = DeviceMessages.GetPower()
        state = DeviceMessages.StatePower(level=0)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0

    async it "responds to starting a cycle when light is on", device, assertResponse, m:
        await device.change_one("power", 0xFFFF, event=None)

        assert device.attrs.clean_details.enabled is False
        assert device.attrs.clean_details.duration_s == 0
        assert device.attrs.clean_details.remaining_s == 0
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.NONE
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        getter = LightMessages.GetLightPower()
        state = DeviceMessages.StatePower(level=0xFFFF)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0xFFFF
        getter = DeviceMessages.GetPower()
        state = DeviceMessages.StatePower(level=0xFFFF)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0xFFFF

        setter = LightMessages.SetHevCycle(enable=True, duration_s=200, res_required=False)
        await assertResponse(setter, True)
        getter = LightMessages.GetHevCycle()
        state = LightMessages.StateHevCycle(duration_s=200, remaining_s=200, last_power=1)
        await assertResponse(getter, [state])
        assert device.attrs.clean_details.enabled is True
        assert device.attrs.clean_details.duration_s == 200
        assert device.attrs.clean_details.remaining_s == 200
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.BUSY
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        getter = LightMessages.GetLightPower()
        state = DeviceMessages.StatePower(level=0xFFFF)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0xFFFF
        getter = DeviceMessages.GetPower()
        state = DeviceMessages.StatePower(level=0xFFFF)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0xFFFF

        await m.add(250)
        getter = LightMessages.GetHevCycle()
        state = LightMessages.StateHevCycle(duration_s=0, remaining_s=0, last_power=0)
        await assertResponse(getter, [state])
        assert device.attrs.clean_details.enabled is False
        assert device.attrs.clean_details.duration_s == 0
        assert device.attrs.clean_details.remaining_s == 0
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.SUCCESS
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        getter = LightMessages.GetLightPower()
        state = DeviceMessages.StatePower(level=0xFFFF)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0xFFFF
        getter = DeviceMessages.GetPower()
        state = DeviceMessages.StatePower(level=0xFFFF)
        await assertResponse(getter, [state])
        assert device.attrs.power == 0xFFFF

    async it "can change default duration", device, assertResponse, m:
        setter = LightMessages.SetHevCycle(enable=True, duration_s=0, res_required=False)
        await assertResponse(setter, True)
        getter = LightMessages.GetHevCycle()
        state = LightMessages.StateHevCycle(duration_s=7200, remaining_s=7200, last_power=0)
        await assertResponse(getter, [state])
        assert device.attrs.clean_details.enabled is True
        assert device.attrs.clean_details.duration_s == 7200
        assert device.attrs.clean_details.remaining_s == 7200
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.BUSY
        assert device.attrs.clean_details.indication is False
        assert device.attrs.clean_details.default_duration_s == 7200

        setter = LightMessages.SetHevCycleConfiguration(indication=True, duration_s=69420)
        state = LightMessages.StateHevCycleConfiguration(indication=True, duration_s=69420)
        await assertResponse(setter, [state])

        setter = LightMessages.SetHevCycle(enable=True, duration_s=0, res_required=False)
        await assertResponse(setter, True)
        assert device.attrs.clean_details.enabled is True
        assert device.attrs.clean_details.duration_s == 69420
        assert device.attrs.clean_details.remaining_s == 69420
        assert device.attrs.clean_details.last_result is LightLastHevCycleResult.BUSY
        assert device.attrs.clean_details.indication is True
        assert device.attrs.clean_details.default_duration_s == 69420

    async it "can interrupt a cycle", device, assertResponse, m:

        async def start(enable, duration):
            setter = LightMessages.SetHevCycle(
                enable=enable, duration_s=duration, res_required=False
            )
            await assertResponse(setter, True)

        async def assertRemaining(duration, remaining, last_power, result):
            getter = LightMessages.GetHevCycle()
            state = LightMessages.StateHevCycle(
                duration_s=duration, remaining_s=remaining, last_power=last_power
            )
            await assertResponse(getter, [state])

            getter = LightMessages.GetLastHevCycleResult()
            state = LightMessages.StateLastHevCycleResult(result=result)
            await assertResponse(getter, [state])

        await assertRemaining(0, 0, 0, LightLastHevCycleResult.NONE)
        await start(True, 2000)
        await assertRemaining(2000, 2000, 0, LightLastHevCycleResult.BUSY)
        await m.add(1720)
        await assertRemaining(2000, 280, 0, LightLastHevCycleResult.BUSY)

        await start(False, 2000)
        await assertRemaining(0, 0, 0, LightLastHevCycleResult.INTERRUPTED_BY_LAN)

        await start(True, 200)
        await assertRemaining(200, 200, 0, LightLastHevCycleResult.BUSY)

        await device.power_off()
        await assertRemaining(0, 0, 0, LightLastHevCycleResult.INTERRUPTED_BY_RESET)
        await device.power_on()
        await assertRemaining(0, 0, 0, LightLastHevCycleResult.INTERRUPTED_BY_RESET)

        await start(True, 1337)
        await m.add(1336)
        await assertRemaining(1337, 1, 0, LightLastHevCycleResult.BUSY)
        await m.add(2)
        await assertRemaining(0, 0, 0, LightLastHevCycleResult.SUCCESS)
