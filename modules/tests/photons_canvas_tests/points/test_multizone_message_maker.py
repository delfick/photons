import pytest
from photons_app import helpers as hp
from photons_canvas.points.simple_messages import MultizoneMessagesMaker
from photons_products import Products

devices = pytest.helpers.mimic()


devices.add("striplcm1")(
    "d073d5000003",
    Products.LCM1_Z,
    hp.Firmware(1, 22),
    value_store=dict(
        power=0,
        label="lcm1-no-extended",
        zones=[hp.Color(0, 0, 0, 0)] * 16,
    ),
)

devices.add("striplcm2noextended")(
    "d073d5000004",
    Products.LCM2_Z,
    hp.Firmware(2, 70),
    value_store=dict(
        power=0,
        label="lcm2-no-extended",
        zones=[hp.Color(0, 0, 0, 0)] * 16,
    ),
)

devices.add("striplcm2extended")(
    "d073d5000005",
    Products.LCM2_Z,
    hp.Firmware(2, 77),
    value_store=dict(
        power=0,
        label="lcm2-extended",
        zones=[hp.Color(0, 0, 0, 0)] * 16,
    ),
)


@pytest.fixture()
async def sender(final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


class TestSetZones:

    async def test_it_set_zones(self, sender):
        colors = [hp.Color(i, 1, 1, 3500) for i in range(16)]

        for strip in devices:
            await strip.change_one("zones", [hp.Color(0, 0, 0, 0)] * 16, event=None)
            maker = MultizoneMessagesMaker(
                strip.serial,
                strip.cap,
                [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors],
            )
            await sender(list(maker.msgs))

        for strip in devices:
            assert strip.attrs.zones == colors

    async def test_it_set_zones_from_a_different_start_zone(self, sender):
        colors = [hp.Color(i, 1, 1, 3500) for i in range(16)]

        for strip in devices:
            await strip.change_one("zones", [hp.Color(0, 0, 0, 0)] * 16, event=None)
            maker = MultizoneMessagesMaker(
                strip.serial,
                strip.cap,
                [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors],
                zone_index=2,
            )
            await sender(list(maker.msgs))

        for strip in devices:
            assert (
                strip.attrs.zones == [hp.Color(0, 0, 0, 0), hp.Color(0, 0, 0, 0)] + colors[:-2]
            ), strip
