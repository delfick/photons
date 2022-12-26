# coding: spec

from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_app.special import FoundSerials
from photons_canvas import orientation as co
from photons_canvas.orientation import Orientation, reorient
from photons_canvas.points import containers as cont
from photons_control.planner import PacketPlan, Skip
from photons_messages import (
    DeviceMessages,
    Direction,
    LightLastHevCycleResult,
    LightMessages,
    MultiZoneEffectType,
    MultiZoneMessages,
    TileEffectType,
    TileMessages,
)
from photons_messages.fields import Color
from photons_products import Products


class Match:
    def __init__(self, against):
        self.against = against

    def __eq__(self, other):
        Empty = type("Empty", (), {})
        return all(other.get(k, Empty) == self.against[k] for k in self.against)

    def __repr__(self):
        return repr(self.against)


class Partial:
    def __init__(s, index, item):
        s.index = index
        s.item = item
        s.equal = None

    def __eq__(s, other):
        print(f"Item {s.index}")
        pytest.helpers.assertPayloadsEquals(other, s.item, allow_missing=True)
        s.equal = other
        return True

    def __repr__(s):
        if s.equal:
            return repr(s.equal)
        else:
            return f"<DIFFERENT: {repr(s.item)}>"


zones1 = [hp.Color(i, 1, 1, 3500) for i in range(30)]
zones2 = [hp.Color(60 - i, 1, 1, 6500) for i in range(20)]
zones3 = [hp.Color(90 - i, 1, 1, 9000) for i in range(40)]

devices = pytest.helpers.mimic()

light1 = devices.add("light1")(
    next(devices.serial_seq),
    Products.LCM3_TILE,
    hp.Firmware(3, 50),
    value_store=dict(
        power=0,
        label="bob",
        infrared=100,
        color=hp.Color(100, 0.5, 0.5, 4500),
    ),
)

light2 = devices.add("light2")(
    next(devices.serial_seq),
    Products.LMB_MESH_A21,
    hp.Firmware(2, 2),
    value_store=dict(
        power=65535,
        label="sam",
        infrared=0,
        color=hp.Color(200, 0.3, 1, 9000),
    ),
)

switch = devices.add("switch")(
    next(devices.serial_seq),
    Products.LCM3_32_SWITCH_I,
    hp.Firmware(3, 90),
    value_store=dict(label="switchy"),
)

striplcm1 = devices.add("striplcm1")(
    next(devices.serial_seq),
    Products.LCM1_Z,
    hp.Firmware(1, 22),
    value_store=dict(
        power=0,
        label="lcm1-no-extended",
        zones=zones1,
    ),
)

striplcm2noextended = devices.add("striplcm2noextended")(
    next(devices.serial_seq),
    Products.LCM2_Z,
    hp.Firmware(2, 70),
    value_store=dict(
        power=0,
        label="lcm2-no-extended",
        zones=zones2,
    ),
)

striplcm2extended = devices.add("striplcm2extended")(
    next(devices.serial_seq),
    Products.LCM2_Z,
    hp.Firmware(2, 77),
    value_store=dict(
        power=0,
        label="lcm2-extended",
        zones=zones3,
    ),
)

clean = devices.add("clean")(next(devices.serial_seq), Products.LCM3_A19_CLEAN, hp.Firmware(3, 70))

two_lights = [devices["light1"].serial, devices["light2"].serial]


@pytest.fixture(scope="module")
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


