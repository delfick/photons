import asyncio
import binascii
import functools
from typing import Protocol

import pytest
import strcs
from interactor.commander import devices
from interactor.commander.store import reg
from photons_app import mimic, special
from photons_app.mimic.transport import MemoryTarget
from photons_app.registers import ReferenceResolverRegister
from photons_control.device_finder import Device, DeviceFinder, Filter, Finder
from photons_control.transform import PowerToggle
from photons_messages import protocol_register
from photons_transport.comms.base import Communication


@pytest.fixture
def finder(sender: Communication, final_future: asyncio.Future) -> Finder:
    return Finder(sender, final_future)


class DeviceFinderCreator(Protocol):
    def __call__(self, options: dict[str, object]) -> devices.DeviceFinder: ...


@pytest.fixture
def create_device_finder(finder: Finder, sender: Communication) -> DeviceFinderCreator:
    return functools.partial(
        reg.create,
        devices.DeviceFinder,
        meta=strcs.Meta(
            {
                "sender": sender,
                "finder": finder,
                "reference_resolver_register": ReferenceResolverRegister(),
            }
        ),
    )


@pytest.fixture
def mimic_devices(devices: mimic.DeviceCollection) -> mimic.DeviceCollection:
    return devices


class TestDeviceFinder:
    class TestCreation:
        def test_it_gets_a_default_timeout(self, create_device_finder: DeviceFinderCreator, sender: Communication, finder: Finder):
            all_devices = special.FoundSerials()
            device_finder = create_device_finder({"selector": all_devices})
            assert isinstance(device_finder, devices.DeviceFinder)
            assert device_finder.sender is sender
            assert device_finder.finder is finder
            assert device_finder.timeout == 20
            assert device_finder.selector.selector is all_devices

        def test_it_can_override_timeout(self, create_device_finder: DeviceFinderCreator, sender: Communication, finder: Finder):
            all_devices = special.FoundSerials()
            device_finder = create_device_finder({"selector": all_devices, "timeout": 200})
            assert isinstance(device_finder, devices.DeviceFinder)
            assert device_finder.sender is sender
            assert device_finder.finder is finder
            assert device_finder.timeout == 200
            assert device_finder.selector.selector is all_devices

        async def test_it_can_override_finder_and_sender(
            self,
            create_device_finder: DeviceFinderCreator,
            sender: Communication,
            mimic_devices: mimic.DeviceCollection,
            final_future: asyncio.Future,
            finder: Finder,
        ):
            all_devices = special.FoundSerials()
            target = MemoryTarget.create(
                {
                    "final_future": final_future,
                    "protocol_register": protocol_register,
                    "devices": mimic_devices,
                }
            )

            async with target.session() as sender2:
                finder2 = Finder(sender2, final_future)
                device_finder = create_device_finder({"finder": finder2, "sender": sender2, "selector": all_devices, "timeout": 200})
                assert isinstance(device_finder, devices.DeviceFinder)
                assert device_finder.sender is sender2
                assert device_finder.finder is finder2
                assert device_finder.timeout == 200
                assert device_finder.selector.selector is all_devices

    class TestUse:
        async def test_it_can_make_a_device_finder_filter_from_FoundSerials(
            self, create_device_finder: DeviceFinderCreator, mimic_devices: mimic.DeviceCollection
        ):
            made = create_device_finder({"selector": special.FoundSerials()})
            fltr = await made.filter
            assert await made.filter is fltr
            del made.filter
            assert await made.filter is not fltr

            assert await made.filter == Filter.empty()

            found = set(await made.serials)
            assert len(found) > 2
            assert found == set(device.serial for device in mimic_devices)

        async def test_it_can_make_a_device_finder_filter_from_HardCodedSerials(
            self, create_device_finder: DeviceFinderCreator, mimic_devices: mimic.DeviceCollection
        ):
            hard_coded = special.HardCodedSerials(["d073d500000a", "d073d5000002"])
            assert len(mimic_devices) > 2
            made = create_device_finder({"selector": hard_coded})
            fltr = await made.filter
            assert await made.filter is fltr
            del made.filter
            assert await made.filter is not fltr

            assert await made.filter == Filter.from_kwargs(serial=["d073d500000a", "d073d5000002"])

            assert set(await made.serials) == set(["d073d500000a", "d073d5000002"])

        async def test_it_can_make_device_finder_filter_from_device_finder(
            self, create_device_finder: DeviceFinderCreator, mimic_devices: mimic.DeviceCollection
        ):
            assert len(mimic_devices) > 1
            made = create_device_finder({"selector": DeviceFinder.from_kwargs(label="dungeon")})
            fltr = await made.filter
            assert await made.filter is fltr
            del made.filter
            # Steals same filter from the selector
            assert await made.filter is fltr

            assert await made.filter == Filter.from_kwargs(label="dungeon")

            assert set(await made.serials) == set(["d073d5000009"])

        async def test_it_makes_serials_filter_from_other_selectors(
            self, create_device_finder: DeviceFinderCreator, mimic_devices: mimic.DeviceCollection
        ):
            class Reference(special.SpecialReference):
                async def find_serials(self, sender: Communication, *, timeout: int, broadcast: bool = True) -> list[str]:
                    return [binascii.unhexlify("d073d5000008"), binascii.unhexlify("d073d5000002")]

            assert len(mimic_devices) > 2
            made = create_device_finder({"selector": Reference()})
            fltr = await made.filter
            assert await made.filter is fltr
            del made.filter
            assert await made.filter is not fltr

            assert await made.filter == Filter.from_kwargs(serial=["d073d5000008", "d073d5000002"])

            assert set(await made.serials) == set(["d073d5000008", "d073d5000002"])

        async def test_it_can_make_a_device_finder(
            self,
            create_device_finder: DeviceFinderCreator,
            mimic_devices: mimic.DeviceCollection,
            finder: Finder,
        ):
            made = create_device_finder({})
            device_finder = await made.device_finder
            assert isinstance(device_finder, DeviceFinder)
            assert device_finder.finder is finder
            assert device_finder.fltr is await made.filter

        async def test_it_can_get_Device_objects(self, create_device_finder: DeviceFinderCreator, mimic_devices: mimic.DeviceCollection):
            made = create_device_finder({})
            assert len(mimic_devices) > 2

            got: list[Device] = []
            i = 0
            async for device in made.devices:
                got.append(device)
                if i == 2:
                    break
                i += 1

            i = 0
            async for device in made.devices:
                if i <= 2:
                    # It memoized up to this point
                    assert device == got[i]
                else:
                    got.append(device)
                i += 1

            assert len(got) == len(mimic_devices)
            assert await made.devices == got
            for device in got:
                assert mimic_devices[device.serial].attrs.label == device.label

        async def test_it_can_get_serials(self, create_device_finder: DeviceFinderCreator, mimic_devices: mimic.DeviceCollection):
            made = create_device_finder({})
            assert len(mimic_devices) > 2

            got: list[str] = []
            i = 0
            async for serial in made.serials:
                got.append(serial)
                if i == 2:
                    break
                i += 1

            i = 0
            async for serial in made.serials:
                if i <= 2:
                    # It memoized up to this point
                    assert serial == got[i]
                else:
                    got.append(serial)
                i += 1

            assert len(got) == len(mimic_devices)
            assert await made.serials == got
            assert set(got) == set(device.serial for device in mimic_devices)

        async def test_it_can_send_messages(self, create_device_finder: DeviceFinderCreator, mimic_devices: mimic.DeviceCollection):
            made = create_device_finder({})
            assert len(mimic_devices) > 2

            for device in mimic_devices:
                await device.attrs.attrs_apply(device.attrs.attrs_path("power").changer_to(0), event=None)
            assert all(device.attrs.power == 0 for device in mimic_devices)

            msg = PowerToggle(duration=0)

            await made.send(msg)
            assert all(device.attrs.power == 65535 for device in mimic_devices if device.cap.is_light)

            await made.send(msg)
            assert all(device.attrs.power == 0 for device in mimic_devices if device.cap.is_light)
