# coding: spec

from photons_control.tile import SetTileEffect, default_tile_palette
from photons_control import test_helpers as chp
from photons_control.planner import Gatherer

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut
from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_transport.fake import FakeDevice
from photons_colour import Parser

from photons_messages import DeviceMessages, LightMessages, TileMessages, TileEffectType
from photons_products import Products

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import uuid


def convert(c):
    c2 = {}
    c2["hue"] = int(c["hue"] / 360 * 65535) / 65535 * 360
    c2["saturation"] = int(c["saturation"] * 65535) / 65535
    c2["brightness"] = int(c["brightness"] * 65535) / 65535
    c2["kelvin"] = c["kelvin"]
    return c2


default_tile_palette = [convert(c) for c in default_tile_palette]

tile1 = FakeDevice(
    "d073d5000001",
    chp.default_responders(
        Products.LCM3_TILE, firmware_build=1548977726000000000, firmware_major=3, firmware_minor=50
    ),
)

tile2 = FakeDevice(
    "d073d5000002",
    chp.default_responders(
        Products.LCM3_TILE, firmware_build=1548977726000000000, firmware_major=3, firmware_minor=50
    ),
)

nottile = FakeDevice(
    "d073d5000003",
    chp.default_responders(
        Products.LMB_MESH_A21,
        firmware_build=1448861477000000000,
        firmware_major=2,
        firmware_minor=2,
    ),
)

lights = [tile1, tile2, nottile]
mlr = chp.ModuleLevelRunner(lights)

setup_module = mlr.setUp
teardown_module = mlr.tearDown

describe AsyncTestCase, "Tile helpers":
    use_default_loop = True

    async before_each:
        self.maxDiff = None
        self.tiles = [tile1, tile2]

    def compare_received(self, by_light):
        for light, msgs in by_light.items():
            assert light in lights
            light.compare_received(msgs, keep_duplicates=True)
            light.reset_received()

    describe "SetTileEffect":

        @mlr.test
        async it "complains if we have more than 16 colors in the palette", runner:
            with self.fuzzyAssertRaisesError(
                PhotonsAppError, "Palette can only be up to 16 colors", got=17
            ):
                SetTileEffect("flame", palette=["red"] * 17)

        @mlr.test
        async it "can power on devices and set tile effect", runner:
            msg = SetTileEffect("flame")
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            for tile in self.tiles:
                self.assertIs(tile.attrs.matrix_effect, TileEffectType.FLAME)

            self.compare_received(
                {
                    nottile: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    tile1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        TileMessages.SetTileEffect.empty_normalise(
                            type=TileEffectType.FLAME,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                    tile2: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        TileMessages.SetTileEffect.empty_normalise(
                            type=TileEffectType.FLAME,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                }
            )

        @mlr.test
        async it "has options", runner:
            msg = SetTileEffect(
                "flame", speed=5, duration=10, power_on_duration=20, palette=["red", "green"]
            )
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            for tile in self.tiles:
                self.assertIs(tile.attrs.matrix_effect, TileEffectType.FLAME)

            palette = [
                {"hue": 0, "saturation": 1, "brightness": 1, "kelvin": 3500},
                {"hue": 120, "saturation": 1, "brightness": 1, "kelvin": 3500},
            ]

            self.compare_received(
                {
                    nottile: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    tile1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=20),
                        TileMessages.SetTileEffect.empty_normalise(
                            type=TileEffectType.FLAME,
                            duration=10,
                            speed=5,
                            palette=[convert(c) for c in palette],
                            palette_count=len(palette),
                        ),
                    ],
                    tile2: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=20),
                        TileMessages.SetTileEffect.empty_normalise(
                            type=TileEffectType.FLAME,
                            duration=10,
                            speed=5,
                            palette=[convert(c) for c in palette],
                            palette_count=len(palette),
                        ),
                    ],
                }
            )

        @mlr.test
        async it "can choose not to turn on devices", runner:
            msg = SetTileEffect("morph", power_on=False)
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            for tile in self.tiles:
                self.assertIs(tile.attrs.matrix_effect, TileEffectType.MORPH)

            self.compare_received(
                {
                    nottile: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    tile1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        TileMessages.SetTileEffect.empty_normalise(
                            type=TileEffectType.MORPH,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                    tile2: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        TileMessages.SetTileEffect.empty_normalise(
                            type=TileEffectType.MORPH,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                }
            )

        @mlr.test
        async it "can target particular devices", runner:
            msg = SetTileEffect("morph", reference=tile1.serial)
            msg2 = SetTileEffect("flame", power_on=False, reference=tile2.serial)
            got = await runner.target.script([msg, msg2]).run_with_all(None)
            self.assertEqual(got, [])

            self.assertIs(tile1.attrs.matrix_effect, TileEffectType.MORPH)
            self.assertIs(tile2.attrs.matrix_effect, TileEffectType.FLAME)

            self.compare_received(
                {
                    tile1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        TileMessages.SetTileEffect.empty_normalise(
                            type=TileEffectType.MORPH,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                    tile2: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        TileMessages.SetTileEffect.empty_normalise(
                            type=TileEffectType.FLAME,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                }
            )
