# coding: spec

from photons_control.planner.plans import Plan, Skip, NoMessages
from photons_control.planner.gatherer import PlanInfo

from photons_app.test_helpers import TestCase

from photons_messages import DeviceMessages

from noseOfYeti.tokeniser.support import noy_sup_setUp
from unittest import mock

describe TestCase, "PlanInfo":
    before_each:
        self.plan = mock.Mock(name="plan")
        self.plankey = mock.Mock(name="plankey")
        self.instance = mock.Mock(name="instance")
        self.completed = mock.Mock(name="completed")

    it "takes in some things":
        info = PlanInfo(self.plan, self.plankey, self.instance, self.completed)
        self.assertIs(info.plan, self.plan)
        self.assertIs(info.plankey, self.plankey)
        self.assertIs(info.instance, self.instance)
        self.assertIs(info.completed, self.completed)
        assert info.done

        info = PlanInfo(self.plan, self.plankey, self.instance, None)
        self.assertIs(info.completed, None)
        assert not info.done

    it "can be marked done":
        info = PlanInfo(self.plan, self.plankey, self.instance, None)
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
                def messages(self):
                    called.append("shouldn't be called")
                    return [get_label]

                class Instance(Plan.Instance):
                    @property
                    def messages(self):
                        called.append(1)
                        return [get_power]

            plan = P()
            instance = plan.Instance("d073d5000001", plan, {})
            plankey = instance.key()

            info = PlanInfo(plan, plankey, instance, None)

            self.assertEqual(called, [])
            messages = info.messages
            self.assertEqual(called, [1])
            self.assertEqual(messages, [get_power])

            # Memoized!
            messages = info.messages
            self.assertEqual(called, [1])
            self.assertEqual(messages, [get_power])

            called = []

            class P(Plan):
                @property
                def messages(self):
                    called.append(2)
                    return [get_label]

            plan = P()
            instance = plan.Instance("d073d5000001", plan, {})
            plankey = instance.key()

            info = PlanInfo(plan, plankey, instance, None)

            self.assertEqual(called, [])
            messages = info.messages
            self.assertEqual(called, [2])
            self.assertEqual(messages, [get_label])

            # Memoized!
            messages = info.messages
            self.assertEqual(called, [2])
            self.assertEqual(messages, [get_label])

    describe "not_done_messages":
        it "yields messages if not already done":
            get_power = DeviceMessages.GetPower()
            get_label = DeviceMessages.GetLabel()

            self.instance.messages = [get_power, get_label]

            info = PlanInfo(self.plan, self.plankey, self.instance, None)
            self.assertEqual(list(info.not_done_messages), [get_power, get_label])
            self.assertEqual(list(info.not_done_messages), [get_power, get_label])

            info.mark_done()
            self.assertEqual(list(info.not_done_messages), [])

            info = PlanInfo(self.plan, self.plankey, self.instance, self.completed)
            self.assertEqual(list(info.not_done_messages), [])

        it "does not yield messages if the messages is Skip":
            self.instance.messages = Skip
            info = PlanInfo(self.plan, self.plankey, self.instance, self.completed)
            self.assertEqual(list(info.not_done_messages), [])

        it "does not yield messages if the messages is NoMessages":
            self.instance.messages = NoMessages
            info = PlanInfo(self.plan, self.plankey, self.instance, self.completed)
            self.assertEqual(list(info.not_done_messages), [])
