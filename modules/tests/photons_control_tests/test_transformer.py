# coding: spec

from photons_app import helpers as hp

from photons_control.transform import Transformer, PowerToggle, PowerToggleGroup
from photons_messages import DeviceMessages, LightMessages, DiscoveryMessages
from photons_control.colour import ColourParser
from photons_products import Products

from unittest import mock
import itertools
import random
import pytest

devices = pytest.helpers.mimic()

light1 = devices.add("light1")(
    "d073d5000001",
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(color=hp.Color(0, 1, 0.3, 2500)),
)

light2 = devices.add("light2")(
    "d073d5000002",
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(power=65535, color=hp.Color(100, 1, 0.5, 2500)),
)

light3 = devices.add("light3")(
    "d073d5000003",
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(power=65535, color=hp.Color(100, 0, 0.8, 2500)),
)


@pytest.fixture(autouse=True)
def set_async_timeout(request):
    request.applymarker(pytest.mark.async_timeout(3))


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


def generate_options(color, exclude=None):
    zero_to_one = [v / 10 for v in range(1, 10, 1)]

    options = {
        "hue": list(range(0, 360, 1)),
        "saturation": zero_to_one,
        "brightness": zero_to_one,
        "kelvin": list(range(3500, 9000, 50)),
        "power": ["on", "off"],
    }

    extra = {
        "duration": list(range(0, 10, 1)),
        "res_required": [True, False],
        "effect": ["sine", "triangle", "saw"],
        "cycles": list(range(0, 10, 1)),
    }

    def make_state(keys, extra_keys):
        state = {}
        if color is not None:
            state["color"] = color

        for k in keys:
            state[k] = random.choice(options[k])

        for k in extra_keys:
            state[k] = random.choice(extra[k])

        print(f"Generated state: {state}")
        return state

    keys = [k for k in options if exclude is None or k not in exclude]
    random.shuffle(keys)

    for r in range(len(keys)):
        for i, comb in enumerate(itertools.combinations(keys, r + 1)):
            if i > 0:
                break

            for r in (0, 2):
                if r == 0:
                    yield make_state(comb, [])
                else:
                    for j, comb2 in enumerate(itertools.combinations(extra, r)):
                        if j > 0:
                            break

                        yield make_state(comb, comb2)


describe "PowerToggle":

    async def run_and_compare(self, sender, msg, *, expected):
        await sender(msg, devices.serials)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

    async it "can return a PowerToggleGroup":
        a = mock.Mock(name="a")
        ptg = mock.Mock(name="power_toggle_group_msg")
        PowerToggleGroup = mock.Mock(name="PowerToggleGroup", return_value=ptg)

        with mock.patch("photons_control.transform.PowerToggleGroup", PowerToggleGroup):
            assert PowerToggle(duration=5, group=True, a=a) is ptg

        PowerToggleGroup.assert_called_once_with(duration=5, a=a)

    async it "toggles the power", sender:
        expected = {
            light1: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=1),
            ],
            light2: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=1)],
            light3: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=1)],
        }
        await self.run_and_compare(sender, PowerToggle(), expected=expected)

        for device in devices:
            devices.store(device).clear()

        expected = {
            light1: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=2)],
            light2: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=2),
            ],
            light3: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=2),
            ],
        }
        await self.run_and_compare(sender, PowerToggle(duration=2), expected=expected)

describe "PowerToggleGroup":

    async def run_and_compare(self, sender, msg, *, expected):
        await sender(msg, devices.serials)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

    async it "toggles the power", sender:
        expected = {
            light1: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=1)],
            light2: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=1)],
            light3: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=1)],
        }
        await self.run_and_compare(sender, PowerToggleGroup(), expected=expected)

        for device in devices:
            device.received = []

        expected = {
            light1: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=2),
            ],
            light2: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=2),
            ],
            light3: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=2),
            ],
        }
        await self.run_and_compare(sender, PowerToggleGroup(duration=2), expected=expected)

        for device in devices:
            device.received = []

        expected = {
            light1: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=3)],
            light2: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=3)],
            light3: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=3)],
        }
        await self.run_and_compare(sender, PowerToggleGroup(duration=3), expected=expected)

