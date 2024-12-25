
import uuid
from unittest import mock

from delfick_project.errors_pytest import assertRaises
from photons_app.errors import PhotonsAppError
from photons_control.planner.plans import Plan, a_plan, make_plans

class TestAPlan:
    def test_it_puts_items_in_plan_by_key(self):
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

class TestMakePlans:
    def test_it_returns_empty_if_given_no_arguments(self):
        assert make_plans() == {}

    def test_it_complains_if_a_key_is_specified_by_label_multiple_times(self):
        msg = "Cannot specify plan by label more than once"
        with assertRaises(PhotonsAppError, msg, specified_multiple_times="one"):
            make_plans("two", "one", "three", "one")

    def test_it_complains_if_a_key_is_in_by_key_and_plans(self):
        msg = "Cannot specify plan by label and by Plan class"
        with assertRaises(PhotonsAppError, msg, specified_twice="one"):
            make_plans("two", "one", one=Plan())

    def test_it_complains_if_a_key_is_provided_by_name_but_not_in_plan_by_key(self):
        with mock.patch("photons_control.planner.plans.plan_by_key", {"two": Plan, "three": Plan}):
            msg = "No default plan for key"
            with assertRaises(PhotonsAppError, msg, wanted="one", available=["two", "three"]):
                make_plans("one")

    def test_it_adds_plans_by_label_to_plans_dictionary(self):
        two_plan = mock.NonCallableMock(name="two_plan", spec=[])
        three_plan = mock.NonCallableMock(name="three_plan", spec=[])
        TwoPlan = mock.Mock(name="TwoPlan", return_value=two_plan)

        with mock.patch("photons_control.planner.plans.plan_by_key", {"two": TwoPlan}):
            expected = {"two": two_plan, "three": three_plan}
            assert make_plans("two", three=three_plan) == expected

    def test_it_returns_plans_as_is_if_no_by_label(self):
        two_plan = mock.NonCallableMock(name="two_plan", spec=[])
        three_plan = mock.NonCallableMock(name="three_plan", spec=[])
        expected = {"two": two_plan, "three": three_plan}
        assert make_plans(two=two_plan, three=three_plan) == expected

class TestPlan:
    def test_it_has_no_messages_or_dependant_info_by_default(self):
        plan = Plan()
        instance = plan.Instance("d073d5001337", plan, {})

        assert plan.messages is None
        assert instance.messages is None
        assert plan.dependant_info is None

    def test_it_has_default_refresh_which_can_be_overridden(self):
        assert Plan().refresh == 10
        assert Plan(refresh=5).refresh == 5

    def test_it_can_have_a_setup_method(self):
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

    def test_it_has_setup_for_Instance(self):
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
