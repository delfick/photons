# coding: spec

from photons_control.planner.plans import Plan, Skip, NoMessages
from photons_control.planner.gatherer import PlanInfo

from photons_messages import DeviceMessages

from unittest import mock
import pytest

describe "PlanInfo":

    @pytest.fixture()
    def V(self):
        class V:
            plan = mock.Mock(name="plan")
            plankey = mock.Mock(name="plankey")
            instance = mock.Mock(name="instance")
            completed = mock.Mock(name="completed")

        return V()

    it "takes in some things", V:
        info = PlanInfo(V.plan, V.plankey, V.instance, V.completed)
        assert info.plan is V.plan
        assert info.plankey is V.plankey
        assert info.instance is V.instance
        assert info.completed is V.completed
        assert info.done

        info = PlanInfo(V.plan, V.plankey, V.instance, None)
        assert info.completed is None
        assert not info.done

    it "can be marked done", V:
        info = PlanInfo(V.plan, V.plankey, V.instance, None)
        assert not info.done

        info.mark_done()
        assert info.done

    describe "messages":
        it "memoizes the messages and cares about instance messages before plan messages":
            called = []

            get_power = DeviceMessages.GetPower()
            get_label = DeviceMessages.GetLabel()

            class P(Plan):
                @property
                def messages(s):
                    called.append("shouldn't be called")
                    return [get_label]

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        called.append(1)
                        return [get_power]

            plan = P()
            instance = plan.Instance("d073d5000001", plan, {})
            plankey = instance.key()

            info = PlanInfo(plan, plankey, instance, None)

            assert called == []
            messages = info.messages
            assert called == [1]
            assert messages == [get_power]

            # Memoized!
            messages = info.messages
            assert called == [1]
            assert messages == [get_power]

            called = []

            class P(Plan):
                @property
                def messages(s):
                    called.append(2)
                    return [get_label]

            plan = P()
            instance = plan.Instance("d073d5000001", plan, {})
            plankey = instance.key()

            info = PlanInfo(plan, plankey, instance, None)

            assert called == []
            messages = info.messages
            assert called == [2]
            assert messages == [get_label]

            # Memoized!
            messages = info.messages
            assert called == [2]
            assert messages == [get_label]

    describe "not_done_messages":
        it "yields messages if not already done", V:
            get_power = DeviceMessages.GetPower()
            get_label = DeviceMessages.GetLabel()

            V.instance.messages = [get_power, get_label]

            info = PlanInfo(V.plan, V.plankey, V.instance, None)
            assert list(info.not_done_messages) == [get_power, get_label]
            assert list(info.not_done_messages) == [get_power, get_label]

            info.mark_done()
            assert list(info.not_done_messages) == []

            info = PlanInfo(V.plan, V.plankey, V.instance, V.completed)
            assert list(info.not_done_messages) == []

        it "does not yield messages if the messages is Skip", V:
            V.instance.messages = Skip
            info = PlanInfo(V.plan, V.plankey, V.instance, V.completed)
            assert list(info.not_done_messages) == []

        it "does not yield messages if the messages is NoMessages", V:
            V.instance.messages = NoMessages
            info = PlanInfo(V.plan, V.plankey, V.instance, V.completed)
            assert list(info.not_done_messages) == []
