from unittest import mock

import pytest
from photons_control.tile import default_tile_palette
from photons_messages.fields import Color


@pytest.fixture
def default_async_timeout() -> float:
    return 15


@pytest.fixture()
def effects_running_status():
    return {
        "results": {
            "d073d5000001": {
                "effect": {"type": "SKIP"},
                "product": {"cap": mock.ANY, "name": "LCM2_A19", "pid": 27, "vid": 1},
            },
            "d073d5000002": {
                "effect": {"type": "SKIP"},
                "product": {"cap": mock.ANY, "name": "LCM2_A19", "pid": 27, "vid": 1},
            },
            "d073d5000003": {
                "effect": {"type": "SKIP"},
                "product": {"cap": mock.ANY, "name": "LCMV4_A19_COLOR", "pid": 22, "vid": 1},
            },
            "d073d5000004": {
                "effect": {"type": "SKIP"},
                "product": {"cap": mock.ANY, "name": "LCMV4_A19_WHITE_LV", "pid": 10, "vid": 1},
            },
            "d073d5000005": {
                "effect": {
                    "options": {
                        "duration": 0.0,
                        "instanceid": mock.ANY,
                        "speed": 0.005,
                        "speed_direction": "RIGHT",
                    },
                    "type": "MOVE",
                },
                "product": {"cap": mock.ANY, "name": "LCM2_Z", "pid": 32, "vid": 1},
            },
            "d073d5000006": {
                "effect": {
                    "options": {
                        "duration": 0.0,
                        "instanceid": mock.ANY,
                        "speed": 0.005,
                        "speed_direction": "RIGHT",
                    },
                    "type": "MOVE",
                },
                "product": {"cap": mock.ANY, "name": "LCM1_Z", "pid": 31, "vid": 1},
            },
            "d073d5000007": {
                "effect": {
                    "options": {
                        "duration": 0.0,
                        "instanceid": mock.ANY,
                        "palette": [Color(**color).as_dict() for color in default_tile_palette],
                        "speed": 0.005,
                    },
                    "type": "MORPH",
                },
                "product": {"cap": mock.ANY, "name": "LCM3_CANDLE", "pid": 57, "vid": 1},
            },
            "d073d5000008": {
                "effect": {
                    "options": {
                        "duration": 0.0,
                        "instanceid": mock.ANY,
                        "palette": [],
                        "speed": 0.005,
                    },
                    "type": "OFF",
                },
                "product": {"cap": mock.ANY, "name": "LCM3_TILE", "pid": 55, "vid": 1},
            },
            "d073d5000009": {
                "effect": {"type": "SKIP"},
                "product": {"cap": mock.ANY, "name": "LCM3_A19_CLEAN", "pid": 90, "vid": 1},
            },
            "d073d500000a": {
                "effect": {"type": "SKIP"},
                "product": {"cap": mock.ANY, "name": "LCM3_32_SWITCH_I", "pid": 89, "vid": 1},
            },
        }
    }


