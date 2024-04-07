# coding: spec

from photons_app import mimic

describe "Status":
    describe "v1":

        async it "has v1 routes", devices: mimic.DeviceCollection, server, responses:
            await server.assertCommand(
                "/v1/lifx/command", {"command": "status"}, json_output={"on": True}
            )

            await server.assertMethod("GET", "/v1/lifx/status", json_output={"on": True})

    describe "v2":

        async it "GET /v2/status", devices: mimic.DeviceCollection, server, responses:
            await server.assertMethod("GET", "/v2/status", json_output={"on": True})
