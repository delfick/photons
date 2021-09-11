# coding: spec

from photons_control.clean import SetCleanConfig, ChangeCleanCycle

from photons_app import helpers as hp

from photons_messages import DeviceMessages, LightMessages, DiscoveryMessages

from photons_products import Products

import pytest

devices = pytest.helpers.mimic()

light1 = devices.add("light1")(
    "d073d5000001",
    Products.LCM3_A19_CLEAN,
    hp.Firmware(3, 70),
    value_store=dict(
        power=0,
        color=hp.Color(0, 1, 0.3, 2500),
    ),
)

light2 = devices.add("light2")(
    "d073d5000002",
    Products.LCM3_A19_CLEAN,
    hp.Firmware(3, 70),
    value_store=dict(
        power=65535,
        indication=True,
        color=hp.Color(100, 1, 0.5, 2500),
    ),
)

light3 = devices.add("light3")(
    "d073d5000003",
    Products.LCM2_A19,
    hp.Firmware(2, 80),
    value_store=dict(
        power=65535,
        color=hp.Color(100, 0, 0.8, 2500),
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
    sender.gatherer.clear_cache()


describe "SetCleanConfig":

    async def run_and_compare(self, sender, msg, *, expected):
        await sender(msg, devices.serials)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

    async it "sets the default config", sender:
        expected = {
            light1: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.SetHevCycleConfiguration(indication=True, duration_s=3600),
            ],
            light2: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.SetHevCycleConfiguration(indication=True, duration_s=3600),
            ],
            light3: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
        }
        await self.run_and_compare(
            sender, SetCleanConfig(indication=True, duration_s=3600), expected=expected
        )


describe "ChangeCleanCycle":

    async def run_and_compare(self, sender, msg, *, expected):
        await sender(msg, devices.serials)

        assert len(devices) > 0

        for device in devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

        for device, msgs in expected.items():
            assert device in devices
            devices.store(device).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
            devices.store(device).clear()

    async it "starts a clean cycle", sender:
        expected = {
            light1: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.SetHevCycle(enable=True, duration_s=7200),
            ],
            light2: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.SetHevCycle(enable=True, duration_s=7200),
            ],
            light3: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
        }
        await self.run_and_compare(
            sender, ChangeCleanCycle(enable=True, duration_s=7200), expected=expected
        )

    async it "stops a clean cycle", sender:
        expected = {
            light1: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.SetHevCycle(enable=False, duration_s=0),
            ],
            light2: [
                DeviceMessages.GetHostFirmware(),
                DeviceMessages.GetVersion(),
                LightMessages.SetHevCycle(enable=False, duration_s=0),
            ],
            light3: [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()],
        }
        await self.run_and_compare(
            sender, ChangeCleanCycle(enable=False, duration_s=0), expected=expected
        )
