# coding: spec

import uuid

from photons_app import mimic

describe "Discovery":
    describe "v1":
        async it "has v1 routes", devices: mimic.DeviceCollection, server, responses:
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

            connection = await server.ws_connect()

            msg_id = str(uuid.uuid1())
            await server.ws_write(
                connection,
                {
                    "path": "/v1/lifx/command",
                    "body": {"command": "discover", "args": {"just_serials": True}},
                    "message_id": msg_id,
                },
            )
            got = await server.ws_read(connection)
            assert got == {
                "message_id": msg_id,
                "request_identifier": got["request_identifier"],
                "reply": [device.serial for device in devices],
            }

    describe "v2":
        async it "GET /v2/discover/serials", devices: mimic.DeviceCollection, server, responses:
            serials = await server.assertMethod("GET", "/v2/discover/serials")
            assert sorted(serials) == sorted(device.serial for device in devices)

            serials = await server.assertMethod("GET", "/v2/discover/serials/match:label=kitchen")
            assert serials == ["d073d5000001"]

        async it "GET /v2/discover/info", devices: mimic.DeviceCollection, server, responses:
            await server.assertMethod(
                "GET", "/v2/discover/info", json_output=responses.discovery_response
            )

            info = await server.assertMethod("GET", "/v2/discover/info/match:label=kitchen")
            assert info == {"d073d5000001": responses.discovery_response["d073d5000001"]}

        async it "PUT /v2/discover", devices: mimic.DeviceCollection, server, responses:
            await server.assertMethod(
                "PUT",
                "/v2/discover",
                body={"command": "info"},
                json_output=responses.discovery_response,
            )

            info = await server.assertMethod(
                "PUT", "/v2/discover", body={"command": "info", "selector": {"label": "kitchen"}}
            )
            assert info == {"d073d5000001": responses.discovery_response["d073d5000001"]}

            serials = await server.assertMethod("PUT", "/v2/discover", body={"command": "serials"})
            assert sorted(serials) == sorted(device.serial for device in devices)

            serials = await server.assertMethod(
                "PUT", "/v2/discover", body={"selector": {"label": "kitchen"}}
            )
            assert serials == ["d073d5000001"]