@pytest.fixture(scope="module")
async def sender(final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture(autouse=True)
async def reset_devices(sender):
    for device in devices:
        await device.reset()
        devices.store(device).clear()
    sender.gatherer.clear_cache()


describe "Default Plans":

    async def gather(self, sender, reference, *by_label, **kwargs):
        plan_args = []
        plan_kwargs = {}
        for thing in by_label:
            if isinstance(thing, str):
                plan_args.append(thing)
            else:
                plan_kwargs.update(thing)
        plans = sender.make_plans(*plan_args, **plan_kwargs)
        return dict(await sender.gatherer.gather_all(plans, reference, **kwargs))

    describe "PacketPlan":

        async it "gets the packet", sender:
            plan = PacketPlan(DeviceMessages.GetPower(), DeviceMessages.StatePower)
            got = await self.gather(sender, two_lights, {"result": plan})
            assert got == {
                light1.serial: (True, {"result": mock.ANY}),
                light2.serial: (True, {"result": mock.ANY}),
            }

            pytest.helpers.print_packet_difference(
                got[light1.serial][1]["result"], DeviceMessages.StatePower(level=0)
            )
            pytest.helpers.print_packet_difference(
                got[light2.serial][1]["result"], DeviceMessages.StatePower(level=65535)
            )

        async it "fails if we can't get the correct response", sender:
            plan = PacketPlan(DeviceMessages.GetPower(), DeviceMessages.StateLabel)
            got = await self.gather(sender, two_lights, {"result": plan})
            assert got == {}

    describe "PresencePlan":

        async it "returns True", sender:
            got = await self.gather(sender, two_lights, "presence")
            assert got == {
                light1.serial: (True, {"presence": True}),
                light2.serial: (True, {"presence": True}),
            }

        async it "allows us to get serials that otherwise wouldn't", sender:
            errors = []
            lost = light2.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetLabel)
            with lost:
                got = await self.gather(
                    sender,
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

        async it "fires for offline devices that have already been discovered", sender:

            errors = []
            _, serials = await FoundSerials().find(sender, timeout=1)
            assert all(serial in serials for serial in two_lights)

            async with light2.offline():
                got = await self.gather(
                    sender,
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

        async it "does not fire for devices that don't exist", sender:
            errors = []

            for serial in two_lights:
                await sender.forget(serial)

            async with light2.offline():
                got = await self.gather(
                    sender,
                    two_lights,
                    "presence",
                    "label",
                    error_catcher=errors,
                    message_timeout=0.1,
                    find_timeout=0.1,
                )

                assert got == {light1.serial: (True, {"presence": True, "label": "bob"})}

    describe "AddressPlan":

        async it "gets the address", sender:
            got = await self.gather(sender, two_lights, "address")
            assert got == {
                light1.serial: (True, {"address": (f"fake://{light1.serial}/memory", 56700)}),
                light2.serial: (True, {"address": (f"fake://{light2.serial}/memory", 56700)}),
            }

    describe "LabelPlan":

        async it "gets the label", sender:
            got = await self.gather(sender, two_lights, "label")
            assert got == {
                light1.serial: (True, {"label": "bob"}),
                light2.serial: (True, {"label": "sam"}),
            }

    describe "StatePlan":

        async it "gets the power", sender:
            state1 = {
                "hue": light1.attrs.color.hue,
                "saturation": light1.attrs.color.saturation,
                "brightness": light1.attrs.color.brightness,
                "kelvin": light1.attrs.color.kelvin,
                "label": "bob",
                "power": 0,
            }

            state2 = {
                "hue": light2.attrs.color.hue,
                "saturation": light2.attrs.color.saturation,
                "brightness": light2.attrs.color.brightness,
                "kelvin": light2.attrs.color.kelvin,
                "label": "sam",
                "power": 65535,
            }

            got = await self.gather(sender, two_lights, "state")
            assert got == {
                light1.serial: (True, {"state": state1}),
                light2.serial: (True, {"state": state2}),
            }

    describe "PowerPlan":

        async it "gets the power", sender:
            got = await self.gather(sender, two_lights, "power")
            assert got == {
                light1.serial: (True, {"power": {"level": 0, "on": False}}),
                light2.serial: (True, {"power": {"level": 65535, "on": True}}),
            }

    describe "HevStatusPlan":

        async it "works when hev is not on", sender:
            assert not clean.attrs.clean_details.enabled
            assert clean.attrs.clean_details.last_result is LightLastHevCycleResult.NONE

            got = await self.gather(sender, [clean.serial, light1.serial], "hev_status")
            assert got == {
                light1.serial: (True, {"hev_status": Skip}),
                clean.serial: (
                    True,
                    {
                        "hev_status": {
                            "current": {"active": False},
                            "last": {"result": LightLastHevCycleResult.NONE},
                        }
                    },
                ),
            }

        async it "works when hev is on", sender, m:
            assert clean.attrs.power == 0
            await sender(LightMessages.SetHevCycle(enable=True, duration_s=20), clean.serial)
            assert clean.attrs.clean_details.enabled
            assert clean.attrs.clean_details.duration_s == 20
            assert clean.attrs.clean_details.last_result is LightLastHevCycleResult.BUSY

            got = await self.gather(sender, [clean.serial, light1.serial], "hev_status")
            assert got == {
                light1.serial: (True, {"hev_status": Skip}),
                clean.serial: (
                    True,
                    {
                        "hev_status": {
                            "current": {
                                "active": True,
                                "duration_s": 20,
                                "remaining": 20,
                                "last_power": 0,
                            },
                            "last": {"result": LightLastHevCycleResult.BUSY},
                        }
                    },
                ),
            }

            await m.add(5)

            got = await self.gather(sender, [clean.serial, light1.serial], "hev_status")
            assert got == {
                light1.serial: (True, {"hev_status": Skip}),
                clean.serial: (
                    True,
                    {
                        "hev_status": {
                            "current": {
                                "active": True,
                                "duration_s": 20,
                                "remaining": 15,
                                "last_power": 0,
                            },
                            "last": {"result": LightLastHevCycleResult.BUSY},
                        }
                    },
                ),
            }

            await m.add(17)

            got = await self.gather(sender, [clean.serial, light1.serial], "hev_status")
            assert got == {
                light1.serial: (True, {"hev_status": Skip}),
                clean.serial: (
                    True,
                    {
                        "hev_status": {
                            "current": {
                                "active": False,
                            },
                            "last": {"result": LightLastHevCycleResult.SUCCESS},
                        }
                    },
                ),
            }

        async it "works with different last result", sender, m:
            await sender(DeviceMessages.SetPower(level=65535), clean.serial)
            await sender(LightMessages.SetHevCycle(enable=True, duration_s=2000), clean.serial)
            await m.add(22)

            got = await self.gather(sender, [clean.serial, light1.serial], "hev_status")
            assert got == {
                light1.serial: (True, {"hev_status": Skip}),
                clean.serial: (
                    True,
                    {
                        "hev_status": {
                            "current": {
                                "active": True,
                                "duration_s": 2000,
                                "remaining": 1978,
                                "last_power": 65535,
                            },
                            "last": {"result": LightLastHevCycleResult.BUSY},
                        }
                    },
                ),
            }

            await sender(LightMessages.SetHevCycle(enable=False, duration_s=20), clean.serial)
            await m.add(2)

            got = await self.gather(sender, [clean.serial, light1.serial], "hev_status")
            assert got == {
                light1.serial: (True, {"hev_status": Skip}),
                clean.serial: (
                    True,
                    {
                        "hev_status": {
                            "current": {
                                "active": False,
                            },
                            "last": {"result": LightLastHevCycleResult.INTERRUPTED_BY_LAN},
                        }
                    },
                ),
            }

        async it "works with different last result from power cycle", sender, m:
            await sender(DeviceMessages.SetPower(level=65535), clean.serial)
            await sender(LightMessages.SetHevCycle(enable=True, duration_s=2000), clean.serial)
            await m.add(20)

            got = await self.gather(sender, [clean.serial, light1.serial], "hev_status")
            assert got == {
                light1.serial: (True, {"hev_status": Skip}),
                clean.serial: (
                    True,
                    {
                        "hev_status": {
                            "current": {
                                "active": True,
                                "duration_s": 2000,
                                "remaining": 1980,
                                "last_power": 65535,
                            },
                            "last": {"result": LightLastHevCycleResult.BUSY},
                        }
                    },
                ),
            }

            async with clean.offline():
                pass

            await m.add(2)
            got = await self.gather(sender, [clean.serial, light1.serial], "hev_status")
            assert got == {
                light1.serial: (True, {"hev_status": Skip}),
                clean.serial: (
                    True,
                    {
                        "hev_status": {
                            "current": {
                                "active": False,
                            },
                            "last": {"result": LightLastHevCycleResult.INTERRUPTED_BY_RESET},
                        }
                    },
                ),
            }

    describe "HEVConfigPlan":

        async it "can get hev config", sender:
            got = await self.gather(sender, [clean.serial, light1.serial], "hev_config")
            assert got == {
                light1.serial: (True, {"hev_config": Skip}),
                clean.serial: (
                    True,
                    {"hev_config": {"duration_s": 7200, "indication": False}},
                ),
            }

            sender.gatherer.clear_cache()
            await sender(
                LightMessages.SetHevCycleConfiguration(duration_s=600, indication=False),
                clean.serial,
            )

            got = await self.gather(sender, [clean.serial, light1.serial], "hev_config")
            assert got == {
                light1.serial: (True, {"hev_config": Skip}),
                clean.serial: (
                    True,
                    {"hev_config": {"duration_s": 600, "indication": False}},
                ),
            }

    describe "CapabilityPlan":

        async it "gets the power", sender:

            def make_version(vendor, product):
                msg = DeviceMessages.StateVersion.create(
                    vendor=vendor, product=product, source=1, sequence=1, target=None
                )
                # in the future, I don't have to do this trick to ensure reserved fields have values
                # Which matters in the test
                return DeviceMessages.StateVersion.create(msg.pack()).payload

            l1c = {
                "cap": Products.LCM3_TILE.cap(3, 50),
                "product": Products.LCM3_TILE,
                "firmware": {
                    "build": 0,
                    "version_major": 3,
                    "version_minor": 50,
                },
                "state_version": make_version(1, 55),
            }
            l2c = {
                "cap": Products.LMB_MESH_A21.cap(2, 2),
                "product": Products.LMB_MESH_A21,
                "firmware": {"build": 0, "version_major": 2, "version_minor": 2},
                "state_version": make_version(1, 1),
            }
            slcm1c = {
                "cap": Products.LCM1_Z.cap(1, 22),
                "product": Products.LCM1_Z,
                "firmware": {
                    "build": 0,
                    "version_major": 1,
                    "version_minor": 22,
                },
                "state_version": make_version(1, 31),
            }
            slcm2nec = {
                "cap": Products.LCM2_Z.cap(2, 70),
                "product": Products.LCM2_Z,
                "firmware": {
                    "build": 0,
                    "version_major": 2,
                    "version_minor": 70,
                },
                "state_version": make_version(1, 32),
            }
            slcm2ec = {
                "cap": Products.LCM2_Z.cap(2, 77),
                "product": Products.LCM2_Z,
                "firmware": {
                    "build": 0,
                    "version_major": 2,
                    "version_minor": 77,
                },
                "state_version": make_version(1, 32),
            }
            cc = {
                "cap": Products.LCM3_A19_CLEAN.cap(3, 70),
                "product": Products.LCM3_A19_CLEAN,
                "firmware": {"build": 0, "version_major": 3, "version_minor": 70},
                "state_version": make_version(1, 90),
            }
            sc = {
                "cap": Products.LCM3_32_SWITCH_I.cap(3, 90),
                "product": Products.LCM3_32_SWITCH_I,
                "firmware": {"build": 0, "version_major": 3, "version_minor": 90},
                "state_version": make_version(1, 89),
            }

            got = await self.gather(sender, devices.serials, "capability")
            assert got == {
                clean.serial: (True, {"capability": cc}),
                switch.serial: (True, {"capability": sc}),
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

        async it "gets the firmware", sender:
            l1c = {
                "build": 0,
                "version_major": 3,
                "version_minor": 50,
            }
            l2c = {
                "build": 0,
                "version_major": 2,
                "version_minor": 2,
            }
            slcm1c = {
                "build": 0,
                "version_major": 1,
                "version_minor": 22,
            }
            slcm2nec = {
                "build": 0,
                "version_major": 2,
                "version_minor": 70,
            }
            slcm2ec = {
                "build": 0,
                "version_major": 2,
                "version_minor": 77,
            }
            cc = {"build": 0, "version_major": 3, "version_minor": 70}
            sc = {"build": 0, "version_major": 3, "version_minor": 90}

            got = await self.gather(sender, devices.serials, "firmware")
            assert got == {
                clean.serial: (True, {"firmware": cc}),
                switch.serial: (True, {"firmware": sc}),
                light1.serial: (True, {"firmware": l1c}),
                light2.serial: (True, {"firmware": l2c}),
                striplcm1.serial: (True, {"firmware": slcm1c}),
                striplcm2noextended.serial: (True, {"firmware": slcm2nec}),
                striplcm2extended.serial: (True, {"firmware": slcm2ec}),
            }

    describe "VersionPlan":

        async it "gets the version", sender:
            got = await self.gather(sender, devices.serials, "version")
            assert got == {
                clean.serial: (True, {"version": Match({"product": 90, "vendor": 1})}),
                switch.serial: (True, {"version": Match({"product": 89, "vendor": 1})}),
                light1.serial: (True, {"version": Match({"product": 55, "vendor": 1})}),
                light2.serial: (True, {"version": Match({"product": 1, "vendor": 1})}),
                striplcm1.serial: (True, {"version": Match({"product": 31, "vendor": 1})}),
                striplcm2noextended.serial: (
                    True,
                    {"version": Match({"product": 32, "vendor": 1})},
                ),
                striplcm2extended.serial: (True, {"version": Match({"product": 32, "vendor": 1})}),
            }

    describe "ZonesPlan":

        async it "gets zones", sender:
            got = await self.gather(sender, devices.serials, "zones")
            expected = {
                clean.serial: (True, {"zones": Skip}),
                switch.serial: (True, {"zones": Skip}),
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
                clean: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
                switch: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
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

            for device in devices:
                if device not in expected:
                    assert False, f"No expectation for {device.serial}"

                devices.store(device).assertIncoming(*expected[device])

    describe "ColorsPlan":

        async it "gets colors for different devices", sender:
            serials = [
                light1.serial,
                light2.serial,
                striplcm1.serial,
                striplcm2extended.serial,
                switch.serial,
            ]

            expectedlcm1 = []
            expectedlcm2 = []
            for ex, strip in [(expectedlcm1, striplcm1), (expectedlcm2, striplcm2extended)]:
                for i, z in enumerate(strip.attrs.zones):
                    z.hue = i
                    ex.append(hp.Color(i, z.saturation, z.brightness, z.kelvin))

            assert len(expectedlcm1) == 30
            assert len(expectedlcm2) == 40

            tile_expected = []
            changes = []
            for i in range(len(light1.attrs.chain)):
                for j in range(64):
                    changes.append(
                        light1.attrs.attrs_path("chain", i, "colors", j, "hue").changer_to(i + j)
                    )
            await light1.attrs.attrs_apply(*changes, event=None)
            for i in range(len(light1.attrs.chain)):
                tile_expected.append(list(light1.attrs.chain[i].colors))

            await light2.change_one("color", hp.Color(100, 0.5, 0.8, 2500), event=None)

            got = await self.gather(sender, serials, "colors")

            assert got[switch.serial][1]["colors"] is Skip
            assert got[light1.serial][1]["colors"] == tile_expected
            assert got[light2.serial][1]["colors"] == [[hp.Color(100, 0.5, 0.8, 2500)]]
            assert got[striplcm1.serial][1]["colors"] == [expectedlcm1]
            assert got[striplcm2extended.serial][1]["colors"] == [expectedlcm2]

            expected = {
                clean: [],
                switch: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
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

            for device in devices:
                if device not in expected:
                    assert False, f"No expectation for {device.serial}"

                devices.store(device).assertIncoming(*expected[device])

    describe "PartsPlan":
        async it "works for a bulb", sender:
            got = await self.gather(sender, [light2.serial], "parts")
            info = got[light2.serial][1]["parts"]

            assert len(info) == 1
            part = info[0]

            assert part is not part.real_part
            for p in (part, part.real_part):
                assert isinstance(p, cont.Part)

                assert p.part_number == 0
                assert p.device.serial == light2.serial
                assert p.device.cap == light2.cap

                assert p.orientation is co.Orientation.RightSideUp
                assert p.bounds == ((0, 1), (0, -1), (1, 1))

                assert p.original_colors is None

            with_colors = await self.gather(sender, [light2.serial], "parts_and_colors")
            info = with_colors[light2.serial][1]["parts_and_colors"]

            assert len(info) == 1
            pc = info[0]

            c = light2.attrs.color
            color = (c.hue, c.saturation, c.brightness, c.kelvin)

            assert pc is part
            assert pc.original_colors == [color]
            assert pc.real_part.original_colors == [color]

        async it "works for a not extended multizone", sender:
            for device, colors in ((striplcm1, zones1), (striplcm2noextended, zones2)):
                got = await self.gather(sender, [device.serial], "parts")
                info = got[device.serial][1]["parts"]

                assert len(info) == 1
                part = info[0]

                assert part is not part.real_part
                for p in (part, part.real_part):
                    assert isinstance(p, cont.Part)

                    assert p.part_number == 0
                    assert p.device.serial == device.serial
                    assert p.device.cap == device.cap
                    assert p.device.cap.has_multizone
                    assert not p.device.cap.has_extended_multizone

                    assert p.orientation is co.Orientation.RightSideUp
                    assert p.bounds == (
                        (0, len(device.attrs.zones)),
                        (0, -1),
                        (len(device.attrs.zones), 1),
                    )

                    assert p.original_colors is None

                with_colors = await self.gather(sender, [device.serial], "parts_and_colors")
                info = with_colors[device.serial][1]["parts_and_colors"]

                assert len(info) == 1
                pc = info[0]

                colors = [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors]

                assert pc is part
                assert pc.original_colors == colors
                assert pc.real_part.original_colors == colors

        async it "works for an extended multizone", sender:
            device = striplcm2extended
            colors = zones3

            got = await self.gather(sender, [device.serial], "parts")
            info = got[device.serial][1]["parts"]

            assert len(info) == 1
            part = info[0]

            assert part is not part.real_part
            for p in (part, part.real_part):
                assert isinstance(p, cont.Part)

                assert p.part_number == 0
                assert p.device.serial == device.serial
                assert p.device.cap == device.cap
                assert p.device.cap.has_multizone
                assert p.device.cap.has_extended_multizone

                assert p.orientation is co.Orientation.RightSideUp
                assert p.bounds == (
                    (0, len(device.attrs.zones)),
                    (0, -1),
                    (len(device.attrs.zones), 1),
                )

                assert p.original_colors is None

            with_colors = await self.gather(sender, [device.serial], "parts_and_colors")
            info = with_colors[device.serial][1]["parts_and_colors"]

            assert len(info) == 1
            pc = info[0]

            colors = [(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors]
            assert pc is part
            assert pc.original_colors == colors
            assert pc.real_part.original_colors == colors

        async it "works for a tile set", sender:
            device = light1

            colors1 = [Color(i, 1, 1, 3500) for i in range(64)]
            colors2 = [Color(i + 100, 0, 0.4, 8000) for i in range(64)]
            colors3 = [Color(i + 200, 0.1, 0.9, 7000) for i in range(64)]

            await device.change(
                (("chain", 0, "colors"), co.reorient(colors1, co.Orientation.RotatedLeft)),
                (("chain", 0, "accel_meas_x"), -10),
                (("chain", 0, "accel_meas_y"), 1),
                (("chain", 0, "accel_meas_z"), 5),
                (("chain", 0, "user_x"), 3),
                (("chain", 0, "user_y"), 5),
                #
                (("chain", 1, "colors"), colors2),
                #
                (("chain", 2, "accel_meas_x"), 1),
                (("chain", 2, "accel_meas_y"), 5),
                (("chain", 2, "accel_meas_z"), 10),
                (("chain", 2, "user_x"), 10),
                (("chain", 2, "user_y"), 25),
                (("chain", 2, "colors"), co.reorient(colors3, co.Orientation.FaceDown)),
                event=None,
            )
            await device.attrs.attrs_apply(
                device.attrs.attrs_path("chain").reduce_length_to(3), event=None
            )

            got = await self.gather(sender, [device.serial], "parts")
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
                    assert p.device.cap == device.cap
                    assert p.device.cap.has_chain

                    assert p.orientation is orientation
                    assert p.bounds == bounds

                    assert p.original_colors is None

            with_colors = await self.gather(sender, [device.serial], "parts_and_colors")
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

        async it "gets chain for a bulb", sender:
            got = await self.gather(sender, [light2.serial], "chain")
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
                        "firmware_build": 0,
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

            colors = [hp.Color(200, 1, 1, 3500)]
            assert info["reorient"](0, colors) == reorient(colors, Orientation.RightSideUp)
            assert info["reverse_orient"](0, colors) == reorient(colors, Orientation.RightSideUp)

        async it "gets chain for a strip", sender:
            serials = [striplcm1.serial, striplcm2noextended.serial, striplcm2extended.serial]
            got = await self.gather(sender, serials, "chain")

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
                        "firmware_build": 0,
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
                        "firmware_build": 0,
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
                        "firmware_build": 0,
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

                colors = [hp.Color(i, 1, 1, 3500) for i in range(30)]
                assert info["reorient"](0, colors) == reorient(colors, Orientation.RightSideUp)
                assert info["reverse_orient"](0, colors) == reorient(
                    colors, Orientation.RightSideUp
                )
            assert info["coords_and_sizes"] == [((0.0, 0.0), (info["width"], 1))]

        async it "gets chain for tiles", sender:
            await light1.change(
                (("chain", 1, "accel_meas_x"), -10),
                (("chain", 1, "accel_meas_y"), 1),
                (("chain", 1, "accel_meas_z"), 5),
                (("chain", 1, "user_x"), 3),
                (("chain", 1, "user_y"), 5),
                #
                (("chain", 3, "accel_meas_x"), 1),
                (("chain", 3, "accel_meas_y"), 5),
                (("chain", 3, "accel_meas_z"), 10),
                (("chain", 3, "user_x"), 10),
                (("chain", 3, "user_y"), 25),
                event=None,
            )

            got = await self.gather(sender, light1.serial, "chain")

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
                clean: [],
                switch: [],
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

            for device in devices:
                if device not in expected:
                    assert False, f"No expectation for {device.serial}"

                devices.store(device).assertIncoming(*expected[device])

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

            colors = [hp.Color(i, 1, 1, 3500) for i in range(64)]

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

        async it "gets firmware effects", sender:
            io = light1.io["MEMORY"]

            @io.packet_filter.intercept_process_request
            async def process_request_light1(event, Cont):
                if event | TileMessages.GetTileEffect:
                    event.set_replies(Cont)
                    event.handled = False
                    event._viewers_only = True
                    return True
                else:
                    raise Cont()

            @io.packet_filter.intercept_process_outgoing
            async def process_outgoing_light1(reply, req_event, Cont):
                if req_event | TileMessages.GetTileEffect:
                    yield TileMessages.StateTileEffect.create(
                        type=TileEffectType.FLAME,
                        speed=10,
                        duration=1,
                        palette_count=2,
                        palette=[hp.Color(120, 1, 1, 3500), hp.Color(360, 1, 1, 3500)],
                        **reply,
                    )
                else:
                    raise Cont()

            io = striplcm1.io["MEMORY"]

            @io.packet_filter.intercept_process_request
            async def process_request_striplcm1(event, Cont):
                if event | MultiZoneMessages.GetMultiZoneEffect:
                    event.set_replies(Cont)
                    event.handled = False
                    event._viewers_only = True
                    return True
                else:
                    raise Cont()

            @io.packet_filter.intercept_process_outgoing
            async def process_outgoing_striplcm1(reply, req_event, Cont):
                if req_event | MultiZoneMessages.GetMultiZoneEffect:
                    yield MultiZoneMessages.StateMultiZoneEffect.create(
                        type=MultiZoneEffectType.MOVE,
                        speed=5,
                        duration=2,
                        parameters={"speed_direction": Direction.LEFT},
                        **reply,
                    )
                else:
                    raise Cont()

            l1 = {
                "type": TileEffectType.FLAME,
                "options": {
                    "duration": 1,
                    "palette": [hp.Color(120, 1, 1, 3500), hp.Color(360, 1, 1, 3500)],
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
            with process_outgoing_light1, process_outgoing_striplcm1, process_request_light1, process_request_striplcm1:
                got = await self.gather(sender, serials, "firmware_effects")
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
                devices.store(device).assertIncoming(*e)
