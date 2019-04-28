# coding: spec

from photons_control.test_helpers import Device, ModuleLevelRunner, Color, HSBKClose
from photons_control.planner import Gatherer, make_plans, Skip

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut
from photons_app.test_helpers import AsyncTestCase

from photons_messages import (
      DeviceMessages, LightMessages, MultiZoneMessages, TileMessages
    , TileEffectType, MultiZoneEffectType
    , Direction
    )
from photons_products_registry import capability_for_ids

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import uuid

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
            with light2.no_reply_to(DeviceMessages.GetLabel):
                got = await self.gather(runner, self.two_lights, "presence", "label"
                    , error_catcher = errors
                    , message_timeout = 0.05
                    , find_timeout = 0.01
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
                    , message_timeout = 0.05
                    , find_timeout = 0.01
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
                , { light1.serial: (True, {"label": "bob", "address": ("127.0.0.1", light1.port)})
                  , light2.serial: (True, {"label": "sam", "address": ("127.0.0.1", light2.port)})
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
            l1c = {"cap": capability_for_ids(55, 1), "has_extended_multizone": False}
            l2c = {"cap": capability_for_ids(1, 1), "has_extended_multizone": False}
            slcm1c = {"cap": capability_for_ids(31, 1), "has_extended_multizone": False}
            slcm2nec = {"cap": capability_for_ids(32, 1), "has_extended_multizone": False}
            slcm2ec = {"cap": capability_for_ids(32, 1), "has_extended_multizone": True}

            got = await self.gather(runner, runner.serials, "capability")
            self.assertEqual(got
                , { light1.serial: (True, {"capability": l1c})
                  , light2.serial: (True, {"capability": l2c})

                  , striplcm1.serial: (True, {"capability": slcm1c})
                  , striplcm2noextended.serial: (True, {"capability": slcm2nec})
                  , striplcm2extended.serial: (True, {"capability": slcm2ec})
                  }
                )

    describe "FirmwarePlan":
        @mlr.test
        async it "gets the power", runner:
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

    describe "ZonesPlan":
        @mlr.test
        async it "gets zones", runner:
            zones1 = [Color(i, 1, 1, 3500) for i in range(30)]
            zones2 = [Color(60 - i, 1, 1, 6500) for i in range(20)]
            zones3 = [Color(90 - i, 1, 1, 9000) for i in range(40)]

            striplcm1.change_zones(zones1)
            striplcm2noextended.change_zones(zones2)
            striplcm2extended.change_zones(zones3)

            got = await self.gather(runner, runner.serials, "zones")
            expected = {
                    light1.serial: (True, {"zones": Skip})
                  , light2.serial: (True, {"zones": Skip})

                  , striplcm1.serial: (True, {"zones": [(i, HSBKClose(z.as_dict())) for i, z in enumerate(zones1)]})
                  , striplcm2noextended.serial: (True, {"zones": [(i, HSBKClose(z.as_dict())) for i, z in enumerate(zones2)]})
                  , striplcm2extended.serial: (True, {"zones": [(i, HSBKClose(z.as_dict())) for i, z in enumerate(zones3)]})
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
                    , palette = [Color(120, 1, 1, 3500).as_dict(), Color(360, 1, 1, 3500).as_dict()]
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
