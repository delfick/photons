import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_control.tile import SetTileEffect, default_tile_palette
from photons_messages import (
    DeviceMessages,
    DiscoveryMessages,
    LightMessages,
    TileEffectType,
    TileMessages,
)
from photons_products import Products


def convert(c):
    return hp.Color(c["hue"], c["saturation"], c["brightness"], c["kelvin"]).as_dict()


default_tile_palette = [convert(c) for c in default_tile_palette]

devices = pytest.helpers.mimic()

tile1 = devices.add("tile1")("d073d5000001", Products.LCM3_TILE, hp.Firmware(3, 50))
tile2 = devices.add("tile2")("d073d5000002", Products.LCM3_TILE, hp.Firmware(3, 50))

nottile = devices.add("nottile")("d073d5000003", Products.LMB_MESH_A21, hp.Firmware(2, 2))

tiles = [tile1, tile2]


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
    sender.gatherer.clear_cache()


class TestTileHelpers:

    def compare_received(self, by_light):
        for light, msgs in by_light.items():
            assert light in devices
            devices.store(light).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(light).clear()

    class TestSetTileEffect:

        async def test_it_complains_if_we_have_more_than_16_colors_in_the_palette(self):
            with assertRaises(PhotonsAppError, "Palette can only be up to 16 colors", got=17):
                SetTileEffect("flame", palette=["red"] * 17)

        async def test_it_can_power_on_devices_and_set_tile_effect(self, sender):
            msg = SetTileEffect("flame")
            got = await sender(msg, devices.serials)
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

        async def test_it_has_options(self, sender):
            msg = SetTileEffect(
                "flame", speed=5, duration=10, power_on_duration=20, palette=["red", "green"]
            )
            got = await sender(msg, devices.serials)
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

        async def test_it_can_choose_not_to_turn_on_devices(self, sender):
            msg = SetTileEffect("morph", power_on=False)
            got = await sender(msg, devices.serials)
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

        async def test_it_can_target_particular_devices(self, sender):
            msg = SetTileEffect("morph", reference=tile1.serial)
            msg2 = SetTileEffect("flame", power_on=False, reference=tile2.serial)
            got = await sender([msg, msg2])
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
