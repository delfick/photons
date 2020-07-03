# coding: spec

from interactor.commander.store import store, load_commands

from photons_control.tile import default_tile_palette
from photons_messages.fields import Color

from unittest import mock
import pytest


@pytest.fixture(scope="module")
def store_clone():
    load_commands()
    return store.clone()


@pytest.fixture(scope="module")
async def wrapper(server_wrapper, store_clone):
    async with server_wrapper(store=store_clone) as wrapper:
        yield wrapper


@pytest.fixture(autouse=True)
async def wrap_tests(wrapper):
    async with wrapper.test_wrap():
        yield


@pytest.fixture()
def runner(wrapper):
    return wrapper.runner


@pytest.fixture()
def sender(wrapper):
    return wrapper.server.sender


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
                        "speed": 5.0,
                    },
                    "type": "MORPH",
                },
                "product": {"cap": mock.ANY, "name": "LCM3_CANDLE", "pid": 57, "vid": 1},
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
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_extended_fw": None,
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
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_extended_fw": None,
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
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_extended_fw": None,
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
                        "has_chain": False,
                        "has_color": False,
                        "has_extended_multizone": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_extended_fw": None,
                        "min_kelvin": 2500,
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
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": True,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_extended_fw": [2, 77],
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
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_ir": False,
                        "has_matrix": False,
                        "has_multizone": True,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_extended_fw": None,
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
                        "speed": 5.0,
                    },
                    "type": "OFF",
                },
                "product": {
                    "cap": {
                        "has_chain": False,
                        "has_color": True,
                        "has_extended_multizone": False,
                        "has_ir": False,
                        "has_matrix": True,
                        "has_multizone": False,
                        "has_variable_color_temp": True,
                        "max_kelvin": 9000,
                        "min_extended_fw": None,
                        "min_kelvin": 2500,
                        "zones": "MATRIX",
                    },
                    "name": "LCM3_CANDLE",
                    "pid": 57,
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


describe "Effect commands":

    async it "can start effects", fake, runner, asserter, results:
        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_stopped,
        )

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {
                "command": "effects/run",
                "args": {"matrix_animation": "MORPH", "linear_animation": "MOVE"},
            },
            json_output=results.success,
        )

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_running,
        )

        await runner.assertPUT(
            asserter, "/v1/lifx/command", {"command": "effects/stop"}, json_output=results.success,
        )

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_stopped,
        )

    async it "can apply a theme first", fake, runner, asserter, results:
        await runner.assertPUT(
            asserter,
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

    async it "can start just matrix effects", fake, runner, asserter, results:
        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_stopped,
        )

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/run", "args": {"matrix_animation": "FLAME"}},
            json_output=results.success,
        )

        results.effects_running["results"]["d073d5000005"]["effect"]["type"] = "OFF"
        del results.effects_running["results"]["d073d5000005"]["effect"]["options"][
            "speed_direction"
        ]

        results.effects_running["results"]["d073d5000006"]["effect"]["type"] = "OFF"
        del results.effects_running["results"]["d073d5000006"]["effect"]["options"][
            "speed_direction"
        ]

        results.effects_running["results"]["d073d5000007"]["effect"]["type"] = "FLAME"

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_running,
        )

        await runner.assertPUT(
            asserter, "/v1/lifx/command", {"command": "effects/stop"}, json_output=results.success,
        )

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_stopped,
        )

    async it "can start just linear effects", fake, runner, asserter, results:
        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_stopped,
        )

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/run", "args": {"linear_animation": "MOVE"}},
            json_output=results.success,
        )

        results.effects_running["results"]["d073d5000005"]["effect"]["type"] = "MOVE"
        results.effects_running["results"]["d073d5000006"]["effect"]["type"] = "MOVE"
        results.effects_running["results"]["d073d5000007"]["effect"]["type"] = "OFF"
        results.effects_running["results"]["d073d5000007"]["effect"]["options"]["palette"] = []

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_running,
        )

        await runner.assertPUT(
            asserter, "/v1/lifx/command", {"command": "effects/stop"}, json_output=results.success,
        )

        await runner.assertPUT(
            asserter,
            "/v1/lifx/command",
            {"command": "effects/status"},
            json_output=results.effects_stopped,
        )

    @pytest.mark.async_timeout(1.5)
    @pytest.mark.focus
    async it "works if devices are offline", fake, runner, asserter, results, sender:
        offline1 = fake.for_serial("d073d5000001").offline()
        offline5 = fake.for_serial("d073d5000005").offline()
        offline7 = fake.for_serial("d073d5000007").offline()

        fail = {
            "error": {"message": "Timed out. Waiting for reply to a packet"},
            "error_code": "TimedOut",
            "status": 400,
        }

        for r in (results.success, results.effects_running, results.effects_stopped):
            r["results"]["d073d5000001"] = fail
            r["results"]["d073d5000005"] = fail
            r["results"]["d073d5000007"] = fail

        with offline1, offline5, offline7:
            await runner.assertPUT(
                asserter,
                "/v1/lifx/command",
                {"command": "effects/status", "args": {"timeout": 0.1}},
                json_output=results.effects_stopped,
            )

            await runner.assertPUT(
                asserter,
                "/v1/lifx/command",
                {
                    "command": "effects/run",
                    "args": {
                        "matrix_animation": "MORPH",
                        "linear_animation": "MOVE",
                        "timeout": 0.1,
                    },
                },
                json_output=results.success,
            )

            await runner.assertPUT(
                asserter,
                "/v1/lifx/command",
                {"command": "effects/status", "args": {"timeout": 0.1}},
                json_output=results.effects_running,
            )

            await runner.assertPUT(
                asserter,
                "/v1/lifx/command",
                {"command": "effects/stop", "args": {"timeout": 0.1}},
                json_output=results.success,
            )

            await runner.assertPUT(
                asserter,
                "/v1/lifx/command",
                {"command": "effects/status", "args": {"timeout": 0.1}},
                json_output=results.effects_stopped,
            )
