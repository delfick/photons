# coding: spec

from photons_control.multizone import find_multizone, zones_from_reference, SetZonesPlan, SetZones, SetZonesEffect
from photons_control.test_helpers import Device, ModuleLevelRunner, Color, HSBKClose
from photons_control.planner import Gatherer, Skip, NoMessages

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut
from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_colour import Parser

from photons_messages import DeviceMessages, LightMessages, MultiZoneMessages, MultiZoneEffectType

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import uuid

zeroColor = Color(0, 0, 0, 3500)

light1 = Device("d073d5000001", use_sockets=False
    , power = 0
    , label = "bob"
    , infrared = 100
    , color = Color(100, 0.5, 0.5, 4500)
    , product_id = 55
    , firmware_build = 1548977726000000000
    , firmware_major = 3
    , firmware_minor = 50
    )

light2 = Device("d073d5000002", use_sockets=False
    , power = 65535
    , label = "sam"
    , infrared = 0
    , color = Color(200, 0.3, 1, 9000)
    , product_id = 1
    , firmware_build = 1448861477000000000
    , firmware_major = 2
    , firmware_minor = 2
    )

striplcm1 = Device("d073d5000003", use_sockets=False
    , power = 0
    , label = "lcm1-no-extended"
    , product_id = 31
    , firmware_build = 1502237570000000000
    , firmware_major = 1
    , firmware_minor = 22
    )

striplcm2noextended = Device("d073d5000004", use_sockets=False
    , power = 0
    , label = "lcm2-no-extended"
    , product_id = 32
    , firmware_build = 1508122125000000000
    , firmware_major = 2
    , firmware_minor = 70
    )

striplcm2extended = Device("d073d5000005", use_sockets=False
    , power = 0
    , label = "lcm2-extended"
    , product_id = 32
    , firmware_build = 1543215651000000000
    , firmware_major = 2
    , firmware_minor = 77
    )

lights = [light1, light2, striplcm1, striplcm2noextended, striplcm2extended]
mlr = ModuleLevelRunner(lights, use_sockets=False)

setUp = mlr.setUp
tearDown = mlr.tearDown

