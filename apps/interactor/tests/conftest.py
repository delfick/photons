from interactor.options import Options
from interactor.server import Server

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import BadRun
from photons_app import helpers as hp

from photons_transport.targets import MemoryTarget
from photons_control import test_helpers as chp
from photons_messages import protocol_register
from photons_transport.fake import FakeDevice
from photons_products import Products

from unittest import mock
import tempfile
import aiohttp
import logging
import asyncio
import pytest
import shutil
import uuid
import sys

log = logging.getLogger("interactor.test_helpers")


class AsyncCMMixin:
    async def __aenter__(self):
        try:
            return await self.start()
        finally:
            # aexit doesn't run if aenter raises an exception
            exc_info = sys.exc_info()
            if exc_info[1] is not None:
                await self.__aexit__(*exc_info)
                raise

    async def start(self):
        raise NotImplementedError()

    async def __aexit__(self, exc_typ, exc, tb):
        await self.finish(exc_typ, exc, tb)

    async def finish(self, exc_typ=None, exc=None, tb=None):
        raise NotImplementedError()


@pytest.fixture(scope="session")
def temp_dir_maker():
    class Maker:
        def __enter__(s):
            s.dir = tempfile.mkdtemp()
            return s.dir

        def __exit__(s, exc_type, exc, tb):
            if hasattr(s, "dir") and s.dir:
                shutil.rmtree(s.dir)

    return Maker


@pytest.fixture(scope="session")
async def server_wrapper():
    return ServerWrapper


@pytest.fixture(scope="session")
def options_maker():
    return make_options


def make_options(host=None, port=None, database=None, memory=True):
    options = {}
    if database or memory:
        options = {"database": database or {"uri": ":memory:"}}

    if host is not None:
        options["host"] = host

    if port is not None:
        options["port"] = port

    return Options.FieldSpec(formatter=MergedOptionStringFormatter).empty_normalise(**options)


class WSTester(AsyncCMMixin):
    def __init__(self, port, path="/v1/ws"):
        self.path = path
        self.port = port
        self.message_id = None

    async def start(self):
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(f"ws://127.0.0.1:{self.port}{self.path}")

        class IsNum:
            def __eq__(self, value):
                self.got = value
                return type(value) is float

            def __repr__(self):
                if hasattr(self, "got"):
                    return repr(self.got)
                else:
                    return "<NOVALUE_COMPARED>"

        await self.check_reply(IsNum(), message_id="__server_time__")
        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        try:
            if hasattr(self, "ws"):
                await self.ws.close()
                await self.ws.receive() is None
        finally:
            if hasattr(self, "session"):
                await self.session.close()

    async def create(self, path, body):
        self.message_id = str(uuid.uuid1())
        msg = {"path": path, "body": body, "message_id": self.message_id}
        await self.ws.send_json(msg)

    async def check_reply(self, reply, message_id=None):
        got = await self.ws.receive_json()
        wanted = {
            "reply": reply,
            "message_id": self.message_id if message_id is None else message_id,
        }
        return pytest.helpers.assertComparison(got, wanted, is_json=True)["reply"]


