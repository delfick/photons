# coding: spec

import binascii

import pytest
from delfick_project.errors_pytest import assertSameError
from photons_app import helpers as hp
from photons_app.errors import TimedOut
from photons_app.mimic.device import Device
from photons_app.mimic.operator import Operator
from photons_app.mimic.transport import MemoryTarget
from photons_app.special import HardCodedSerials
from photons_messages import DeviceMessages, Services, protocol_register
from photons_products import Products
from photons_transport.errors import FailedToFindDevice
from photons_transport.targets import LanTarget


class Responder(Operator):
    attrs = [Operator.Attr.Static("power", 0)]

    async def respond(s, event):
        if event | DeviceMessages.GetPower:
            event.set_replies(DeviceMessages.StatePower(level=s.device_attrs.power))
        elif event | DeviceMessages.SetPower:
            event.set_replies(DeviceMessages.StatePower(level=s.device_attrs.power))
            await s.device_attrs.attrs_apply(
                s.device_attrs.attrs_path("power").changer_to(event.pkt.level), event=event
            )


@pytest.fixture()
def make_device():
    def make_device(has_memory=True, has_udp=False, value_store=None):
        return Device(
            "d073d5001337",
            Products.LCM2_A19,
            hp.Firmware(2, 80),
            lambda d: Responder(d),
            value_store={
                "no_memory_io": not has_memory,
                "no_udp_io": not has_udp,
                "only_io_and_viewer_operators": True,
                **(value_store or {}),
            },
        )

    return make_device


describe "can send over memory":

    @pytest.fixture()
    async def device(self, final_future, make_device):
        device = make_device()
        async with device.session(final_future):
            yield device

    @pytest.fixture()
    async def sender(self, final_future, device):
        configuration = {"final_future": final_future, "protocol_register": protocol_register}
        async with MemoryTarget.create(configuration, {"devices": [device]}).session() as sender:
            yield sender

    async it "can send and receive messages using memory target", sender, device:
        pkts = await sender(DeviceMessages.SetPower(level=65535), device.serial)
        assert len(pkts) == 1
        pkt = pkts[0]
        assert pkt | DeviceMessages.StatePower
        assert pkt.level == 0

        pkts = await sender(DeviceMessages.GetPower(), device.serial)
        assert len(pkts) == 1
        pkt = pkts[0]
        assert pkt | DeviceMessages.StatePower
        assert pkt.level == 65535

        pkts = await sender(DeviceMessages.SetPower(level=0, res_required=False), device.serial)
        assert len(pkts) == 0

        pkts = await sender(DeviceMessages.GetPower(), device.serial)
        assert len(pkts) == 1
        pkt = pkts[0]
        assert pkt | DeviceMessages.StatePower
        assert pkt.level == 0

    async it "times out if the device is offline", sender, device, FakeTime, MockedCallLater:
        pkts = await sender(DeviceMessages.GetPower(), device.serial)
        assert len(pkts) == 1
        pkt = pkts[0]
        assert pkt | DeviceMessages.StatePower
        assert pkt.level == 0

        async with device.offline():
            with FakeTime() as t:
                async with MockedCallLater(t):
                    errors = []
                    pkts = await sender(
                        DeviceMessages.GetPower(),
                        device.serial,
                        message_timeout=2,
                        error_catcher=errors,
                    )
                    assert len(pkts) == 0
                    assert len(errors) == 1
                    assertSameError(
                        errors[0],
                        TimedOut,
                        "Waiting for reply to a packet",
                        dict(serial=device.serial, sent_pkt_type=20),
                        [],
                    )

                    await sender.forget(device.serial)

                    errors = []
                    pkts = await sender(
                        DeviceMessages.GetPower(),
                        device.serial,
                        find_timeout=2,
                        error_catcher=errors,
                    )
                    assert len(pkts) == 0
                    assert len(errors) == 1
                    assertSameError(
                        errors[0],
                        FailedToFindDevice,
                        "",
                        dict(serial=device.serial),
                        [],
                    )


describe "can send over udp":

    @pytest.fixture()
    async def device(self, final_future, make_device):
        device = make_device(has_udp=True, value_store={"port": 56700})
        async with device.session(final_future):
            yield device

    @pytest.fixture()
    async def sender(self, final_future, device):
        configuration = {"final_future": final_future, "protocol_register": protocol_register}
        async with LanTarget.create(configuration).session() as sender:
            yield sender

    async it "can send and receive messages using lan target target", sender, device:
        reference = HardCodedSerials([device.serial])
        found, serials = await reference.find(sender, timeout=1)
        assert serials == [device.serial]
        assert (
            found[binascii.unhexlify(device.serial)][Services.UDP].port
            == device.io[Services.UDP.name].options.port
        )

        pkts = await sender(DeviceMessages.SetPower(level=65535), device.serial)
        assert len(pkts) == 1
        pkt = pkts[0]
        assert pkt | DeviceMessages.StatePower
        assert pkt.level == 0

        pkts = await sender(DeviceMessages.GetPower(), device.serial)
        assert len(pkts) == 1
        pkt = pkts[0]
        assert pkt | DeviceMessages.StatePower
        assert pkt.level == 65535

        pkts = await sender(DeviceMessages.SetPower(level=0, res_required=False), device.serial)
        assert len(pkts) == 0

        pkts = await sender(DeviceMessages.GetPower(), device.serial)
        assert len(pkts) == 1
        pkt = pkts[0]
        assert pkt | DeviceMessages.StatePower
        assert pkt.level == 0

    async it "times out if the device is offline", sender, device, FakeTime, MockedCallLater:
        pkts = await sender(DeviceMessages.GetPower(), device.serial)
        assert len(pkts) == 1
        pkt = pkts[0]
        assert pkt | DeviceMessages.StatePower
        assert pkt.level == 0

        async with device.offline():
            with FakeTime() as t:
                async with MockedCallLater(t):
                    errors = []
                    pkts = await sender(
                        DeviceMessages.GetPower(),
                        device.serial,
                        message_timeout=2,
                        error_catcher=errors,
                    )
                    assert len(pkts) == 0
                    assert len(errors) == 1
                    assertSameError(
                        errors[0],
                        TimedOut,
                        "Waiting for reply to a packet",
                        dict(serial=device.serial, sent_pkt_type=20),
                        [],
                    )

                    await sender.forget(device.serial)

                    errors = []
                    pkts = await sender(
                        DeviceMessages.GetPower(),
                        device.serial,
                        find_timeout=2,
                        error_catcher=errors,
                    )
                    assert len(pkts) == 0
                    assert len(errors) == 1
                    assertSameError(
                        errors[0],
                        FailedToFindDevice,
                        "",
                        dict(serial=device.serial),
                        [],
                    )
