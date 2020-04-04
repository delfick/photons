# coding: spec

from photons_control.multizone import (
    find_multizone,
    zones_from_reference,
    SetZonesPlan,
    SetZones,
    SetZonesEffect,
)
from photons_control.planner import Skip, NoMessages
from photons_control import test_helpers as chp

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut
from photons_colour import Parser

from photons_messages import DeviceMessages, LightMessages, MultiZoneMessages, MultiZoneEffectType
from photons_products.registry import Capability
from photons_transport.fake import FakeDevice
from photons_products import Products

from delfick_project.errors_pytest import assertRaises
import pytest
import uuid


zeroColor = chp.Color(0, 0, 0, 3500)
zones1 = [chp.Color(i, 1, 1, 3500) for i in range(30)]
zones2 = [chp.Color(90 - i, 1, 1, 3500) for i in range(6)]
zones3 = [chp.Color(300 - i, 1, 1, 3500) for i in range(16)]

light1 = FakeDevice(
    "d073d5000001",
    chp.default_responders(
        Products.LCM3_TILE,
        power=0,
        label="bob",
        infrared=100,
        color=chp.Color(100, 0.5, 0.5, 4500),
        firmware=chp.Firmware(3, 50, 1548977726000000000),
    ),
)

light2 = FakeDevice(
    "d073d5000002",
    chp.default_responders(
        Products.LMB_MESH_A21,
        power=65535,
        label="sam",
        infrared=0,
        color=chp.Color(200, 0.3, 1, 9000),
        firmware=chp.Firmware(2, 2, 1448861477000000000),
    ),
)

striplcm1 = FakeDevice(
    "d073d5000003",
    chp.default_responders(
        Products.LCM1_Z,
        power=0,
        label="lcm1-no-extended",
        firmware=chp.Firmware(1, 22, 1502237570000000000),
        zones=zones1,
    ),
)

striplcm2noextended = FakeDevice(
    "d073d5000004",
    chp.default_responders(
        Products.LCM2_Z,
        power=0,
        label="lcm2-no-extended",
        firmware=chp.Firmware(2, 70, 1508122125000000000),
        zones=zones2,
    ),
)

striplcm2extended = FakeDevice(
    "d073d5000005",
    chp.default_responders(
        Products.LCM2_Z,
        power=0,
        label="lcm2-extended",
        firmware=chp.Firmware(2, 77, 1543215651000000000),
        zones=zones3,
    ),
)

strips = [striplcm1, striplcm2extended, striplcm2noextended]
lights = [light1, light2, *strips]


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner(lights) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


