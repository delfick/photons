# coding: spec

import asyncio
from unittest import mock

import pytest
from photons_app import mimic

describe "Clean":
    describe "v1":

        @pytest.mark.async_timeout(15)
        async it "has v1 routes", devices: mimic.DeviceCollection, server, responses:
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
            await asyncio.sleep(2)
            got = await server.assertCommand(
                "/v1/lifx/command", {"command": "clean/status"}, json_output=result
            )
            assert (
                7150
                < got["results"][devices["clean"].serial]["status"]["current"]["remaining"]
                < 7200
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
            await asyncio.sleep(2)
            await server.assertCommand(
                "/v1/lifx/command", {"command": "clean/status"}, json_output=result
            )
