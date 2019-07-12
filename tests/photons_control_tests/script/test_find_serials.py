# coding: spec

from photons_control import test_helpers as chp
from photons_control.script import find_serials

from photons_app.test_helpers import AsyncTestCase
from photons_app.special import FoundSerials

from photons_transport.fake import FakeDevice

from input_algorithms import spec_base as sb

light1 = FakeDevice("d073d5000001", chp.default_responders())
light2 = FakeDevice("d073d5000002", chp.default_responders())
light3 = FakeDevice("d073d5000003", chp.default_responders())

mlr = chp.ModuleLevelRunner([light1, light2, light3])

setUp = mlr.setUp
tearDown = mlr.tearDown

describe AsyncTestCase, "Repeater":
    use_default_loop = True

    @mlr.test
    async it "can find all serials", runner:
        async with runner.target.session() as afr:
            for ref in ("", "_", None, sb.NotSpecified, FoundSerials()):
                self.assertEqual(await find_serials(ref, afr, timeout=1), (runner.serials, []))

    @mlr.test
    async it "can find a specific serial", runner:
        async with runner.target.session() as afr:
            self.assertEqual(await find_serials(light1.serial, afr, timeout=1), ([light1.serial], []))

        async with runner.target.session() as afr:
            with light1.offline():
                self.assertEqual(await find_serials(light1.serial, afr, timeout=0.5), ([], [light1.serial]))

    @mlr.test
    async it "can find a number of serials", runner:
        for ref in (f"{light1.serial},{light2.serial}", [light1.serial, light2.serial]):
            async with runner.target.session() as afr:
                self.assertEqual(await find_serials(ref, afr, timeout=1), ([light1.serial, light2.serial], []))

            with light1.offline():
                async with runner.target.session() as afr:
                    self.assertEqual(await find_serials(ref, afr, timeout=0.5), ([light2.serial], [light1.serial]))
