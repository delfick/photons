# coding: spec

from photons_app.errors import ProgrammerError, BadTask
from photons_app.option_spec.task_objs import Task
from photons_app.test_helpers import AsyncTestCase
from photons_app.task_finder import TaskFinder
from photons_app.actions import all_tasks

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from delfick_project.norms import sb
from unittest import mock
import asynctest

describe AsyncTestCase, "TaskFinder":
    async before_each:
        self.collector = mock.Mock(name="collector")
        self.task_finder = TaskFinder(self.collector)

    async it "takes in a collector":
        task_finder = TaskFinder(self.collector)

        self.assertIs(task_finder.collector, self.collector)
        self.assertIs(task_finder.tasks, all_tasks)

    describe "task_runner":
        async before_each:
            self.task = mock.Mock(name="task")

        describe "after finding tasks":
            async before_each:
                self.one_task = mock.Mock(name="one")
                self.one_task.run = asynctest.mock.CoroutineMock(name="run")

                self.two_task = mock.Mock(name="two")
                self.two_task.run = asynctest.mock.CoroutineMock(name="two_task")

                self.tasks = {"one": self.one_task, "two": self.two_task}
                self.task_finder.tasks = self.tasks

            async it "complains if the task is not in self.tasks":
                assert "three" not in self.task_finder.tasks
                with self.fuzzyAssertRaisesError(
                    BadTask, "Unknown task", task="three", available=["one", "two"]
                ):
                    await self.task_finder.task_runner("three")

                with self.fuzzyAssertRaisesError(
                    BadTask, "Unknown task", task="three", available=["one", "two"]
                ):
                    await self.task_finder.task_runner("target:three")

            async it "runs the chosen task":
                res = mock.Mock(name="res")
                self.one_task.run.return_value = res

                available_actions = mock.Mock(name="available_actions")

                with mock.patch("photons_app.task_finder.available_actions", available_actions):
                    self.assertIs(await self.task_finder.task_runner("one"), res)

                self.one_task.run.assert_called_once_with(
                    sb.NotSpecified, self.collector, available_actions, self.tasks
                )

            async it "runs the chosen task with the specified target":
                res = mock.Mock(name="res")
                self.one_task.run.return_value = res

                available_actions = mock.Mock(name="available_actions")

                with mock.patch("photons_app.task_finder.available_actions", available_actions):
                    self.assertIs(await self.task_finder.task_runner("target:one"), res)

                self.one_task.run.assert_called_once_with(
                    "target", self.collector, available_actions, self.tasks
                )

            async it "runs the chosen task with the other kwargs":
                one = mock.Mock(name="one")
                res = mock.Mock(name="res")
                self.one_task.run.return_value = res

                available_actions = mock.Mock(name="available_actions")

                with mock.patch("photons_app.task_finder.available_actions", available_actions):
                    self.assertIs(
                        await self.task_finder.task_runner("target:one", one=one, two=3), res
                    )

                self.one_task.run.assert_called_once_with(
                    "target", self.collector, available_actions, self.tasks, one=one, two=3
                )
