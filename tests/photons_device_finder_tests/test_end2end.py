# coding: spec

from photons_device_finder import DeviceFinder, InfoPoints, DeviceFinderWrap, Filter

from photons_app.registers import ProtocolRegister

from photons_messages import DeviceMessages, LightMessages, protocol_register
from photons_transport.fake import FakeDevice, Responder
from photons_transport.targets import MemoryTarget
from photons_control import test_helpers as chp
from photons_products import Products

from delfick_project.norms import dictobj
import asyncio
import pytest
import uuid


class Collection(dictobj):
    fields = ["uuid", "label", "updated_at"]


class CollectionResponder(Responder):
    _fields = ["group", "location"]

    async def respond(self, device, pkt, source):
        if pkt | DeviceMessages.GetGroup:
            yield DeviceMessages.StateGroup(
                group=device.attrs.group.uuid,
                label=device.attrs.group.label,
                updated_at=device.attrs.group.updated_at,
            )

        elif pkt | DeviceMessages.GetLocation:
            yield DeviceMessages.StateLocation(
                location=device.attrs.location.uuid,
                label=device.attrs.location.label,
                updated_at=device.attrs.location.updated_at,
            )


device1 = FakeDevice(
    "d073d5000001",
    chp.default_responders(
        Products.LCMV4_BR30_COLOR,
        color=chp.Color(120, 0.4, 0.3, 3500),
        firmware=chp.Firmware(1, 22, 0),
        label="kitchen",
        power=65535,
    )
    + [
        CollectionResponder(
            group=Collection("1234", "one", 1), location=Collection("7890", "one", 1)
        )
    ],
)

device2 = FakeDevice(
    "d073d5000002",
    chp.default_responders(
        Products.LCMV4_A19_COLOR,
        color=chp.Color(120, 0.4, 0.3, 3500),
        label="bathroom",
        firmware=chp.Firmware(1, 22, 0),
        power=0,
    )
    + [
        CollectionResponder(
            group=Collection("1234", "two", 2), location=Collection("1234", "two", 2)
        )
    ],
)

device3 = FakeDevice(
    "d073d5000003",
    chp.default_responders(
        Products.LCM2_A19_PLUS,
        color=chp.Color(120, 0.4, 0.3, 3500),
        label="hallway",
        firmware=chp.Firmware(1, 22, 0),
        infrared=65535,
        power=65535,
    )
    + [
        CollectionResponder(
            group=Collection("4567", "three", 1), location=Collection("7890", "four", 4)
        )
    ],
)


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner([device1, device2, device3]) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


