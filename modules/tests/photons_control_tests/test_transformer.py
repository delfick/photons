
import itertools
import random
from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_control.colour import ColourParser
from photons_control.transform import PowerToggle, PowerToggleGroup, Transformer
from photons_messages import DeviceMessages, DiscoveryMessages, LightMessages
from photons_products import Products

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


@pytest.fixture
def default_async_timeout() -> float:
    return 3


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


class TestPowerToggle:

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

    async def test_it_can_return_a_PowerToggleGroup(self):
        a = mock.Mock(name="a")
        ptg = mock.Mock(name="power_toggle_group_msg")
        PowerToggleGroup = mock.Mock(name="PowerToggleGroup", return_value=ptg)

        with mock.patch("photons_control.transform.PowerToggleGroup", PowerToggleGroup):
            assert PowerToggle(duration=5, group=True, a=a) is ptg

        PowerToggleGroup.assert_called_once_with(duration=5, a=a)

    async def test_it_toggles_the_power(self, sender):
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

class TestPowerToggleGroup:

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

    async def test_it_toggles_the_power(self, sender):
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

class TestTransformer:

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

    async def test_it_returns_an_empty_list_if_no_power_or_color_options(self):
        assert Transformer.using({}) == []

    async def test_it_Uses_SetPower_if_no_duration(self, sender):
        msg = DeviceMessages.SetPower(level=0, res_required=False)
        expected = {device: [msg] for device in devices}
        await self.transform(sender, {"power": "off"}, expected=expected)

        for device in devices:
            await device.reset()

        msg = DeviceMessages.SetPower(level=65535, res_required=False)
        expected = {device: [msg] for device in devices}
        await self.transform(sender, {"power": "on"}, expected=expected)

    async def test_it_uses_SetLightPower_if_we_have_duration(self, sender):
        msg = LightMessages.SetLightPower(level=0, duration=100, res_required=False)
        expected = {device: [msg] for device in devices}
        await self.transform(sender, {"power": "off", "duration": 100}, expected=expected)

        for device in devices:
            await device.reset()
        msg = LightMessages.SetLightPower(level=65535, duration=20, res_required=False)
        expected = {device: [msg] for device in devices}
        await self.transform(sender, {"power": "on", "duration": 20}, expected=expected)

    async def test_it_just_uses_ColourParsermsg(self, sender):
        for color in (random.choice(["red", "blue", "green", "yellow"]), None):
            for state in generate_options(color, exclude=["power"]):
                want = ColourParser.msg(color, overrides=state)
                want.res_required = False

                for device in devices:
                    await device.reset()
                expected = {device: [want] for device in devices}
                await self.transform(sender, state, expected=expected)

    async def test_it_can_ignore_brightness(self, sender):
        want = ColourParser.msg("hue:200 saturation:1")
        want.res_required = False

        expected = {device: [want] for device in devices}
        await self.transform(
            sender,
            {"color": "hue:200 saturation:1 brightness:0.3"},
            expected=expected,
            keep_brightness=True,
        )

    async def test_it_sets_color_with_duration(self, sender):
        state = {"color": "blue", "duration": 10}
        want = ColourParser.msg("blue", overrides={"duration": 10})
        expected = {device: [want] for device in devices}
        await self.transform(sender, state, expected=expected, keep_brightness=True)

    async def test_it_sets_power_off_even_if_light_already_off(self, sender):
        state = {"color": "blue", "power": "off", "duration": 10}
        power = LightMessages.SetLightPower(level=0, duration=10)
        set_color = ColourParser.msg("blue", overrides={"duration": 10})
        expected = {device: [power, set_color] for device in devices}
        await self.transform(sender, state, expected=expected)

    async def test_it_pipelines_turn_off_and_color_when_both_color_and_poweroff(self, sender):
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

    class TestWhenPowerOnAndNeedColor:

        async def test_it_sets_power_on_if_it_needs_to(self, sender):
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

        async def test_it_sets_power_on_if_it_needs_to_with_duration(self, sender):
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

        async def test_it_can_see_brightness_in_state(self, sender):
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

        async def test_it_can_ignore_brightness_in_color(self, sender):
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

        async def test_it_can_ignore_brightness_in_state(self, sender):
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

        async def test_it_can_retain_previous_color_when_powering_on(self, sender):
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
