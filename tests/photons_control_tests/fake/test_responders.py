# coding: spec

from photons_control import test_helpers as chp

from photons_app.test_helpers import AsyncTestCase, print_packet_difference
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

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp

describe AsyncTestCase, "Responders":

    def assertAttrs(self, **attrs):
        for key, val in attrs.items():
            self.assertEqual(self.device.attrs[key], val)

    async def assertResponse(self, pkt, expected, **expected_attrs):
        got = await self.device.make_response(pkt, "udp")
        if got is None:
            self.assertEqual(expected, [])
        else:
            if expected is True:
                self.assertGreater(len(got), 0)
            else:
                self.assertEqual(len(got), len(expected), got)

                different = False
                for g, e in zip(got, expected):
                    if e | TileMessages.StateTileEffect and g | TileMessages.StateTileEffect:
                        e.instanceid = g.instanceid
                    if g != e:
                        dfferent = print_packet_difference(g, e, ignore_unspecified_expected=True)

                    # Make sure message can be packed
                    g.source = 1
                    g.sequence = 1
                    g.target = None
                    g.pack()

                assert not different, got

        for key, val in expected_attrs.items():
            self.assertEqual(self.device.attrs[key], val)

    describe "LightStateResponder":
        async before_each:
            self.device = FakeDevice("d073d5000001", [chp.LightStateResponder()])
            await self.device.start()
            self.assertAttrs(label="", power=0, color=chp.Color(0, 0, 1, 3500))

        async it "responds to label messages":
            await self.assertResponse(
                DeviceMessages.GetLabel(), [DeviceMessages.StateLabel(label="")]
            )
            await self.assertResponse(
                DeviceMessages.SetLabel(label="sam"),
                [DeviceMessages.StateLabel(label="sam")],
                label="sam",
            )
            await self.assertResponse(
                DeviceMessages.GetLabel(), [DeviceMessages.StateLabel(label="sam")], label="sam"
            )

        async it "responds to power messages":
            await self.assertResponse(
                DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=0)]
            )
            await self.assertResponse(
                DeviceMessages.SetPower(level=200), [DeviceMessages.StatePower(level=0)], power=200
            )
            await self.assertResponse(
                DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=200)], power=200
            )

        async it "responds to light power messages":
            await self.assertResponse(
                DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=0)]
            )
            await self.assertResponse(
                LightMessages.SetLightPower(level=200),
                [LightMessages.StateLightPower(level=0)],
                power=200,
            )
            await self.assertResponse(
                DeviceMessages.GetPower(), [DeviceMessages.StatePower(level=200)], power=200
            )

        async it "responds to Color messages":

            def light_state(label, power, hue, saturation, brightness, kelvin):
                return LightMessages.LightState.empty_normalise(
                    label=label,
                    power=power,
                    hue=hue,
                    saturation=saturation,
                    brightness=brightness,
                    kelvin=kelvin,
                )

            await self.assertResponse(LightMessages.GetColor(), [light_state("", 0, 0, 0, 1, 3500)])

            await self.assertResponse(
                DeviceMessages.SetLabel(label="bob"),
                [DeviceMessages.StateLabel(label="bob")],
                label="bob",
            )
            await self.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 0, 0, 0, 1, 3500)]
            )

            await self.assertResponse(
                DeviceMessages.SetPower(level=300), [DeviceMessages.StatePower(level=0)], power=300
            )
            await self.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 0, 0, 1, 3500)]
            )

            await self.assertResponse(
                LightMessages.SetColor(hue=100, saturation=0.5, brightness=0.5, kelvin=4500),
                [light_state("bob", 300, 0, 0, 1, 3500)],
            )
            await self.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 100, 0.5, 0.5, 4500)]
            )

            await self.assertResponse(
                LightMessages.SetWaveform(
                    hue=200, saturation=0.6, brightness=0.4, kelvin=9000, waveform=Waveform.SAW
                ),
                [light_state("bob", 300, 100, 0.5, 0.5, 4500)],
            )
            await self.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 200, 0.6, 0.4, 9000)]
            )

            await self.assertResponse(
                LightMessages.SetWaveformOptional(hue=333),
                [light_state("bob", 300, 200, 0.6, 0.4, 9000)],
            )
            await self.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 333, 0.6, 0.4, 9000)]
            )

            await self.assertResponse(
                LightMessages.SetWaveformOptional(saturation=0),
                [light_state("bob", 300, 333, 0.6, 0.4, 9000)],
            )
            await self.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 0.4, 9000)]
            )

            await self.assertResponse(
                LightMessages.SetWaveformOptional(brightness=1),
                [light_state("bob", 300, 333, 0, 0.4, 9000)],
            )
            await self.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 1, 9000)]
            )

            await self.assertResponse(
                LightMessages.SetWaveformOptional(kelvin=6789),
                [light_state("bob", 300, 333, 0, 1, 9000)],
            )
            await self.assertResponse(
                LightMessages.GetColor(), [light_state("bob", 300, 333, 0, 1, 6789)]
            )

    describe "InfraredResponder":
        async before_each:
            self.device = FakeDevice(
                "d073d5000001",
                [
                    chp.ProductResponder.from_product(Products.LCM2_A19_PLUS),
                    chp.InfraredResponder(),
                ],
            )
            await self.device.start()
            self.assertAttrs(infrared=0)

        async it "responds to infrared messages":
            await self.assertResponse(
                LightMessages.GetInfrared(), [LightMessages.StateInfrared(brightness=0)]
            )
            await self.assertResponse(
                LightMessages.SetInfrared(brightness=100),
                [LightMessages.StateInfrared(brightness=0)],
                infrared=100,
            )
            await self.assertResponse(
                LightMessages.GetInfrared(),
                [LightMessages.StateInfrared(brightness=100)],
                infrared=100,
            )

        async it "doesn't respond to infrared if the product doesn't have infrared":
            self.device = FakeDevice(
                "d073d5000001",
                [chp.ProductResponder.from_product(Products.LCM2_A19), chp.InfraredResponder()],
            )
            await self.device.start()
            assert "infrared" not in self.device.attrs

            await self.assertResponse(LightMessages.GetInfrared(), [])
            await self.assertResponse(LightMessages.SetInfrared(brightness=100), [])

        async it "does respond to infrared if the product doesn't have infrared but is LCM3":
            self.device = FakeDevice(
                "d073d5000001",
                [chp.ProductResponder.from_product(Products.LCM3_TILE), chp.InfraredResponder()],
            )
            await self.device.start()
            assert "infrared" in self.device.attrs

            await self.assertResponse(
                LightMessages.GetInfrared(), [LightMessages.StateInfrared(brightness=0)]
            )
            await self.assertResponse(
                LightMessages.SetInfrared(brightness=100),
                [LightMessages.StateInfrared(brightness=0)],
                infrared=100,
            )
            await self.assertResponse(
                LightMessages.GetInfrared(),
                [LightMessages.StateInfrared(brightness=100)],
                infrared=100,
            )

    describe "MatrixResponder":
        async before_each:
            self.device = FakeDevice(
                "d073d5000001",
                [chp.ProductResponder.from_product(Products.LCM3_TILE), chp.MatrixResponder()],
            )
            await self.device.start()
            self.assertAttrs(matrix_effect=TileEffectType.OFF)

        async it "responds to tile effect messages":
            await self.assertResponse(
                TileMessages.GetTileEffect(),
                [
                    TileMessages.StateTileEffect.empty_normalise(
                        type=TileEffectType.OFF, palette_count=0, parameters={}
                    )
                ],
            )
            await self.assertResponse(
                TileMessages.SetTileEffect(
                    type=TileEffectType.FLAME, palette_count=1, palette=[chp.Color(1, 0, 1, 3500)]
                ),
                [
                    TileMessages.StateTileEffect.empty_normalise(
                        type=TileEffectType.OFF, palette_count=0, parameters={}, palette=[]
                    )
                ],
                matrix_effect=TileEffectType.FLAME,
            )
            await self.assertResponse(
                TileMessages.GetTileEffect(),
                [
                    TileMessages.StateTileEffect.empty_normalise(
                        type=TileEffectType.FLAME,
                        palette_count=1,
                        parameters={},
                        palette=[chp.Color(1, 0, 1, 3500)] + [chp.Color(0, 0, 0, 0)] * 15,
                    )
                ],
                matrix_effect=TileEffectType.FLAME,
            )

        async it "doesn't respond to tile messages if the product doesn't have chain":
            self.device = FakeDevice(
                "d073d5000001",
                [
                    chp.ProductResponder.from_product(Products.LCMV4_A19_COLOR),
                    chp.MatrixResponder(),
                ],
            )
            await self.device.start()
            assert "matrix_effect" not in self.device.attrs

            await self.assertResponse(TileMessages.GetTileEffect(), [])
            await self.assertResponse(
                TileMessages.SetTileEffect.empty_normalise(
                    type=TileEffectType.FLAME, parameters={}, palette=[chp.Color(0, 0, 0, 3500)]
                ),
                [],
            )

    describe "ZonesResponder":

        async def make_device(self, enum, firmware, zones=None):
            self.device = FakeDevice(
                "d073d5000001",
                [
                    chp.ProductResponder.from_product(enum, firmware),
                    chp.ZonesResponder(zones=zones),
                ],
            )
            await self.device.start()
            if zones is not None:
                self.assertAttrs(zones_effect=MultiZoneEffectType.OFF, zones=zones)
            else:
                assert "zones_effect" not in self.device.attrs
                assert "zones" not in self.device.attrs

        async it "complains if you try to set too many zones":
            zones = [chp.Color(0, 0, 0, 0)] * 83
            with self.fuzzyAssertRaisesError(PhotonsAppError, "Can only have up to 82 zones!"):
                await self.make_device(Products.LCM1_Z, chp.Firmware(0, 0, 0), zones)

        async it "doesn't respond if we aren't a multizone device":
            await self.make_device(Products.LCMV4_A19_COLOR, chp.Firmware(0, 0, 0))

            await self.assertResponse(MultiZoneMessages.GetMultiZoneEffect(), [])
            await self.assertResponse(
                MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                    type=MultiZoneEffectType.MOVE, parameters={}
                ),
                [],
            )

            await self.assertResponse(
                MultiZoneMessages.GetColorZones(start_index=0, end_index=255), []
            )
            await self.assertResponse(
                MultiZoneMessages.SetColorZones(
                    start_index=0, end_index=1, hue=0, saturation=1, brightness=1, kelvin=3500
                ),
                [],
            )

            await self.assertResponse(MultiZoneMessages.GetExtendedColorZones(), [])
            await self.assertResponse(
                MultiZoneMessages.SetExtendedColorZones(colors=[chp.Color(0, 0, 0, 0)]), []
            )

        async it "doesn't respond to extended multizone if we aren't extended multizone":
            cases = [
                (Products.LCM1_Z, chp.Firmware(0, 0, 0), [chp.Color(0, 0, 0, 0)]),
                (Products.LCM2_Z, chp.Firmware(0, 0, 0), [chp.Color(0, 0, 0, 0)]),
            ]

            for case in cases:
                await self.make_device(*case)

                await self.assertResponse(MultiZoneMessages.GetMultiZoneEffect(), True)
                await self.assertResponse(
                    MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                        type=MultiZoneEffectType.MOVE, parameters={}
                    ),
                    True,
                )

                await self.assertResponse(
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=255), True
                )
                await self.assertResponse(
                    MultiZoneMessages.SetColorZones(
                        start_index=0, end_index=1, hue=0, saturation=1, brightness=1, kelvin=3500
                    ),
                    True,
                )

                await self.assertResponse(MultiZoneMessages.GetExtendedColorZones(), [])
                await self.assertResponse(
                    MultiZoneMessages.SetExtendedColorZones(colors=[chp.Color(0, 0, 0, 0)]), []
                )

        async it "responds to all messages if we have extended multizone":
            await self.make_device(
                Products.LCM2_Z, chp.Firmware(2, 77, 1543215651000000000), [chp.Color(0, 0, 0, 0)]
            )

            await self.assertResponse(MultiZoneMessages.GetMultiZoneEffect(), True)
            await self.assertResponse(
                MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                    type=MultiZoneEffectType.MOVE, parameters={}
                ),
                True,
            )

            await self.assertResponse(
                MultiZoneMessages.GetColorZones(start_index=0, end_index=255), True
            )
            await self.assertResponse(
                MultiZoneMessages.SetColorZones(
                    start_index=0, end_index=1, hue=0, saturation=1, brightness=1, kelvin=3500
                ),
                True,
            )

            await self.assertResponse(MultiZoneMessages.GetExtendedColorZones(), True)
            await self.assertResponse(
                MultiZoneMessages.SetExtendedColorZones(
                    colors_count=1, zone_index=0, colors=[chp.Color(0, 0, 0, 0)]
                ),
                True,
            )

        async it "responds to effect messages":
            await self.make_device(
                Products.LCM2_Z, chp.Firmware(2, 77, 1543215651000000000), [chp.Color(0, 0, 0, 0)]
            )

            await self.assertResponse(
                MultiZoneMessages.GetMultiZoneEffect(),
                [MultiZoneMessages.StateMultiZoneEffect(type=MultiZoneEffectType.OFF)],
            )
            await self.assertResponse(
                MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                    type=MultiZoneEffectType.MOVE, parameters={}
                ),
                [MultiZoneMessages.StateMultiZoneEffect(type=MultiZoneEffectType.OFF)],
                zones_effect=MultiZoneEffectType.MOVE,
            )
            await self.assertResponse(
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
            await self.make_device(Products.LCM2_Z, chp.Firmware(2, 77, 1543215651000000000), zones)

            await self.assertResponse(
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
            await self.assertResponse(
                MultiZoneMessages.SetColorZones(
                    start_index=7, end_index=8, hue=100, saturation=0, brightness=0.1, kelvin=6500
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
            await self.assertResponse(
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
            await self.make_device(
                Products.LCM2_Z, chp.Firmware(2, 77, 1543215651000000000), list(zones)
            )

            await self.assertResponse(
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
            await self.assertResponse(
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
            await self.assertResponse(
                MultiZoneMessages.GetExtendedColorZones(),
                [
                    MultiZoneMessages.StateExtendedColorZones(
                        zones_count=11, zone_index=0, colors_count=11, colors=zones
                    )
                ],
            )

    describe "ProductResponder":

        async def make_device(self, product, firmware):
            self.device = FakeDevice(
                "d073d5000001", [chp.ProductResponder.from_product(product, firmware)]
            )
            await self.device.start()
            self.assertAttrs(
                product=product,
                vendor_id=product.vendor.vid,
                product_id=product.pid,
                firmware=firmware,
            )

        async it "can determine the devices capability":
            await self.make_device(Products.LCMV4_A19_COLOR, chp.Firmware(1, 23, 0))
            cap = chp.ProductResponder.capability(self.device)
            self.assertIsInstance(cap, Products.LCMV4_A19_COLOR.cap_kls)
            self.assertEqual(cap.firmware_major, 1)
            self.assertEqual(cap.firmware_minor, 23)

            await self.make_device(Products.LCM3_TILE, chp.Firmware(3, 50, 0))
            cap = chp.ProductResponder.capability(self.device)
            self.assertIsInstance(cap, Products.LCM3_TILE.cap_kls)
            self.assertEqual(cap.firmware_major, 3)
            self.assertEqual(cap.firmware_minor, 50)

        async it "responds to GetVersion":
            await self.make_device(Products.LCMV4_A19_COLOR, chp.Firmware(1, 23, 0))
            await self.assertResponse(
                DeviceMessages.GetVersion(),
                [DeviceMessages.StateVersion(vendor=1, product=22, version=0)],
            )

            await self.make_device(Products.LCM3_TILE, chp.Firmware(3, 50, 0))
            await self.assertResponse(
                DeviceMessages.GetVersion(),
                [DeviceMessages.StateVersion(vendor=1, product=55, version=0)],
            )

        async it "responds to GetHostFirmware":
            await self.make_device(Products.LCMV4_A19_COLOR, chp.Firmware(1, 23, 2, 100))
            await self.assertResponse(
                DeviceMessages.GetHostFirmware(),
                [DeviceMessages.StateHostFirmware(build=2, version_major=1, version_minor=23)],
            )

            await self.make_device(Products.LCM3_TILE, chp.Firmware(3, 50, 4, 400))
            await self.assertResponse(
                DeviceMessages.GetHostFirmware(),
                [DeviceMessages.StateHostFirmware(build=4, version_major=3, version_minor=50)],
            )

        async it "responds to GetWifiFirmware":
            await self.make_device(Products.LCMV4_A19_COLOR, chp.Firmware(1, 23, 2, 100))
            await self.assertResponse(
                DeviceMessages.GetWifiFirmware(),
                [DeviceMessages.StateWifiFirmware(build=0, version_major=0, version_minor=0)],
            )

            await self.make_device(Products.LCM3_TILE, chp.Firmware(3, 50, 4, 400))
            await self.assertResponse(
                DeviceMessages.GetWifiFirmware(),
                [DeviceMessages.StateWifiFirmware(build=0, version_major=0, version_minor=0)],
            )
