# coding: spec

from unittest import mock

import pytest
from interactor.commander.store import load_commands, store
from photons_app import helpers as hp


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


@pytest.fixture(autouse=True)
async def m(FakeTime, MockedCallLater):
    with FakeTime() as t:
        async with MockedCallLater(t) as m:
            yield m


@pytest.fixture()
async def server(store_clone, devices, server_wrapper, sender, final_future):
    async with server_wrapper(store_clone, sender, final_future) as server:
        yield server


describe "Clean Commands":

    @pytest.mark.async_timeout(15)
    async it "has clean commands", devices, server, responses, m:
        all_ok = {"results": {d.serial: "ok" for d in devices}}

        result = {
            "results": {
                "d073d5000009": {
                    "config": {"duration_s": 7200, "indication": False},
                    "status": {"current": {"active": False}, "last": {"result": "NONE"}},
                }
            }
        }
        await server.assertCommand(
            "/v1/lifx/command", {"command": "clean/status"}, json_output=result
        )

        # Start a cycle
        await server.assertCommand(
            "/v1/lifx/command", {"command": "clean/start"}, json_output=all_ok
        )

        result = {
            "results": {
                "d073d5000009": {
                    "config": {"duration_s": 7200, "indication": False},
                    "status": {
                        "current": {
                            "active": True,
                            "duration_s": 7200,
                            "last_power": 65535,
                            "remaining": mock.ANY,
                        },
                        "last": {"result": "BUSY"},
                    },
                }
            }
        }
        await m.add(2)
        got = await server.assertCommand(
            "/v1/lifx/command", {"command": "clean/status"}, json_output=result
        )
        assert (
            7150 < got["results"][devices["clean"].serial]["status"]["current"]["remaining"] < 7200
        )

        # Stop the cycle
        await server.assertCommand(
            "/v1/lifx/command", {"command": "clean/stop"}, json_output=all_ok
        )

        result = {
            "results": {
                "d073d5000009": {
                    "config": {"duration_s": 7200, "indication": False},
                    "status": {
                        "current": {"active": False},
                        "last": {"result": "INTERRUPTED_BY_LAN"},
                    },
                }
            }
        }
        await m.add(2)
        await server.assertCommand(
            "/v1/lifx/command", {"command": "clean/status"}, json_output=result
        )
