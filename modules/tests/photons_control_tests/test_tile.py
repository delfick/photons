# coding: spec

from photons_control.tile import SetTileEffect, default_tile_palette
from photons_control import test_helpers as chp

from photons_app.errors import PhotonsAppError
from photons_transport.fake import FakeDevice

from photons_messages import DeviceMessages, LightMessages, TileMessages, TileEffectType
from photons_products import Products

from delfick_project.errors_pytest import assertRaises
import pytest


def convert(c):
    return chp.Color(c["hue"], c["saturation"], c["brightness"], c["kelvin"]).as_dict()


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

tiles = [tile1, tile2]
lights = [*tiles, nottile]


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner(lights) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


describe "Tile helpers":

    def compare_received(self, by_light):
        for light, msgs in by_light.items():
            assert light in lights
            light.compare_received(msgs, keep_duplicates=True)
            light.reset_received()

    describe "SetTileEffect":

        async it "complains if we have more than 16 colors in the palette", runner:
            with assertRaises(PhotonsAppError, "Palette can only be up to 16 colors", got=17):
                SetTileEffect("flame", palette=["red"] * 17)

        async it "can power on devices and set tile effect", runner:
            msg = SetTileEffect("flame")
            got = await runner.sender(msg, runner.serials)
            assert got == []

            for tile in tiles:
                assert tile.attrs.matrix_effect is TileEffectType.FLAME

            self.compare_received(
                {
                    nottile: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    tile1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        TileMessages.SetTileEffect.create(
                            type=TileEffectType.FLAME,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                    tile2: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        TileMessages.SetTileEffect.create(
                            type=TileEffectType.FLAME,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                }
            )

        async it "has options", runner:
            msg = SetTileEffect(
                "flame", speed=5, duration=10, power_on_duration=20, palette=["red", "green"]
            )
            got = await runner.sender(msg, runner.serials)
            assert got == []

            for tile in tiles:
                assert tile.attrs.matrix_effect is TileEffectType.FLAME

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
                        TileMessages.SetTileEffect.create(
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
                        TileMessages.SetTileEffect.create(
                            type=TileEffectType.FLAME,
                            duration=10,
                            speed=5,
                            palette=[convert(c) for c in palette],
                            palette_count=len(palette),
                        ),
                    ],
                }
            )

        async it "can choose not to turn on devices", runner:
            msg = SetTileEffect("morph", power_on=False)
            got = await runner.sender(msg, runner.serials)
            assert got == []

            for tile in tiles:
                assert tile.attrs.matrix_effect is TileEffectType.MORPH

            self.compare_received(
                {
                    nottile: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    tile1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        TileMessages.SetTileEffect.create(
                            type=TileEffectType.MORPH,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                    tile2: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        TileMessages.SetTileEffect.create(
                            type=TileEffectType.MORPH,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                }
            )

        async it "can target particular devices", runner:
            msg = SetTileEffect("morph", reference=tile1.serial)
            msg2 = SetTileEffect("flame", power_on=False, reference=tile2.serial)
            got = await runner.sender([msg, msg2])
            assert got == []

            assert tile1.attrs.matrix_effect is TileEffectType.MORPH
            assert tile2.attrs.matrix_effect is TileEffectType.FLAME

            self.compare_received(
                {
                    tile1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        TileMessages.SetTileEffect.create(
                            type=TileEffectType.MORPH,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                    tile2: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        TileMessages.SetTileEffect.create(
                            type=TileEffectType.FLAME,
                            palette=default_tile_palette,
                            palette_count=len(default_tile_palette),
                        ),
                    ],
                }
            )
