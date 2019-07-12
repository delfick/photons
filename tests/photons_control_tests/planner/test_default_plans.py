# coding: spec

from photons_control.planner import Gatherer, make_plans, Skip
from photons_control import test_helpers as chp

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut
from photons_app.test_helpers import AsyncTestCase

from photons_messages import (
      DeviceMessages, LightMessages, MultiZoneMessages, TileMessages
    , TileEffectType, MultiZoneEffectType
    , Direction
    )
from photons_products_registry import (
      capability_for_ids, enum_for_ids, UnknownProduct
    , LIFIProductRegistry
    )
from photons_transport.fake import FakeDevice

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import uuid

zones1 = [chp.Color(i, 1, 1, 3500) for i in range(30)]
zones2 = [chp.Color(60 - i, 1, 1, 6500) for i in range(20)]
zones3 = [chp.Color(90 - i, 1, 1, 9000) for i in range(40)]

light1 = FakeDevice("d073d5000001"
    , chp.default_responders(LIFIProductRegistry.LCM3_TILE
        , power = 0
        , label = "bob"
        , infrared = 100
        , color = chp.Color(100, 0.5, 0.5, 4500)
        , firmware = chp.Firmware(3, 50, 1548977726000000000)
        )
    )

light2 = FakeDevice("d073d5000002"
    , chp.default_responders(LIFIProductRegistry.LMB_MESH_A21
        , power = 65535
        , label = "sam"
        , infrared = 0
        , color = chp.Color(200, 0.3, 1, 9000)
        , firmware = chp.Firmware(2, 2, 1448861477000000000)
        )
    )

striplcm1 = FakeDevice("d073d5000003"
    , chp.default_responders(LIFIProductRegistry.LCM1_Z
        , power = 0
        , label = "lcm1-no-extended"
        , firmware = chp.Firmware(1, 22, 1502237570000000000)
        , zones = zones1
        )
    )

striplcm2noextended = FakeDevice("d073d5000004"
    , chp.default_responders(LIFIProductRegistry.LCM2_Z
        , power = 0
        , label = "lcm2-no-extended"
        , firmware = chp.Firmware(2, 70, 1508122125000000000)
        , zones = zones2
        )
    )

striplcm2extended = FakeDevice("d073d5000005"
    , chp.default_responders(LIFIProductRegistry.LCM2_Z
        , power = 0
        , label = "lcm2-extended"
        , firmware = chp.Firmware(2, 77, 1543215651000000000)
        , zones = zones3
        )
    )

lights = [light1, light2, striplcm1, striplcm2noextended, striplcm2extended]
mlr = chp.ModuleLevelRunner(lights)

setUp = mlr.setUp
tearDown = mlr.tearDown

