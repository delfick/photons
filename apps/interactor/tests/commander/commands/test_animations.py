# coding: spec

from interactor.commander.store import store, load_commands

from photons_app import helpers as hp

from photons_canvas.points.simple_messages import Set64
from photons_messages import TileMessages

from unittest import mock
import pytest


@pytest.fixture(scope="module")
def store_clone():
    load_commands()
    return store.clone()


@pytest.fixture(scope="module")
async def server(store_clone, server_wrapper, FakeTime, MockedCallLater):
    """
    I create a new server per test because the tests get confused way too easily
    and hang because I need MockedCallLater in these ones
    """

    @hp.asynccontextmanager
    async def server():
        with FakeTime() as t:
            async with MockedCallLater(t) as m:
                async with server_wrapper(store_clone) as server:
                    async with server.per_test():
                        yield server, m

    return server


describe "Animation Commands":

    async it "can get info and help", fake, server:
        async with server() as (server, m):
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
                json_output={"animations": {}, "paused": []},
            )

            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/help"},
            )
            assert b"Available animations include" in got
            assert b"* dice" in got
            assert b"To see options for a particular animation, run this again" in got

            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/help", "args": {"animation_name": "dice"}},
            )
            assert b"dice animation" in got
            assert b"This animation has the following options:" in got
            assert b"colour range options" in got

    @pytest.mark.async_timeout(5)
    async it "can control an animation", fake, server:
        async with server() as (server, m):
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

            await m.add(0.5)

            # info
            info = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
            )
            assert info["animations"] == {identity2: mock.ANY}
            assert info["paused"] == []

    @pytest.mark.async_timeout(5)
    async it "pausing an animation actually pauses the animation", fake, server:
        async with server() as (server, m):
            tile = fake.for_serial("d073d5000008")
            first_set_64 = tile.wait_for("memory", Set64)
            assert tile.received == []

            # start
            got = await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/start", "args": {"animations": [["balls", {"every": 3}]]}},
            )
            identity = got["started"]

            await first_set_64
            await m.add(5)
            assert any(pkt | TileMessages.Set64 for pkt in tile.received), [
                type(pkt).__name__ for pkt in tile.received
            ]
            tile.received.clear()

            identity = got["started"]
            await m.add(5)
            assert any(pkt | TileMessages.Set64 for pkt in tile.received), [
                type(pkt).__name__ for pkt in tile.received
            ]

            # pause
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/pause", "args": {"pause": [identity]}},
            )
            tile.received.clear()
            await m.add(5)
            tile.received.clear()

            await m.add(5)
            assert not any(pkt | TileMessages.Set64 for pkt in tile.received), [
                type(pkt).__name__ for pkt in tile.received
            ]

            # resume
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/resume", "args": {"resume": [identity]}},
            )
            tile.received.clear()

            await m.add(5)
            assert any(pkt | TileMessages.Set64 for pkt in tile.received), [
                type(pkt).__name__ for pkt in tile.received
            ]

            # stop
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/stop", "args": {"stop": [identity]}},
            )
            tile.received.clear()
            await m.add(5)
            tile.received.clear()

            await m.add(5)
            assert not any(pkt | TileMessages.Set64 for pkt in tile.received), [
                type(pkt).__name__ for pkt in tile.received
            ]

            # info
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "animation/info"},
                json_output={"animations": {}, "paused": []},
            )

    @pytest.mark.async_timeout(5)
    async it "can get information", fake, server:
        async with server() as (server, m):
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
                    "ball_colors": "<ManyColor:[((0, 360), (1000.0, 1000.0), (1000.0, 1000.0), (3500.0, 3500.0))]>",
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
