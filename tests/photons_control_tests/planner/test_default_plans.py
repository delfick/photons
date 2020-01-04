# coding: spec

from photons_control.planner import Gatherer, make_plans, Skip
from photons_control import test_helpers as chp

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut
from photons_app.test_helpers import AsyncTestCase

from photons_messages import (
    DeviceMessages,
    LightMessages,
    MultiZoneMessages,
    TileMessages,
    TileEffectType,
    MultiZoneEffectType,
    Direction,
)
from photons_control.orientation import Orientation
from photons_transport.fake import FakeDevice
from photons_products import Products

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import uuid
import json

zones1 = [chp.Color(i, 1, 1, 3500) for i in range(30)]
zones2 = [chp.Color(60 - i, 1, 1, 6500) for i in range(20)]
zones3 = [chp.Color(90 - i, 1, 1, 9000) for i in range(40)]

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
            self.assertEqual(
                got,
                {
                    light1.serial: (True, {"presence": True}),
                    light2.serial: (True, {"presence": True}),
                },
            )

        @mlr.test
        async it "allows us to get serials that otherwise wouldn't", runner:
            errors = []
            with light2.no_replies_for(DeviceMessages.GetLabel):
                got = await self.gather(
                    runner,
                    self.two_lights,
                    "presence",
                    "label",
                    error_catcher=errors,
                    message_timeout=0.1,
                    find_timeout=0.1,
                )

                self.assertEqual(
                    got,
                    {
                        light1.serial: (True, {"presence": True, "label": "bob"}),
                        light2.serial: (False, {"presence": True}),
                    },
                )

        @mlr.test
        async it "does not fire for offline devices", runner:
            errors = []
            with light2.offline():
                got = await self.gather(
                    runner,
                    self.two_lights,
                    "presence",
                    "label",
                    error_catcher=errors,
                    message_timeout=0.1,
                    find_timeout=0.1,
                )

                self.assertEqual(got, {light1.serial: (True, {"presence": True, "label": "bob"})})

    describe "AddressPlan":

        @mlr.test
        async it "gets the address", runner:
            got = await self.gather(runner, self.two_lights, "label", "address")
            self.assertEqual(
                got,
                {
                    light1.serial: (
                        True,
                        {"label": "bob", "address": (f"fake://{light1.serial}/memory", 56700)},
                    ),
                    light2.serial: (
                        True,
                        {"label": "sam", "address": (f"fake://{light2.serial}/memory", 56700)},
                    ),
                },
            )

        @mlr.test
        async it "requires atleast one other plan", runner:
            got = await self.gather(runner, self.two_lights, "address")
            self.assertEqual(got, {})

    describe "LabelPlan":

        @mlr.test
        async it "gets the label", runner:
            got = await self.gather(runner, self.two_lights, "label")
            self.assertEqual(
                got,
                {light1.serial: (True, {"label": "bob"}), light2.serial: (True, {"label": "sam"})},
            )

    describe "StatePlan":

        @mlr.test
        async it "gets the power", runner:
            state1 = {
                "hue": 99.9990844586862,
                "saturation": 0.49999237048905165,
                "brightness": 0.49999237048905165,
                "kelvin": 4500,
                "label": "bob",
                "power": 0,
                "reserved6": b"\x00\x00",
                "reserved7": b"\x00\x00\x00\x00\x00\x00\x00\x00",
            }

            state2 = {
                "hue": 199.9981689173724,
                "saturation": 0.29999237048905164,
                "brightness": 1.0,
                "kelvin": 9000,
                "label": "sam",
                "power": 65535,
                "reserved6": b"\x00\x00",
                "reserved7": b"\x00\x00\x00\x00\x00\x00\x00\x00",
            }

            got = await self.gather(runner, self.two_lights, "state")
            self.assertEqual(
                got,
                {
                    light1.serial: (True, {"state": state1}),
                    light2.serial: (True, {"state": state2}),
                },
            )

    describe "PowerPlan":

        @mlr.test
        async it "gets the power", runner:
            got = await self.gather(runner, self.two_lights, "power")
            self.assertEqual(
                got,
                {
                    light1.serial: (True, {"power": {"level": 0, "on": False}}),
                    light2.serial: (True, {"power": {"level": 65535, "on": True}}),
                },
            )

    describe "CapabilityPlan":

        @mlr.test
        async it "gets the power", runner:
            l1c = {"cap": Products.LCM3_TILE.cap(3, 50), "product": Products.LCM3_TILE}
            l2c = {"cap": Products.LMB_MESH_A21.cap(2, 2), "product": Products.LMB_MESH_A21}
            slcm1c = {"cap": Products.LCM1_Z.cap(1, 22), "product": Products.LCM1_Z}
            slcm2nec = {"cap": Products.LCM2_Z.cap(2, 70), "product": Products.LCM2_Z}
            slcm2ec = {"cap": Products.LCM2_Z.cap(2, 77), "product": Products.LCM2_Z}

            got = await self.gather(runner, runner.serials, "capability")
            self.assertEqual(
                got,
                {
                    light1.serial: (True, {"capability": l1c}),
                    light2.serial: (True, {"capability": l2c}),
                    striplcm1.serial: (True, {"capability": slcm1c}),
                    striplcm2noextended.serial: (True, {"capability": slcm2nec}),
                    striplcm2extended.serial: (True, {"capability": slcm2ec}),
                },
            )

            for serial, (_, info) in got.items():
                if serial == striplcm2extended.serial:
                    assert info["capability"]["cap"].has_extended_multizone
                else:
                    assert not info["capability"]["cap"].has_extended_multizone

    describe "FirmwarePlan":

        @mlr.test
        async it "gets the firmware", runner:
            empty = b"\x00\x00\x00\x00\x00\x00\x00\x00"
            l1c = {
                "build": 1548977726000000000,
                "reserved6": empty,
                "version_major": 3,
                "version_minor": 50,
            }
            l2c = {
                "build": 1448861477000000000,
                "reserved6": empty,
                "version_major": 2,
                "version_minor": 2,
            }
            slcm1c = {
                "build": 1502237570000000000,
                "reserved6": empty,
                "version_major": 1,
                "version_minor": 22,
            }
            slcm2nec = {
                "build": 1508122125000000000,
                "reserved6": empty,
                "version_major": 2,
                "version_minor": 70,
            }
            slcm2ec = {
                "build": 1543215651000000000,
                "reserved6": empty,
                "version_major": 2,
                "version_minor": 77,
            }

            got = await self.gather(runner, runner.serials, "firmware")
            self.assertEqual(
                got,
                {
                    light1.serial: (True, {"firmware": l1c}),
                    light2.serial: (True, {"firmware": l2c}),
                    striplcm1.serial: (True, {"firmware": slcm1c}),
                    striplcm2noextended.serial: (True, {"firmware": slcm2nec}),
                    striplcm2extended.serial: (True, {"firmware": slcm2ec}),
                },
            )

    describe "VersionPlan":

        @mlr.test
        async it "gets the version", runner:
            got = await self.gather(runner, runner.serials, "version")
            self.assertEqual(
                got,
                {
                    light1.serial: (True, {"version": {"product": 55, "vendor": 1, "version": 0}}),
                    light2.serial: (True, {"version": {"product": 1, "vendor": 1, "version": 0}}),
                    striplcm1.serial: (
                        True,
                        {"version": {"product": 31, "vendor": 1, "version": 0}},
                    ),
                    striplcm2noextended.serial: (
                        True,
                        {"version": {"product": 32, "vendor": 1, "version": 0}},
                    ),
                    striplcm2extended.serial: (
                        True,
                        {"version": {"product": 32, "vendor": 1, "version": 0}},
                    ),
                },
            )

    describe "ZonesPlan":

        @mlr.test
        async it "gets zones", runner:
            got = await self.gather(runner, runner.serials, "zones")
            expected = {
                light1.serial: (True, {"zones": Skip}),
                light2.serial: (True, {"zones": Skip}),
                striplcm1.serial: (True, {"zones": [(i, c) for i, c in enumerate(zones1)]}),
                striplcm2noextended.serial: (
                    True,
                    {"zones": [(i, c) for i, c in enumerate(zones2)]},
                ),
                striplcm2extended.serial: (True, {"zones": [(i, c) for i, c in enumerate(zones3)]}),
            }
            self.assertEqual(got, expected)

            expected = {
                light1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                striplcm1: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=255),
                ],
                striplcm2noextended: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=255),
                ],
                striplcm2extended: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    MultiZoneMessages.GetExtendedColorZones(),
                ],
            }

            for device in runner.devices:
                if device not in expected:
                    assert False, f"No expectation for {device.serial}"

                device.compare_received(expected[device])

    describe "ChainPlan":

        @mlr.test
        async it "gets tile information", runner:
            got = await self.gather(runner, runner.serials, "chain")

            class Partial:
                def __init__(s, item):
                    s.item = item

                def __eq__(s, other):
                    other = {k: other[k] for k in s.item}

                    if s.item != other:
                        print("Want", json.dumps(s.item))
                        print("=====")
                        print("Got", json.dumps(other))
                        self.assertEqual(other, s.item)

                    return s.item == other

            chain = [
                Partial(
                    {
                        "accel_meas_x": 0,
                        "accel_meas_y": 0,
                        "accel_meas_z": 0,
                        "device_version_product": 55,
                        "device_version_vendor": 1,
                        "device_version_version": 0,
                        "firmware_build": 0,
                        "firmware_version_major": 3,
                        "firmware_version_minor": 50,
                        "height": 8,
                        "user_x": 0,
                        "user_y": 0,
                        "width": 8,
                    }
                ),
                Partial(
                    {
                        "accel_meas_x": 0,
                        "accel_meas_y": 0,
                        "accel_meas_z": 0,
                        "device_version_product": 55,
                        "device_version_vendor": 1,
                        "device_version_version": 0,
                        "firmware_build": 0,
                        "firmware_version_major": 3,
                        "firmware_version_minor": 50,
                        "height": 8,
                        "user_x": 0,
                        "user_y": 0,
                        "width": 8,
                    }
                ),
                Partial(
                    {
                        "accel_meas_x": 0,
                        "accel_meas_y": 0,
                        "accel_meas_z": 0,
                        "device_version_product": 55,
                        "device_version_vendor": 1,
                        "device_version_version": 0,
                        "firmware_build": 0,
                        "firmware_version_major": 3,
                        "firmware_version_minor": 50,
                        "height": 8,
                        "user_x": 0,
                        "user_y": 0,
                        "width": 8,
                    }
                ),
                Partial(
                    {
                        "accel_meas_x": 0,
                        "accel_meas_y": 0,
                        "accel_meas_z": 0,
                        "device_version_product": 55,
                        "device_version_vendor": 1,
                        "device_version_version": 0,
                        "firmware_build": 0,
                        "firmware_version_major": 3,
                        "firmware_version_minor": 50,
                        "height": 8,
                        "user_x": 0,
                        "user_y": 0,
                        "width": 8,
                    }
                ),
                Partial(
                    {
                        "accel_meas_x": 0,
                        "accel_meas_y": 0,
                        "accel_meas_z": 0,
                        "device_version_product": 55,
                        "device_version_vendor": 1,
                        "device_version_version": 0,
                        "firmware_build": 0,
                        "firmware_version_major": 3,
                        "firmware_version_minor": 50,
                        "height": 8,
                        "user_x": 0,
                        "user_y": 0,
                        "width": 8,
                    }
                ),
            ]

            orientations = {
                0: Orientation.RightSideUp,
                1: Orientation.RightSideUp,
                2: Orientation.RightSideUp,
                3: Orientation.RightSideUp,
                4: Orientation.RightSideUp,
            }

            expected = {
                light1.serial: (True, {"chain": {"chain": chain, "orientations": orientations}}),
                light2.serial: (True, {"chain": Skip}),
                striplcm1.serial: (True, {"chain": Skip}),
                striplcm2noextended.serial: (True, {"chain": Skip}),
                striplcm2extended.serial: (True, {"chain": Skip}),
            }
            self.assertEqual(got, expected)

            expected = {
                light1: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    TileMessages.GetDeviceChain(),
                ],
                light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                striplcm1: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion(),],
                striplcm2noextended: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                ],
                striplcm2extended: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion(),],
            }

            for device in runner.devices:
                if device not in expected:
                    assert False, f"No expectation for {device.serial}"

                device.compare_received(expected[device])

    describe "FirmwareEffectsPlan":

        @mlr.test
        async it "gets firmware effects", runner:
            light1.set_reply(
                TileMessages.GetTileEffect,
                TileMessages.StateTileEffect.empty_normalise(
                    type=TileEffectType.FLAME,
                    speed=10,
                    duration=1,
                    palette_count=2,
                    palette=[chp.Color(120, 1, 1, 3500), chp.Color(360, 1, 1, 3500)],
                ),
            )

            striplcm1.set_reply(
                MultiZoneMessages.GetMultiZoneEffect,
                MultiZoneMessages.StateMultiZoneEffect.empty_normalise(
                    type=MultiZoneEffectType.MOVE,
                    speed=5,
                    duration=2,
                    parameters={"speed_direction": Direction.LEFT},
                ),
            )

            l1 = {
                "type": TileEffectType.FLAME,
                "options": {
                    "duration": 1,
                    "palette": [chp.Color(120, 1, 1, 3500), chp.Color(360, 1, 1, 3500)],
                    "speed": 10.0,
                    "instanceid": mock.ANY,
                },
            }

            slcm1 = {
                "type": MultiZoneEffectType.MOVE,
                "options": {
                    "duration": 2,
                    "speed": 5.0,
                    "speed_direction": Direction.LEFT,
                    "instanceid": mock.ANY,
                },
            }

            serials = [light1.serial, light2.serial, striplcm1.serial]
            got = await self.gather(runner, serials, "firmware_effects")
            expected = {
                light1.serial: (True, {"firmware_effects": l1}),
                light2.serial: (True, {"firmware_effects": Skip}),
                striplcm1.serial: (True, {"firmware_effects": slcm1}),
            }
            self.assertEqual(got, expected)

            expected = {
                light1: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    TileMessages.GetTileEffect(),
                ],
                light2: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                striplcm1: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    MultiZoneMessages.GetMultiZoneEffect(),
                ],
            }

            for device, e in expected.items():
                device.compare_received(e)