class ServerWrapper(AsyncCMMixin):
    def __init__(self, store, **kwargs):
        self.store = store
        self.kwargs = kwargs
        self.cleaners = []

    def per_test(self):
        class PerTest(AsyncCMMixin):
            async def start(s):
                for device in fakery.devices:
                    await device.reset()

            async def finish(s, exc_typ=None, exc=None, tb=None):
                for device in fakery.devices:
                    await device.wait_for_reboot_fut

        return PerTest()

    def ws_stream(self, path="/v1/ws"):
        return WSTester(self.port, path=path)

    async def ws_connect(self):
        if hasattr(self, "ws"):
            await self.ws.finish(None, None, None)
        self.ws = await WSTester(self.port, "/v1/ws").start()
        return self.ws

    async def ws_read(self, connection):
        return await self.ws.ws.receive_json()

    async def ws_write(self, connection, msg):
        return await self.ws.ws.send_json(msg)

    async def command(self, path, body, *, expect_status):
        async with aiohttp.ClientSession() as session:
            content = None
            try:
                async with session.put(
                    f"http://127.0.0.1:{self.port}{path}", json=body
                ) as response:
                    content = await response.read()
                    if "json" in response.headers.get("Content-Type", ""):
                        content = await response.json()
                    assert response.status == expect_status, content
                    return content
            except aiohttp.ClientResponseError as error:
                raise BadRun("Failed to get a result", error=error, content=content)

    async def assertCommand(self, path, command, status=200, json_output=None, text_output=None):
        try:
            got = await self.command(path, command, expect_status=status)
            return got
        except BadRun as error:
            assert error.kwargs["status"] == status
            if json_output is not None:
                assert error.kwargs["content"] == json_output
            if text_output is not None:
                assert error.kwargs["content"] == text_output
        else:
            if json_output is not None:
                assert got == json_output
            if text_output is not None:
                assert got == text_output

    @hp.memoized_property
    def final_future(self):
        return hp.create_future()

    @hp.memoized_property
    def server(self):
        return Server(self.final_future, self.store)

    async def start(self):
        self.port = self.kwargs.get("port", None) or pytest.helpers.free_port()
        await pytest.helpers.wait_for_no_port(self.port)

        self.options = make_options(**{**self.kwargs, "port": self.port})

        self.Wrapped = fakery(self.options, self.final_future)
        await self.Wrapped.__aenter__()

        self.sender = await self.options.lan.make_sender()

        self._task = hp.async_as_background(
            self.server.serve(
                "127.0.0.1", self.options.port, self.options, self.sender, self.cleaners
            )
        )

        await pytest.helpers.wait_for_port(self.port)

        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        self.final_future.cancel()
        if hasattr(self, "_task"):
            await asyncio.wait([self._task])

        if hasattr(self.server.finder.finish, "mock_calls"):
            assert len(self.server.finder.finish.mock_calls) == 0

        waited = []
        async with hp.TaskHolder(hp.create_future()) as ts:
            for cleaner in self.cleaners:
                waited.append(ts.add(cleaner()))

        async with hp.TaskHolder(hp.create_future()) as ts:
            if hasattr(self, "Wrapped"):
                waited.append(ts.add(self.Wrapped.__aexit__(exc_typ, exc, tb)))

            waited.append(ts.add(pytest.helpers.wait_for_no_port(self.port)))
            waited.append(ts.add(self.options.lan.close_sender(self.sender)))

            if hasattr(self, "ws"):
                waited.append(ts.add(self.ws.__aexit__(None, None, None)))

        # make sure none failed
        for w in waited:
            await w

        # Prevent coroutine not awaited error
        await asyncio.sleep(0.01)

        if hasattr(self.server.finder.finish, "mock_calls"):
            self.server.finder.finish.assert_called_once_with()


identifier = lambda: str(uuid.uuid4()).replace("-", "")

group_one_label = "Living Room"
group_one_uuid = identifier()

group_two_label = "Bathroom"
group_two_uuid = identifier()

group_three_label = "desk"
group_three_uuid = identifier()

location_one_label = "Home"
location_one_uuid = identifier()

location_two_label = "Work"
location_two_uuid = identifier()

zones = []
for i in range(16):
    zones.append(chp.Color(i * 10, 1, 1, 2500))


class FakeDevice(FakeDevice):
    def compare_received_set(self, expected, keep_duplicates=False):
        self.received = [m for m in self.received if m.__class__.__name__.startswith("Set")]
        super().compare_received(expected, keep_duplicates=keep_duplicates)

    def expect_no_set_messages(self):
        assert not any([m for m in self.received if m.__class__.__name__.startswith("Set")])


a19_1 = FakeDevice(
    "d073d5000001",
    chp.default_responders(
        Products.LCM2_A19,
        label="kitchen",
        power=0,
        group_label=group_one_label,
        group_uuid=group_one_uuid,
        location_label=location_one_label,
        location_uuid=location_one_uuid,
        color=chp.Color(0, 1, 1, 2500),
        firmware=chp.Firmware(2, 75, 1521690429),
    ),
)

a19_2 = FakeDevice(
    "d073d5000002",
    chp.default_responders(
        Products.LCM2_A19,
        label="bathroom",
        power=65535,
        color=chp.Color(100, 1, 1, 2500),
        group_label=group_two_label,
        group_uuid=group_two_uuid,
        location_label=location_one_label,
        location_uuid=location_one_uuid,
        firmware=chp.Firmware(2, 75, 1521690429),
    ),
)