describe "Device finder":

    def expect_received(self, device, *msgs):
        if not msgs:
            assert device.received == []

        # De-duplicate to not fail on retries
        typs = []
        for m in device.received:
            if type(m) not in typs:
                typs.append(type(m))

        assert len(typs) == len(msgs), typs
        for t, m in zip(typs, msgs):
            assert t == m, "expected {0} to be {1}".format(t, m)

        while device.received:
            device.received.pop()

    async it "can find all serials", runner:
        async with runner.target.session() as afr:
            finder = DeviceFinder(runner.target)
            try:
                serials = await finder.serials()
                assert sorted(serials) == sorted([device1.serial, device2.serial, device3.serial])
            finally:
                await finder.finish()

    async it "can find a particular serial", runner:
        async with runner.target.session() as afr:
            finder = DeviceFinder(runner.target)
            try:
                serials = await finder.serials(serial=[device1.serial])
                assert sorted(serials) == sorted([device1.serial])
            finally:
                await finder.finish()

    async it "can find with the device finder wrap", runner:
        wrap = DeviceFinderWrap(Filter.from_kwargs(), runner.target)
        try:
            async with runner.target.session() as afr:
                found, serials = await wrap.find(afr, timeout=5)
                want = sorted([d.serial for d in runner.devices])
                assert sorted(found.serials) == want
                assert sorted(serials) == want
        finally:
            await wrap.finish()

    @pytest.mark.async_timeout(10)
    async it "can be used to get info", runner:

        class W:
            async def __aenter__(s):
                s.finder = DeviceFinder(
                    runner.target,
                    service_search_interval=1,
                    information_search_interval=2,
                    repeat_spread=0.1,
                )
                await s.finder.start()
                return s.finder

            async def __aexit__(s, exc_type, exc, tb):
                await s.finder.finish()

        async with W() as finder:
            info = await finder.info_for()
            expected = {
                "d073d5000001": {
                    "serial": "d073d5000001",
                    "label": "kitchen",
                    "power": "on",
                    "hue": 120.0,
                    "saturation": 0.4,
                    "brightness": 0.29999237048905164,
                    "kelvin": 3500,
                    "firmware_version": "1.22",
                    "product_id": 20,
                    "product_identifier": "lifx_br30_color",
                    "group_id": "12340000000000000000000000000000",
                    "group_name": "two",
                    "location_name": "four",
                    "location_id": "78900000000000000000000000000000",
                    "cap": [
                        "color",
                        "not_chain",
                        "not_ir",
                        "not_matrix",
                        "not_multizone",
                        "variable_color_temp",
                    ],
                },
                "d073d5000002": {
                    "serial": "d073d5000002",
                    "label": "bathroom",
                    "power": "off",
                    "hue": 120.0,
                    "saturation": 0.4,
                    "brightness": 0.29999237048905164,
                    "kelvin": 3500,
                    "firmware_version": "1.22",
                    "product_id": 22,
                    "product_identifier": "lifx_a19_color",
                    "group_id": "12340000000000000000000000000000",
                    "group_name": "two",
                    "location_name": "two",
                    "location_id": "12340000000000000000000000000000",
                    "cap": [
                        "color",
                        "not_chain",
                        "not_ir",
                        "not_matrix",
                        "not_multizone",
                        "variable_color_temp",
                    ],
                },
                "d073d5000003": {
                    "serial": "d073d5000003",
                    "label": "hallway",
                    "power": "on",
                    "hue": 120.0,
                    "saturation": 0.4,
                    "brightness": 0.29999237048905164,
                    "kelvin": 3500,
                    "firmware_version": "1.22",
                    "product_id": 29,
                    "product_identifier": "lifx_a19_plus",
                    "group_id": "45670000000000000000000000000000",
                    "group_name": "three",
                    "location_name": "four",
                    "location_id": "78900000000000000000000000000000",
                    "cap": [
                        "color",
                        "ir",
                        "not_chain",
                        "not_matrix",
                        "not_multizone",
                        "variable_color_temp",
                    ],
                },
            }

            assert info == expected

            self.expect_received(device1, *[type(e.value.msg) for e in InfoPoints])
            self.expect_received(device2, *[type(e.value.msg) for e in InfoPoints])
            self.expect_received(device3, *[type(e.value.msg) for e in InfoPoints])

            serials = await finder.serials(label="kitchen", force_refresh=True)
            self.expect_received(device1, LightMessages.GetColor)
            self.expect_received(device2, LightMessages.GetColor)
            self.expect_received(device3, LightMessages.GetColor)
            assert serials == [device1.serial]

            serials = await finder.serials(group_name="two", force_refresh=True)
            self.expect_received(device1, DeviceMessages.GetGroup)
            self.expect_received(device2, DeviceMessages.GetGroup)
            self.expect_received(device3, DeviceMessages.GetGroup)
            assert set(serials) == set([device1.serial, device2.serial])

            # And make sure filters without refresh don't ruin other filters
            assert set(await finder.serials()) == set(
                [device1.serial, device2.serial, device3.serial]
            )
            assert set(await finder.serials(label="kitchen")) == set([device1.serial])
            assert set(await finder.serials(group_name="two")) == set(
                [device1.serial, device2.serial]
            )

            device1.attrs.color = chp.Color(72, 0.8, 0.6, 2500)
            device2.attrs.label = "blah"
            device3.attrs.group = Collection("1111", "oneoneone", 7)

            await asyncio.sleep(2)
            self.expect_received(device1, *[type(e.value.msg) for e in InfoPoints])
            self.expect_received(device2, *[type(e.value.msg) for e in InfoPoints])
            self.expect_received(device3, *[type(e.value.msg) for e in InfoPoints])

            info = await finder.info_for()
            expected = {
                "d073d5000001": {
                    "serial": "d073d5000001",
                    "label": "kitchen",
                    "power": "on",
                    "hue": 72,
                    "saturation": 0.8,
                    "brightness": 0.6,
                    "kelvin": 2500,
                    "firmware_version": "1.22",
                    "product_id": 20,
                    "product_identifier": "lifx_br30_color",
                    "group_id": "12340000000000000000000000000000",
                    "group_name": "two",
                    "location_name": "four",
                    "location_id": "78900000000000000000000000000000",
                    "cap": [
                        "color",
                        "not_chain",
                        "not_ir",
                        "not_matrix",
                        "not_multizone",
                        "variable_color_temp",
                    ],
                },
                "d073d5000002": {
                    "serial": "d073d5000002",
                    "label": "blah",
                    "power": "off",
                    "hue": 120.0,
                    "saturation": 0.4,
                    "brightness": 0.29999237048905164,
                    "kelvin": 3500,
                    "firmware_version": "1.22",
                    "product_id": 22,
                    "product_identifier": "lifx_a19_color",
                    "group_id": "12340000000000000000000000000000",
                    "group_name": "two",
                    "location_name": "two",
                    "location_id": "12340000000000000000000000000000",
                    "cap": [
                        "color",
                        "not_chain",
                        "not_ir",
                        "not_matrix",
                        "not_multizone",
                        "variable_color_temp",
                    ],
                },
                "d073d5000003": {
                    "serial": "d073d5000003",
                    "label": "hallway",
                    "power": "on",
                    "hue": 120.0,
                    "saturation": 0.4,
                    "brightness": 0.29999237048905164,
                    "kelvin": 3500,
                    "firmware_version": "1.22",
                    "product_id": 29,
                    "product_identifier": "lifx_a19_plus",
                    "group_id": "11110000000000000000000000000000",
                    "group_name": "oneoneone",
                    "location_name": "four",
                    "location_id": "78900000000000000000000000000000",
                    "cap": [
                        "color",
                        "ir",
                        "not_chain",
                        "not_matrix",
                        "not_multizone",
                        "variable_color_temp",
                    ],
                },
            }

            assert info == expected

            self.expect_received(device1)
            self.expect_received(device2)
            self.expect_received(device3)

            script = runner.target.script(DeviceMessages.GetPower())

            async with runner.target.session() as afr:
                found = []
                async for pkt, _, _ in script.run_with(finder.find(), afr):
                    assert pkt | DeviceMessages.StatePower
                    found.append((pkt.serial, pkt.payload.level))

                self.expect_received(device1, DeviceMessages.GetPower)
                self.expect_received(device2, DeviceMessages.GetPower)
                self.expect_received(device3, DeviceMessages.GetPower)

                assert sorted(found) == sorted(
                    [(device1.serial, 65535), (device2.serial, 0), (device3.serial, 65535)]
                )

                found = []
                async for pkt, _, _ in script.run_with(finder.find(location_name="four"), afr):
                    assert pkt | DeviceMessages.StatePower
                    found.append((pkt.serial, pkt.payload.level))

                assert sorted(found) == sorted([(device1.serial, 65535), (device3.serial, 65535)])

                self.expect_received(device1, DeviceMessages.GetPower)
                self.expect_received(device3, DeviceMessages.GetPower)

                serials = await finder.serials(product_identifier="*color*", force_refresh=True)
                assert sorted(serials) == sorted([device1.serial, device2.serial])
