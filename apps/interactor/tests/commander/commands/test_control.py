# coding: spec

from interactor.commander.store import store, load_commands

from photons_messages import DeviceMessages, LightMessages
from photons_control.colour import ColourParser

from unittest import mock
import pytest


@pytest.fixture(scope="module")
def store_clone():
    load_commands()
    return store.clone()


@pytest.fixture(scope="module")
async def server(store_clone, server_wrapper):
    async with server_wrapper(store_clone) as server:
        yield server


@pytest.fixture(autouse=True)
async def wrap_tests(server):
    async with server.per_test():
        yield


describe "Control Commands":

    async it "has discovery commands", fake, server, responses:
        await server.assertCommand(
            "/v1/lifx/command", {"command": "discover"}, json_output=responses.discovery_response,
        )

        serials = await server.assertCommand(
            "/v1/lifx/command", {"command": "discover", "args": {"just_serials": True}}
        )
        assert sorted(serials) == sorted(device.serial for device in fake.devices)

        serials = await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover", "args": {"matcher": {"group_name": "Living Room"}}},
        )
        wanted = {
            device.serial: responses.discovery_response[device.serial]
            for device in fake.devices
            if device.attrs.group_label == "Living Room"
        }
        assert len(wanted) == 2
        assert serials == wanted

        serials = await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover", "args": {"just_serials": True, "matcher": "label=kitchen"}},
        )
        assert serials == [fake.for_attribute("label", "kitchen")[0].serial]

        serials = await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover", "args": {"just_serials": True, "matcher": "label=lamp"}},
        )
        assert serials == [d.serial for d in fake.for_attribute("label", "lamp", 2)]

        serials = await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover", "args": {"just_serials": True, "matcher": "label=blah"}},
            status=200,
        )
        assert serials == []

    async it "has query commands", fake, server, responses:
        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "query", "args": {"pkt_type": 101}},
            json_output=responses.light_state_responses,
        )

        results = responses.light_state_responses["results"]
        expected = {
            device.serial: results[device.serial]
            for device in fake.for_attribute("power", 65535, expect=6)
        }
        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "query", "args": {"pkt_type": 101, "matcher": "power=on"}},
            json_output={"results": expected},
        )

        bathroom_light = fake.for_serial("d073d5000002")
        with bathroom_light.offline():
            expected["d073d5000002"] = {
                "error": {
                    "message": "Timed out. Waiting for reply to a packet",
                    "sent_pkt_type": 101,
                    "source": mock.ANY,
                    "sequence": mock.ANY,
                },
                "error_code": "TimedOut",
                "status": 400,
            }
            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "query",
                    "args": {"pkt_type": 101, "matcher": "power=on", "timeout": 0.1},
                },
                json_output={"results": expected},
            )

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "query", "args": {"pkt_type": "GetLabel"}},
            json_output=responses.label_state_responses,
        )

        await server.assertCommand(
            "/v1/lifx/command",
            {
                "command": "query",
                "args": {
                    "pkt_type": 502,
                    "pkt_args": {"start_index": 0, "end_index": 255},
                    "matcher": "cap=multizone",
                },
            },
            json_output=responses.multizone_state_responses,
        )

    async it "has set commands", fake, server:
        expected = {"results": {device.serial: "ok" for device in fake.devices}}

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "set", "args": {"pkt_type": "SetPower", "pkt_args": {"level": 0}}},
            json_output=expected,
        )

        for device in fake.devices:
            device.compare_received_set([DeviceMessages.SetPower(level=0)])
            device.reset_received()

        # With an offline light
        bathroom_light = fake.for_serial("d073d5000002")
        with bathroom_light.offline():
            expected["results"]["d073d5000002"] = {
                "error": {
                    "message": "Timed out. Waiting for reply to a packet",
                    "sent_pkt_type": 21,
                    "source": mock.ANY,
                    "sequence": mock.ANY,
                },
                "error_code": "TimedOut",
                "status": 400,
            }

            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "set",
                    "args": {"pkt_type": "SetPower", "pkt_args": {"level": 65535}, "timeout": 0.1},
                },
                json_output=expected,
            )

            for device in fake.devices:
                if device is not bathroom_light:
                    device.compare_received_set([DeviceMessages.SetPower(level=65535)])
                    device.reset_received()

        # With a matcher
        kitchen_light = fake.for_attribute("label", "kitchen", expect=1)[0]
        expected = {"results": {kitchen_light.serial: "ok"}}

        await server.assertCommand(
            "/v1/lifx/command",
            {
                "command": "set",
                "args": {"pkt_type": 24, "pkt_args": {"label": "blah"}, "matcher": "label=kitchen"},
            },
            json_output=expected,
        )

        kitchen_light.compare_received_set([DeviceMessages.SetLabel(label="blah")])
        for device in fake.devices:
            if device is not kitchen_light:
                device.expect_no_set_messages()

    async it "has power_toggle command", fake, server:
        expected = {"results": {device.serial: "ok" for device in fake.devices}}

        await server.assertCommand(
            "/v1/lifx/command", {"command": "power_toggle"}, json_output=expected,
        )

        for device in fake.devices:
            if device.serial == "d073d5000001":
                device.compare_received_set([LightMessages.SetLightPower(level=65535, duration=1)])
            else:
                device.compare_received_set([LightMessages.SetLightPower(level=0, duration=1)])
            device.reset_received()

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle", "args": {"duration": 2}},
            json_output=expected,
        )

        for device in fake.devices:
            if device.serial == "d073d5000001":
                device.compare_received_set([LightMessages.SetLightPower(level=0, duration=2)])
            else:
                device.compare_received_set([LightMessages.SetLightPower(level=65535, duration=2)])
            device.reset_received()

    async it "has power_toggle group command", fake, server:
        expected = {"results": {device.serial: "ok" for device in fake.devices}}

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle", "args": {"group": True}},
            json_output=expected,
        )

        for device in fake.devices:
            device.compare_received_set([LightMessages.SetLightPower(level=0, duration=1)])
            device.reset_received()

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle", "args": {"duration": 2, "group": True}},
            json_output=expected,
        )

        for device in fake.devices:
            device.compare_received_set([LightMessages.SetLightPower(level=65535, duration=2)])
            device.reset_received()

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle", "args": {"duration": 3, "group": True}},
            json_output=expected,
        )

        for device in fake.devices:
            device.compare_received_set([LightMessages.SetLightPower(level=0, duration=3)])
            device.reset_received()

    async it "has transform command", fake, server:
        # Just power
        expected = {"results": {device.serial: "ok" for device in fake.devices}}

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "transform", "args": {"transform": {"power": "off"}}},
            json_output=expected,
        )

        for device in fake.devices:
            device.compare_received_set([DeviceMessages.SetPower(level=0)])
            device.reset_received()

        # Just color
        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "transform", "args": {"transform": {"color": "red", "effect": "sine"}}},
            json_output=expected,
        )

        for device in fake.devices:
            device.compare_received_set(
                [ColourParser.msg("red", overrides={"effect": "sine", "res_required": False})]
            )
            device.reset_received()

        # Power on and color
        for device in fake.devices:
            device.attrs.power = 0
            device.attrs.color.brightness = 0.5
        fake.for_serial("d073d5000001").attrs.power = 65535
        fake.for_serial("d073d5000003").attrs.power = 65535

        tv_light = fake.for_attribute("label", "tv", expect=1)[0]
        with tv_light.offline():
            expected["results"]["d073d5000006"] = {
                "error": {
                    "message": "Timed out. Waiting for reply to a packet",
                    "sent_pkt_type": 101,
                    "source": mock.ANY,
                    "sequence": mock.ANY,
                },
                "error_code": "TimedOut",
                "status": 400,
            }
            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "transform",
                    "args": {"transform": {"power": "on", "color": "blue"}, "timeout": 0.2},
                },
                json_output=expected,
            )

        for device in fake.devices:
            if device.attrs.label == "tv":
                device.expect_no_set_messages()
            elif device.serial in ("d073d5000001", "d073d5000003"):
                device.compare_received_set(
                    [ColourParser.msg("blue", overrides={"res_required": False})]
                )
            else:
                device.compare_received_set(
                    [
                        ColourParser.msg(
                            "blue", overrides={"brightness": 0, "res_required": False}
                        ),
                        DeviceMessages.SetPower(level=65535, res_required=False),
                        ColourParser.msg(
                            "blue", overrides={"brightness": 0.5, "res_required": False}
                        ),
                    ]
                )
            device.reset_received()

        # Power on and transition color
        for device in fake.devices:
            device.attrs.power = 0
            device.attrs.color.brightness = 0.5
        fake.for_serial("d073d5000001").attrs.power = 65535
        fake.for_serial("d073d5000003").attrs.power = 65535

        tv_light = fake.for_attribute("label", "tv", expect=1)[0]
        with tv_light.offline():
            expected["results"]["d073d5000006"] = {
                "error": {
                    "message": "Timed out. Waiting for reply to a packet",
                    "sent_pkt_type": 101,
                    "source": mock.ANY,
                    "sequence": mock.ANY,
                },
                "error_code": "TimedOut",
                "status": 400,
            }
            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "transform",
                    "args": {
                        "transform": {"power": "on", "color": "blue"},
                        "transform_options": {"transition_color": True},
                        "timeout": 0.2,
                    },
                },
                json_output=expected,
            )

        for device in fake.devices:
            if device.attrs.label == "tv":
                device.expect_no_set_messages()
            elif device.serial in ("d073d5000001", "d073d5000003"):
                device.compare_received_set(
                    [ColourParser.msg("blue", overrides={"res_required": False})]
                )
            else:
                device_reset = ColourParser.msg(
                    "blue", overrides={"brightness": 0, "res_required": False,},
                )
                device_reset.set_hue = 0
                device_reset.set_saturation = 0
                device_reset.set_kelvin = 0
                device.compare_received_set(
                    [
                        device_reset,
                        DeviceMessages.SetPower(level=65535, res_required=False),
                        ColourParser.msg(
                            "blue", overrides={"brightness": 0.5, "res_required": False}
                        ),
                    ]
                )
