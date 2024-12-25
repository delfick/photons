import pytest
from photons_app import helpers as hp
from photons_control.script import ForCapability
from photons_messages import DeviceMessages, DiscoveryMessages, LightMessages
from photons_products import Products

devices = pytest.helpers.mimic()


a19 = devices.add("light1")(
    next(devices.serial_seq),
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(power=0),
)

clean = devices.add("light2")(
    next(devices.serial_seq),
    Products.LCM3_A19_CLEAN,
    hp.Firmware(3, 70),
    value_store=dict(power=0),
)

ir = devices.add("light3")(
    next(devices.serial_seq),
    Products.LCM2_A19_PLUS,
    hp.Firmware(2, 80),
    value_store=dict(power=0),
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
    sender.gatherer.clear_cache()


class TestFromCapability:

    async def assertScript(self, sender, msg, *, expected, **kwargs):
        await sender(msg, devices.serials, **kwargs)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

    async def test_it_sends_the_messages_to_devices_with_only_correct_capability(self, sender):

        msg = ForCapability(hev=LightMessages.GetHevCycle())

        expected = {
            a19: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
            clean: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.GetHevCycle(),
            ],
            ir: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
        }

        await self.assertScript(sender, msg, expected=expected)

    async def test_it_can_send_message_to_groups(self, sender):

        msg = ForCapability(**{"ir,hev": DeviceMessages.SetPower(level=65535)})

        expected = {
            a19: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
            clean: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                DeviceMessages.SetPower(level=65535),
            ],
            ir: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                DeviceMessages.SetPower(level=65535),
            ],
        }

        await self.assertScript(sender, msg, expected=expected)

    async def test_it_can_send_to_negative_capability(self, sender):

        msg = ForCapability(hev=LightMessages.GetHevCycle(), not_hev=LightMessages.GetLightPower())

        expected = {
            a19: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.GetLightPower(),
            ],
            clean: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.GetHevCycle(),
            ],
            ir: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.GetLightPower(),
            ],
        }

        await self.assertScript(sender, msg, expected=expected)
