# coding: spec

from photons_control.planner.script import WithSender
from photons_control import test_helpers as chp

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut

from photons_messages import DeviceMessages, LightMessages
from photons_transport.fake import FakeDevice
from photons_products import Products

import pytest
import uuid

light1 = FakeDevice(
    "d073d5000001", chp.default_responders(Products.LCM2_A19_PLUS, power=0, infrared=100)
)

light2 = FakeDevice(
    "d073d5000002", chp.default_responders(Products.LCM2_A19_PLUS, power=65535, infrared=0)
)


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner([light1, light2]) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


describe "WithSender":

    async it "yields responses with key from original message", runner:
        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())
        key3 = str(uuid.uuid4())
        key4 = str(uuid.uuid4())

        msg1 = DeviceMessages.GetPower()
        msg2 = LightMessages.GetInfrared()

        wsmsg1 = WithSender(msg1, key1, light1.serial)
        wsmsg2 = WithSender(msg2, key2, light1.serial)
        wsmsg3 = WithSender(msg1, key3, light2.serial)
        wsmsg4 = WithSender(msg2, key4, light2.serial)

        got = {}
        async for k, pkt in runner.target.script([wsmsg1, wsmsg2, wsmsg3, wsmsg4]).run_with(
            runner.serials
        ):
            assert k not in got
            got[k] = pkt

        assert len(got) == 4

        def assertCorrect(pkt, kls, serial, **kwargs):
            assert pkt | kls, pkt
            assert pkt.serial == serial, pkt
            for k, v in kwargs.items():
                assert getattr(pkt, k) == v, pkt

        assertCorrect(got[key1], DeviceMessages.StatePower, light1.serial, level=0)
        assertCorrect(got[key2], LightMessages.StateInfrared, light1.serial, brightness=100)
        assertCorrect(got[key3], DeviceMessages.StatePower, light2.serial, level=65535)
        assertCorrect(got[key4], LightMessages.StateInfrared, light2.serial, brightness=0)

        for pkt in (got[key1], got[key2]):
            assert pkt._with_sender_address == (f"fake://{light1.serial}/memory", 56700)

        for pkt in (got[key3], got[key4]):
            assert pkt._with_sender_address == (f"fake://{light2.serial}/memory", 56700)
