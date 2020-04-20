# coding: spec

from photons_control import test_helpers as chp
from photons_control.script import find_serials

from photons_app.special import FoundSerials

from photons_transport.fake import FakeDevice

from delfick_project.norms import sb
import pytest

light1 = FakeDevice("d073d5000001", chp.default_responders())
light2 = FakeDevice("d073d5000002", chp.default_responders())
light3 = FakeDevice("d073d5000003", chp.default_responders())


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner([light1, light2, light3]) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


describe "Repeater":

    async it "can find all serials", runner:
        async with runner.target.session() as sender:
            for ref in ("", "_", None, sb.NotSpecified, FoundSerials()):
                assert await find_serials(ref, sender, timeout=1) == (runner.serials, [])

    async it "can find a specific serial", runner:
        async with runner.target.session() as sender:
            assert await find_serials(light1.serial, sender, timeout=1) == ([light1.serial], [])

        async with runner.target.session() as sender:
            with light1.offline():
                assert await find_serials(light1.serial, sender, timeout=0.5) == (
                    [],
                    [light1.serial],
                )

    async it "can find a number of serials", runner:
        for ref in (f"{light1.serial},{light2.serial}", [light1.serial, light2.serial]):
            async with runner.target.session() as sender:
                assert await find_serials(ref, sender, timeout=1) == (
                    [light1.serial, light2.serial],
                    [],
                )

            with light1.offline():
                async with runner.target.session() as sender:
                    assert await find_serials(ref, sender, timeout=0.5) == (
                        [light2.serial],
                        [light1.serial],
                    )
