# coding: spec

from photons_control.script import find_serials

from photons_app.special import FoundSerials
from photons_app import helpers as hp

from photons_products import Products

from delfick_project.norms import sb
import pytest

devices = pytest.helpers.mimic()

light1 = devices.add("light1")("d073d5000001", Products.LCM2_A19, hp.Firmware(2, 80))
light2 = devices.add("light2")("d073d5000002", Products.LCM2_A19, hp.Firmware(2, 80))
light3 = devices.add("light3")("d073d5000003", Products.LCM2_A19, hp.Firmware(2, 80))


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


describe "Finding serials":

    async it "can find all serials", sender:
        for ref in ("", "_", None, sb.NotSpecified, FoundSerials()):
            assert await find_serials(ref, sender, timeout=1) == (devices.serials, [])

    async it "can find a specific serial", sender:
        assert await find_serials(light1.serial, sender, timeout=1) == ([light1.serial], [])

        async with sender.transport_target.session() as sender:
            async with light1.offline():
                assert await find_serials(light1.serial, sender, timeout=0.5) == (
                    [],
                    [light1.serial],
                )

    async it "can find a number of serials", sender:
        for ref in (f"{light1.serial},{light2.serial}", [light1.serial, light2.serial]):
            assert light1.has_power
            assert light2.has_power

            async with sender.transport_target.session() as sender:
                assert await find_serials(ref, sender, timeout=1) == (
                    [light1.serial, light2.serial],
                    [],
                )

            async with light1.offline():
                assert not light1.has_power
                assert light2.has_power
                async with sender.transport_target.session() as sender:
                    assert await find_serials(ref, sender, timeout=0.5) == (
                        [light2.serial],
                        [light1.serial],
                    )