color1000 = FakeDevice(
    "d073d5000003",
    chp.default_responders(
        Products.LCMV4_A19_COLOR,
        label="lamp",
        power=65535,
        color=chp.Color(100, 0, 1, 2500),
        group_label=group_three_label,
        group_uuid=group_three_uuid,
        location_label=location_two_label,
        location_uuid=location_two_uuid,
        firmware=chp.Firmware(1, 1, 1530327089),
    ),
)

white800 = FakeDevice(
    "d073d5000004",
    chp.default_responders(
        Products.LCMV4_A19_WHITE_LV,
        label="lamp",
        power=65535,
        color=chp.Color(100, 0, 1, 2500),
        group_label=group_three_label,
        group_uuid=group_three_uuid,
        location_label=location_two_label,
        location_uuid=location_two_uuid,
        firmware=chp.Firmware(1, 1, 1530327089),
    ),
)

strip1 = FakeDevice(
    "d073d5000005",
    chp.default_responders(
        Products.LCM2_Z,
        label="desk",
        power=65535,
        zones=zones,
        color=chp.Color(200, 0.5, 0.5, 2500),
        group_label=group_one_label,
        group_uuid=group_one_uuid,
        location_label=location_one_label,
        location_uuid=location_one_uuid,
        firmware=chp.Firmware(2, 75, 1521690429),
    ),
)

strip2 = FakeDevice(
    "d073d5000006",
    chp.default_responders(
        Products.LCM1_Z,
        label="tv",
        power=65535,
        zones=zones,
        color=chp.Color(200, 0.5, 0.5, 2500),
        group_label=group_three_label,
        group_uuid=group_three_uuid,
        location_label=location_two_label,
        location_uuid=location_two_uuid,
        firmware=chp.Firmware(1, 1, 1530327089),
    ),
)

candle = FakeDevice(
    "d073d5000007",
    chp.default_responders(
        Products.LCM3_CANDLE,
        label="pretty",
        power=65535,
        group_label=group_three_label,
        group_uuid=group_three_uuid,
        location_label=location_two_label,
        location_uuid=location_two_uuid,
        firmware=chp.Firmware(3, 50, 1562659776000000000),
    ),
)


class Fakery:
    def __init__(self):
        self.devices = [a19_1, a19_2, color1000, white800, strip1, strip2, candle]

    def for_serial(self, serial):
        for d in self.devices:
            if d.serial == serial:
                return d
        assert False, f"Expected one device with serial {serial}"

    def for_attribute(self, key, value, expect=1):
        got = []
        for d in self.devices:
            if d.attrs[key] == value:
                got.append(d)
        assert len(got) == expect, f"Expected {expect} devices, got {len(got)}: {got}"
        return got

    def __call__(self, options, final_future):
        configuration = {
            "final_future": final_future,
            "protocol_register": protocol_register,
        }

        options.lan = MemoryTarget.create(configuration, {"devices": self.devices})
        options.fake_devices = self.devices

        class Call(AsyncCMMixin):
            async def start(s):
                for device in fakery.devices:
                    await device.start()
                return s

            async def finish(s, exc_typ=None, exc=None, tb=None):
                for device in fakery.devices:
                    await device.finish()

        return Call()


fakery = Fakery()


@pytest.fixture()
def fake():
    return fakery


class Around:
    def __init__(self, val, gap=0.05):
        self.val = val
        self.gap = gap

    def __eq__(self, other):
        return other - self.gap < self.val < other + self.gap

    def __repr__(self):
        return f"<Around {self.val}>"