describe AsyncTestCase, "SetZonesPlan":
    async before_each:
        self.specifier = [
              ["red", 10]
            , ["blue", 3]
            , ["hue:78 brightness:0.5", 5]
            , ["#234455", 2]
            , [[100], 1]
            , [[100, 0.5], 1]
            , [[100, 0.5, 0.5], 1]
            , [[100, 0.5, 0.5, 9000], 1]
            , [[0, 0, 0, 0], 1]
            , [{"hue": 100}, 1]
            , [{"hue": 100, "saturation": 0.5}, 1]
            , [{"hue": 100, "saturation": 0.5, "brightness": 0.5}, 1]
            , [{"hue": 100, "saturation": 0.5, "brightness": 0.5, "kelvin": 9000}, 1]
            , [{"hue": 0, "saturation": 0, "brightness": 0, "kelvin": 0}, 1]
            ]

    async it "works out old style and extended style messages":
        plan = SetZonesPlan(self.specifier)

        assert all(msg | MultiZoneMessages.SetColorZones for msg in plan.set_color_old)
        assert plan.set_color_new | MultiZoneMessages.SetExtendedColorZones

        colorRed = {'hue': 0.0, 'saturation': 1.0, 'brightness': 1.0, 'kelvin': 3500}
        colorBlue = {'hue': 249.9977111467155, 'saturation': 1.0, 'brightness': 1.0, 'kelvin': 3500}
        colorHSBK = {'hue': 77.99862668802929, 'saturation': 0.0, 'brightness': 0.49999237048905165, 'kelvin': 3500}
        colorHEX = {'hue': 200.39917601281758, 'saturation': 0.5882200350957504, 'brightness': 0.3333333333333333, 'kelvin': 3500}

        hue100 = 99.9990844586862
        half = 0.49999237048905165

        expected_old = [
              { 'start_index': 0, 'end_index': 9
              , **colorRed
              }
            , { 'start_index': 10, 'end_index': 12
              , **colorBlue
              }
            , { 'start_index': 13, 'end_index': 17
              , **colorHSBK
              }
            , { 'start_index': 18, 'end_index': 19
              , **colorHEX
              }
            , { 'start_index': 20, 'end_index': 20
              , "hue": hue100, "saturation": 0.0, "brightness": 1.0, "kelvin": 3500
              }
            , { 'start_index': 21, 'end_index': 21
              , "hue": hue100, "saturation": half, "brightness": 1.0, "kelvin": 3500
              }
            , { 'start_index': 22, 'end_index': 22
              , "hue": hue100, "saturation": half, "brightness": half, "kelvin": 3500
              }
            , { 'start_index': 23, 'end_index': 23
              , "hue": hue100, "saturation": half, "brightness": half, "kelvin": 9000
              }
            , { 'start_index': 24, 'end_index': 24
              , "hue": 0.0, "saturation": 0.0, "brightness": 0.0, "kelvin": 0
              }
            , { 'start_index': 25, 'end_index': 25
              , "hue": hue100, "saturation": 0.0, "brightness": 1.0, "kelvin": 3500
              }
            , { 'start_index': 26, 'end_index': 26
              , "hue": hue100, "saturation": half, "brightness": 1.0, "kelvin": 3500
              }
            , { 'start_index': 27, 'end_index': 27
              , "hue": hue100, "saturation": half, "brightness": half, "kelvin": 3500
              }
            , { 'start_index': 28, 'end_index': 28
              , "hue": hue100, "saturation": half, "brightness": half, "kelvin": 9000
              }
            , { 'start_index': 29, 'end_index': 29
              , "hue": 0.0, "saturation": 0.0, "brightness": 0.0, "kelvin": 0
              }
            ]

        self.assertEqual(len(plan.set_color_old), len(expected_old))
        for e, o in zip(expected_old, plan.set_color_old):
            for k, v in e.items():
                self.assertEqual(v, o[k])

        def hsbk(*args, **kwargs):
            h, s, b, k = Parser.hsbk(*args, **kwargs)
            return {"hue": h, "saturation": s, "brightness": b, "kelvin": k}

        colorRed = hsbk("red", overrides={"brightness": 1.0, "kelvin": 3500})
        colorBlue = hsbk("blue", overrides={"brightness": 1.0, "kelvin": 3500})
        colorHSBK = hsbk("hue:78 brightness:0.5", overrides={"saturation": 0, "kelvin": 3500})
        colorHEX = hsbk("#234455", overrides={"kelvin": 3500})

        self.maxDiff = None
        expected_new = [colorRed] * 10 + [colorBlue] * 3 + [colorHSBK] * 5 + [colorHEX] * 2
        for _ in range(2):
            expected_new.append({"hue": 100, "saturation": 0, "brightness": 1, "kelvin": 3500})
            expected_new.append({"hue": 100, "saturation": 0.5, "brightness": 1, "kelvin": 3500})
            expected_new.append({"hue": 100, "saturation": 0.5, "brightness": 0.5, "kelvin": 3500})
            expected_new.append({"hue": 100, "saturation": 0.5, "brightness": 0.5, "kelvin": 9000})
            expected_new.append({"hue": 0, "saturation": 0, "brightness": 0, "kelvin": 0})

        self.assertEqual(plan.set_color_new.colors, expected_new)
        self.assertEqual(plan.set_color_new.zone_index, 0)
        self.assertEqual(plan.set_color_new.colors_count, len(expected_new))

    async it "can overrides hue":
        plan = SetZonesPlan(self.specifier, overrides={"hue": 1})

        for o in plan.set_color_old:
            self.assertEqual(o["hue"], 0.9997711146715496)

        self.assertEqual(plan.set_color_new.colors_count, 30)
        for i in range(28):
            self.assertEqual(plan.set_color_new.colors[i]["hue"], 1)

    async it "can overrides saturation":
        plan = SetZonesPlan(self.specifier, overrides={"saturation": 0.3})

        for o in plan.set_color_old:
            self.assertEqual(o["saturation"], 0.29999237048905164)

        self.assertEqual(plan.set_color_new.colors_count, 30)
        for i in range(28):
            self.assertEqual(plan.set_color_new.colors[i]["saturation"], 0.3)

    async it "can overrides brightness":
        plan = SetZonesPlan(self.specifier, overrides={"brightness": 0.6})

        for o in plan.set_color_old:
            self.assertEqual(o["brightness"], 0.6)

        self.assertEqual(plan.set_color_new.colors_count, 30)
        for i in range(28):
            self.assertEqual(plan.set_color_new.colors[i]["brightness"], 0.6)

    async it "can overrides kelvin":
        plan = SetZonesPlan(self.specifier, overrides={"kelvin": 8000})

        for o in plan.set_color_old:
            self.assertEqual(o["kelvin"], 8000)

        self.assertEqual(plan.set_color_new.colors_count, 30)
        for i in range(28):
            self.assertEqual(plan.set_color_new.colors[i]["kelvin"], 8000)

    async it "can override duration":
        plan = SetZonesPlan(self.specifier)

        for o in plan.set_color_old:
            self.assertEqual(o["duration"], 1)

        self.assertEqual(plan.set_color_new.duration, 1)

        plan = SetZonesPlan(self.specifier, duration=20)

        for o in plan.set_color_old:
            self.assertEqual(o["duration"], 20)

        self.assertEqual(plan.set_color_new.duration, 20)

    async it "can start at a different zone_index":
        plan = SetZonesPlan(self.specifier, zone_index=10)

        expected_old = [
              { 'start_index': 10 + 0, 'end_index': 10 + 9}
            , { 'start_index': 10 + 10, 'end_index': 10 + 12}
            , { 'start_index': 10 + 13, 'end_index': 10 + 17}
            , { 'start_index': 10 + 18, 'end_index': 10 + 19}
            , { 'start_index': 10 + 20, 'end_index': 10 + 20}
            , { 'start_index': 10 + 21, 'end_index': 10 + 21}
            , { 'start_index': 10 + 22, 'end_index': 10 + 22}
            , { 'start_index': 10 + 23, 'end_index': 10 + 23}
            , { 'start_index': 10 + 24, 'end_index': 10 + 24}
            , { 'start_index': 10 + 25, 'end_index': 10 + 25}
            , { 'start_index': 10 + 26, 'end_index': 10 + 26}
            , { 'start_index': 10 + 27, 'end_index': 10 + 27}
            , { 'start_index': 10 + 28, 'end_index': 10 + 28}
            ]

        for e, o in zip(expected_old, plan.set_color_old):
            for k, v in e.items():
                self.assertEqual(v, o[k])

        self.assertEqual(plan.set_color_new.zone_index, 10)

    async it "complains if we have more than 82 colors":
        with self.fuzzyAssertRaisesError(PhotonsAppError, "colors can only go up to 82 colors", got=87):
            SetZonesPlan([["red", 80], ["blue", 7]])

    async it "complains if we have no colors":
        with self.fuzzyAssertRaisesError(PhotonsAppError, "No colors were specified"):
            SetZonesPlan([])

    @with_timeout
    async it "can create messages to send back":
        plan = SetZonesPlan(self.specifier)

        instance1 = plan.Instance(light1.serial, plan, {"c": {"cap": {"has_multizone": False}, "has_extended_multizone": False}})
        instance2 = plan.Instance(striplcm1.serial, plan, {"c": {"cap": {"has_multizone": True}, "has_extended_multizone": False}})
        instance3 = plan.Instance(striplcm2noextended.serial, plan, {"c": {"cap": {"has_multizone": True}, "has_extended_multizone": False}})
        instance4 = plan.Instance(striplcm2extended.serial, plan, {"c": {"cap": {"has_multizone": True}, "has_extended_multizone": True}})

        self.assertIs(instance1.messages, Skip)
        for instance in (instance2, instance3, instance4):
            self.assertIs(instance.messages, NoMessages)

        msgsLcm1 = await instance2.info()
        msgsLcm2Noextended = await instance3.info()
        msgsLcm2Extended = await instance4.info()

        for m in (msgsLcm1, msgsLcm2Noextended):
            assert all(msg | MultiZoneMessages.SetColorZones for msg in m)
        assert msgsLcm2Extended | MultiZoneMessages.SetExtendedColorZones

        for msg in msgsLcm1:
            self.assertEqual(msg.serial, striplcm1.serial)

        for msg in msgsLcm2Noextended:
            self.assertEqual(msg.serial, striplcm2noextended.serial)

        self.assertEqual(msgsLcm2Extended.serial, striplcm2extended.serial)

