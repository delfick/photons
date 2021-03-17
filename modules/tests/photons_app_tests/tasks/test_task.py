# coding: spec

from photons_app.tasks.tasks import NewTask as Task
from photons_app.photons_app import PhotonsApp
from photons_app.collector import Collector
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import dictobj, sb
from unittest import mock
import pytest


describe "Task":
    it "has a create method":
        collector = Collector()
        collector.prepare(None, {})
        photons_app = collector.configuration["photons_app"]
        assert isinstance(photons_app, PhotonsApp)

        task = Task.create("in_tests", "MyAmazingTask", collector)
        assert task.collector is collector
        assert task.photons_app is photons_app
        assert task.instantiated_name == "MyAmazingTask"

        class T(Task):
            thing = dictobj.Field(sb.listof(sb.string_spec()))

        t2 = T.create("in_tests", "MyAmazingTask", collector)
        assert t2.collector is collector
        assert t2.photons_app is photons_app
        assert t2.instantiated_name == "MyAmazingTask"
        assert t2.thing == []

        t3 = T.create("in_tests", "MyAmazingerTask", collector, thing="one")
        assert t3.collector is collector
        assert t3.photons_app is photons_app
        assert t3.instantiated_name == "MyAmazingerTask"
        assert t3.thing == ["one"]

    async it "has a run method":
        a = mock.Mock(name="a")
        b = mock.Mock(name="b")
        d = mock.Mock(name="d")

        collector = Collector()
        collector.prepare(None, {})
        task = Task.create("in_tests", "MyAmazingTask", collector)

        post = pytest.helpers.AsyncMock(name="post")
        execute_task = pytest.helpers.AsyncMock(name="execute_task", return_value=d)

        with mock.patch.multiple(task, post=post, execute_task=execute_task):
            assert (await task.run(a=a, c=b)) is d
            execute_task.assert_called_once_with(a=a, c=b)
            post.assert_called_once_with()

            post.reset_mock()
            execute_task.reset_mock()
            execute_task.side_effect = ValueError("HI")

            with assertRaises(ValueError, "HI"):
                await task.run(a=a, c=b)

            execute_task.assert_called_once_with(a=a, c=b)
            post.assert_called_once_with()

    it "has a shortcut to run in a loop":
        got = []

        class T(Task):
            async def execute_task(s, **kwargs):
                fut = hp.create_future()
                fut.set_result(True)
                await fut
                got.append(kwargs)

        collector = Collector()
        collector.prepare(None, {})

        task = T.create("in_tests", "Thing", collector)
        task.run_loop(wat=1, blah=2)

        assert got == [{"wat": 1, "blah": 2}]
