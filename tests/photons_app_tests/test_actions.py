# coding: spec

from photons_app.option_spec.task_objs import Task
from photons_app.test_helpers import TestCase
from photons_app.actions import an_action

from noseOfYeti.tokeniser.support import noy_sup_setUp
import uuid
import mock

describe TestCase, "an_action":
    it "takes in some options":
        target = mock.Mock(name="target")
        needs_reference = mock.Mock(name="needs_reference")
        special_reference = mock.Mock(name="special_reference")
        needs_target = mock.Mock(name="needs_target")

        wrapper = an_action(
              target = target
            , needs_reference = needs_reference
            , special_reference = special_reference
            , needs_target = needs_target
            )

        self.assertIs(wrapper.target, target)
        self.assertIs(wrapper.needs_reference, needs_reference)
        self.assertIs(wrapper.special_reference, special_reference)
        self.assertIs(wrapper.needs_target, needs_target)

    describe "wrapping a function":
        before_each:
            self.target = mock.Mock(name="target")
            self.needs_reference = mock.Mock(name="needs_reference")
            self.special_reference = mock.Mock(name="special_reference")
            self.needs_target = mock.Mock(name="needs_target")

            self.wrapper = an_action(
                  target = self.target
                , needs_reference = self.needs_reference
                , special_reference = self.special_reference
                , needs_target = self.needs_target
                )

            self.func_name = str(uuid.uuid1())
            self.func = mock.Mock(name='func', __name__=self.func_name)

        it "namespaces by target in available_actions":
            actions = {}
            with mock.patch("photons_app.actions.available_actions", actions):
                self.assertIs(self.wrapper(self.func), self.func)

            self.assertEqual(actions, {self.target: {self.func_name: self.func}})

        it "adds information to the func":
            actions = {}
            with mock.patch("photons_app.actions.available_actions", actions):
                self.assertIs(self.wrapper(self.func), self.func)

            self.assertIs(self.func.target, self.target)
            self.assertIs(self.func.needs_reference, self.needs_reference)
            self.assertIs(self.func.special_reference, self.special_reference)
            self.assertIs(self.func.needs_target, self.needs_target)

        it "adds to all_tasks":
            actions = {}
            all_tasks = {}
            with mock.patch("photons_app.actions.available_actions", actions):
                with mock.patch("photons_app.actions.all_tasks", all_tasks):
                    self.assertIs(self.wrapper(self.func), self.func)

            self.assertEqual(all_tasks, {self.func_name: Task(action=self.func_name, label="Project")})

        it "adds to all_tasks with specified label":
            label = str(uuid.uuid1())
            actions = {}
            all_tasks = {}
            with mock.patch("photons_app.actions.available_actions", actions):
                with mock.patch("photons_app.actions.all_tasks", all_tasks):
                    self.assertIs(an_action(label=label)(self.func), self.func)

            self.assertEqual(all_tasks, {self.func_name: Task(action=self.func_name, label=label)})
