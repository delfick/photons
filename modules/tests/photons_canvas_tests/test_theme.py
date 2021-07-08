# coding: spec

from photons_canvas.theme import ApplyTheme

from photons_app.special import FoundSerials
from photons_app import helpers as hp

from photons_control import test_helpers as chp
from photons_transport.fake import FakeDevice
from photons_products import Products

import pytest

bulb = FakeDevice(
    "d073d5000002",
    chp.default_responders(
        Products.LMB_MESH_A21,
        power=0,
        label="sam",
        infrared=0,
        color=hp.Color(0, 0, 0, 0),
        firmware=hp.Firmware(2, 2),
    ),
)


tile = FakeDevice(
    "d073d5000001",
    chp.default_responders(
        Products.LCM3_TILE,
        power=0,
        label="bob",
        infrared=100,
        color=hp.Color(100, 0.5, 0.5, 4500),
        firmware=hp.Firmware(3, 50),
    ),
)

striplcm1 = FakeDevice(
    "d073d5000003",
    chp.default_responders(
        Products.LCM1_Z,
        power=65535,
        label="lcm1-no-extended",
        firmware=hp.Firmware(1, 22),
        zones=[hp.Color(0, 0, 0, 0) for i in range(20)],
    ),
)

striplcm2noextended = FakeDevice(
    "d073d5000004",
    chp.default_responders(
        Products.LCM2_Z,
        power=0,
        label="lcm2-no-extended",
        firmware=hp.Firmware(2, 70),
        zones=[hp.Color(0, 0, 0, 0) for i in range(30)],
    ),
)

striplcm2extended = FakeDevice(
    "d073d5000005",
    chp.default_responders(
        Products.LCM2_Z,
        power=0,
        label="lcm2-extended",
        firmware=hp.Firmware(2, 77),
        zones=[hp.Color(0, 0, 0, 0) for i in range(82)],
    ),
)

lights = [bulb, tile, striplcm1, striplcm2noextended, striplcm2extended]


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner(lights) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


@pytest.fixture(autouse=True)
def set_async_timeout(request):
    request.applymarker(pytest.mark.async_timeout(3))


describe "ApplyTheme":

    async it "can apply a theme", runner:
        msg = ApplyTheme.msg({})
        await runner.sender(msg, FoundSerials())

        for light in lights:
            assert light.attrs.power == 65535

        colors = [
            bulb.attrs.color,
            *striplcm1.attrs.zones,
            *striplcm2noextended.attrs.zones,
            *striplcm2extended.attrs.zones,
        ]
        for _, cs in tile.attrs.chain:
            colors.extend(cs)

        assert len(colors) == 1 + 20 + 30 + 82 + (64 * 5)

        non_zero_hues = []
        for c in colors:
            if c.hue != 0:
                non_zero_hues.append(c.hue)
            assert c.saturation == 1
            assert c.brightness == hp.Color(0, 0, 0.3, 0).brightness
            assert c.kelvin == 3500

        assert len(non_zero_hues) > 200

    async it "can have options", runner:
        msg = ApplyTheme.msg({"power_on": False, "overrides": {"saturation": 0.2}})
        await runner.sender(msg, FoundSerials())

        for light in lights:
            if light is striplcm1:
                assert light.attrs.power == 65535
            else:
                assert light.attrs.power == 0

        colors = [
            bulb.attrs.color,
            *striplcm1.attrs.zones,
            *striplcm2noextended.attrs.zones,
            *striplcm2extended.attrs.zones,
        ]
        for _, cs in tile.attrs.chain:
            colors.extend(cs)

        assert len(colors) == 1 + 20 + 30 + 82 + (64 * 5)

        non_zero_hues = []
        for c in colors:
            if c.hue != 0:
                non_zero_hues.append(c.hue)
            assert c.saturation == hp.Color(0, 0.2, 0, 0).saturation
            assert c.brightness == hp.Color(0, 0, 0.3, 0).brightness
            assert c.kelvin == 3500

        assert len(non_zero_hues) > 200
