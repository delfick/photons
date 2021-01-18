# coding: spec

from photons_app.collector import TaskFinder
from photons_app.actions import all_tasks
from photons_app.errors import BadTask
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import pytest

describe "TaskFinder":

    @pytest.fixture()
    def collector(self):
        return mock.Mock(name="collector")

    @pytest.fixture()
    def task_finder(self, collector):
        return TaskFinder(collector)

    async it "takes in a collector", collector:
        task_finder = TaskFinder(collector)

        assert task_finder.collector is collector
        assert task_finder.tasks is all_tasks

    describe "task_runner":

        @pytest.fixture()
        def V(self, collector, task_finder):
            class V:
                task = mock.Mock(name="task")
                target = mock.Mock(name="target")

                def __init__(s):
                    s.collector = collector
                    s.task_finder = task_finder
                    s.task_finder.tasks = s.tasks

                @hp.memoized_property
                def one_task(s):
                    one_task = mock.Mock(name="one")
                    one_task.run = pytest.helpers.AsyncMock(name="run")
                    return one_task

                @hp.memoized_property
                def two_task(s):
                    two_task = mock.Mock(name="two")
                    two_task.run = pytest.helpers.AsyncMock(name="two_task")
                    return two_task

                @hp.memoized_property
                def tasks(s):
                    return {"one": s.one_task, "two": s.two_task}

            return V()

        async it "complains if the task is not in self.tasks", V:
            assert "three" not in V.task_finder.tasks
            with assertRaises(BadTask, "Unknown task", task="three", available=["one", "two"]):
                await V.task_finder.task_runner(V.target, "three")

        async it "runs the chosen task", V:
            res = mock.Mock(name="res")
            V.one_task.run.return_value = res

            available_actions = mock.Mock(name="available_actions")

            with mock.patch("photons_app.collector.available_actions", available_actions):
                assert await V.task_finder.task_runner(V.target, "one") is res

            V.one_task.run.assert_called_once_with(
                V.target, V.collector, available_actions, V.tasks
            )

        async it "runs the chosen task with the other kwargs", V:
            one = mock.Mock(name="one")
            res = mock.Mock(name="res")
            V.one_task.run.return_value = res

            available_actions = mock.Mock(name="available_actions")

            with mock.patch("photons_app.collector.available_actions", available_actions):
                assert await V.task_finder.task_runner(V.target, "one", one=one, two=3) is res

            V.one_task.run.assert_called_once_with(
                V.target, V.collector, available_actions, V.tasks, one=one, two=3
            )
