# coding: spec

from photons_app.mimic.event import Events
from photons_app import helpers as hp

from photons_products import Products
from photons_messages import DeviceMessages, LightMessages, RelayMessages

import pytest

devices = pytest.helpers.mimic()

devices.add("switch")(
    next(devices.serial_seq),
    Products.LCM3_32_SWITCH_I,
    hp.Firmware(3, 80),
    value_store=dict(
        group={"label": "gl", "identity": "abcd", "updated_at": 1},
        location={"label": "ll", "identity": "efef", "updated_at": 2},
    ),
)


@pytest.fixture(scope="module")
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


@pytest.fixture(scope="module")
async def sender(final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture(autouse=True)
async def reset_devices(sender):
    for device in devices:
        await device.reset()
        devices.store(device).clear()


def makeAssertResponse(device):
    async def assertResponse(send, expected, **attrs):
        send = send.clone()
        send.update(source=2, sequence=2, target=device.serial)
        event = await device.event(Events.INCOMING, device.io["MEMORY"], pkt=send)
        assert event.handled or event.replies
        if expected is not True:
            pytest.helpers.assertSamePackets(event.replies, *expected)
        if attrs:
            devices.store(device).assertAttrs(**attrs)

    return assertResponse


def makeAssertUnhandled(device):
    async def assertUnhandled(send):
        send = send.clone()
        send.update(source=2, sequence=2, target=device.serial)
        event = await device.event(Events.INCOMING, device.io["MEMORY"], pkt=send)
        assert not event.handled and not event.replies

    return assertUnhandled


describe "SwitchDevice":

    @pytest.fixture()
    def device(self):
        device = devices["switch"]
        devices.store(device).assertAttrs(label="")
        return device

    @pytest.fixture()
    def assertResponse(self, device, **attrs):
        return makeAssertResponse(device, **attrs)

    async it "responds to label messages", device, assertResponse:
        await assertResponse(DeviceMessages.GetLabel(), [DeviceMessages.StateLabel(label="")])
        await assertResponse(
            DeviceMessages.SetLabel(label="sam"),
            [DeviceMessages.StateLabel(label="sam")],
            label="sam",
        )
        await assertResponse(
            DeviceMessages.GetLabel(), [DeviceMessages.StateLabel(label="sam")], label="sam"
        )

    async it "can change the power of the specified relay", device, assertResponse:
        await assertResponse(
            RelayMessages.SetRPower(relay_index=1, level=65535),
            [RelayMessages.StateRPower(relay_index=1, level=65535)],
            relays={0: 0, 1: 65535, 2: 0, 3: 0},
        )

    async it "returns the power level of the specified relay", device, assertResponse:
        await assertResponse(
            RelayMessages.GetRPower(relay_index=1),
            [RelayMessages.StateRPower(relay_index=1, level=65535)],
            relays={0: 0, 1: 65535, 2: 0, 3: 0},
        )

    async it "replies to light messages with a StateUnhandled packet", device, assertResponse:

        assertUnhandled = makeAssertUnhandled(device)

        await assertUnhandled(LightMessages.GetColor())
        await assertUnhandled(LightMessages.GetLightPower())
