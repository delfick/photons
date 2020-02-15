# coding: spec

from photons_control.planner import Gatherer, make_plans, Skip
from photons_control import test_helpers as chp

from photons_app.test_helpers import AsyncTestCase, assert_payloads_equals
from photons_app.errors import PhotonsAppError, RunErrors, TimedOut

from photons_messages import (
    DeviceMessages,
    LightMessages,
    MultiZoneMessages,
    TileMessages,
    TileEffectType,
    MultiZoneEffectType,
    Direction,
)
from photons_control.orientation import Orientation, reorient
from photons_transport.fake import FakeDevice
from photons_products import Products

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import uuid
import json


class Partial:
    def __init__(s, index, item):
        s.index = index
        s.item = item
        s.equal = None

    def __eq__(s, other):
        print(f"Item {s.index}")
        assert_payloads_equals(other, s.item)
        s.equal = other
        return True

    def __repr__(s):
        if self.equal:
            return repr(s.equal)
        else:
            return f"<DIFFERENT: {repr(s.item)}>"


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

setup_module = mlr.setUp
teardown_module = mlr.tearDown

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
            }

            state2 = {
                "hue": 199.9981689173724,
                "saturation": 0.29999237048905164,
                "brightness": 1.0,
                "kelvin": 9000,
                "label": "sam",
                "power": 65535,
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
            l1c = {
                "cap": Products.LCM3_TILE.cap(3, 50),
                "product": Products.LCM3_TILE,
                "firmware": {
                    "build": 1548977726000000000,
                    "version_major": 3,
                    "version_minor": 50,
                },
            }
            l2c = {
                "cap": Products.LMB_MESH_A21.cap(2, 2),
                "product": Products.LMB_MESH_A21,
                "firmware": {"build": 1448861477000000000, "version_major": 2, "version_minor": 2,},
            }
            slcm1c = {
                "cap": Products.LCM1_Z.cap(1, 22),
                "product": Products.LCM1_Z,
                "firmware": {
                    "build": 1502237570000000000,
                    "version_major": 1,
                    "version_minor": 22,
                },
            }
            slcm2nec = {
                "cap": Products.LCM2_Z.cap(2, 70),
                "product": Products.LCM2_Z,
                "firmware": {
                    "build": 1508122125000000000,
                    "version_major": 2,
                    "version_minor": 70,
                },
            }
            slcm2ec = {
                "cap": Products.LCM2_Z.cap(2, 77),
                "product": Products.LCM2_Z,
                "firmware": {
                    "build": 1543215651000000000,
                    "version_major": 2,
                    "version_minor": 77,
                },
            }

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
            l1c = {
                "build": 1548977726000000000,
                "version_major": 3,
                "version_minor": 50,
            }
            l2c = {
                "build": 1448861477000000000,
                "version_major": 2,
                "version_minor": 2,
            }
            slcm1c = {
                "build": 1502237570000000000,
                "version_major": 1,
                "version_minor": 22,
            }
            slcm2nec = {
                "build": 1508122125000000000,
                "version_major": 2,
                "version_minor": 70,
            }
            slcm2ec = {
                "build": 1543215651000000000,
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

    describe "ColorsPlan":

        @mlr.test
        async it "gets colors for different devices", runner:
            serials = [light1.serial, light2.serial, striplcm1.serial, striplcm2extended.serial]

            expectedlcm1 = []
            expectedlcm2 = []
            for ex, strip in [(expectedlcm1, striplcm1), (expectedlcm2, striplcm2extended)]:
                for i, z in enumerate(strip.attrs.zones):
                    z.hue = i
                    ex.append(chp.Color(i, z.saturation, z.brightness, z.kelvin))

            self.assertEqual(len(expectedlcm1), 30)
            self.assertEqual(len(expectedlcm2), 40)

            tile_expected = []
            for i in range(len(light1.attrs.chain)):
                for j in range(64):
                    light1.attrs.chain[i][1][j].hue = i + j
                tile_expected.append(list(light1.attrs.chain[i][1]))

            light2.attrs.color = chp.Color(100, 0.5, 0.8, 2500)

            got = await self.gather(runner, serials, "colors")

            self.assertEqual(got[light1.serial][1]["colors"], tile_expected)
            self.assertEqual(got[light2.serial][1]["colors"], [[chp.Color(100, 0.5, 0.8, 2500)]])
            self.assertEqual(got[striplcm1.serial][1]["colors"], [expectedlcm1])
            self.assertEqual(got[striplcm2extended.serial][1]["colors"], [expectedlcm2])

            expected = {
                light1: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    TileMessages.GetDeviceChain(),
                    TileMessages.Get64(length=255, tile_index=0, width=8, x=0, y=0),
                ],
                light2: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    LightMessages.GetColor(),
                ],
                striplcm1: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    MultiZoneMessages.GetColorZones(start_index=0, end_index=255),
                ],
                striplcm2noextended: [],
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
        async it "gets chain for a bulb", runner:
            got = await self.gather(runner, [light2.serial], "chain")
            info = got[light2.serial][1]["chain"]

            self.assertEqual(
                info["chain"],
                [
                    Partial(
                        0,
                        {
                            "accel_meas_x": 0,
                            "accel_meas_y": 0,
                            "accel_meas_z": 0,
                            "device_version_product": 1,
                            "device_version_vendor": 1,
                            "device_version_version": 0,
                            "firmware_build": 1448861477000000000,
                            "firmware_version_major": 2,
                            "firmware_version_minor": 2,
                            "height": 1,
                            "user_x": 0,
                            "user_y": 0,
                            "width": 1,
                        },
                    ),
                ],
            )
            self.assertEqual(info["width"], 1)

            self.assertEqual(info["orientations"], {0: Orientation.RightSideUp})
            self.assertEqual(len(info["random_orientations"]), 1)
            self.assertEqual(info["coords_and_sizes"], [((0.0, 0.0), (1, 1))])

            colors = [chp.Color(200, 1, 1, 3500)]
            self.assertEqual(info["reorient"](0, colors), reorient(colors, Orientation.RightSideUp))
            self.assertEqual(
                info["reverse_orient"](0, colors), reorient(colors, Orientation.RightSideUp)
            )

        @mlr.test
        async it "gets chain for a strip", runner:
            serials = [striplcm1.serial, striplcm2noextended.serial, striplcm2extended.serial]
            got = await self.gather(runner, serials, "chain")

            lcm1_info = got[striplcm1.serial][1]["chain"]
            self.assertEqual(
                lcm1_info["chain"],
                [
                    Partial(
                        0,
                        {
                            "accel_meas_x": 0,
                            "accel_meas_y": 0,
                            "accel_meas_z": 0,
                            "device_version_product": 31,
                            "device_version_vendor": 1,
                            "device_version_version": 0,
                            "firmware_build": 1502237570000000000,
                            "firmware_version_major": 1,
                            "firmware_version_minor": 22,
                            "height": 1,
                            "user_x": 0,
                            "user_y": 0,
                            "width": 30,
                        },
                    ),
                ],
            )
            self.assertEqual(lcm1_info["width"], 30)

            striplcm2ne_info = got[striplcm2noextended.serial][1]["chain"]
            self.assertEqual(
                striplcm2ne_info["chain"],
                [
                    Partial(
                        0,
                        {
                            "accel_meas_x": 0,
                            "accel_meas_y": 0,
                            "accel_meas_z": 0,
                            "device_version_product": 32,
                            "device_version_vendor": 1,
                            "device_version_version": 0,
                            "firmware_build": 1508122125000000000,
                            "firmware_version_major": 2,
                            "firmware_version_minor": 70,
                            "height": 1,
                            "user_x": 0,
                            "user_y": 0,
                            "width": 20,
                        },
                    ),
                ],
            )
            self.assertEqual(striplcm2ne_info["width"], 20)

            striplcm2_info = got[striplcm2extended.serial][1]["chain"]
            self.assertEqual(
                striplcm2_info["chain"],
                [
                    Partial(
                        0,
                        {
                            "accel_meas_x": 0,
                            "accel_meas_y": 0,
                            "accel_meas_z": 0,
                            "device_version_product": 32,
                            "device_version_vendor": 1,
                            "device_version_version": 0,
                            "firmware_build": 1543215651000000000,
                            "firmware_version_major": 2,
                            "firmware_version_minor": 77,
                            "height": 1,
                            "user_x": 0,
                            "user_y": 0,
                            "width": 40,
                        },
                    ),
                ],
            )
            self.assertEqual(striplcm2_info["width"], 40)

            for _, info in got.values():
                info = info["chain"]

                self.assertEqual(info["orientations"], {0: Orientation.RightSideUp})

                colors = [chp.Color(i, 1, 1, 3500) for i in range(30)]
                self.assertEqual(
                    info["reorient"](0, colors), reorient(colors, Orientation.RightSideUp)
                )
                self.assertEqual(
                    info["reverse_orient"](0, colors), reorient(colors, Orientation.RightSideUp)
                )
            self.assertEqual(info["coords_and_sizes"], [((0.0, 0.0), (info["width"], 1))])

        @mlr.test
        async it "gets chain for tiles", runner:
            chain = light1.attrs.chain

            chain[1][0].accel_meas_x = -10
            chain[1][0].accel_meas_y = 1
            chain[1][0].accel_meas_z = 5
            chain[1][0].user_x = 3
            chain[1][0].user_y = 5

            chain[3][0].accel_meas_x = 1
            chain[3][0].accel_meas_y = 5
            chain[3][0].accel_meas_z = 10
            chain[3][0].user_x = 10
            chain[3][0].user_y = 25

            got = await self.gather(runner, light1.serial, "chain")

            chain = [
                Partial(
                    0,
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
                    },
                ),
                Partial(
                    1,
                    {
                        "accel_meas_x": -10,
                        "accel_meas_y": 1,
                        "accel_meas_z": 5,
                        "device_version_product": 55,
                        "device_version_vendor": 1,
                        "device_version_version": 0,
                        "firmware_build": 0,
                        "firmware_version_major": 3,
                        "firmware_version_minor": 50,
                        "height": 8,
                        "user_x": 3,
                        "user_y": 5,
                        "width": 8,
                    },
                ),
                Partial(
                    2,
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
                    },
                ),
                Partial(
                    3,
                    {
                        "accel_meas_x": 1,
                        "accel_meas_y": 5,
                        "accel_meas_z": 10,
                        "device_version_product": 55,
                        "device_version_vendor": 1,
                        "device_version_version": 0,
                        "firmware_build": 0,
                        "firmware_version_major": 3,
                        "firmware_version_minor": 50,
                        "height": 8,
                        "user_x": 10,
                        "user_y": 25,
                        "width": 8,
                    },
                ),
                Partial(
                    4,
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
                    },
                ),
            ]

            orientations = {
                0: Orientation.RightSideUp,
                1: Orientation.RotatedLeft,
                2: Orientation.RightSideUp,
                3: Orientation.FaceDown,
                4: Orientation.RightSideUp,
            }

            expected = {
                light1: [
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetVersion(),
                    TileMessages.GetDeviceChain(),
                ],
                light2: [],
                striplcm1: [],
                striplcm2noextended: [],
                striplcm2extended: [],
            }

            for device in runner.devices:
                if device not in expected:
                    assert False, f"No expectation for {device.serial}"

                device.compare_received(expected[device])

            info = got[light1.serial][1]["chain"]
            self.assertEqual(info["chain"], chain)
            self.assertEqual(info["orientations"], orientations)
            self.assertEqual(info["width"], 8)
            self.assertEqual(
                info["coords_and_sizes"],
                [
                    ((0.0, 0.0), (8, 8)),
                    ((3.0, 5.0), (8, 8)),
                    ((0.0, 0.0), (8, 8)),
                    ((10.0, 25.0), (8, 8)),
                    ((0.0, 0.0), (8, 8)),
                ],
            )

            self.assertEqual(len(info["random_orientations"]), len(info["orientations"]))

            colors = [chp.Color(i, 1, 1, 3500) for i in range(64)]

            self.assertEqual(info["reorient"](1, colors), reorient(colors, Orientation.RotatedLeft))
            self.assertEqual(info["reorient"](3, colors), reorient(colors, Orientation.FaceDown))
            self.assertEqual(info["reorient"](4, colors), reorient(colors, Orientation.RightSideUp))

            # and make sure we don't fail if we randomize
            info["reorient"](1, colors, randomize=True)

            ro = info["reverse_orient"]
            self.assertEqual(ro(1, colors), reorient(colors, Orientation.RotatedRight))
            self.assertEqual(ro(3, colors), reorient(colors, Orientation.FaceUp))
            self.assertEqual(ro(4, colors), reorient(colors, Orientation.RightSideUp))

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