@pytest.fixture()
def effects_stopped_status():
    return {
        "results": {
            "d073d5000001": {
                "effect": {"type": "SKIP"},
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_hev": False,
                        "has_ir": False,
                        "has_relays": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_kelvin": 2500,
                        "zones": "SINGLE",
                    },
                    "name": "LCM2_A19",
                    "pid": 27,
                    "vid": 1,
                },
            },
            "d073d5000002": {
                "effect": {"type": "SKIP"},
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_hev": False,
                        "has_relays": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_kelvin": 2500,
                        "zones": "SINGLE",
                    },
                    "name": "LCM2_A19",
                    "pid": 27,
                    "vid": 1,
                },
            },
            "d073d5000003": {
                "effect": {"type": "SKIP"},
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_hev": False,
                        "has_relays": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_kelvin": 2500,
                        "zones": "SINGLE",
                    },
                    "name": "LCMV4_A19_COLOR",
                    "pid": 22,
                    "vid": 1,
                },
            },
            "d073d5000004": {
                "effect": {"type": "SKIP"},
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": False,
                        "has_color": False,
                        "has_extended_multizone": False,
                        "has_hev": False,
                        "has_relays": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 6500,
                        "min_kelvin": 2700,
                        "zones": "SINGLE",
                    },
                    "name": "LCMV4_A19_WHITE_LV",
                    "pid": 10,
                    "vid": 1,
                },
            },
            "d073d5000005": {
                "effect": {
                    "options": {"duration": 0.0, "instanceid": mock.ANY, "speed": 0.005},
                    "type": "OFF",
                },
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_hev": False,
                        "has_relays": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": True,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_kelvin": 2500,
                        "zones": "LINEAR",
                    },
                    "name": "LCM2_Z",
                    "pid": 32,
                    "vid": 1,
                },
            },
            "d073d5000006": {
                "effect": {
                    "options": {"duration": 0.0, "instanceid": mock.ANY, "speed": 0.005},
                    "type": "OFF",
                },
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_hev": False,
                        "has_relays": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": True,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_kelvin": 2500,
                        "zones": "LINEAR",
                    },
                    "name": "LCM1_Z",
                    "pid": 31,
                    "vid": 1,
                },
            },
            "d073d5000007": {
                "effect": {
                    "options": {
                        "duration": 0.0,
                        "instanceid": mock.ANY,
                        "palette": [],
                        "speed": 0.005,
                    },
                    "type": "OFF",
                },
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_hev": False,
                        "has_relays": False,
                        "has_ir": False,
                        "has_matrix": True,
                        "has_multizone": False,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_kelvin": 1500,
                        "zones": "MATRIX",
                    },
                    "name": "LCM3_CANDLE",
                    "pid": 57,
                    "vid": 1,
                },
            },
            "d073d5000008": {
                "effect": {
                    "options": {
                        "duration": 0.0,
                        "instanceid": mock.ANY,
                        "palette": [],
                        "speed": 0.005,
                    },
                    "type": "OFF",
                },
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": True,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_hev": False,
                        "has_relays": False,
                        "has_ir": False,
                        "has_matrix": True,
                        "has_multizone": False,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_kelvin": 2500,
                        "zones": "MATRIX",
                    },
                    "name": "LCM3_TILE",
                    "pid": 55,
                    "vid": 1,
                },
            },
            "d073d5000009": {
                "effect": {"type": "SKIP"},
                "product": {
                    "cap": {
                        "has_buttons": False,
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_hev": True,
                        "has_ir": False,
                        "has_relays": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_unhandled": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_kelvin": 1500,
                        "zones": "SINGLE",
                    },
                    "name": "LCM3_A19_CLEAN",
                    "pid": 90,
                    "vid": 1,
                },
            },
            "d073d500000a": {
                "effect": {"type": "SKIP"},
                "product": {
                    "cap": {
                        "has_buttons": True,
                        "has_chain": None,
                        "has_color": None,
                        "has_extended_multizone": None,
                        "has_hev": None,
                        "has_ir": None,
                        "has_matrix": None,
                        "has_multizone": None,
                        "has_relays": True,
                        "has_unhandled": True,
                        "has_variable_color_temp": None,
                        "max_kelvin": None,
                        "min_kelvin": None,
                        "zones": None,
                    },
                    "name": "LCM3_32_SWITCH_I",
                    "pid": 89,
                    "vid": 1,
                },
            },
        }
    }


@pytest.fixture()
def success_result():
    return {
        "results": {
            "d073d5000001": "ok",
            "d073d5000002": "ok",
            "d073d5000003": "ok",
            "d073d5000004": "ok",
            "d073d5000005": "ok",
            "d073d5000006": "ok",
            "d073d5000007": "ok",
            "d073d5000008": "ok",
            "d073d5000009": "ok",
            "d073d500000a": "ok",
        }
    }


@pytest.fixture()
def results(effects_running_status, effects_stopped_status, success_result):
    class Results:
        def __init__(s):
            s.effects_running = effects_running_status
            s.effects_stopped = effects_stopped_status
            s.success = success_result

    return Results()


