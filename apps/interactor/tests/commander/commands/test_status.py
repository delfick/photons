
from photons_app import mimic

class TestStatus:
    class TestV1:

        async def test_it_has_v1_routes(self, devices: mimic.DeviceCollection, server, responses):
            await server.assertCommand(
                "/v1/lifx/command", {"command": "status"}, json_output={"on": True}
            )

            await server.assertMethod("GET", "/v1/lifx/status", json_output={"on": True})

    class TestV2:

        async def test_it_GET_v2_status(self, devices: mimic.DeviceCollection, server, responses):
            await server.assertMethod("GET", "/v2/status", json_output={"on": True})
