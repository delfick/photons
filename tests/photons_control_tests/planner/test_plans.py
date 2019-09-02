# coding: spec

from photons_control.planner.plans import a_plan, pktkey, make_plans, Plan

from photons_app.errors import PhotonsAppError
from photons_app.test_helpers import TestCase

from photons_messages import DeviceMessages, DiscoveryMessages, Services

from noseOfYeti.tokeniser.support import noy_sup_setUp
from unittest import mock
import uuid

describe TestCase, "a_plan":
    it "puts items in plan_by_key":
        d = {}
        key = str(uuid.uuid1())
        key2 = str(uuid.uuid1())

        class Plan:
            pass

        class Plan2:
            pass

        with mock.patch("photons_control.planner.plans.plan_by_key", d):
            self.assertIs(a_plan(key)(Plan), Plan)
        self.assertEqual(d, {key: Plan})

        with mock.patch("photons_control.planner.plans.plan_by_key", d):
            self.assertIs(a_plan(key2)(Plan2), Plan2)
        self.assertEqual(d, {key: Plan, key2: Plan2})

describe TestCase, "pktkey":
    it "returns a tuple of information representing the packet":
        get_service = DiscoveryMessages.StateService.empty_normalise(
            source=0, sequence=1, target="d073d5000001", service=Services.UDP, port=56700
        )

        key = pktkey(get_service)
        self.assertEqual(key, (1024, 3, '{"port": 56700, "service": "<Services.UDP: 1>"}'))

        get_service2 = DiscoveryMessages.StateService.empty_normalise(
            source=1, sequence=2, target="d073d5000002", service=Services.UDP, port=56700
        )
        key = pktkey(get_service)
        self.assertEqual(key, (1024, 3, '{"port": 56700, "service": "<Services.UDP: 1>"}'))

        get_power = DeviceMessages.GetPower()
        key = pktkey(get_power)
        self.assertEqual(key, (1024, 20, "{}"))

        state_power = DeviceMessages.StatePower(level=0)
        key = pktkey(state_power)
        self.assertEqual(key, (1024, 22, '{"level": 0}'))

describe TestCase, "make_plans":
    it "returns empty if given no arguments":
        self.assertEqual(make_plans(), {})

    it "complains if a key is specified by label multiple times":
        msg = "Cannot specify plan by label more than once"
        with self.fuzzyAssertRaisesError(PhotonsAppError, msg, specified_multiple_times="one"):
            make_plans("two", "one", "three", "one")

    it "complains if a key is in by_key and plans":
        msg = "Cannot specify plan by label and by Plan class"
        with self.fuzzyAssertRaisesError(PhotonsAppError, msg, specified_twice="one"):
            make_plans("two", "one", one=Plan())

    it "complains if a key is provided by name but not in plan_by_key":
        with mock.patch("photons_control.planner.plans.plan_by_key", {"two": Plan, "three": Plan}):
            msg = "No default plan for key"
            with self.fuzzyAssertRaisesError(
                PhotonsAppError, msg, wanted="one", available=["two", "three"]
            ):
                make_plans("one")

    it "adds plans by label to plans dictionary":
        two_plan = mock.NonCallableMock(name="two_plan", spec=[])
        three_plan = mock.NonCallableMock(name="three_plan", spec=[])
        TwoPlan = mock.Mock(name="TwoPlan", return_value=two_plan)

        with mock.patch("photons_control.planner.plans.plan_by_key", {"two": TwoPlan}):
            expected = {"two": two_plan, "three": three_plan}
            self.assertEqual(make_plans("two", three=three_plan), expected)

    it "returns plans as is if no by label":
        two_plan = mock.NonCallableMock(name="two_plan", spec=[])
        three_plan = mock.NonCallableMock(name="three_plan", spec=[])
        expected = {"two": two_plan, "three": three_plan}
        self.assertEqual(make_plans(two=two_plan, three=three_plan), expected)

describe TestCase, "Plan":
    before_each:
        self.serial = "d073d5000001"
        self.plan = Plan()
        self.instance = self.plan.Instance(self.serial, self.plan, {})

    it "has no messages or dependant_info by default":
        self.assertEqual(self.plan.messages, None)
        self.assertEqual(self.instance.messages, None)
        self.assertEqual(self.plan.dependant_info, None)

    it "has default refresh which can be overridden":
        self.assertEqual(self.plan.refresh, 10)
        self.assertEqual(Plan(refresh=5).refresh, 5)

    it "can have a setup method":
        called = []

        class P(Plan):
            def setup(self, *args, **kwargs):
                called.append((args, kwargs))

        one = mock.Mock(name="one")
        two = mock.Mock(name="two")
        three = mock.Mock(name="three")

        p = P(one, two, three=three)
        self.assertEqual(called.pop(), ((one, two), {"three": three}))
        self.assertEqual(p.refresh, 10)

        p = P(one, two, three=three, refresh=6)
        self.assertEqual(called.pop(), ((one, two), {"three": three, "refresh": 6}))
        self.assertEqual(p.refresh, 6)

    it "has setup for Instance":
        called = []

        class P(Plan):
            class Instance(Plan.Instance):
                def setup(self):
                    called.append((self.serial, self.parent, self.deps))

        plan = P()
        deps = mock.Mock(name="deps")
        serial = mock.Mock(name="serial")

        instance = plan.Instance(serial, plan, deps)
        self.assertEqual(called, [(serial, plan, deps)])
