from unittest.mock import ANY


class TestCommands:
    class TestV1:
        async def test_it_has_http_commands(self, server, responses):
            # invalid path
            await server.assertCommand(
                "/blah",
                {"command": "query", "args": {"pkt_type": 101}},
                json_output={
                    "description": "Not Found",
                    "message": "Requested URL /blah not found",
                    "status": 404,
                },
                status=404,
            )

            # invalid command
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "no"},
                json_output={
                    "description": "Bad Request",
                    "message": "Unknown command 'no'",
                    "status": 400,
                },
                status=400,
            )

            # valid command
            await server.assertCommand(
                "/v1/lifx/command",
                {"command": "query", "args": {"pkt_type": 101}},
                json_output=responses.light_state_responses,
            )

        async def test_it_has_websocket_commands(self, server, responses):
            async with server.ws_stream() as stream:
                # Invalid path
                await stream.create("/blah", {"stuff": True})
                await stream.check_reply(
                    {
                        "error": {
                            "available": ["/v1/lifx/command"],
                            "error": "Specified path is invalid",
                            "wanted": "/blah",
                        },
                        "error_code": "NoSuchPath",
                    }
                )

                # invalid command
                await stream.create("/v1/lifx/command", {"command": "nope"})
                reply = await stream.check_reply(ANY)
                assert len(reply["error"]["available"]) > 5

                assert reply == {
                    "error": {
                        "error": "Specified command is unknown",
                        "wanted": "nope",
                        "available": ANY,
                    },
                    "error_code": "NoSuchCommand",
                }

                # valid command
                await stream.create(
                    "/v1/lifx/command",
                    {"command": "query", "args": {"pkt_type": 101}},
                )
                await stream.check_reply(responses.light_state_responses)
