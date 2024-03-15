# coding: spec

import asyncio
from unittest import mock

import pytest
from photons_app.mimic.event import Events
from photons_canvas.points.simple_messages import Set64


@pytest.fixture(autouse=True)
def set_async_timeout(request):
    request.applymarker(pytest.mark.async_timeout(15))


describe "Animation Commands":
    describe "V1":
        async it "can get info and help", server:
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
                json_output={"animations": {}, "paused": []},
            )

            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/help"},
            )
            assert "Available animations include" in got
            assert "* dice" in got
            assert "To see options for a particular animation, run this again" in got

            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/help", "args": {"animation_name": "dice"}},
            )
            assert "dice animation" in got
            assert "This animation has the following options:" in got
            assert "colour range options" in got

        async it "can control an animation", server:
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
                json_output={"animations": {}, "paused": []},
            )

            identity = "first"
            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/start", "args": {"identity": identity}},
            )

            assert "animations" in got
            assert got["animations"] == [identity]
            assert got["started"] == identity

            identity2 = "second"
            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/start", "args": {"identity": identity2}},
            )

            assert "animations" in got
            identities = [identity, identity2]
            assert got["animations"] == identities
            assert got["started"] == identity2

            info = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
            )
            assert info == {"animations": {identity: mock.ANY, identity2: mock.ANY}, "paused": []}

            # pause
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/pause", "args": {"pause": identity}},
                json_output={"animations": identities, "paused": [identity], "pausing": [identity]},
            )
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/pause", "args": {"pause": identity2}},
                json_output={
                    "animations": identities,
                    "paused": identities,
                    "pausing": [identity2],
                },
            )

            # resume
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/resume", "args": {"resume": identity2}},
                json_output={
                    "animations": identities,
                    "paused": [identity],
                    "resuming": [identity2],
                },
            )

            # pause multiple
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/pause", "args": {"pause": identities}},
                json_output={"animations": identities, "paused": identities, "pausing": identities},
            )

            # resume
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/resume", "args": {"resume": identities}},
                json_output={
                    "animations": identities,
                    "paused": [],
                    "resuming": identities,
                },
            )

            # pause
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/pause", "args": {"pause": identity}},
                json_output={"animations": identities, "paused": [identity], "pausing": [identity]},
            )

            # info
            info = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
            )
            assert info["animations"] == {identity: mock.ANY, identity2: mock.ANY}
            assert info["paused"] == [identity]

            # stop
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/stop", "args": {"stop": identity}},
                json_output={
                    "animations": [identity, identity2],
                    "paused": [identity],
                    "stopping": [identity],
                },
            )

            await asyncio.sleep(0.5)

            # info
            info = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
            )
            assert info["animations"] == {identity2: mock.ANY}
            assert info["paused"] == []

        async it "pausing an animation actually pauses the animation", devices, server:
            tile = devices["tile"]
            io = tile.io["MEMORY"]
            store = devices.store(tile)
            store.clear()

            first_set_64 = tile.attrs.event_waiter.wait_for_incoming(io, Set64)

            # start
            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/start", "args": {"animations": [["balls", {"every": 3}]]}},
            )
            identity = got["started"]

            await first_set_64
            now = store.count(Events.INCOMING(tile, io, pkt=Set64))
            assert now > 0
            await asyncio.sleep(5)
            now2 = store.count(Events.INCOMING(tile, io, pkt=Set64))
            assert now2 > now

            identity = got["started"]
            await asyncio.sleep(5)
            assert store.count(Events.INCOMING(tile, io, pkt=Set64)) > now

            # pause
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/pause", "args": {"pause": [identity]}},
            )
            await asyncio.sleep(5)
            store.clear()
            await asyncio.sleep(5)
            assert store.count(Events.INCOMING(tile, io, pkt=Set64)) == 0

            # resume
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/resume", "args": {"resume": [identity]}},
            )

            await asyncio.sleep(5)
            assert store.count(Events.INCOMING(tile, io, pkt=Set64)) > 0

            # stop
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/stop", "args": {"stop": [identity]}},
            )
            store.clear()
            await asyncio.sleep(5)
            store.clear()

            await asyncio.sleep(5)
            assert store.count(Events.INCOMING(tile, io, pkt=Set64)) == 0

            # info
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
                json_output={"animations": {}, "paused": []},
            )

        async it "can get information", server:
            # start
            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/start", "args": {"animations": [["balls", {"every": 0.3}]]}},
            )
            identity = got["started"]

            info = await server.assertCommand("/v1/lifx/command", {"command": "animation/info"})

            assert info["paused"] == []

            assert identity in info["animations"]
            assert info["animations"][identity]["animations_ran"] == 1
            assert info["animations"][identity]["current_animation"] == {
                "name": "balls",
                "options": {
                    "ball_colors": "<ManyColor:[((0, 360), (1000, 1000), (1000, 1000), (3500, 3500))]>",
                    "fade_amount": 0.02,
                    "num_balls": 5,
                    "rate": "<Rate 0.9 -> 1>",
                },
                "started": mock.ANY,
            }

            assert info["animations"][identity]["options"]["combined"]
            assert "unlocked" in info["animations"][identity]["options"]["pauser"]
            assert info["animations"][identity]["options"]["noisy_network"] == 0

            specific = await server.assertCommand(
                "/v1/lifx/command", {"command": "animation/info", "args": {"identity": identity}}
            )
            info["animations"][identity]["current_animation"]["started"] = mock.ANY
            assert info["animations"][identity] == specific
