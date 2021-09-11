# coding: spec

from interactor.commander.store import store, load_commands

from photons_app.mimic.event import Events
from photons_app import helpers as hp

from photons_messages import DeviceMessages, LightMessages
from photons_control.colour import ColourParser

from unittest import mock
import pytest


@pytest.fixture()
def store_clone():
    load_commands()
    return store.clone()


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


@pytest.fixture()
async def sender(devices, final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture()
async def server(
    store_clone, devices, server_wrapper, sender, final_future, FakeTime, MockedCallLater
):
    with FakeTime() as t:
        async with MockedCallLater(t):
            async with server_wrapper(store_clone, sender, final_future) as server:
                yield server


describe "Control Commands":

    async it "has discovery commands", devices, server, responses:
        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover"},
            json_output=responses.discovery_response,
        )

        serials = await server.assertCommand(
            "/v1/lifx/command", {"command": "discover", "args": {"just_serials": True}}
        )
        assert sorted(serials) == sorted(device.serial for device in devices)

        serials = await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover", "args": {"matcher": {"group_name": "Living Room"}}},
        )
        wanted = {
            device.serial: responses.discovery_response[device.serial]
            for device in devices
            if device.attrs.group.label == "Living Room"
        }
        assert len(wanted) == 2
        assert serials == wanted

        serials = await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover", "args": {"just_serials": True, "matcher": "label=kitchen"}},
        )
        assert serials == [devices.for_attribute("label", "kitchen")[0].serial]

        serials = await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover", "args": {"just_serials": True, "matcher": "label=lamp"}},
        )
        assert serials == [d.serial for d in devices.for_attribute("label", "lamp", 2)]

        serials = await server.assertCommand(
            "/v1/lifx/command",
            {"command": "discover", "args": {"just_serials": True, "matcher": "label=blah"}},
            status=200,
        )
        assert serials == []

    async it "has query commands", devices, server, responses:
        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "query", "args": {"pkt_type": 101}},
            json_output=responses.light_state_responses,
        )

        results = responses.light_state_responses["results"]
        expected = {
            device.serial: results[device.serial]
            for device in devices.for_attribute("power", 65535, expect=8)
        }
        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "query", "args": {"pkt_type": 101, "matcher": "power=on"}},
            json_output={"results": expected},
        )

        bathroom_light = devices["d073d5000002"]
        async with bathroom_light.offline():
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

    async it "has set commands", devices, server:
        expected = {"results": {device.serial: "ok" for device in devices}}

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "set", "args": {"pkt_type": "SetPower", "pkt_args": {"level": 0}}},
            json_output=expected,
        )

        for device in devices:
            io = device.io["MEMORY"]
            assert (
                devices.store(device).count(
                    Events.INCOMING(device, io, pkt=DeviceMessages.SetPower(level=0))
                )
                == 1
            )
            devices.store(device).clear()

        # With an offline light
        bathroom_light = devices["d073d5000002"]
        async with bathroom_light.offline():
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

            for device in devices:
                if device is not bathroom_light:
                    io = device.io["MEMORY"]
                    assert (
                        devices.store(device).count(
                            Events.INCOMING(device, io, pkt=DeviceMessages.SetPower(level=0xFFFF))
                        )
                        == 1
                    )
                    devices.store(device).clear()

        # With a matcher
        kitchen_light = devices.for_attribute("label", "kitchen", expect=1)[0]
        expected = {"results": {kitchen_light.serial: "ok"}}

        await server.assertCommand(
            "/v1/lifx/command",
            {
                "command": "set",
                "args": {"pkt_type": 24, "pkt_args": {"label": "blah"}, "matcher": "label=kitchen"},
            },
            json_output=expected,
        )

        assert (
            devices.store(kitchen_light).count(
                Events.INCOMING(
                    kitchen_light,
                    kitchen_light.io["MEMORY"],
                    pkt=DeviceMessages.SetLabel(label="blah"),
                )
            )
            == 1
        )
        for device in devices:
            if device is not kitchen_light:
                devices.store(device).assertNoSetMessages()

    async it "has power_toggle command", devices, server:
        expected = {"results": {device.serial: "ok" for device in devices}}

        for device in devices:
            if device.serial == "d073d5000001":
                await device.change_one("power", 0, event=None)
            else:
                await device.change_one("power", 0xFFFF, event=None)

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle"},
            json_output=expected,
        )

        for device in devices:
            io = device.io["MEMORY"]
            if device.serial == "d073d5000001":
                assert (
                    devices.store(device).count(
                        Events.INCOMING(
                            device, io, pkt=LightMessages.SetLightPower(level=65535, duration=1)
                        )
                    )
                    == 1
                )
            else:
                assert (
                    devices.store(device).count(
                        Events.INCOMING(
                            device, io, pkt=LightMessages.SetLightPower(level=0, duration=1)
                        )
                    )
                    == 1
                )
            devices.store(device).clear()

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle", "args": {"duration": 2}},
            json_output=expected,
        )

        for device in devices:
            io = device.io["MEMORY"]
            if device.serial == "d073d5000001":
                assert (
                    devices.store(device).count(
                        Events.INCOMING(
                            device, io, pkt=LightMessages.SetLightPower(level=0, duration=2)
                        )
                    )
                    == 1
                )
            else:
                assert (
                    devices.store(device).count(
                        Events.INCOMING(
                            device, io, pkt=LightMessages.SetLightPower(level=65535, duration=2)
                        )
                    )
                    == 1
                )
            devices.store(device).clear()

    async it "has power_toggle group command", devices, server:
        expected = {"results": {device.serial: "ok" for device in devices}}

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle", "args": {"group": True}},
            json_output=expected,
        )

        for device in devices:
            io = device.io["MEMORY"]
            assert (
                devices.store(device).count(
                    Events.INCOMING(
                        device, io, pkt=LightMessages.SetLightPower(level=0, duration=1)
                    )
                )
                == 1
            )
            devices.store(device).clear()

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle", "args": {"duration": 2, "group": True}},
            json_output=expected,
        )

        for device in devices:
            io = device.io["MEMORY"]
            assert (
                devices.store(device).count(
                    Events.INCOMING(
                        device, io, pkt=LightMessages.SetLightPower(level=65535, duration=2)
                    )
                )
                == 1
            )
            devices.store(device).clear()

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "power_toggle", "args": {"duration": 3, "group": True}},
            json_output=expected,
        )

        for device in devices:
            io = device.io["MEMORY"]
            assert (
                devices.store(device).count(
                    Events.INCOMING(
                        device, io, pkt=LightMessages.SetLightPower(level=0, duration=3)
                    )
                )
                == 1
            )
            devices.store(device).clear()

    @pytest.mark.async_timeout(5)
    async it "has transform command", devices, server:
        # Just power
        expected = {"results": {device.serial: "ok" for device in devices}}

        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "transform", "args": {"transform": {"power": "off"}}},
            json_output=expected,
        )

        for device in devices:
            io = device.io["MEMORY"]
            assert (
                devices.store(device).count(
                    Events.INCOMING(device, io, pkt=DeviceMessages.SetPower(level=0))
                )
                == 1
            )
            devices.store(device).clear()

        # Just color
        await server.assertCommand(
            "/v1/lifx/command",
            {"command": "transform", "args": {"transform": {"color": "red", "effect": "sine"}}},
            json_output=expected,
        )

        for device in devices:
            io = device.io["MEMORY"]
            want = Events.INCOMING(
                device,
                io,
                pkt=(
                    LightMessages.SetWaveformOptional,
                    ColourParser.msg(
                        "red", overrides={"effect": "sine", "res_required": False}
                    ).payload.as_dict(),
                ),
            )
            assert devices.store(device).count(want) == 1, device
            devices.store(device).clear()

        # Power on and color
        for device in devices:
            await device.change_one("power", 0, event=None)
            await device.change_one(("color", "brightness"), 0.5, event=None)
        await devices["d073d5000001"].change_one("power", 0xFFFF, event=None)
        await devices["d073d5000003"].change_one("power", 0xFFFF, event=None)

        tv_light = devices.for_attribute("label", "tv", expect=1)[0]
        async with tv_light.offline():
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

        for device in devices:
            io = device.io["MEMORY"]
            if device.attrs.label == "tv":
                devices.store(device).assertNoSetMessages()
            elif device.serial in ("d073d5000001", "d073d5000003"):
                devices.store(device).count(
                    Events.INCOMING(
                        device, io, pkt=ColourParser.msg("blue", overrides={"res_required": False})
                    )
                ) == 1
            else:
                for pkt in [
                    ColourParser.msg("blue", overrides={"brightness": 0, "res_required": False}),
                    DeviceMessages.SetPower(level=65535, res_required=False),
                    ColourParser.msg("blue", overrides={"brightness": 0.5, "res_required": False}),
                ]:
                    assert devices.store(device).count(Events.INCOMING(device, io, pkt=pkt)) == 1
            devices.store(device).clear()

        # Power on and transition color
        for device in devices:
            await device.change_one("power", 0, event=None)
            await device.change_one(("color", "brightness"), 0.5, event=None)
        await devices["d073d5000001"].change_one("power", 0xFFFF, event=None)
        await devices["d073d5000003"].change_one("power", 0xFFFF, event=None)

        tv_light = devices.for_attribute("label", "tv", expect=1)[0]
        async with tv_light.offline():
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

        for device in devices:
            io = device.io["MEMORY"]
            if device.attrs.label == "tv":
                devices.store(device).assertNoSetMessages()
            elif device.serial in ("d073d5000001", "d073d5000003"):
                assert (
                    devices.store(device).count(
                        Events.INCOMING(
                            device,
                            io,
                            pkt=ColourParser.msg("blue", overrides={"res_required": False}),
                        )
                    )
                    == 1
                )
            else:
                device_reset = ColourParser.msg(
                    "blue",
                    overrides={
                        "brightness": 0,
                        "res_required": False,
                    },
                )
                device_reset.set_hue = 0
                device_reset.set_saturation = 0
                device_reset.set_kelvin = 0
                assert (
                    devices.store(device).count(
                        Events.INCOMING(
                            device, io, pkt=DeviceMessages.SetPower(level=65535, res_required=False)
                        )
                    )
                    == 1
                )
                assert (
                    devices.store(device).count(
                        Events.INCOMING(
                            device,
                            io,
                            pkt=ColourParser.msg(
                                "blue", overrides={"brightness": 0.5, "res_required": False}
                            ),
                        )
                    )
                    == 1
                )