describe "SetZonesPlan":

    @pytest.fixture()
    def specifier(self):
        return [
            ["red", 10],
            ["blue", 3],
            ["hue:78 brightness:0.5", 5],
            ["#234455", 2],
            [[100], 1],
            [[100, 0.5], 1],
            [[100, 0.5, 0.5], 1],
            [[100, 0.5, 0.5, 9000], 1],
            [[0, 0, 0, 0], 1],
            [{"hue": 100}, 1],
            [{"hue": 100, "saturation": 0.5}, 1],
            [{"hue": 100, "saturation": 0.5, "brightness": 0.5}, 1],
            [{"hue": 100, "saturation": 0.5, "brightness": 0.5, "kelvin": 9000}, 1],
            [{"hue": 0, "saturation": 0, "brightness": 0, "kelvin": 0}, 1],
        ]

    async it "works out old style and extended style messages", specifier:
        plan = SetZonesPlan(specifier)

        assert all(msg | MultiZoneMessages.SetColorZones for msg in plan.set_color_old)
        assert plan.set_color_new | MultiZoneMessages.SetExtendedColorZones

        colorRed = chp.Color(0, 1, 1, 3500)
        colorBlue = chp.Color(250, 1, 1, 3500)
        colorHSBK = chp.Color(78, 0, 0.5, 3500)
        colorHEX = chp.Color(200.39917601281758, 0.5882200350957504, 0.3333333333333333, 3500)

        hue100 = chp.Color(100, 0, 0, 3500).hue
        half = chp.Color(0, 0.5, 0, 3500).saturation

        expected_old = [
            {"start_index": 0, "end_index": 9, **colorRed.as_dict()},
            {"start_index": 10, "end_index": 12, **colorBlue.as_dict()},
            {"start_index": 13, "end_index": 17, **colorHSBK.as_dict()},
            {"start_index": 18, "end_index": 19, **colorHEX.as_dict()},
            {
                "start_index": 20,
                "end_index": 20,
                "hue": hue100,
                "saturation": 0.0,
                "brightness": 1.0,
                "kelvin": 3500,
            },
            {
                "start_index": 21,
                "end_index": 21,
                "hue": hue100,
                "saturation": half,
                "brightness": 1.0,
                "kelvin": 3500,
            },
            {
                "start_index": 22,
                "end_index": 22,
                "hue": hue100,
                "saturation": half,
                "brightness": half,
                "kelvin": 3500,
            },
            {
                "start_index": 23,
                "end_index": 23,
                "hue": hue100,
                "saturation": half,
                "brightness": half,
                "kelvin": 9000,
            },
            {
                "start_index": 24,
                "end_index": 24,
                "hue": 0.0,
                "saturation": 0.0,
                "brightness": 0.0,
                "kelvin": 0,
            },
            {
                "start_index": 25,
                "end_index": 25,
                "hue": hue100,
                "saturation": 0.0,
                "brightness": 1.0,
                "kelvin": 3500,
            },
            {
                "start_index": 26,
                "end_index": 26,
                "hue": hue100,
                "saturation": half,
                "brightness": 1.0,
                "kelvin": 3500,
            },
            {
                "start_index": 27,
                "end_index": 27,
                "hue": hue100,
                "saturation": half,
                "brightness": half,
                "kelvin": 3500,
            },
            {
                "start_index": 28,
                "end_index": 28,
                "hue": hue100,
                "saturation": half,
                "brightness": half,
                "kelvin": 9000,
            },
            {
                "start_index": 29,
                "end_index": 29,
                "hue": 0.0,
                "saturation": 0.0,
                "brightness": 0.0,
                "kelvin": 0,
            },
        ]

        assert len(plan.set_color_old) == len(expected_old)
        for e, o in zip(expected_old, plan.set_color_old):
            for k, v in e.items():
                assert v == pytest.approx(o[k])

        def hsbk(*args, **kwargs):
            h, s, b, k = Parser.hsbk(*args, **kwargs)
            return chp.Color(h, s, b, k)

        colorRed = hsbk("red", overrides={"brightness": 1.0, "kelvin": 3500})
        colorBlue = hsbk("blue", overrides={"brightness": 1.0, "kelvin": 3500})
        colorHSBK = hsbk("hue:78 brightness:0.5", overrides={"saturation": 0, "kelvin": 3500})
        colorHEX = hsbk("#234455", overrides={"kelvin": 3500})

        self.maxDiff = None
        expected_new = [colorRed] * 10 + [colorBlue] * 3 + [colorHSBK] * 5 + [colorHEX] * 2
        for _ in range(2):
            expected_new.append(chp.Color(100, 0, 1, 3500))
            expected_new.append(chp.Color(100, 0.5, 1, 3500))
            expected_new.append(chp.Color(100, 0.5, 0.5, 3500))
            expected_new.append(chp.Color(100, 0.5, 0.5, 9000))
            expected_new.append(chp.Color(0, 0, 0, 0))

        nw = plan.set_color_new
        assert nw.colors_count == len(expected_new), nw

        for i, (c, n) in enumerate(zip(nw.colors, expected_new)):
            for k in n.keys():
                assert c[k] == pytest.approx(n[k], rel=1e-6)
        assert nw.zone_index == 0

    async it "can overrides hue", specifier:
        plan = SetZonesPlan(specifier, overrides={"hue": 1})

        expected = chp.Color(1, 0, 0, 3500).hue

        for o in plan.set_color_old:
            assert o.hue == expected

        assert plan.set_color_new.colors_count == 30
        for i in range(28):
            assert plan.set_color_new.colors[i].hue == expected

    async it "can overrides saturation", specifier:
        plan = SetZonesPlan(specifier, overrides={"saturation": 0.3})

        expected = chp.Color(0, 0.3, 0, 3500).saturation

        for o in plan.set_color_old:
            assert o.saturation == expected

        assert plan.set_color_new.colors_count == 30
        for i in range(28):
            assert plan.set_color_new.colors[i].saturation == expected

    async it "can overrides brightness", specifier:
        plan = SetZonesPlan(specifier, overrides={"brightness": 0.6})

        expected = chp.Color(0, 0, 0.6, 3500).brightness

        for o in plan.set_color_old:
            assert o.brightness == expected

        assert plan.set_color_new.colors_count == 30
        for i in range(28):
            assert plan.set_color_new.colors[i].brightness == expected

    async it "can overrides kelvin", specifier:
        plan = SetZonesPlan(specifier, overrides={"kelvin": 8000})

        for o in plan.set_color_old:
            assert o.kelvin == 8000

        assert plan.set_color_new.colors_count == 30
        for i in range(28):
            assert plan.set_color_new.colors[i].kelvin == 8000

    async it "can override duration", specifier:
        plan = SetZonesPlan(specifier)

        for o in plan.set_color_old:
            assert o.duration == 1

        assert plan.set_color_new.duration == 1

        plan = SetZonesPlan(specifier, duration=20)

        for o in plan.set_color_old:
            assert o.duration == 20

        assert plan.set_color_new.duration == 20

    async it "can start at a different zone_index", specifier:
        plan = SetZonesPlan(specifier, zone_index=10)

        expected_old = [
            {"start_index": 10 + 0, "end_index": 10 + 9},
            {"start_index": 10 + 10, "end_index": 10 + 12},
            {"start_index": 10 + 13, "end_index": 10 + 17},
            {"start_index": 10 + 18, "end_index": 10 + 19},
            {"start_index": 10 + 20, "end_index": 10 + 20},
            {"start_index": 10 + 21, "end_index": 10 + 21},
            {"start_index": 10 + 22, "end_index": 10 + 22},
            {"start_index": 10 + 23, "end_index": 10 + 23},
            {"start_index": 10 + 24, "end_index": 10 + 24},
            {"start_index": 10 + 25, "end_index": 10 + 25},
            {"start_index": 10 + 26, "end_index": 10 + 26},
            {"start_index": 10 + 27, "end_index": 10 + 27},
            {"start_index": 10 + 28, "end_index": 10 + 28},
        ]

        for e, o in zip(expected_old, plan.set_color_old):
            for k, v in e.items():
                assert v == o[k]

        assert plan.set_color_new.zone_index == 10

    async it "complains if we have more than 82 colors":
        with assertRaises(PhotonsAppError, "colors can only go up to 82 colors", got=87):
            SetZonesPlan([["red", 80], ["blue", 7]])

    async it "complains if we have no colors":
        with assertRaises(PhotonsAppError, "No colors were specified"):
            SetZonesPlan([])

    async it "can create messages to send back", specifier:
        plan = SetZonesPlan(specifier)

        def make(options):
            return type("Capability", (Capability,), options)

        instance1 = plan.Instance(
            light1.serial,
            plan,
            {"c": {"cap": make({"has_multizone": False, "has_extended_multizone": False})}},
        )
        instance2 = plan.Instance(
            striplcm1.serial,
            plan,
            {"c": {"cap": make({"has_multizone": True, "has_extended_multizone": False})}},
        )
        instance3 = plan.Instance(
            striplcm2noextended.serial,
            plan,
            {"c": {"cap": make({"has_multizone": True, "has_extended_multizone": False})}},
        )
        instance4 = plan.Instance(
            striplcm2extended.serial,
            plan,
            {"c": {"cap": make({"has_multizone": True, "has_extended_multizone": True})}},
        )

        assert instance1.messages is Skip
        for instance in (instance2, instance3, instance4):
            assert instance.messages is NoMessages

        msgsLcm1 = await instance2.info()
        msgsLcm2Noextended = await instance3.info()
        msgsLcm2Extended = await instance4.info()

        for m in (msgsLcm1, msgsLcm2Noextended):
            assert all(msg | MultiZoneMessages.SetColorZones for msg in m)
        assert msgsLcm2Extended | MultiZoneMessages.SetExtendedColorZones

        for msg in msgsLcm1:
            assert msg.serial == striplcm1.serial

        for msg in msgsLcm2Noextended:
            assert msg.serial == striplcm2noextended.serial

        assert msgsLcm2Extended.serial == striplcm2extended.serial

