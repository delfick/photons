# coding: spec

import pytest
from photons_app import helpers as hp
from photons_app.special import FoundSerials
from photons_canvas.theme import ApplyTheme
from photons_products import Products

devices = pytest.helpers.mimic()

devices.add("bulb")(
    "d073d5000002",
    Products.LMB_MESH_A21,
    hp.Firmware(2, 2),
    value_store=dict(power=0, label="sam", infrared=0, color=hp.Color(0, 0, 0, 0)),
)

devices.add("tile")(
    "d073d5000001",
    Products.LCM3_TILE,
    hp.Firmware(3, 50),
    value_store=dict(
        power=0,
        label="bob",
        infrared=100,
        color=hp.Color(100, 0.5, 0.5, 4500),
    ),
)

devices.add("striplcm1")(
    "d073d5000003",
    Products.LCM1_Z,
    hp.Firmware(1, 22),
    value_store=dict(
        power=65535,
        label="lcm1-no-extended",
        zones=[hp.Color(0, 0, 0, 0) for i in range(20)],
    ),
)

devices.add("striplcm2noextended")(
    "d073d5000004",
    Products.LCM2_Z,
    hp.Firmware(2, 70),
    value_store=dict(
        power=0,
        label="lcm2-no-extended",
        zones=[hp.Color(0, 0, 0, 0) for i in range(30)],
    ),
)

devices.add("striplcm2extended")(
    "d073d5000005",
    Products.LCM2_Z,
    hp.Firmware(2, 77),
    value_store=dict(
        power=0,
        label="lcm2-extended",
        zones=[hp.Color(0, 0, 0, 0) for i in range(82)],
    ),
)


@pytest.fixture()
async def sender(final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture
def default_async_timeout() -> float:
    return 3


describe "ApplyTheme":

    async it "can apply a theme", async_timeout, sender:
        async_timeout.set_timeout_seconds(15)
        msg = ApplyTheme.msg({})
        await sender(msg, FoundSerials())

        for light in devices:
            assert light.attrs.power == 65535

        colors = [
            ("bulb", devices["bulb"].attrs.color),
            *[("striplcm1", c) for c in devices["striplcm1"].attrs.zones],
            *[("striplcm2noextended", c) for c in devices["striplcm2noextended"].attrs.zones],
            *[("striplcm2extended", c) for c in devices["striplcm2extended"].attrs.zones],
        ]
        for i, ch in enumerate(devices["tile"].attrs.chain):
            colors.extend([(("tile", i), c) for c in ch.colors])

        assert len(colors) == 1 + 20 + 30 + 82 + (64 * 5)

        non_zero_hues = []
        for index, (name, c) in enumerate(colors):
            if c.hue != 0:
                non_zero_hues.append(c.hue)
            assert c.saturation == 1, (index, name)
            assert c.brightness == hp.Color(0, 0, 0.3, 0).brightness, (index, name)
            assert c.kelvin == 3500, (index, name)

        assert len(non_zero_hues) > 200

    async it "can have options", async_timeout, sender:
        async_timeout.set_timeout_seconds(15)
        msg = ApplyTheme.msg({"power_on": False, "overrides": {"saturation": 0.2}})
        await sender(msg, FoundSerials())

        for light in devices:
            if light is devices["striplcm1"]:
                assert light.attrs.power == 65535
            else:
                assert light.attrs.power == 0

        colors = [
            devices["bulb"].attrs.color,
            *devices["striplcm1"].attrs.zones,
            *devices["striplcm2noextended"].attrs.zones,
            *devices["striplcm2extended"].attrs.zones,
        ]
        for ch in devices["tile"].attrs.chain:
            colors.extend(ch.colors)

        assert len(colors) == 1 + 20 + 30 + 82 + (64 * 5)

        non_zero_hues = []
        for c in colors:
            if c.hue != 0:
                non_zero_hues.append(c.hue)
            assert c.saturation == hp.Color(0, 0.2, 0, 0).saturation
            assert c.brightness == hp.Color(0, 0, 0.3, 0).brightness
            assert c.kelvin == 3500

        assert len(non_zero_hues) > 200
