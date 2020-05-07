# coding: spec

from photons_canvas.points.simple_messages import MultizoneMessagesMaker

from photons_control import test_helpers as chp
from photons_transport.fake import FakeDevice
from photons_products import Products

import pytest


striplcm1 = FakeDevice(
    "d073d5000003",
    chp.default_responders(
        Products.LCM1_Z,
        power=0,
        label="lcm1-no-extended",
        zones=[chp.Color(0, 0, 0, 0)] * 16,
        firmware=chp.Firmware(1, 22, 1502237570000000000),
    ),
)

striplcm2noextended = FakeDevice(
    "d073d5000004",
    chp.default_responders(
        Products.LCM2_Z,
        power=0,
        label="lcm2-no-extended",
        zones=[chp.Color(0, 0, 0, 0)] * 16,
        firmware=chp.Firmware(2, 70, 1508122125000000000),
    ),
)

striplcm2extended = FakeDevice(
    "d073d5000005",
    chp.default_responders(
        Products.LCM2_Z,
        power=0,
        label="lcm2-extended",
        zones=[chp.Color(0, 0, 0, 0)] * 16,
        firmware=chp.Firmware(2, 77, 1543215651000000000),
    ),
)

strips = [striplcm1, striplcm2extended, striplcm2noextended]


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner(strips) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


describe "SetZones":

    async it "set zones", runner:
        colors = [chp.Color(i, 1, 1, 3500) for i in range(16)]

        for strip in strips:
            strip.attrs.zones = [chp.Color(0, 0, 0, 0)] * 16
            cap = chp.ProductResponder.capability(strip)
            maker = MultizoneMessagesMaker(
                strip.serial, cap, [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors]
            )
            await runner.sender(list(maker.msgs))

        for strip in strips:
            assert strip.attrs.zones == colors

    async it "set zones from a different start zone", runner:
        colors = [chp.Color(i, 1, 1, 3500) for i in range(16)]

        for strip in strips:
            strip.attrs.zones = [chp.Color(0, 0, 0, 0)] * 16
            cap = chp.ProductResponder.capability(strip)
            maker = MultizoneMessagesMaker(
                strip.serial,
                cap,
                [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors],
                zone_index=2,
            )
            await runner.sender(list(maker.msgs))

        for strip in strips:
            assert (
                strip.attrs.zones == [chp.Color(0, 0, 0, 0), chp.Color(0, 0, 0, 0)] + colors[:-2]
            ), strip