discovery_response = {
    "d073d5000001": {
        "brightness": 1.0,
        "cap": [
            "color",
            "not_chain",
            "not_ir",
            "not_matrix",
            "not_multizone",
            "variable_color_temp",
        ],
        "firmware_version": "2.75",
        "group_id": mock.ANY,
        "group_name": "Living Room",
        "hue": 0.0,
        "kelvin": 2500,
        "label": "kitchen",
        "location_id": mock.ANY,
        "location_name": "Home",
        "power": "off",
        "product_id": 27,
        "product_identifier": "lifx_a19",
        "saturation": 1.0,
        "serial": "d073d5000001",
    },
    "d073d5000002": {
        "brightness": 1.0,
        "cap": [
            "color",
            "not_chain",
            "not_ir",
            "not_matrix",
            "not_multizone",
            "variable_color_temp",
        ],
        "firmware_version": "2.75",
        "group_id": mock.ANY,
        "group_name": "Bathroom",
        "hue": Around(100),
        "kelvin": 2500,
        "label": "bathroom",
        "location_id": mock.ANY,
        "location_name": "Home",
        "power": "on",
        "product_id": 27,
        "product_identifier": "lifx_a19",
        "saturation": 1.0,
        "serial": "d073d5000002",
    },
    "d073d5000003": {
        "brightness": 1.0,
        "cap": [
            "color",
            "not_chain",
            "not_ir",
            "not_matrix",
            "not_multizone",
            "variable_color_temp",
        ],
        "firmware_version": "1.1",
        "group_id": mock.ANY,
        "group_name": "desk",
        "hue": Around(100),
        "kelvin": 2500,
        "label": "lamp",
        "location_id": mock.ANY,
        "location_name": "Work",
        "power": "on",
        "product_id": 22,
        "product_identifier": "lifx_a19_color",
        "saturation": 0.0,
        "serial": "d073d5000003",
    },
    "d073d5000004": {
        "brightness": 1.0,
        "cap": [
            "not_chain",
            "not_color",
            "not_ir",
            "not_matrix",
            "not_multizone",
            "variable_color_temp",
        ],
        "firmware_version": "1.1",
        "group_id": mock.ANY,
        "group_name": "desk",
        "hue": Around(100),
        "kelvin": 2500,
        "label": "lamp",
        "location_id": mock.ANY,
        "location_name": "Work",
        "power": "on",
        "product_id": 10,
        "product_identifier": "lifx_a19_white",
        "saturation": 0.0,
        "serial": "d073d5000004",
    },
    "d073d5000005": {
        "brightness": Around(0.5),
        "cap": ["color", "multizone", "not_chain", "not_ir", "not_matrix", "variable_color_temp"],
        "firmware_version": "2.75",
        "group_id": mock.ANY,
        "group_name": "Living Room",
        "hue": Around(200),
        "kelvin": 2500,
        "label": "desk",
        "location_id": mock.ANY,
        "location_name": "Home",
        "power": "on",
        "product_id": 32,
        "product_identifier": "lifx_z",
        "saturation": Around(0.5),
        "serial": "d073d5000005",
    },
    "d073d5000006": {
        "brightness": Around(0.5),
        "cap": ["color", "multizone", "not_chain", "not_ir", "not_matrix", "variable_color_temp"],
        "firmware_version": "1.1",
        "group_id": mock.ANY,
        "group_name": "desk",
        "hue": Around(200),
        "kelvin": 2500,
        "label": "tv",
        "location_id": mock.ANY,
        "location_name": "Work",
        "power": "on",
        "product_id": 31,
        "product_identifier": "lifx_z",
        "saturation": Around(0.5),
        "serial": "d073d5000006",
    },
    "d073d5000007": {
        "brightness": 1.0,
        "cap": ["color", "matrix", "not_chain", "not_ir", "not_multizone", "variable_color_temp"],
        "firmware_version": "3.50",
        "group_id": mock.ANY,
        "group_name": "desk",
        "hue": 0.0,
        "kelvin": 3500,
        "label": "pretty",
        "location_id": mock.ANY,
        "location_name": "Work",
        "power": "on",
        "product_id": 57,
        "product_identifier": "lifx_candle",
        "saturation": 1.0,
        "serial": "d073d5000007",
    },
}