class TestEffects:
    class TestV1:
        async def test_it_can_start_effects(self, server, results):
            results.effects_running["results"]["d073d5000008"]["effect"]["type"] = "MORPH"
            palette = results.effects_running["results"]["d073d5000007"]["effect"]["options"]["palette"]
            results.effects_running["results"]["d073d5000008"]["effect"]["options"]["palette"] = palette

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_stopped,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "effects/run",
                    "args": {"matrix_animation": "MORPH", "linear_animation": "MOVE"},
                },
                json_output=results.success,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_running,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/stop"},
                json_output=results.success,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_stopped,
            )

        async def test_it_can_apply_a_theme_first(self, server, results):
            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "effects/run",
                    "args": {
                        "apply_theme": True,
                        "matrix_animation": "MORPH",
                        "linear_animation": "MOVE",
                    },
                },
                json_output=results.success,
            )

        async def test_it_can_start_just_matrix_effects(self, server, results):
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_stopped,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/run", "args": {"matrix_animation": "FLAME"}},
                json_output=results.success,
            )

            results.effects_running["results"]["d073d5000005"]["effect"]["type"] = "OFF"
            del results.effects_running["results"]["d073d5000005"]["effect"]["options"]["speed_direction"]

            results.effects_running["results"]["d073d5000006"]["effect"]["type"] = "OFF"
            del results.effects_running["results"]["d073d5000006"]["effect"]["options"]["speed_direction"]

            results.effects_running["results"]["d073d5000007"]["effect"]["type"] = "FLAME"
            results.effects_running["results"]["d073d5000008"]["effect"]["type"] = "FLAME"

            palette = results.effects_running["results"]["d073d5000007"]["effect"]["options"]["palette"]
            results.effects_running["results"]["d073d5000008"]["effect"]["options"]["palette"] = palette

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_running,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/stop"},
                json_output=results.success,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_stopped,
            )

        async def test_it_can_start_just_linear_effects(self, server, results):
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_stopped,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/run", "args": {"linear_animation": "MOVE"}},
                json_output=results.success,
            )

            results.effects_running["results"]["d073d5000005"]["effect"]["type"] = "MOVE"
            results.effects_running["results"]["d073d5000006"]["effect"]["type"] = "MOVE"
            results.effects_running["results"]["d073d5000007"]["effect"]["type"] = "OFF"
            results.effects_running["results"]["d073d5000007"]["effect"]["options"]["palette"] = []

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_running,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/stop"},
                json_output=results.success,
            )

            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "effects/status"},
                json_output=results.effects_stopped,
            )

        async def test_it_can_start_linear_effects_and_power_on(self, devices, server, results):
            for device in devices:
                await device.change_one("power", 0, event=None)

            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "effects/run",
                    "args": {"linear_animation": "MOVE", "linear_options": {"power_on": True}},
                },
                json_output=results.success,
            )

            for device in devices:
                if device.serial in ("d073d5000005", "d073d5000006"):
                    assert device.attrs.power == 65535

        async def test_it_can_start_matrix_effects_and_power_on(self, devices, server, results):
            for device in devices:
                await device.change_one("power", 0, event=None)

            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "effects/run",
                    "args": {"matrix_animation": "FLAME", "matrix_options": {"power_on": True}},
                },
                json_output=results.success,
            )

            for device in devices:
                if device.serial in ("d073d5000007", "d073d5000008"):
                    assert device.attrs.power == 65535

        async def test_it_can_start_matrix_and_linear_effects_without_powering_on(self, devices, server, results):
            for device in devices:
                await device.change_one("power", 0, event=None)

            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "effects/run",
                    "args": {
                        "matrix_animation": "FLAME",
                        "matrix_options": {"power_on": False},
                        "linear_animation": "MOVE",
                        "linear_options": {"power_on": False},
                    },
                },
                json_output=results.success,
            )

            for device in devices:
                assert device.attrs.power == 0

        async def test_it_can_stop_matrix_and_linear_effects_without_powering_on(self, devices, server, results):
            for device in devices:
                await device.change_one("power", 0, event=None)

            await server.assertCommand(
                "/v1/lifx/command",
                {
                    "command": "effects/stop",
                    "args": {
                        "stop_matrix": True,
                        "matrix_options": {"power_on": False},
                        "stop_linear": True,
                        "linear_options": {"power_on": False},
                    },
                },
                json_output=results.success,
            )

            for device in devices:
                assert device.attrs.power == 0

        async def test_it_works_if_devices_are_offline(self, devices, server, results, sender):
            offline1 = devices["d073d5000001"].offline()
            offline5 = devices["d073d5000005"].offline()
            offline7 = devices["d073d5000007"].offline()

            fail = {
                "error": {
                    "message": "Timed out. Waiting for reply to a packet",
                    "sent_pkt_type": 32,
                    "sequence": mock.ANY,
                    "source": mock.ANY,
                },
                "error_code": "TimedOut",
            }

            for r in (results.success, results.effects_running, results.effects_stopped):
                r["results"]["d073d5000001"] = fail
                r["results"]["d073d5000005"] = fail
                r["results"]["d073d5000007"] = fail
                del r["results"]["d073d5000008"]

            matcher = {"cap": "not_chain"}
            await server.assertCommand("/v1/lifx/command", {"command": "discover"})

            async with offline1, offline5, offline7:
                await server.assertCommand(
                    "/v1/lifx/command",
                    {"command": "effects/status", "args": {"timeout": 3, "matcher": matcher}},
                    json_output=results.effects_stopped,
                )

                await server.assertCommand(
                    "/v1/lifx/command",
                    {
                        "command": "effects/run",
                        "args": {
                            "matrix_animation": "MORPH",
                            "linear_animation": "MOVE",
                            "timeout": 3,
                            "matcher": matcher,
                        },
                    },
                    json_output=results.success,
                )

                await server.assertCommand(
                    "/v1/lifx/command",
                    {"command": "effects/status", "args": {"timeout": 3, "matcher": matcher}},
                    json_output=results.effects_running,
                )

                await server.assertCommand(
                    "/v1/lifx/command",
                    {"command": "effects/stop", "args": {"timeout": 3, "matcher": matcher}},
                    json_output=results.success,
                )

                await server.assertCommand(
                    "/v1/lifx/command",
                    {"command": "effects/status", "args": {"timeout": 3, "matcher": matcher}},
                    json_output=results.effects_stopped,
                )
