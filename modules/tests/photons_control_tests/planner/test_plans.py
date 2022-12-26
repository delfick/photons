# coding: spec

import uuid
from unittest import mock

from delfick_project.errors_pytest import assertRaises
from photons_app.errors import PhotonsAppError
from photons_control.planner.plans import Plan, a_plan, make_plans

describe "a_plan":
    it "puts items in plan_by_key":
        d = {}
        key = str(uuid.uuid1())
        key2 = str(uuid.uuid1())

        class Plan:
            pass

        class Plan2:
            pass

        with mock.patch("photons_control.planner.plans.plan_by_key", d):
            assert a_plan(key)(Plan) is Plan
        assert d == {key: Plan}

        with mock.patch("photons_control.planner.plans.plan_by_key", d):
            assert a_plan(key2)(Plan2) is Plan2
        assert d == {key: Plan, key2: Plan2}

describe "make_plans":
    it "returns empty if given no arguments":
        assert make_plans() == {}

    it "complains if a key is specified by label multiple times":
        msg = "Cannot specify plan by label more than once"
        with assertRaises(PhotonsAppError, msg, specified_multiple_times="one"):
            make_plans("two", "one", "three", "one")

    it "complains if a key is in by_key and plans":
        msg = "Cannot specify plan by label and by Plan class"
        with assertRaises(PhotonsAppError, msg, specified_twice="one"):
            make_plans("two", "one", one=Plan())

    it "complains if a key is provided by name but not in plan_by_key":
        with mock.patch("photons_control.planner.plans.plan_by_key", {"two": Plan, "three": Plan}):
            msg = "No default plan for key"
            with assertRaises(PhotonsAppError, msg, wanted="one", available=["two", "three"]):
                make_plans("one")

    it "adds plans by label to plans dictionary":
        two_plan = mock.NonCallableMock(name="two_plan", spec=[])
        three_plan = mock.NonCallableMock(name="three_plan", spec=[])
        TwoPlan = mock.Mock(name="TwoPlan", return_value=two_plan)

        with mock.patch("photons_control.planner.plans.plan_by_key", {"two": TwoPlan}):
            expected = {"two": two_plan, "three": three_plan}
            assert make_plans("two", three=three_plan) == expected

    it "returns plans as is if no by label":
        two_plan = mock.NonCallableMock(name="two_plan", spec=[])
        three_plan = mock.NonCallableMock(name="three_plan", spec=[])
        expected = {"two": two_plan, "three": three_plan}
        assert make_plans(two=two_plan, three=three_plan) == expected

describe "Plan":
    it "has no messages or dependant_info by default":
        plan = Plan()
        instance = plan.Instance("d073d5001337", plan, {})

        assert plan.messages is None
        assert instance.messages is None
        assert plan.dependant_info is None

    it "has default refresh which can be overridden":
        assert Plan().refresh == 10
        assert Plan(refresh=5).refresh == 5

    it "can have a setup method":
        called = []

        class P(Plan):
            def setup(s, *args, **kwargs):
                called.append((args, kwargs))

        one = mock.Mock(name="one")
        two = mock.Mock(name="two")
        three = mock.Mock(name="three")

        p = P(one, two, three=three)
        assert called.pop() == ((one, two), {"three": three})
        assert p.refresh == 10

        p = P(one, two, three=three, refresh=6)
        assert called.pop() == ((one, two), {"three": three, "refresh": 6})
        assert p.refresh == 6

    it "has setup for Instance":
        called = []

        class P(Plan):
            class Instance(Plan.Instance):
                def setup(s):
                    called.append((s.serial, s.parent, s.deps))

        plan = P()
        deps = mock.Mock(name="deps")
        serial = mock.Mock(name="serial")

        plan.Instance(serial, plan, deps)
        assert called == [(serial, plan, deps)]
