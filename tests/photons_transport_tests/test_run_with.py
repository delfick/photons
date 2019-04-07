# coding: spec

from photons_app.test_helpers import AsyncTestCase

from photons_control.test_helpers import Device, ModuleLevelRunner
from photons_messages import DeviceMessages, LightMessages
from photons_control.script import Pipeline

from collections import defaultdict

light1 = Device("d073d5000001"
    , use_sockets = False
    )

light2 = Device("d073d5000002"
    , use_sockets = False
    )

light3 = Device("d073d5000003"
    , use_sockets = False
    )

mlr = ModuleLevelRunner([light1, light2, light3], use_sockets=False)

setUp = mlr.setUp
tearDown = mlr.tearDown

describe AsyncTestCase, "run_with":
    use_default_loop = True

    @mlr.test
    async it "can run multiple complex things at the same time", runner:
        pipeline1 = Pipeline([DeviceMessages.GetPower()])
        pipeline2 = Pipeline([DeviceMessages.GetLabel(), LightMessages.GetColor()])

        got = defaultdict(list)
        async for pkt, _, _ in runner.target.script([pipeline1, pipeline2]).run_with(runner.serials):
            got[pkt.serial].append(pkt)

        assert len(runner.devices) > 0
        assert all(serial in got for serial in runner.serials)

        for serial, pkts in got.items():
            pkts = sorted(pkts, key=lambda p: p.pkt_type)
            self.assertEqual(len(pkts), 3, pkts)
            assert pkts[0] | DeviceMessages.StatePower
            assert pkts[1] | DeviceMessages.StateLabel
            assert pkts[2] | LightMessages.LightState
