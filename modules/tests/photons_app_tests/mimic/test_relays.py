import pytest
from photons_app import helpers as hp
from photons_app.mimic.event import Events
from photons_app.mimic.operators.relays import Relay, RelayPowerGetter
from photons_messages import DeviceMessages, RelayMessages
from photons_products import Products

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


def makeAssertEvent(device):
    async def assertEvent(event_maker, **attrs):
        await event_maker()
        if attrs:
            devices.store(device).assertAttrs(**attrs)

    return assertEvent


def makeAssertState(device):
    async def assertState(question, expected):
        assert device.state_for(question) == expected

    return assertState


class TestRelays:
    @pytest.fixture()
    def device(self):
        device = devices["switch"]
        devices.store(device).assertAttrs(label="")
        return device

    @pytest.fixture()
    def assertResponse(self, device, **attrs):
        return makeAssertResponse(device, **attrs)

    @pytest.fixture()
    def assertState(self, device, **attrs):
        return makeAssertState(device, **attrs)

    @pytest.fixture()
    def assertEvent(self, device, **attrs):
        return makeAssertEvent(device, **attrs)

    async def test_it_can_change_the_power_of_all_the_relays(self, device, assertResponse, assertEvent):
        await assertResponse(
            DeviceMessages.GetPower(),
            [DeviceMessages.StatePower(level=0)],
        )

        await assertResponse(
            DeviceMessages.SetPower(level=65535),
            [DeviceMessages.StatePower(level=0)],
            relays=[
                Relay.create(power=65535),
                Relay.create(power=65535),
                Relay.create(power=65535),
                Relay.create(power=65535),
            ],
            power=65535,
        )

        await assertResponse(
            DeviceMessages.SetPower(level=0),
            [DeviceMessages.StatePower(level=65535)],
            relays=[
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=0),
            ],
            power=0,
        )

        await assertEvent(
            lambda: device.event(Events.SET_RELAYS_POWER, relays={1: 65535, 3: 65535}),
            relays=[
                Relay.create(power=0),
                Relay.create(power=65535),
                Relay.create(power=0),
                Relay.create(power=65535),
            ],
            power=65535,
        )

        await assertResponse(
            DeviceMessages.SetPower(level=0),
            [DeviceMessages.StatePower(level=65535)],
            relays=[
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=0),
            ],
            power=0,
        )

        await assertEvent(
            lambda: device.event(Events.SET_RELAYS_POWER, relays={0: 65535, 2: 65535}),
            relays=[
                Relay.create(power=65535),
                Relay.create(power=0),
                Relay.create(power=65535),
                Relay.create(power=0),
            ],
            power=65535,
        )

        await assertResponse(
            DeviceMessages.SetPower(level=65535),
            [DeviceMessages.StatePower(level=65535)],
            relays=[
                Relay.create(power=65535),
                Relay.create(power=65535),
                Relay.create(power=65535),
                Relay.create(power=65535),
            ],
            power=65535,
        )

    async def test_it_can_change_the_power_of_the_specified_relay(self, device, assertResponse):
        await assertResponse(
            DeviceMessages.GetPower(),
            [DeviceMessages.StatePower(level=0)],
        )

        await assertResponse(
            RelayMessages.SetRPower(relay_index=1, level=65535),
            [RelayMessages.StateRPower(relay_index=1, level=0)],
            relays=[
                Relay.create(power=0),
                Relay.create(power=65535),
                Relay.create(power=0),
                Relay.create(power=0),
            ],
            power=65535,
        )

        await assertResponse(
            DeviceMessages.GetPower(),
            [DeviceMessages.StatePower(level=65535)],
        )

        await assertResponse(
            RelayMessages.SetRPower(relay_index=2, level=65535),
            [RelayMessages.StateRPower(relay_index=2, level=0)],
            relays=[
                Relay.create(power=0),
                Relay.create(power=65535),
                Relay.create(power=65535),
                Relay.create(power=0),
            ],
            power=65535,
        )

        await assertResponse(
            RelayMessages.SetRPower(relay_index=1, level=0),
            [RelayMessages.StateRPower(relay_index=1, level=65535)],
            relays=[
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=65535),
                Relay.create(power=0),
            ],
            power=65535,
        )

        await assertResponse(
            RelayMessages.SetRPower(relay_index=1, level=0),
            [RelayMessages.StateRPower(relay_index=1, level=0)],
            relays=[
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=65535),
                Relay.create(power=0),
            ],
            power=65535,
        )

        await assertResponse(
            DeviceMessages.GetPower(),
            [DeviceMessages.StatePower(level=65535)],
        )

        await assertResponse(
            RelayMessages.SetRPower(relay_index=2, level=0),
            [RelayMessages.StateRPower(relay_index=2, level=65535)],
            relays=[
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=0),
            ],
            power=0,
        )

        await assertResponse(
            DeviceMessages.GetPower(),
            [DeviceMessages.StatePower(level=0)],
        )

    async def test_it_can_change_the_power_of_the_multiple_relays(self, device, assertResponse, assertEvent):
        await assertResponse(
            DeviceMessages.GetPower(),
            [DeviceMessages.StatePower(level=0)],
        )

        await assertEvent(
            lambda: device.event(Events.SET_RELAYS_POWER, relays={1: 65535, 3: 65535}),
            relays=[
                Relay.create(power=0),
                Relay.create(power=65535),
                Relay.create(power=0),
                Relay.create(power=65535),
            ],
            power=65535,
        )

        await assertResponse(
            DeviceMessages.GetPower(),
            [DeviceMessages.StatePower(level=65535)],
        )

        await assertEvent(
            lambda: device.event(Events.SET_RELAYS_POWER, relays={1: 0, 2: 65535, 3: 65535}),
            relays=[
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=65535),
                Relay.create(power=65535),
            ],
            power=65535,
        )

        await assertEvent(
            lambda: device.event(Events.SET_RELAYS_POWER, relays={2: 0, 3: 0}),
            relays=[
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=0),
                Relay.create(power=0),
            ],
            power=0,
        )

        await assertResponse(
            DeviceMessages.GetPower(),
            [DeviceMessages.StatePower(level=0)],
        )

    async def test_it_returns_the_power_level_of_the_specified_relay(self, device, assertResponse, assertState):
        await assertResponse(
            RelayMessages.GetRPower(relay_index=1),
            [RelayMessages.StateRPower(relay_index=1, level=0)],
        )

        await assertState(
            RelayPowerGetter(index=1),
            RelayMessages.StateRPower(relay_index=1, level=0),
        )

        await assertResponse(
            RelayMessages.SetRPower(relay_index=1, level=65535),
            [RelayMessages.StateRPower(relay_index=1, level=0)],
        )

        await assertResponse(
            RelayMessages.GetRPower(relay_index=1),
            [RelayMessages.StateRPower(relay_index=1, level=65535)],
        )

        await assertState(
            RelayPowerGetter(index=1),
            RelayMessages.StateRPower(relay_index=1, level=65535),
        )

        await assertState(
            RelayPowerGetter(index=2),
            RelayMessages.StateRPower(relay_index=2, level=0),
        )
