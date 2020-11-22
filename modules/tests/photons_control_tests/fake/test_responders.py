# coding: spec

from photons_control import test_helpers as chp

from photons_app.test_helpers import print_packet_difference
from photons_app.errors import PhotonsAppError

from photons_products import Products
from photons_messages import (
    DeviceMessages,
    LightMessages,
    TileMessages,
    MultiZoneMessages,
    Waveform,
    TileEffectType,
    MultiZoneEffectType,
)
from photons_transport.fake import FakeDevice

from delfick_project.errors_pytest import assertRaises
import pytest


class Device:
    def __init__(self, *responders):
        self.device = FakeDevice("d073d5000001", responders)

    def __getattr__(self, key):
        device = object.__getattribute__(self, "device")
        if hasattr(device, key):
            return getattr(device, key)
        return object.__getattribute__(self, key)

    async def __aenter__(self):
        await self.device.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.device.finish()

    def assertAttrs(self, **attrs):
        for key, val in attrs.items():
            assert self.device.attrs[key] == val

    async def assertResponse(self, pkt, expected, **expected_attrs):
        got = await self.device.make_response(pkt, "udp")
        if got is None:
            assert expected == []
        else:
            if expected is True:
                assert len(got) > 0
            else:
                assert len(got) == len(expected), got

                different = False
                for g, e in zip(got, expected):
                    if e | TileMessages.StateTileEffect and g | TileMessages.StateTileEffect:
                        e.instanceid = g.instanceid
                    if g != e:
                        print_packet_difference(g, e, ignore_unspecified_expected=True)

                    # Make sure message can be packed
                    g.source = 1
                    g.sequence = 1
                    g.target = None
                    g.pack()

                assert not different, got

        for key, val in expected_attrs.items():
            assert self.device.attrs[key] == val