describe "Multizone helpers":

    def compare_received(self, by_light):
        for light, msgs in by_light.items():
            assert light in lights
            light.compare_received(msgs)
            light.reset_received()

    def compare_received_klses(self, by_light):
        for light, msgs in by_light.items():
            assert light in lights
            light.compare_received_klses(msgs)
            light.reset_received()

    describe "find_multizone":

        async it "yields serials and capability", runner:
            got = {}
            async for serial, cap in find_multizone(runner.serials, runner.sender):
                assert serial not in got
                got[serial] = cap.has_extended_multizone

            assert got == {
                striplcm1.serial: False,
                striplcm2noextended.serial: False,
                striplcm2extended.serial: True,
            }

        async it "resends messages each time if we reset the gatherer", runner:
            async for serial, cap in find_multizone(runner.serials, runner.sender):
                pass

            want = {
                device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                for device in lights
            }
            self.compare_received(want)

            del runner.sender.gatherer
            async for serial, cap in find_multizone(runner.serials, runner.sender):
                pass

            want = {
                device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                for device in lights
            }
            self.compare_received(want)

        async it "uses cached gatherer on the sender", runner:
            async for serial, cap in find_multizone(runner.serials, runner.sender):
                pass

            want = {
                device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                for device in lights
            }
            self.compare_received(want)

            async for serial, cap in find_multizone(runner.serials, runner.sender):
                pass

            want = {device: [] for device in lights}
            self.compare_received(want)

    describe "zones_from_reference":

        async it "yield zones", runner:
            got = {}
            async for serial, zones in zones_from_reference(runner.serials, runner.sender):
                assert serial not in got
                got[serial] = zones

            assert got == {
                striplcm1.serial: [(i, c) for i, c in enumerate(zones1)],
                striplcm2noextended.serial: [(i, c) for i, c in enumerate(zones2)],
                striplcm2extended.serial: [(i, c) for i, c in enumerate(zones3)],
            }

        async it "resends messages if no gatherer is reset between runs", runner:
            async for serial, zones in zones_from_reference(runner.serials, runner.sender):
                pass

            want = {
                device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                for device in lights
            }
            want[striplcm1].append(MultiZoneMessages.GetColorZones(start_index=0, end_index=255))
            want[striplcm2noextended].append(
                MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
            )
            want[striplcm2extended].append(MultiZoneMessages.GetExtendedColorZones())
            self.compare_received(want)

            del runner.sender.gatherer
            async for serial, zones in zones_from_reference(runner.serials, runner.sender):
                pass

            self.compare_received(want)

        async it "uses cached gatherer on the sender", runner:
            async for serial, zones in zones_from_reference(runner.serials, runner.sender):
                pass

            want = {
                device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                for device in lights
            }
            want[striplcm1].append(MultiZoneMessages.GetColorZones(start_index=0, end_index=255))
            want[striplcm2noextended].append(
                MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
            )
            want[striplcm2extended].append(MultiZoneMessages.GetExtendedColorZones())
            self.compare_received(want)

            async for serial, zones in zones_from_reference(runner.serials, runner.sender):
                pass

            self.compare_received({device: [] for device in lights})

    describe "SetZones":

        async it "can power on devices and set zones", runner:
            for device in strips:
                device.attrs.zones = [zeroColor] * 16

            msg = SetZones([["red", 7], ["blue", 5]])
            got = await runner.sender(msg, runner.serials)
            assert got == []

            red = chp.Color(0, 1, 1, 3500)
            blue = chp.Color(250, 1, 1, 3500)
            assert striplcm1.attrs.zones == [red] * 7 + [blue] * 5 + [zeroColor] * 4
            assert striplcm2extended.attrs.zones == [red] * 7 + [blue] * 5 + [zeroColor] * 4
            assert striplcm2extended.attrs.zones == [red] * 7 + [blue] * 5 + [zeroColor] * 4

            self.compare_received_klses(
                {
                    light1: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion],
                    light2: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion],
                    striplcm1: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2noextended: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2extended: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetExtendedColorZones,
                    ],
                }
            )

        async it "can skip turning on lights", runner:
            for device in strips:
                device.attrs.zones = [zeroColor] * 16

            msg = SetZones([["red", 7], ["blue", 5]], power_on=False)
            got = await runner.sender(msg, runner.serials)
            assert got == []

            self.compare_received_klses(
                {
                    light1: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion],
                    light2: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion],
                    striplcm1: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2noextended: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2extended: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        MultiZoneMessages.SetExtendedColorZones,
                    ],
                }
            )

        async it "can target particular lights", runner:
            for device in strips:
                device.attrs.zones = [zeroColor] * 16

            lcm2strips = [striplcm2extended.serial, striplcm2noextended.serial]

            msg2 = SetZones([["red", 7], ["blue", 5]], reference=striplcm1.serial)
            msg = SetZones([["green", 7], ["yellow", 5]], power_on=False, reference=lcm2strips)
            got = await runner.sender([msg, msg2], None)
            assert got == []

            red = chp.Color(0, 1, 1, 3500)
            blue = chp.Color(250, 1, 1, 3500)
            assert striplcm1.attrs.zones == [red] * 7 + [blue] * 5 + [zeroColor] * 4

            green = chp.Color(120, 1, 1, 3500)
            yellow = chp.Color(60, 1, 1, 3500)
            assert striplcm2extended.attrs.zones == [green] * 7 + [yellow] * 5 + [zeroColor] * 4
            assert striplcm2extended.attrs.zones == [green] * 7 + [yellow] * 5 + [zeroColor] * 4

            self.compare_received_klses(
                {
                    striplcm1: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2noextended: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2extended: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        MultiZoneMessages.SetExtendedColorZones,
                    ],
                }
            )

        async it "can give duration to messages", runner:
            for device in strips:
                device.attrs.zones = [zeroColor] * 16

            msg = SetZones([["green", 7], ["yellow", 5]], duration=5)
            got = await runner.sender(msg, [s.serial for s in strips])
            assert got == []

            for device in strips:
                assert device.received.pop(0) | DeviceMessages.GetHostFirmware
                assert device.received.pop(0) | DeviceMessages.GetVersion

                for msg in device.received:
                    assert msg.duration == 5

        async it "uses cached gatherer on the sender", runner:
            for device in strips:
                device.attrs.zones = [zeroColor] * 16

            msg = SetZones([["green", 7], ["yellow", 5]])
            got = await runner.sender(msg, runner.serials)
            assert got == []

            self.compare_received_klses(
                {
                    light1: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion],
                    light2: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion],
                    striplcm1: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2noextended: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2extended: [
                        DeviceMessages.GetHostFirmware,
                        DeviceMessages.GetVersion,
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetExtendedColorZones,
                    ],
                }
            )

            msg = SetZones([["green", 7], ["yellow", 5]])
            got = await runner.sender(msg, [s.serial for s in strips])
            assert got == []

            self.compare_received_klses(
                {
                    striplcm1: [
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2noextended: [
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetColorZones,
                        MultiZoneMessages.SetColorZones,
                    ],
                    striplcm2extended: [
                        LightMessages.SetLightPower,
                        MultiZoneMessages.SetExtendedColorZones,
                    ],
                }
            )

    describe "SetZonesEffect":

        async it "can power on devices and set zones effect", runner:
            msg = SetZonesEffect("move")
            got = await runner.sender(msg, runner.serials)
            assert got == []

            for strip in strips:
                assert strip.attrs.zones_effect is MultiZoneEffectType.MOVE

            self.compare_received(
                {
                    light1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    striplcm1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            type=MultiZoneEffectType.MOVE
                        ),
                    ],
                    striplcm2noextended: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            type=MultiZoneEffectType.MOVE
                        ),
                    ],
                    striplcm2extended: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            type=MultiZoneEffectType.MOVE
                        ),
                    ],
                }
            )

        async it "has options", runner:
            msg = SetZonesEffect("move", speed=5, duration=10, power_on_duration=20)
            got = await runner.sender(msg, runner.serials)
            assert got == []

            for strip in strips:
                assert strip.attrs.zones_effect is MultiZoneEffectType.MOVE

            self.compare_received(
                {
                    light1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    striplcm1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=20),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            duration=10, type=MultiZoneEffectType.MOVE, speed=5
                        ),
                    ],
                    striplcm2noextended: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=20),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            duration=10, type=MultiZoneEffectType.MOVE, speed=5
                        ),
                    ],
                    striplcm2extended: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=20),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            duration=10, type=MultiZoneEffectType.MOVE, speed=5
                        ),
                    ],
                }
            )

        async it "can choose not to turn on devices", runner:
            msg = SetZonesEffect("move", power_on=False)
            got = await runner.sender(msg, runner.serials)
            assert got == []

            for strip in strips:
                assert strip.attrs.zones_effect is MultiZoneEffectType.MOVE

            self.compare_received(
                {
                    light1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                    striplcm1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            type=MultiZoneEffectType.MOVE
                        ),
                    ],
                    striplcm2noextended: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            type=MultiZoneEffectType.MOVE
                        ),
                    ],
                    striplcm2extended: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            type=MultiZoneEffectType.MOVE
                        ),
                    ],
                }
            )

        async it "can target particular devices", runner:
            lcm2strips = [striplcm2extended.serial, striplcm2noextended.serial]

            msg = SetZonesEffect("move", power_on=False, reference=striplcm1.serial)
            msg2 = SetZonesEffect("move", duration=5, reference=lcm2strips)
            got = await runner.sender([msg, msg2])
            assert got == []

            for strip in strips:
                assert strip.attrs.zones_effect is MultiZoneEffectType.MOVE

            self.compare_received(
                {
                    striplcm1: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            type=MultiZoneEffectType.MOVE
                        ),
                    ],
                    striplcm2noextended: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            duration=5, type=MultiZoneEffectType.MOVE
                        ),
                    ],
                    striplcm2extended: [
                        DeviceMessages.GetHostFirmware(),
                        DeviceMessages.GetVersion(),
                        LightMessages.SetLightPower(level=65535, duration=1),
                        MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
                            duration=5, type=MultiZoneEffectType.MOVE
                        ),
                    ],
                }
            )