describe "Transformer":

    async def transform(
        self, sender, state, *, expected, keep_brightness=False, transition_color=False
    ):
        msg = Transformer.using(
            state, keep_brightness=keep_brightness, transition_color=transition_color
        )
        await sender(msg, devices.serials)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

    async it "returns an empty list if no power or color options":
        assert Transformer.using({}) == []

    async it "Uses SetPower if no duration", sender:
        msg = DeviceMessages.SetPower(level=0, res_required=False)
        expected = {device: [msg] for device in devices}
        await self.transform(sender, {"power": "off"}, expected=expected)

        for device in devices:
            await device.reset()

        msg = DeviceMessages.SetPower(level=65535, res_required=False)
        expected = {device: [msg] for device in devices}
        await self.transform(sender, {"power": "on"}, expected=expected)

    async it "uses SetLightPower if we have duration", sender:
        msg = LightMessages.SetLightPower(level=0, duration=100, res_required=False)
        expected = {device: [msg] for device in devices}
        await self.transform(sender, {"power": "off", "duration": 100}, expected=expected)

        for device in devices:
            await device.reset()
        msg = LightMessages.SetLightPower(level=65535, duration=20, res_required=False)
        expected = {device: [msg] for device in devices}
        await self.transform(sender, {"power": "on", "duration": 20}, expected=expected)

    async it "just uses ColourParser.msg", sender:
        for color in (random.choice(["red", "blue", "green", "yellow"]), None):
            for state in generate_options(color, exclude=["power"]):
                want = ColourParser.msg(color, overrides=state)
                want.res_required = False

                for device in devices:
                    await device.reset()
                expected = {device: [want] for device in devices}
                await self.transform(sender, state, expected=expected)

    async it "can ignore brightness", sender:
        want = ColourParser.msg("hue:200 saturation:1")
        want.res_required = False

        expected = {device: [want] for device in devices}
        await self.transform(
            sender,
            {"color": "hue:200 saturation:1 brightness:0.3"},
            expected=expected,
            keep_brightness=True,
        )

    async it "sets color with duration", sender:
        state = {"color": "blue", "duration": 10}
        want = ColourParser.msg("blue", overrides={"duration": 10})
        expected = {device: [want] for device in devices}
        await self.transform(sender, state, expected=expected, keep_brightness=True)

    async it "sets power off even if light already off", sender:
        state = {"color": "blue", "power": "off", "duration": 10}
        power = LightMessages.SetLightPower(level=0, duration=10)
        set_color = ColourParser.msg("blue", overrides={"duration": 10})
        expected = {device: [power, set_color] for device in devices}
        await self.transform(sender, state, expected=expected)

    async it "pipelines turn off and color when both color and power=off", sender:
        for state in generate_options("red"):
            state["power"] = "off"
            transformer = Transformer()
            color_message = transformer.color_message(state, False)
            power_message = transformer.power_message(state)

            assert color_message is not None
            assert power_message is not None

            for device in devices:
                await device.reset()
            expected = {device: [power_message, color_message] for device in devices}
            await self.transform(sender, state, expected=expected)

    describe "When power on and need color":

        async it "sets power on if it needs to", sender:
            state = {"color": "blue", "power": "on"}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"brightness": 0}),
                    DeviceMessages.SetPower(level=65535),
                    ColourParser.msg(
                        "blue", overrides={"brightness": light1.attrs.color.brightness}
                    ),
                ],
                light2: [LightMessages.GetColor(), ColourParser.msg("blue")],
                light3: [LightMessages.GetColor(), ColourParser.msg("blue")],
            }
            await self.transform(sender, state, expected=expected)

        async it "sets power on if it needs to with duration", sender:
            state = {"color": "blue brightness:0.3", "power": "on", "duration": 10}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"brightness": 0}),
                    LightMessages.SetLightPower(level=65535, duration=10),
                    ColourParser.msg("blue", overrides={"brightness": 0.3, "duration": 10}),
                ],
                light2: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue brightness:0.3", overrides={"duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue brightness:0.3", overrides={"duration": 10}),
                ],
            }
            await self.transform(sender, state, expected=expected)

        async it "can see brightness in state", sender:
            state = {"color": "blue", "brightness": 0.3, "power": "on", "duration": 10}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"brightness": 0}),
                    LightMessages.SetLightPower(level=65535, duration=10),
                    ColourParser.msg("blue", overrides={"brightness": 0.3, "duration": 10}),
                ],
                light2: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue brightness:0.3", overrides={"duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue brightness:0.3", overrides={"duration": 10}),
                ],
            }
            await self.transform(sender, state, expected=expected)

        async it "can ignore brightness in color", sender:
            state = {"color": "blue brightness:0.3", "power": "on", "duration": 10}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"brightness": 0}),
                    LightMessages.SetLightPower(level=65535, duration=10),
                    ColourParser.msg(
                        "blue",
                        overrides={"brightness": light1.attrs.color.brightness, "duration": 10},
                    ),
                ],
                light2: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"duration": 10}),
                ],
            }
            await self.transform(sender, state, expected=expected, keep_brightness=True)

        async it "can ignore brightness in state", sender:
            state = {"color": "blue", "brightness": 0.3, "power": "on", "duration": 10}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"brightness": 0}),
                    LightMessages.SetLightPower(level=65535, duration=10),
                    ColourParser.msg(
                        "blue",
                        overrides={"brightness": light1.attrs.color.brightness, "duration": 10},
                    ),
                ],
                light2: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"duration": 10}),
                ],
            }
            await self.transform(sender, state, expected=expected, keep_brightness=True)

        async it "can retain previous color when powering on", sender:
            state = {"color": "blue", "brightness": 0.3, "power": "on", "duration": 10}
            light1_reset = ColourParser.msg("blue", overrides={"brightness": 0})
            light1_reset.set_hue = 0
            light1_reset.set_saturation = 0
            light1_reset.set_kelvin = 0
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    light1_reset,
                    LightMessages.SetLightPower(level=65535, duration=10),
                    ColourParser.msg("blue ", overrides={"brightness": 0.3, "duration": 10}),
                ],
                light2: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"brightness": 0.3, "duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    ColourParser.msg("blue", overrides={"brightness": 0.3, "duration": 10}),
                ],
            }
            await self.transform(sender, state, expected=expected, transition_color=True)