describe "Responders":

    describe "LightStateResponder":

        @pytest.fixture()
        async def device(self):
            device = Device(chp.LightStateResponder())
            async with device:
                device.assertAttrs(label="", power=0, color=chp.Color(0, 0, 1, 3500))
                yield device

        async it "responds to label messages", device:
            await device.assertResponse(
                DeviceMessages.GetLabel(), [DeviceMessages.StateLabel(label="")]
            )
            await device.assertResponse(
                DeviceMessages.SetLabel(label="sam"),
                [DeviceMessages.StateLabel(label="sam")],
                label="sam",
            )
            await device.assertResponse(
                DeviceMessages.GetLabel(), [DeviceMessages.StateLabel(label="sam")], label="sam"
            )

        async it "responds to power messages", device:
            await device.assertResponse(
                DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=0)]
            )
            await device.assertResponse(
                DeviceMessages.SetPower(level=200), [DeviceMessages.StatePower(level=0)], power=200
            )
            await device.assertResponse(
                DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=200)], power=200
            )

        async it "responds to light power messages", device:
            await device.assertResponse(
                DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=0)]
            )
            await device.assertResponse(
                LightMessages.SetLightPower(level=200),
                [LightMessages.StateLightPower(level=0)],
                power=200,
            )
            await device.assertResponse(
                DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=200)], power=200
            )

        async it "responds to Color messages", device:

            def light_state(label, power, hue, saturation, brightness, kelvin):
                return LightMessages.LightState.create(
                    label=label,
                    power=power,
                    hue=hue,
                    saturation=saturation,
                    brightness=brightness,
                    kelvin=kelvin,
                )

            await device.assertResponse(
                LightMessages.GetColor(), [light_state("", 0, 0, 0, 1, 3500)]
            )

            await device.assertResponse(
                DeviceMessages.SetLabel(label="bob"),
                [DeviceMessages.StateLabel(label="bob")],
                label="bob",
            )
            await device.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 0, 0, 0, 1, 3500)]
            )

            await device.assertResponse(
                DeviceMessages.SetPower(level=300), [DeviceMessages.StatePower(level=0)], power=300
            )
            await device.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 0, 0, 1, 3500)]
            )

            await device.assertResponse(
                LightMessages.SetColor(hue=100, saturation=0.5, brightness=0.5, kelvin=4500),
                [light_state("bob", 300, 0, 0, 1, 3500)],
            )
            await device.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 100, 0.5, 0.5, 4500)]
            )

            await device.assertResponse(
                LightMessages.SetWaveform(
                    hue=200, saturation=0.6, brightness=0.4, kelvin=9000, waveform=Waveform.SAW
                ),
                [light_state("bob", 300, 100, 0.5, 0.5, 4500)],
            )
            await device.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 200, 0.6, 0.4, 9000)]
            )

            await device.assertResponse(
                LightMessages.SetWaveformOptional(hue=333),
                [light_state("bob", 300, 200, 0.6, 0.4, 9000)],
            )
            await device.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 333, 0.6, 0.4, 9000)]
            )

            await device.assertResponse(
                LightMessages.SetWaveformOptional(saturation=0),
                [light_state("bob", 300, 333, 0.6, 0.4, 9000)],
            )
            await device.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 0.4, 9000)]
            )

            await device.assertResponse(
                LightMessages.SetWaveformOptional(brightness=1),
                [light_state("bob", 300, 333, 0, 0.4, 9000)],
            )
            await device.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 1, 9000)]
            )

            await device.assertResponse(
                LightMessages.SetWaveformOptional(kelvin=6789),
                [light_state("bob", 300, 333, 0, 1, 9000)],
            )
            await device.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 1, 6789)]
            )

    describe "InfraredResponder":

        @pytest.fixture()
        async def device(self):
            device = Device(
                chp.ProductResponder.from_product(Products.LCM2_A19_PLUS), chp.InfraredResponder()
            )

            async with device:
                device.assertAttrs(infrared=0)
                yield device

        async it "responds to infrared messages", device:
            await device.assertResponse(
                LightMessages.GetInfrared(), [LightMessages.StateInfrared(brightness=0)]
            )
            await device.assertResponse(
                LightMessages.SetInfrared(brightness=100),
                [LightMessages.StateInfrared(brightness=0)],
                infrared=100,
            )
            await device.assertResponse(
                LightMessages.GetInfrared(),
                [LightMessages.StateInfrared(brightness=100)],
                infrared=100,
            )

        async it "doesn't respond to infrared if the product doesn't have infrared":
            device = Device(
                chp.ProductResponder.from_product(Products.LCM2_A19), chp.InfraredResponder()
            )

            async with device:
                assert "infrared" not in device.attrs

                await device.assertResponse(LightMessages.GetInfrared(), [])
                await device.assertResponse(LightMessages.SetInfrared(brightness=100), [])

        async it "does respond to infrared if the product doesn't have infrared but is LCM3":
            device = Device(
                chp.ProductResponder.from_product(Products.LCM3_TILE), chp.InfraredResponder()
            )

            async with device:
                assert "infrared" in device.attrs

                await device.assertResponse(
                    LightMessages.GetInfrared(), [LightMessages.StateInfrared(brightness=0)]
                )
                await device.assertResponse(
                    LightMessages.SetInfrared(brightness=100),
                    [LightMessages.StateInfrared(brightness=0)],
                    infrared=100,
                )
                await device.assertResponse(
                    LightMessages.GetInfrared(),
                    [LightMessages.StateInfrared(brightness=100)],
                    infrared=100,
                )

    describe "MatrixResponder":

        @pytest.fixture
        async def device(self):
            device = Device(
                chp.ProductResponder.from_product(Products.LCM3_TILE), chp.MatrixResponder()
            )

            async with device:
                device.assertAttrs(matrix_effect=TileEffectType.OFF)
                yield device

        async it "responds to tile effect messages", device:
            await device.assertResponse(
                TileMessages.GetTileEffect(),
                [
                    TileMessages.StateTileEffect.create(
                        type=TileEffectType.OFF, palette_count=0, parameters={}
                    )
                ],
            )
            await device.assertResponse(
                TileMessages.SetTileEffect(
                    type=TileEffectType.FLAME, palette_count=1, palette=[chp.Color(1, 0, 1, 3500)]
                ),
                [
                    TileMessages.StateTileEffect.create(
                        type=TileEffectType.OFF, palette_count=0, parameters={}, palette=[]
                    )
                ],
                matrix_effect=TileEffectType.FLAME,
            )
            await device.assertResponse(
                TileMessages.GetTileEffect(),
                [
                    TileMessages.StateTileEffect.create(
                        type=TileEffectType.FLAME,
                        palette_count=1,
                        parameters={},
                        palette=[chp.Color(1, 0, 1, 3500)] + [chp.Color(0, 0, 0, 0)] * 15,
                    )
                ],
                matrix_effect=TileEffectType.FLAME,
            )

        async it "doesn't respond to tile messages if the product doesn't have chain":
            device = Device(
                chp.ProductResponder.from_product(Products.LCMV4_A19_COLOR), chp.MatrixResponder()
            )

            async with device:
                assert "matrix_effect" not in device.attrs

                await device.assertResponse(TileMessages.GetTileEffect(), [])
                await device.assertResponse(
                    TileMessages.SetTileEffect.create(
                        type=TileEffectType.FLAME, parameters={}, palette=[chp.Color(0, 0, 0, 3500)]
                    ),
                    [],
                )

    describe "ZonesResponder":

        def make_device(self, enum, firmware, zones=None):
            return Device(
                chp.ProductResponder.from_product(enum, firmware), chp.ZonesResponder(zones=zones)
            )

        async it "complains if you try to set too many zones":
            zones = [chp.Color(0, 0, 0, 0)] * 83
            with assertRaises(PhotonsAppError, "Can only have up to 82 zones!"):
                async with self.make_device(Products.LCM1_Z, chp.Firmware(0, 0, 0), zones):
                    pass

        async it "doesn't respond if we aren't a multizone device":
            async with self.make_device(Products.LCMV4_A19_COLOR, chp.Firmware(0, 0, 0)) as device:
                assert "zones_effect" not in device.attrs
                assert "zones" not in device.attrs

                await device.assertResponse(MultiZoneMessages.GetMultiZoneEffect(), [])
                await device.assertResponse(
                    MultiZoneMessages.SetMultiZoneEffect.create(
                        type=MultiZoneEffectType.MOVE, parameters={}
                    ),
                    [],
                )

                await device.assertResponse(
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=255), []
                )
                await device.assertResponse(
                    MultiZoneMessages.SetColorZones(
                        start_index=0, end_index=1, hue=0, saturation=1, brightness=1, kelvin=3500
                    ),
                    [],
                )

                await device.assertResponse(MultiZoneMessages.GetExtendedColorZones(), [])
                await device.assertResponse(
                    MultiZoneMessages.SetExtendedColorZones(colors=[chp.Color(0, 0, 0, 0)]), []
                )

        async it "doesn't respond to extended multizone if we aren't extended multizone":
            cases = [
                (Products.LCM1_Z, chp.Firmware(0, 0, 0), [chp.Color(0, 0, 0, 0)]),
                (Products.LCM2_Z, chp.Firmware(0, 0, 0), [chp.Color(0, 0, 0, 0)]),
            ]

            for case in cases:
                async with self.make_device(*case) as device:
                    device.assertAttrs(
                        zones_effect=MultiZoneEffectType.OFF, zones=[chp.Color(0, 0, 0, 0)]
                    )

                    await device.assertResponse(MultiZoneMessages.GetMultiZoneEffect(), True)
                    await device.assertResponse(
                        MultiZoneMessages.SetMultiZoneEffect.create(
                            type=MultiZoneEffectType.MOVE, parameters={}
                        ),
                        True,
                    )

                    await device.assertResponse(
                        MultiZoneMessages.GetColorZones(start_index=0, end_index=255), True
                    )
                    await device.assertResponse(
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

                    await device.assertResponse(MultiZoneMessages.GetExtendedColorZones(), [])
                    await device.assertResponse(
                        MultiZoneMessages.SetExtendedColorZones(colors=[chp.Color(0, 0, 0, 0)]), []
                    )

        async it "responds to all messages if we have extended multizone":
            async with self.make_device(
                Products.LCM2_Z, chp.Firmware(2, 77, 1543215651000000000), [chp.Color(0, 0, 0, 0)]
            ) as device:
                device.assertAttrs(
                    zones_effect=MultiZoneEffectType.OFF, zones=[chp.Color(0, 0, 0, 0)]
                )

                await device.assertResponse(MultiZoneMessages.GetMultiZoneEffect(), True)
                await device.assertResponse(
                    MultiZoneMessages.SetMultiZoneEffect.create(
                        type=MultiZoneEffectType.MOVE, parameters={}
                    ),
                    True,
                )

                await device.assertResponse(
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=255), True
                )
                await device.assertResponse(
                    MultiZoneMessages.SetColorZones(
                        start_index=0, end_index=1, hue=0, saturation=1, brightness=1, kelvin=3500
                    ),
                    True,
                )

                await device.assertResponse(MultiZoneMessages.GetExtendedColorZones(), True)
                await device.assertResponse(
                    MultiZoneMessages.SetExtendedColorZones(
                        colors_count=1, zone_index=0, colors=[chp.Color(0, 0, 0, 0)]
                    ),
                    True,
                )

        async it "responds to effect messages":
            async with self.make_device(
                Products.LCM2_Z, chp.Firmware(2, 77, 1543215651000000000), [chp.Color(0, 0, 0, 0)]
            ) as device:
                device.assertAttrs(
                    zones_effect=MultiZoneEffectType.OFF, zones=[chp.Color(0, 0, 0, 0)]
                )

                await device.assertResponse(
                    MultiZoneMessages.GetMultiZoneEffect(),
                    [MultiZoneMessages.StateMultiZoneEffect(type=MultiZoneEffectType.OFF)],
                )
                await device.assertResponse(
                    MultiZoneMessages.SetMultiZoneEffect.create(
                        type=MultiZoneEffectType.MOVE, parameters={}
                    ),
                    [MultiZoneMessages.StateMultiZoneEffect(type=MultiZoneEffectType.OFF)],
                    zones_effect=MultiZoneEffectType.MOVE,
                )
                await device.assertResponse(
                    MultiZoneMessages.GetMultiZoneEffect(),
                    [MultiZoneMessages.StateMultiZoneEffect(type=MultiZoneEffectType.MOVE)],
                )

        async it "responds to old multizone":
            zones = [
                chp.Color(0, 0, 0, 0),
                chp.Color(1, 0.1, 0.1, 3500),
                chp.Color(2, 0.2, 0.1, 3500),
                chp.Color(3, 0.2, 0.3, 3500),
                chp.Color(3, 0.2, 0.3, 3500),
                chp.Color(3, 0.2, 0.3, 3500),
                chp.Color(6, 0.6, 0.5, 3500),
                chp.Color(7, 0.6, 0.7, 3500),
                chp.Color(8, 0.8, 0.7, 3500),
                chp.Color(9, 0.8, 0.9, 3500),
                chp.Color(10, 1.0, 0.9, 3500),
            ]
            async with self.make_device(
                Products.LCM2_Z, chp.Firmware(2, 77, 1543215651000000000), zones
            ) as device:
                device.assertAttrs(zones_effect=MultiZoneEffectType.OFF, zones=zones)

                await device.assertResponse(
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=255),
                    [
                        MultiZoneMessages.StateMultiZone(
                            zones_count=11, zone_index=0, colors=zones[0:8]
                        ),
                        MultiZoneMessages.StateMultiZone(
                            zones_count=11, zone_index=8, colors=zones[8:]
                        ),
                    ],
                )

                await device.assertResponse(
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=13),
                    [
                        MultiZoneMessages.StateMultiZone(
                            zones_count=11, zone_index=0, colors=zones[0:8]
                        ),
                        MultiZoneMessages.StateMultiZone(
                            zones_count=11, zone_index=8, colors=zones[8:10]
                        ),
                    ],
                )

                await device.assertResponse(
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=0),
                    [
                        MultiZoneMessages.StateZone(
                            zones_count=100, zone_index=0, **zones[0].as_dict()
                        )
                    ],
                )

                await device.assertResponse(
                    MultiZoneMessages.SetColorZones(
                        start_index=7,
                        end_index=8,
                        hue=100,
                        saturation=0,
                        brightness=0.1,
                        kelvin=6500,
                    ),
                    [
                        MultiZoneMessages.StateMultiZone(
                            zones_count=11, zone_index=0, colors=zones[0:8]
                        ),
                        MultiZoneMessages.StateMultiZone(
                            zones_count=11, zone_index=8, colors=zones[8:]
                        ),
                    ],
                )

                zones[7] = chp.Color(100, 0, 0.1, 6500)
                zones[8] = chp.Color(100, 0, 0.1, 6500)
                await device.assertResponse(
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=255),
                    [
                        MultiZoneMessages.StateMultiZone(
                            zones_count=11, zone_index=0, colors=zones[0:8]
                        ),
                        MultiZoneMessages.StateMultiZone(
                            zones_count=11, zone_index=8, colors=zones[8:]
                        ),
                    ],
                )

        async it "responds to extended multizone":
            zones = [
                chp.Color(0, 0, 0, 0),
                chp.Color(1, 0.1, 0.1, 3500),
                chp.Color(2, 0.2, 0.1, 3500),
                chp.Color(3, 0.2, 0.3, 3500),
                chp.Color(3, 0.2, 0.3, 3500),
                chp.Color(3, 0.2, 0.3, 3500),
                chp.Color(6, 0.6, 0.5, 3500),
                chp.Color(7, 0.6, 0.7, 3500),
                chp.Color(8, 0.8, 0.7, 3500),
                chp.Color(9, 0.8, 0.9, 3500),
                chp.Color(10, 1.0, 0.9, 3500),
            ]

            async with self.make_device(
                Products.LCM2_Z, chp.Firmware(2, 77, 1543215651000000000), list(zones)
            ) as device:
                device.assertAttrs(zones_effect=MultiZoneEffectType.OFF, zones=zones)

                await device.assertResponse(
                    MultiZoneMessages.GetExtendedColorZones(),
                    [
                        MultiZoneMessages.StateExtendedColorZones(
                            zones_count=11, zone_index=0, colors_count=11, colors=zones
                        )
                    ],
                )

                new_colors = [
                    chp.Color(100, 0.2, 0.3, 9000),
                    chp.Color(200, 0.3, 0.4, 8000),
                    chp.Color(300, 0.5, 0.6, 7000),
                ]
                await device.assertResponse(
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
                await device.assertResponse(
                    MultiZoneMessages.GetExtendedColorZones(),
                    [
                        MultiZoneMessages.StateExtendedColorZones(
                            zones_count=11, zone_index=0, colors_count=11, colors=zones
                        )
                    ],
                )

    describe "ProductResponder":

        def make_device(self, product, firmware):
            device = Device(chp.ProductResponder.from_product(product, firmware))

            def assertProduct():
                device.assertAttrs(
                    product=product,
                    vendor_id=product.vendor.vid,
                    product_id=product.pid,
                    firmware=firmware,
                )

            return device, assertProduct

        async it "can determine the devices capability":
            device, assertProduct = self.make_device(
                Products.LCMV4_A19_COLOR, chp.Firmware(1, 23, 0)
            )
            async with device:
                assertProduct()

                cap = chp.ProductResponder.capability(device)
                assert isinstance(cap, Products.LCMV4_A19_COLOR.cap_kls)
                assert cap.firmware_major == 1
                assert cap.firmware_minor == 23

            device, assertProduct = self.make_device(Products.LCM3_TILE, chp.Firmware(3, 50, 0))
            async with device:
                assertProduct()

                cap = chp.ProductResponder.capability(device)
                assert isinstance(cap, Products.LCM3_TILE.cap_kls)
                assert cap.firmware_major == 3
                assert cap.firmware_minor == 50

        async it "responds to GetVersion":
            device, assertProduct = self.make_device(
                Products.LCMV4_A19_COLOR, chp.Firmware(1, 23, 0)
            )
            async with device:
                assertProduct()

                await device.assertResponse(
                    DeviceMessages.GetVersion(),
                    [DeviceMessages.StateVersion(vendor=1, product=22)],
                )

            device, assertProduct = self.make_device(Products.LCM3_TILE, chp.Firmware(3, 50, 0))
            async with device:
                assertProduct()
                await device.assertResponse(
                    DeviceMessages.GetVersion(),
                    [DeviceMessages.StateVersion(vendor=1, product=55)],
                )

        async it "responds to GetHostFirmware":
            device, assertProduct = self.make_device(
                Products.LCMV4_A19_COLOR, chp.Firmware(1, 23, 2, 100)
            )
            async with device:
                assertProduct()
                await device.assertResponse(
                    DeviceMessages.GetHostFirmware(),
                    [DeviceMessages.StateHostFirmware(build=2, version_major=1, version_minor=23)],
                )

            device, assertProduct = self.make_device(
                Products.LCM3_TILE, chp.Firmware(3, 50, 4, 400)
            )
            async with device:
                assertProduct()
                await device.assertResponse(
                    DeviceMessages.GetHostFirmware(),
                    [DeviceMessages.StateHostFirmware(build=4, version_major=3, version_minor=50)],
                )

        async it "responds to GetWifiFirmware":
            device, assertProduct = self.make_device(
                Products.LCMV4_A19_COLOR, chp.Firmware(1, 23, 2, 100)
            )
            async with device:
                assertProduct()
                await device.assertResponse(
                    DeviceMessages.GetWifiFirmware(),
                    [DeviceMessages.StateWifiFirmware(build=0, version_major=0, version_minor=0)],
                )

            device, assertProduct = self.make_device(
                Products.LCM3_TILE, chp.Firmware(3, 50, 4, 400)
            )
            async with device:
                assertProduct()
                await device.assertResponse(
                    DeviceMessages.GetWifiFirmware(),
                    [DeviceMessages.StateWifiFirmware(build=0, version_major=0, version_minor=0)],
                )

    describe "GroupingResponder":

        @pytest.fixture()
        async def device(self):
            device = Device(
                chp.GroupingResponder(
                    group_label="gl",
                    group_uuid="abcd",
                    group_updated_at=1,
                    location_label="ll",
                    location_uuid="efef",
                    location_updated_at=2,
                )
            )
            async with device:
                device.assertAttrs(
                    group_label="gl",
                    group_uuid="abcd",
                    group_updated_at=1,
                    location_label="ll",
                    location_uuid="efef",
                    location_updated_at=2,
                )
                yield device

        async it "responds to group", device:
            getter = DeviceMessages.GetGroup()
            state = DeviceMessages.StateGroup(group="abcd", label="gl", updated_at=1)
            await device.assertResponse(getter, [state])

            setter = DeviceMessages.SetGroup.create(group="dcba", label="gl2", updated_at=3)
            state = DeviceMessages.StateGroup(group=setter.group, label="gl2", updated_at=3)
            await device.assertResponse(
                setter, [state], group_label="gl2", group_uuid=setter.group, group_updated_at=3
            )
            await device.assertResponse(getter, [state])

        async it "responds to location", device:
            getter = DeviceMessages.GetLocation()
            state = DeviceMessages.StateLocation(location="efef", label="ll", updated_at=2)
            await device.assertResponse(getter, [state])

            setter = DeviceMessages.SetLocation.create(location="fefe", label="ll2", updated_at=6)
            state = DeviceMessages.StateLocation(
                location=setter.location, label="ll2", updated_at=6
            )
            await device.assertResponse(
                setter,
                [state],
                location_label="ll2",
                location_uuid=setter.location,
                location_updated_at=6,
            )
            await device.assertResponse(getter, [state])