light_state_responses = {
    "results": {
        "d073d5000001": {
            "payload": {
                "brightness": 1.0,
                "hue": 0.0,
                "kelvin": 2500,
                "label": "kitchen",
                "power": 0,
                "saturation": 1.0,
            },
            "pkt_name": "LightState",
            "pkt_type": 107,
        },
        "d073d5000002": {
            "payload": {
                "brightness": 1.0,
                "hue": Around(100),
                "kelvin": 2500,
                "label": "bathroom",
                "power": 65535,
                "saturation": 1.0,
            },
            "pkt_name": "LightState",
            "pkt_type": 107,
        },
        "d073d5000003": {
            "payload": {
                "brightness": 1.0,
                "hue": Around(100),
                "kelvin": 2500,
                "label": "lamp",
                "power": 65535,
                "saturation": 0.0,
            },
            "pkt_name": "LightState",
            "pkt_type": 107,
        },
        "d073d5000004": {
            "payload": {
                "brightness": 1.0,
                "hue": Around(100),
                "kelvin": 2500,
                "label": "lamp",
                "power": 65535,
                "saturation": 0.0,
            },
            "pkt_name": "LightState",
            "pkt_type": 107,
        },
        "d073d5000005": {
            "payload": {
                "brightness": Around(0.5),
                "hue": Around(200),
                "kelvin": 2500,
                "label": "desk",
                "power": 65535,
                "saturation": Around(0.5),
            },
            "pkt_name": "LightState",
            "pkt_type": 107,
        },
        "d073d5000006": {
            "payload": {
                "brightness": Around(0.5),
                "hue": Around(200),
                "kelvin": 2500,
                "label": "tv",
                "power": 65535,
                "saturation": Around(0.5),
            },
            "pkt_name": "LightState",
            "pkt_type": 107,
        },
        "d073d5000007": {
            "payload": {
                "brightness": 1.0,
                "hue": 0.0,
                "kelvin": 3500,
                "label": "pretty",
                "power": 65535,
                "saturation": 1.0,
            },
            "pkt_name": "LightState",
            "pkt_type": 107,
        },
    }
}

label_state_responses = {
    "results": {
        "d073d5000001": {"payload": {"label": "kitchen"}, "pkt_name": "StateLabel", "pkt_type": 25},
        "d073d5000002": {
            "payload": {"label": "bathroom"},
            "pkt_name": "StateLabel",
            "pkt_type": 25,
        },
        "d073d5000003": {"payload": {"label": "lamp"}, "pkt_name": "StateLabel", "pkt_type": 25},
        "d073d5000004": {"payload": {"label": "lamp"}, "pkt_name": "StateLabel", "pkt_type": 25},
        "d073d5000005": {"payload": {"label": "desk"}, "pkt_name": "StateLabel", "pkt_type": 25},
        "d073d5000006": {"payload": {"label": "tv"}, "pkt_name": "StateLabel", "pkt_type": 25},
        "d073d5000007": {"payload": {"label": "pretty"}, "pkt_name": "StateLabel", "pkt_type": 25},
    }
}

multizone_state_responses = {
    "results": {
        "d073d5000005": [
            {
                "payload": {
                    "colors": [
                        {"brightness": 1.0, "hue": 0.0, "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(10), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(20), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(30), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(40), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(50), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(60), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(70), "kelvin": 2500, "saturation": 1.0},
                    ],
                    "zones_count": 16,
                    "zone_index": 0,
                },
                "pkt_name": "StateMultiZone",
                "pkt_type": 506,
            },
            {
                "payload": {
                    "colors": [
                        {"brightness": 1.0, "hue": Around(80), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(90), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(100), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(110), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(120), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(130), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(140), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(150), "kelvin": 2500, "saturation": 1.0},
                    ],
                    "zones_count": 16,
                    "zone_index": 8,
                },
                "pkt_name": "StateMultiZone",
                "pkt_type": 506,
            },
        ],
        "d073d5000006": [
            {
                "payload": {
                    "colors": [
                        {"brightness": 1.0, "hue": 0.0, "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(10), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(20), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(30), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(40), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(50), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(60), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(70), "kelvin": 2500, "saturation": 1.0},
                    ],
                    "zones_count": 16,
                    "zone_index": 0,
                },
                "pkt_name": "StateMultiZone",
                "pkt_type": 506,
            },
            {
                "payload": {
                    "colors": [
                        {"brightness": 1.0, "hue": Around(80), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(90), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(100), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(110), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(120), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(130), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(140), "kelvin": 2500, "saturation": 1.0},
                        {"brightness": 1.0, "hue": Around(150), "kelvin": 2500, "saturation": 1.0},
                    ],
                    "zones_count": 16,
                    "zone_index": 8,
                },
                "pkt_name": "StateMultiZone",
                "pkt_type": 506,
            },
        ],
    }
}


@pytest.fixture(scope="session")
def responses():
    class Responses:
        def __init__(s):
            s.discovery_response = discovery_response
            s.light_state_responses = light_state_responses
            s.multizone_state_responses = multizone_state_responses
            s.label_state_responses = label_state_responses

    return Responses()
