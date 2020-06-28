# coding: spec

from photons_control.planner import Skip, PacketPlan
from photons_control import test_helpers as chp

from photons_app.test_helpers import assert_payloads_equals, print_packet_difference
from photons_app.special import FoundSerials

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
from photons_canvas.points import containers as cont
from photons_transport.fake import FakeDevice
from photons_canvas import orientation as co
from photons_messages.fields import Color
from photons_products import Products

from unittest import mock
import pytest


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
        if s.equal:
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
two_lights = [light1.serial, light2.serial]


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner(lights) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


describe "Default Plans":

    async def gather(self, runner, reference, *by_label, **kwargs):
        plan_args = []
        plan_kwargs = {}
        for thing in by_label:
            if isinstance(thing, str):
                plan_args.append(thing)
            else:
                plan_kwargs.update(thing)
        plans = runner.sender.make_plans(*plan_args, **plan_kwargs)
        return dict(await runner.sender.gatherer.gather_all(plans, reference, **kwargs))

    describe "PacketPlan":

        async it "gets the packet", runner:
            plan = PacketPlan(DeviceMessages.GetPower(), DeviceMessages.StatePower)
            got = await self.gather(runner, two_lights, {"result": plan})
            assert got == {
                light1.serial: (True, {"result": mock.ANY}),
                light2.serial: (True, {"result": mock.ANY}),
            }

            print_packet_difference(
                got[light1.serial][1]["result"], DeviceMessages.StatePower(level=0)
            )
            print_packet_difference(
                got[light2.serial][1]["result"], DeviceMessages.StatePower(level=65535)
            )

        async it "fails if we can't get the correct response", runner:
            plan = PacketPlan(DeviceMessages.GetPower(), DeviceMessages.StateLabel)
            got = await self.gather(runner, two_lights, {"result": plan})
            assert got == {}

    describe "PresencePlan":

        async it "returns True", runner:
            got = await self.gather(runner, two_lights, "presence")
            assert got == {
                light1.serial: (True, {"presence": True}),
                light2.serial: (True, {"presence": True}),
            }

        async it "allows us to get serials that otherwise wouldn't", runner:
            errors = []
            with light2.no_replies_for(DeviceMessages.GetLabel):
                got = await self.gather(
                    runner,
                    two_lights,
                    "presence",
                    "label",
                    error_catcher=errors,
                    message_timeout=0.1,
                    find_timeout=0.1,
                )

                assert got == {
                    light1.serial: (True, {"presence": True, "label": "bob"}),
                    light2.serial: (False, {"presence": True}),
                }

        async it "fires for offline devices that have already been discovered", runner:
            errors = []
            _, serials = await FoundSerials().find(runner.sender, timeout=1)
            assert all(serial in serials for serial in two_lights)

            with light2.offline():
                got = await self.gather(
                    runner,
                    two_lights,
                    "presence",
                    "label",
                    error_catcher=errors,
                    message_timeout=0.1,
                    find_timeout=0.1,
                )

                assert got == {
                    light1.serial: (True, {"presence": True, "label": "bob"}),
                    light2.serial: (False, {"presence": True}),
                }

        async it "does not fire for devices that don't exist", runner:
            errors = []

            for serial in two_lights:
                await runner.sender.forget(serial)

            with light2.offline():
                got = await self.gather(
                    runner,
                    two_lights,
                    "presence",
                    "label",
                    error_catcher=errors,
                    message_timeout=0.1,
                    find_timeout=0.1,
                )

                assert got == {light1.serial: (True, {"presence": True, "label": "bob"})}

    describe "AddressPlan":

        async it "gets the address", runner:
            got = await self.gather(runner, two_lights, "address")
            assert got == {
                light1.serial: (True, {"address": (f"fake://{light1.serial}/memory", 56700)}),
                light2.serial: (True, {"address": (f"fake://{light2.serial}/memory", 56700)}),
            }

    describe "LabelPlan":

        async it "gets the label", runner:
            got = await self.gather(runner, two_lights, "label")
            assert got == {
                light1.serial: (True, {"label": "bob"}),
                light2.serial: (True, {"label": "sam"}),
            }

    describe "StatePlan":

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

            got = await self.gather(runner, two_lights, "state")
            assert got == {
                light1.serial: (True, {"state": state1}),
                light2.serial: (True, {"state": state2}),
            }

    describe "PowerPlan":

        async it "gets the power", runner:
            got = await self.gather(runner, two_lights, "power")
            assert got == {
                light1.serial: (True, {"power": {"level": 0, "on": False}}),
                light2.serial: (True, {"power": {"level": 65535, "on": True}}),
            }

    describe "CapabilityPlan":

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
            assert got == {
                light1.serial: (True, {"capability": l1c}),
                light2.serial: (True, {"capability": l2c}),
                striplcm1.serial: (True, {"capability": slcm1c}),
                striplcm2noextended.serial: (True, {"capability": slcm2nec}),
                striplcm2extended.serial: (True, {"capability": slcm2ec}),
            }

            for serial, (_, info) in got.items():
                if serial == striplcm2extended.serial:
                    assert info["capability"]["cap"].has_extended_multizone
                else:
                    assert not info["capability"]["cap"].has_extended_multizone

    describe "FirmwarePlan":

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
            assert got == {
                light1.serial: (True, {"firmware": l1c}),
                light2.serial: (True, {"firmware": l2c}),
                striplcm1.serial: (True, {"firmware": slcm1c}),
                striplcm2noextended.serial: (True, {"firmware": slcm2nec}),
                striplcm2extended.serial: (True, {"firmware": slcm2ec}),
            }

    describe "VersionPlan":

        async it "gets the version", runner:
            got = await self.gather(runner, runner.serials, "version")
            assert got == {
                light1.serial: (True, {"version": {"product": 55, "vendor": 1, "version": 0}}),
                light2.serial: (True, {"version": {"product": 1, "vendor": 1, "version": 0}}),
                striplcm1.serial: (True, {"version": {"product": 31, "vendor": 1, "version": 0}},),
                striplcm2noextended.serial: (
                    True,
                    {"version": {"product": 32, "vendor": 1, "version": 0}},
                ),
                striplcm2extended.serial: (
                    True,
                    {"version": {"product": 32, "vendor": 1, "version": 0}},
                ),
            }

    describe "ZonesPlan":

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
            assert got == expected

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

        async it "gets colors for different devices", runner:
            serials = [light1.serial, light2.serial, striplcm1.serial, striplcm2extended.serial]

            expectedlcm1 = []
            expectedlcm2 = []
            for ex, strip in [(expectedlcm1, striplcm1), (expectedlcm2, striplcm2extended)]:
                for i, z in enumerate(strip.attrs.zones):
                    z.hue = i
                    ex.append(chp.Color(i, z.saturation, z.brightness, z.kelvin))

            assert len(expectedlcm1) == 30
            assert len(expectedlcm2) == 40

            tile_expected = []
            for i in range(len(light1.attrs.chain)):
                for j in range(64):
                    light1.attrs.chain[i][1][j].hue = i + j
                tile_expected.append(list(light1.attrs.chain[i][1]))

            light2.attrs.color = chp.Color(100, 0.5, 0.8, 2500)

            got = await self.gather(runner, serials, "colors")

            assert got[light1.serial][1]["colors"] == tile_expected
            assert got[light2.serial][1]["colors"] == [[chp.Color(100, 0.5, 0.8, 2500)]]
            assert got[striplcm1.serial][1]["colors"] == [expectedlcm1]
            assert got[striplcm2extended.serial][1]["colors"] == [expectedlcm2]

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

    describe "PartsPlan":
        async it "works for a bulb", runner:
            got = await self.gather(runner, [light2.serial], "parts")
            info = got[light2.serial][1]["parts"]

            assert len(info) == 1
            part = info[0]

            assert part is not part.real_part
            for p in (part, part.real_part):
                assert isinstance(p, cont.Part)

                assert p.part_number == 0
                assert p.device.serial == light2.serial
                assert p.device.cap == chp.ProductResponder.capability(light2)

                assert p.orientation is co.Orientation.RightSideUp
                assert p.bounds == ((0, 1), (0, -1), (1, 1))

                assert p.original_colors is None

            with_colors = await self.gather(runner, [light2.serial], "parts_and_colors")
            info = with_colors[light2.serial][1]["parts_and_colors"]

            assert len(info) == 1
            pc = info[0]

            c = light2.attrs.color
            color = (c.hue, c.saturation, c.brightness, c.kelvin)

            assert pc is part
            assert pc.original_colors == [color]
            assert pc.real_part.original_colors == [color]

        async it "works for a not extended multizone", runner:
            for device, colors in ((striplcm1, zones1), (striplcm2noextended, zones2)):
                got = await self.gather(runner, [device.serial], "parts")
                info = got[device.serial][1]["parts"]

                assert len(info) == 1
                part = info[0]

                assert part is not part.real_part
                for p in (part, part.real_part):
                    assert isinstance(p, cont.Part)

                    assert p.part_number == 0
                    assert p.device.serial == device.serial
                    assert p.device.cap == chp.ProductResponder.capability(device)
                    assert p.device.cap.has_multizone
                    assert not p.device.cap.has_extended_multizone

                    assert p.orientation is co.Orientation.RightSideUp
                    assert p.bounds == (
                        (0, len(device.attrs.zones)),
                        (0, -1),
                        (len(device.attrs.zones), 1),
                    )

                    assert p.original_colors is None

                with_colors = await self.gather(runner, [device.serial], "parts_and_colors")
                info = with_colors[device.serial][1]["parts_and_colors"]

                assert len(info) == 1
                pc = info[0]

                colors = [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors]

                assert pc is part
                assert pc.original_colors == colors
                assert pc.real_part.original_colors == colors

        async it "works for an extended multizone", runner:
            device = striplcm2extended
            colors = zones3

            got = await self.gather(runner, [device.serial], "parts")
            info = got[device.serial][1]["parts"]

            assert len(info) == 1
            part = info[0]

            assert part is not part.real_part
            for p in (part, part.real_part):
                assert isinstance(p, cont.Part)

                assert p.part_number == 0
                assert p.device.serial == device.serial
                assert p.device.cap == chp.ProductResponder.capability(device)
                assert p.device.cap.has_multizone
                assert p.device.cap.has_extended_multizone

                assert p.orientation is co.Orientation.RightSideUp
                assert p.bounds == (
                    (0, len(device.attrs.zones)),
                    (0, -1),
                    (len(device.attrs.zones), 1),
                )

                assert p.original_colors is None

            with_colors = await self.gather(runner, [device.serial], "parts_and_colors")
            info = with_colors[device.serial][1]["parts_and_colors"]

            assert len(info) == 1
            pc = info[0]

            colors = [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors]
            assert pc is part
            assert pc.original_colors == colors
            assert pc.real_part.original_colors == colors

        async it "works for a tile set", runner:
            light1.attrs.chain = []
            await chp.MatrixResponder().start(light1)

            device = light1

            colors1 = [Color(i, 1, 1, 3500) for i in range(64)]
            colors2 = [Color(i + 100, 0, 0.4, 8000) for i in range(64)]
            colors3 = [Color(i + 200, 0.1, 0.9, 7000) for i in range(64)]

            chain = device.attrs.chain

            chain[0][0].accel_meas_x = -10
            chain[0][0].accel_meas_y = 1
            chain[0][0].accel_meas_z = 5
            chain[0][0].user_x = 3
            chain[0][0].user_y = 5

            chain[2][0].accel_meas_x = 1
            chain[2][0].accel_meas_y = 5
            chain[2][0].accel_meas_z = 10
            chain[2][0].user_x = 10
            chain[2][0].user_y = 25

            device.attrs.chain = [
                (chain[0][0], co.reorient(colors1, co.Orientation.RotatedLeft)),
                (chain[1][0], colors2),
                (chain[2][0], co.reorient(colors3, co.Orientation.FaceDown)),
            ]

            got = await self.gather(runner, [device.serial], "parts")
            info = got[device.serial][1]["parts"]

            assert len(info) == 3

            boundses = [
                ((24, 32), (40, 32), (8, 8)),
                ((0, 8), (0, -8), (8, 8)),
                ((80, 88), (200, 192), (8, 8)),
            ]

            orientations = [
                co.Orientation.RotatedLeft,
                co.Orientation.RightSideUp,
                co.Orientation.FaceDown,
            ]

            for i, (part, orientation, bounds) in enumerate(zip(info, orientations, boundses)):
                assert part is not part.real_part
                for p in (part, part.real_part):
                    assert isinstance(p, cont.Part)

                    assert p.part_number == i
                    assert p.device.serial == device.serial
                    assert p.device.cap == chp.ProductResponder.capability(device)
                    assert p.device.cap.has_chain

                    assert p.orientation is orientation
                    assert p.bounds == bounds

                    assert p.original_colors is None

            with_colors = await self.gather(runner, [device.serial], "parts_and_colors")
            infoc = with_colors[device.serial][1]["parts_and_colors"]

            for i, (pc, colors) in enumerate(zip(infoc, (colors1, colors2, colors3))):
                colors = [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors]

                assert pc is info[i]

                if pc.original_colors != colors:
                    print(f"Part {i}")
                    for j, (g, w) in enumerate(zip(pc.original_colors, colors)):
                        if g != w:
                            print(f"\tColor {j}")
                            print("\t\t", g)
                            print("\t\t", w)
                            print()

                assert pc.original_colors == colors
                assert pc.real_part.original_colors == colors

    describe "ChainPlan":

        async it "gets chain for a bulb", runner:
            got = await self.gather(runner, [light2.serial], "chain")
            info = got[light2.serial][1]["chain"]

            assert info["chain"] == [
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
            ]
            assert info["width"] == 1

            assert info["orientations"] == {0: Orientation.RightSideUp}
            assert len(info["random_orientations"]) == 1
            assert info["coords_and_sizes"] == [((0.0, 0.0), (1, 1))]

            colors = [chp.Color(200, 1, 1, 3500)]
            assert info["reorient"](0, colors) == reorient(colors, Orientation.RightSideUp)
            assert info["reverse_orient"](0, colors) == reorient(colors, Orientation.RightSideUp)

        async it "gets chain for a strip", runner:
            serials = [striplcm1.serial, striplcm2noextended.serial, striplcm2extended.serial]
            got = await self.gather(runner, serials, "chain")

            lcm1_info = got[striplcm1.serial][1]["chain"]
            assert lcm1_info["chain"] == [
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
            ]
            assert lcm1_info["width"] == 30

            striplcm2ne_info = got[striplcm2noextended.serial][1]["chain"]
            assert striplcm2ne_info["chain"] == [
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
            ]
            assert striplcm2ne_info["width"] == 20

            striplcm2_info = got[striplcm2extended.serial][1]["chain"]
            assert striplcm2_info["chain"] == [
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
            ]
            assert striplcm2_info["width"] == 40

            for _, info in got.values():
                info = info["chain"]

                assert info["orientations"] == {0: Orientation.RightSideUp}

                colors = [chp.Color(i, 1, 1, 3500) for i in range(30)]
                assert info["reorient"](0, colors) == reorient(colors, Orientation.RightSideUp)
                assert info["reverse_orient"](0, colors) == reorient(
                    colors, Orientation.RightSideUp
                )
            assert info["coords_and_sizes"] == [((0.0, 0.0), (info["width"], 1))]

        async it "gets chain for tiles", runner:
            light1.attrs.chain = []
            await chp.MatrixResponder().start(light1)

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
            assert info["chain"] == chain
            assert info["orientations"] == orientations
            assert info["width"] == 8
            assert info["coords_and_sizes"] == [
                ((0.0, 0.0), (8, 8)),
                ((3.0, 5.0), (8, 8)),
                ((0.0, 0.0), (8, 8)),
                ((10.0, 25.0), (8, 8)),
                ((0.0, 0.0), (8, 8)),
            ]

            assert len(info["random_orientations"]) == len(info["orientations"])

            colors = [chp.Color(i, 1, 1, 3500) for i in range(64)]

            assert info["reorient"](1, colors) == reorient(colors, Orientation.RotatedLeft)
            assert info["reorient"](3, colors) == reorient(colors, Orientation.FaceDown)
            assert info["reorient"](4, colors) == reorient(colors, Orientation.RightSideUp)

            # and make sure we don't fail if we randomize
            info["reorient"](1, colors, randomize=True)

            ro = info["reverse_orient"]
            assert ro(1, colors) == reorient(colors, Orientation.RotatedRight)
            assert ro(3, colors) == reorient(colors, Orientation.FaceUp)
            assert ro(4, colors) == reorient(colors, Orientation.RightSideUp)

    describe "FirmwareEffectsPlan":

        async it "gets firmware effects", runner:
            light1.set_reply(
                TileMessages.GetTileEffect,
                TileMessages.StateTileEffect.create(
                    type=TileEffectType.FLAME,
                    speed=10,
                    duration=1,
                    palette_count=2,
                    palette=[chp.Color(120, 1, 1, 3500), chp.Color(360, 1, 1, 3500)],
                ),
            )

            striplcm1.set_reply(
                MultiZoneMessages.GetMultiZoneEffect,
                MultiZoneMessages.StateMultiZoneEffect.create(
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
            assert got == expected

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