describe AsyncTestCase, "Default Plans":
    use_default_loop = True

    async before_each:
        self.maxDiff = None
        self.two_lights = [light1.serial, light2.serial]

    async def gather(self, runner, reference, *by_label, **kwargs):
        gatherer = Gatherer(runner.target)
        plans = make_plans(*by_label)
        return dict(await gatherer.gather_all(plans, reference, **kwargs))

    describe "PresencePlan":
        @mlr.test
        async it "returns True", runner:
            got = await self.gather(runner, self.two_lights, "presence")
            self.assertEqual(got
                , { light1.serial: (True, {"presence": True})
                  , light2.serial: (True, {"presence": True})
                  }
                )

        @mlr.test
        async it "allows us to get serials that otherwise wouldn't", runner:
            errors = []
            with light2.no_replies_for(DeviceMessages.GetLabel):
                got = await self.gather(runner, self.two_lights, "presence", "label"
                    , error_catcher = errors
                    , message_timeout = 0.1
                    , find_timeout = 0.1
                    )

                self.assertEqual(got
                    , { light1.serial: (True, {"presence": True, "label": "bob"})
                      , light2.serial: (False, {"presence": True})
                      }
                    )

        @mlr.test
        async it "does not fire for offline devices", runner:
            errors = []
            with light2.offline():
                got = await self.gather(runner, self.two_lights, "presence", "label"
                    , error_catcher = errors
                    , message_timeout = 0.1
                    , find_timeout = 0.1
                    )

                self.assertEqual(got
                    , { light1.serial: (True, {"presence": True, "label": "bob"})
                      }
                    )

    describe "AddressPlan":
        @mlr.test
        async it "gets the address", runner:
            got = await self.gather(runner, self.two_lights, "label", "address")
            self.assertEqual(got
                , { light1.serial: (True, {"label": "bob", "address": (f"fake://{light1.serial}/memory", 56700)})
                  , light2.serial: (True, {"label": "sam", "address": (f"fake://{light2.serial}/memory", 56700)})
                  }
                )

        @mlr.test
        async it "requires atleast one other plan", runner:
            got = await self.gather(runner, self.two_lights, "address")
            self.assertEqual(got, {})

    describe "LabelPlan":
        @mlr.test
        async it "gets the label", runner:
            got = await self.gather(runner, self.two_lights, "label")
            self.assertEqual(got
                , { light1.serial: (True, {"label": "bob"})
                  , light2.serial: (True, {"label": "sam"})
                  }
                )

    describe "StatePlan":
        @mlr.test
        async it "gets the power", runner:
            state1 = {
                  'hue': 99.9990844586862
                , 'saturation': 0.49999237048905165
                , 'brightness': 0.49999237048905165
                , 'kelvin': 4500

                , 'label': 'bob'
                , 'power': 0

                , 'reserved6': b'\x00\x00'
                , 'reserved7': b'\x00\x00\x00\x00\x00\x00\x00\x00'
                }

            state2 = {
                  'hue': 199.9981689173724
                , 'saturation': 0.29999237048905164
                , 'brightness': 1.0
                , 'kelvin': 9000

                , 'label': 'sam'
                , 'power': 65535

                , 'reserved6': b'\x00\x00'
                , 'reserved7': b'\x00\x00\x00\x00\x00\x00\x00\x00'
                }

            got = await self.gather(runner, self.two_lights, "state")
            self.assertEqual(got
                , { light1.serial: (True, {"state": state1})
                  , light2.serial: (True, {"state": state2})
                  }
                )

    describe "PowerPlan":
        @mlr.test
        async it "gets the power", runner:
            got = await self.gather(runner, self.two_lights, "power")
            self.assertEqual(got
                , { light1.serial: (True, {"power": {"level": 0, "on": False}})
                  , light2.serial: (True, {"power": {"level": 65535, "on": True}})
                  }
                )

    describe "CapabilityPlan":
        @mlr.test
        async it "gets the power", runner:
            l1c = {"cap": capability_for_ids(55, 1), "has_extended_multizone": False, "product": enum_for_ids(55, 1)}
            l2c = {"cap": capability_for_ids(1, 1), "has_extended_multizone": False, "product": enum_for_ids(1, 1)}
            slcm1c = {"cap": capability_for_ids(31, 1), "has_extended_multizone": False, "product": enum_for_ids(31, 1)}
            slcm2nec = {"cap": capability_for_ids(32, 1), "has_extended_multizone": False, "product": enum_for_ids(32, 1)}
            slcm2ec = {"cap": capability_for_ids(32, 1), "has_extended_multizone": True, "product": enum_for_ids(32, 1)}

            got = await self.gather(runner, runner.serials, "capability")
            self.assertEqual(got
                , { light1.serial: (True, {"capability": l1c})
                  , light2.serial: (True, {"capability": l2c})

                  , striplcm1.serial: (True, {"capability": slcm1c})
                  , striplcm2noextended.serial: (True, {"capability": slcm2nec})
                  , striplcm2extended.serial: (True, {"capability": slcm2ec})
                  }
                )
        @mlr.test
        async it "adds unknown products to error catcher", runner:
            errors = []

            def efi(pid, vid):
                if pid == 55:
                    raise UnknownProduct(product_id=pid, vendor_id=vid)
                return enum_for_ids(pid, vid)

            with mock.patch("photons_control.planner.plans.enum_for_ids", efi):
                got = await self.gather(runner, runner.serials, "capability", error_catcher=errors)

            assert sorted(list(got)), sorted([light2, striplcm1, striplcm2noextended, striplcm2extended])
            self.assertEqual(errors, [UnknownProduct(product_id=55, vendor_id=1)])

    describe "FirmwarePlan":
        @mlr.test
        async it "gets the firmware", runner:
            empty = b'\x00\x00\x00\x00\x00\x00\x00\x00'
            l1c = {"build": 1548977726000000000, "reserved6": empty, "version_major": 3, "version_minor": 50}
            l2c = {"build": 1448861477000000000, "reserved6": empty, "version_major": 2, "version_minor": 2}
            slcm1c = {"build": 1502237570000000000, "reserved6": empty, "version_major": 1, "version_minor": 22}
            slcm2nec = {"build": 1508122125000000000, "reserved6": empty, "version_major": 2, "version_minor": 70}
            slcm2ec = {"build": 1543215651000000000, "reserved6": empty, "version_major": 2, "version_minor": 77}

            got = await self.gather(runner, runner.serials, "firmware")
            self.assertEqual(got
                , { light1.serial: (True, {"firmware": l1c})
                  , light2.serial: (True, {"firmware": l2c})

                  , striplcm1.serial: (True, {"firmware": slcm1c})
                  , striplcm2noextended.serial: (True, {"firmware": slcm2nec})
                  , striplcm2extended.serial: (True, {"firmware": slcm2ec})
                  }
                )

    describe "VersionPlan":
        @mlr.test
        async it "gets the version", runner:
            got = await self.gather(runner, runner.serials, "version")
            self.assertEqual(got
                , { light1.serial: (True, {"version": {"product": 55, "vendor": 1, "version": 0}})
                  , light2.serial: (True, {"version": {"product": 1, "vendor": 1, "version": 0}})

                  , striplcm1.serial: (True, {"version": {"product": 31, "vendor": 1, "version": 0}})
                  , striplcm2noextended.serial: (True, {"version": {"product": 32, "vendor": 1, "version": 0}})
                  , striplcm2extended.serial: (True, {"version": {"product": 32, "vendor": 1, "version": 0}})
                  }
                )

    describe "ZonesPlan":
        @mlr.test
        async it "gets zones", runner:
            got = await self.gather(runner, runner.serials, "zones")
            expected = {
                    light1.serial: (True, {"zones": Skip})
                  , light2.serial: (True, {"zones": Skip})

                  , striplcm1.serial: (True, {"zones": [(i, chp.HSBKClose(z.as_dict())) for i, z in enumerate(zones1)]})
                  , striplcm2noextended.serial: (True, {"zones": [(i, chp.HSBKClose(z.as_dict())) for i, z in enumerate(zones2)]})
                  , striplcm2extended.serial: (True, {"zones": [(i, chp.HSBKClose(z.as_dict())) for i, z in enumerate(zones3)]})
                  }
            self.assertEqual(got, expected)

            expected = {
                  light1:
                  [ DeviceMessages.GetHostFirmware()
                  , DeviceMessages.GetVersion()
                  ]
                , light2:
                  [ DeviceMessages.GetHostFirmware()
                  , DeviceMessages.GetVersion()
                  ]
                , striplcm1:
                  [ DeviceMessages.GetHostFirmware()
                  , DeviceMessages.GetVersion()
                  , MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
                  ]
                , striplcm2noextended:
                  [ DeviceMessages.GetHostFirmware()
                  , DeviceMessages.GetVersion()
                  , MultiZoneMessages.GetColorZones(start_index=0, end_index=255)
                  ]
                , striplcm2extended:
                  [ DeviceMessages.GetHostFirmware()
                  , DeviceMessages.GetVersion()
                  , MultiZoneMessages.GetExtendedColorZones()
                  ]
                }

            for device in runner.devices:
                if device not in expected:
                    assert False, f"No expectation for {device.serial}"

                device.compare_received(expected[device])

    describe "FirmwareEffectsPlan":
        @mlr.test
        async it "gets firmware effects", runner:
            light1.set_reply(TileMessages.GetTileEffect
                , TileMessages.StateTileEffect.empty_normalise(
                      type = TileEffectType.FLAME
                    , speed = 10
                    , duration = 1
                    , palette_count = 2
                    , palette = [chp.Color(120, 1, 1, 3500).as_dict(), chp.Color(360, 1, 1, 3500).as_dict()]
                    )
                )

            striplcm1.set_reply(MultiZoneMessages.GetMultiZoneEffect
                , MultiZoneMessages.StateMultiZoneEffect.empty_normalise(
                      type = MultiZoneEffectType.MOVE
                    , speed = 5
                    , duration = 2
                    , parameters  = {"speed_direction": Direction.LEFT}
                    )
                )

            l1 = {
                  "type": TileEffectType.FLAME
                , "options":
                  { "duration": 1
                  , 'palette':
                    [ {'brightness': 1.0, 'hue': 120.0, 'kelvin': 3500, 'saturation': 1.0}
                    , {'brightness': 1.0, 'hue': 360.0, 'kelvin': 3500, 'saturation': 1.0}
                    ]
                  , 'speed': 10.0
                  , 'instanceid': mock.ANY
                  }
                }

            slcm1 = {
                  "type": MultiZoneEffectType.MOVE
                , "options":
                  { 'duration': 2
                  , 'speed': 5.0
                  , 'speed_direction': Direction.LEFT
                  , 'instanceid': mock.ANY
                  }
                }

            serials = [light1.serial, light2.serial, striplcm1.serial]
            got = await self.gather(runner, serials, "firmware_effects")
            expected =  {
                    light1.serial: (True, {"firmware_effects": l1})
                  , light2.serial: (True, {"firmware_effects": Skip})
                  , striplcm1.serial: (True, {"firmware_effects": slcm1})
                  }
            self.assertEqual(got, expected)

            expected = {
                  light1:
                  [ DeviceMessages.GetHostFirmware()
                  , DeviceMessages.GetVersion()
                  , TileMessages.GetTileEffect()
                  ]
                , light2:
                  [ DeviceMessages.GetHostFirmware()
                  , DeviceMessages.GetVersion()
                  ]
                , striplcm1:
                  [ DeviceMessages.GetHostFirmware()
                  , DeviceMessages.GetVersion()
                  , MultiZoneMessages.GetMultiZoneEffect()
                  ]
                }

            for device, e in expected.items():
                device.compare_received(e)