describe AsyncTestCase, "Multizone helpers":
    use_default_loop = True

    async before_each:
        self.maxDiff = None
        self.strips = [striplcm1, striplcm2extended, striplcm2noextended]

    def compare_received(self, by_light):
        for light, msgs in by_light.items():
            assert light in lights
            light.compare_received(msgs, keep_duplicates=True)
            light.reset_received()

    def compare_received_klses(self, by_light):
        for light, msgs in by_light.items():
            assert light in lights
            light.compare_received_klses(msgs, keep_duplicates=True)
            light.reset_received()

    describe "find_multizone":
        @mlr.test
        async it "yields serials and whether we have extended multizone", runner:
            got = {}
            async with runner.target.session() as afr:
                async for serial, has_extended_multizone in find_multizone(runner.target, runner.serials, afr):
                    assert serial not in got
                    got[serial] = has_extended_multizone

            self.assertEqual(got
                , { striplcm1.serial: False
                  , striplcm2noextended.serial: False
                  , striplcm2extended.serial: True
                  }
                )

        @mlr.test
        async it "resends messages each time if we don't give a gatherer", runner:
            async with runner.target.session() as afr:
                async for serial, has_extended_multizone in find_multizone(runner.target, runner.serials, afr):
                    pass

                want = {device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()] for device in lights}
                self.compare_received(want)

                async for serial, has_extended_multizone in find_multizone(runner.target, runner.serials, afr):
                    pass

                want = {device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()] for device in lights}
                self.compare_received(want)

        @mlr.test
        async it "has cache if we provide a gatherer", runner:
            gatherer = Gatherer(runner.target)

            async with runner.target.session() as afr:
                async for serial, has_extended_multizone in find_multizone(runner.target, runner.serials, afr, gatherer=gatherer):
                    pass

                want = {device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()] for device in lights}
                self.compare_received(want)

                async for serial, has_extended_multizone in find_multizone(runner.target, runner.serials, afr, gatherer=gatherer):
                    pass

                want = {device: [] for device in lights}
                self.compare_received(want)

    describe "zones_from_reference":
        def set_zones(self):
            zones1 = [Color(i, 1, 1, 3500) for i in range(30)]
            zones2 = [Color(90 - i, 1, 1, 3500) for i in range(6)]
            zones3 = [Color(300 - i, 1, 1, 3500) for i in range(16)]

            striplcm1.change_zones(zones1)
            striplcm2noextended.change_zones(zones2)
            striplcm2extended.change_zones(zones3)

            return (zones1, zones2, zones3)

        @mlr.test
        async it "yield zones", runner:
            zones1, zones2, zones3 = self.set_zones()

            got = {}
            async with runner.target.session() as afr:
                async for serial, zones in zones_from_reference(runner.target, runner.serials, afr):
                    assert serial not in got
                    got[serial] = zones

            self.assertEqual(got
                , { striplcm1.serial: [(i, HSBKClose(z.as_dict())) for i, z in enumerate(zones1)]
                  , striplcm2noextended.serial: [(i, HSBKClose(z.as_dict())) for i, z in enumerate(zones2)]
                  , striplcm2extended.serial: [(i, HSBKClose(z.as_dict())) for i, z in enumerate(zones3)]
                  }
                )

        @mlr.test
        async it "resends messages if no gatherer is provided", runner:
            self.set_zones()

            async with runner.target.session() as afr:
                async for serial, zones in zones_from_reference(runner.target, runner.serials, afr):
                    pass

            want = {device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()] for device in lights}
            want[striplcm1].append(MultiZoneMessages.GetColorZones(start_index=0, end_index=255))
            want[striplcm2noextended].append(MultiZoneMessages.GetColorZones(start_index=0, end_index=255))
            want[striplcm2extended].append(MultiZoneMessages.GetExtendedColorZones())
            self.compare_received(want)

            async with runner.target.session() as afr:
                async for serial, zones in zones_from_reference(runner.target, runner.serials, afr):
                    pass

            self.compare_received(want)

        @mlr.test
        async it "caches messages if gatherer is provided", runner:
            self.set_zones()

            gatherer = Gatherer(runner.target)
            async with runner.target.session() as afr:
                async for serial, zones in zones_from_reference(runner.target, runner.serials, afr, gatherer=gatherer):
                    pass

            want = {device: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()] for device in lights}
            want[striplcm1].append(MultiZoneMessages.GetColorZones(start_index=0, end_index=255))
            want[striplcm2noextended].append(MultiZoneMessages.GetColorZones(start_index=0, end_index=255))
            want[striplcm2extended].append(MultiZoneMessages.GetExtendedColorZones())
            self.compare_received(want)

            async with runner.target.session() as afr:
                async for serial, zones in zones_from_reference(runner.target, runner.serials, afr, gatherer=gatherer):
                    pass

            self.compare_received({device: [] for device in lights})

    describe "SetZones":
        @mlr.test
        async it "can power on devices and set zones", runner:
            for device in self.strips:
                device.change_zones([zeroColor] * 16)

            msg = SetZones([["red", 7], ["blue", 5]])
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            red = {"hue": 0, "saturation": 1.0, "brightness": 1.0, "kelvin": 3500}
            blue = {"hue": 249.9977111467155, "saturation": 1.0, "brightness": 1.0, "kelvin": 3500}
            self.assertEqual(striplcm1.zones, [red] * 7 + [blue] * 5 + [zeroColor] * 4)
            self.assertEqual(striplcm2extended.zones, [red] * 7 + [blue] * 5 + [zeroColor] * 4)
            self.assertEqual(striplcm2extended.zones, [red] * 7 + [blue] * 5 + [zeroColor] * 4)

            self.compare_received_klses(
                  { light1: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion]
                  , light2: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion]

                  , striplcm1:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , LightMessages.SetLightPower
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , LightMessages.SetLightPower
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , LightMessages.SetLightPower
                    , MultiZoneMessages.SetExtendedColorZones
                    ]
                  }
                )

        @mlr.test
        async it "can skip turning on lights", runner:
            for device in self.strips:
                device.change_zones([zeroColor] * 16)

            msg = SetZones([["red", 7], ["blue", 5]], power_on=False)
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            self.compare_received_klses(
                  { light1: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion]
                  , light2: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion]

                  , striplcm1:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , MultiZoneMessages.SetExtendedColorZones
                    ]
                  }
                )

        @mlr.test
        async it "can target particular lights", runner:
            for device in self.strips:
                device.change_zones([zeroColor] * 16)

            lcm2strips = [striplcm2extended.serial, striplcm2noextended.serial]

            msg2 = SetZones([["red", 7], ["blue", 5]], reference=striplcm1.serial)
            msg = SetZones([["green", 7], ["yellow", 5]], power_on=False, reference=lcm2strips)
            got = await runner.target.script([msg, msg2]).run_with_all(None)
            self.assertEqual(got, [])

            red = {"hue": 0, "saturation": 1.0, "brightness": 1.0, "kelvin": 3500}
            blue = {"hue": 249.9977111467155, "saturation": 1.0, "brightness": 1.0, "kelvin": 3500}
            self.assertEqual(striplcm1.zones, [red] * 7 + [blue] * 5 + [zeroColor] * 4)

            green = {"hue": 120.0, "saturation": 1.0, "brightness": 1.0, "kelvin": 3500}
            yellow = {"hue": 59.997253376058595, "saturation": 1.0, "brightness": 1.0, "kelvin": 3500}
            self.assertEqual(striplcm2extended.zones, [green] * 7 + [yellow] * 5 + [zeroColor] * 4)
            self.assertEqual(striplcm2extended.zones, [green] * 7 + [yellow] * 5 + [zeroColor] * 4)

            self.compare_received_klses(
                  { striplcm1:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , LightMessages.SetLightPower
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , MultiZoneMessages.SetExtendedColorZones
                    ]
                  }
                )

        @mlr.test
        async it "can give duration to messages", runner:
            for device in self.strips:
                device.change_zones([zeroColor] * 16)

            msg = SetZones([["green", 7], ["yellow", 5]], duration=5)
            got = await runner.target.script(msg).run_with_all([s.serial for s in self.strips])
            self.assertEqual(got, [])

            for device in self.strips:
                assert device.received.pop(0) | DeviceMessages.GetHostFirmware
                assert device.received.pop(0) | DeviceMessages.GetVersion

                for msg in device.received:
                    self.assertEqual(msg.duration, 5)

        @mlr.test
        async it "can reuse a gatherer", runner:
            gatherer = Gatherer(runner.target)

            for device in self.strips:
                device.change_zones([zeroColor] * 16)

            msg = SetZones([["green", 7], ["yellow", 5]], gatherer=gatherer)
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            self.compare_received_klses(
                  { light1: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion]
                  , light2: [DeviceMessages.GetHostFirmware, DeviceMessages.GetVersion]

                  , striplcm1:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , LightMessages.SetLightPower
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , LightMessages.SetLightPower
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware
                    , DeviceMessages.GetVersion
                    , LightMessages.SetLightPower
                    , MultiZoneMessages.SetExtendedColorZones
                    ]
                  }
                )

            msg = SetZones([["green", 7], ["yellow", 5]], gatherer=gatherer)
            got = await runner.target.script(msg).run_with_all([s.serial for s in self.strips])
            self.assertEqual(got, [])

            self.compare_received_klses(
                  { striplcm1:
                    [ LightMessages.SetLightPower
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2noextended:
                    [ LightMessages.SetLightPower
                    , MultiZoneMessages.SetColorZones
                    , MultiZoneMessages.SetColorZones
                    ]
                  , striplcm2extended:
                    [ LightMessages.SetLightPower
                    , MultiZoneMessages.SetExtendedColorZones
                    ]
                  }
                )

    describe "SetZonesEffect":
        @mlr.test
        async it "can power on devices and set zones effect", runner:
            msg = SetZonesEffect("move")
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            for strip in self.strips:
                self.assertIs(strip.zones_effect, MultiZoneEffectType.MOVE)

            self.compare_received(
                  { light1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                  , light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]

                  , striplcm1:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  }
                )

        @mlr.test
        async it "has options", runner:
            msg = SetZonesEffect("move", speed=5, duration=10, power_on_duration=20)
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            for strip in self.strips:
                self.assertIs(strip.zones_effect, MultiZoneEffectType.MOVE)

            self.compare_received(
                  { light1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                  , light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]

                  , striplcm1:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=20)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(duration=10, type=MultiZoneEffectType.MOVE, speed=5)
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=20)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(duration=10, type=MultiZoneEffectType.MOVE, speed=5)
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=20)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(duration=10, type=MultiZoneEffectType.MOVE, speed=5)
                    ]
                  }
                )

        @mlr.test
        async it "can choose not to turn on devices", runner:
            msg = SetZonesEffect("move", power_on=False)
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            for strip in self.strips:
                self.assertIs(strip.zones_effect, MultiZoneEffectType.MOVE)

            self.compare_received(
                  { light1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                  , light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]

                  , striplcm1:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  }
                )

        @mlr.test
        async it "can target particular devices", runner:
            lcm2strips = [striplcm2extended.serial, striplcm2noextended.serial]

            msg = SetZonesEffect("move", power_on=False, reference=striplcm1.serial)
            msg2 = SetZonesEffect("move", duration=5, reference=lcm2strips)
            got = await runner.target.script([msg, msg2]).run_with_all(None)
            self.assertEqual(got, [])

            for strip in self.strips:
                self.assertIs(strip.zones_effect, MultiZoneEffectType.MOVE)

            self.compare_received(
                  { striplcm1:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(duration=5, type=MultiZoneEffectType.MOVE)
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(duration=5, type=MultiZoneEffectType.MOVE)
                    ]
                  }
                )

        @mlr.test
        async it "can be passed in a gatherer", runner:
            gatherer = Gatherer(runner.target)

            msg = SetZonesEffect("move", gatherer=gatherer)
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            for strip in self.strips:
                self.assertIs(strip.zones_effect, MultiZoneEffectType.MOVE)

            self.compare_received(
                  { light1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]
                  , light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]

                  , striplcm1:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  , striplcm2noextended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  , striplcm2extended:
                    [ DeviceMessages.GetHostFirmware()
                    , DeviceMessages.GetVersion()
                    , LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.MOVE)
                    ]
                  }
                )

            msg = SetZonesEffect("off", gatherer=gatherer)
            got = await runner.target.script(msg).run_with_all(runner.serials)
            self.assertEqual(got, [])

            for strip in self.strips:
                self.assertIs(strip.zones_effect, MultiZoneEffectType.OFF)

            self.compare_received(
                  { light1: []
                  , light2: []

                  , striplcm1:
                    [ LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.OFF)
                    ]
                  , striplcm2noextended:
                    [ LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.OFF)
                    ]
                  , striplcm2extended:
                    [ LightMessages.SetLightPower(level=65535, duration=1)
                    , MultiZoneMessages.SetMultiZoneEffect.empty_normalise(type=MultiZoneEffectType.OFF)
                    ]
                  }
                )
