# coding: spec

import asyncio
import time
from unittest import mock

import pytest
from alt_pytest_asyncio.plugin import OverrideLoop
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import dictobj, sb
from photons_app import helpers as hp
from photons_app.collector import Collector
from photons_app.photons_app import PhotonsApp
from photons_app.tasks.tasks import Task

describe "Task":

    @pytest.fixture()
    def collector(self):
        with OverrideLoop(new_loop=False):
            collector = Collector()
            collector.prepare(None, {})
            yield collector

    it "has a create method", collector:
        photons_app = collector.configuration["photons_app"]
        assert isinstance(photons_app, PhotonsApp)

        task = Task.create(collector, instantiated_name="MyAmazingTask")
        assert task.collector is collector
        assert task.photons_app is photons_app
        assert task.instantiated_name == "MyAmazingTask"

        class T(Task):
            thing = dictobj.Field(sb.listof(sb.string_spec()))

        t2 = T.create(collector, instantiated_name="MyAmazingTask", where="in_tests")
        assert t2.collector is collector
        assert t2.photons_app is photons_app
        assert t2.instantiated_name == "MyAmazingTask"
        assert t2.thing == []

        t3 = T.create(collector, instantiated_name="MyAmazingerTask", thing="one")
        assert t3.collector is collector
        assert t3.photons_app is photons_app
        assert t3.instantiated_name == "MyAmazingerTask"
        assert t3.thing == ["one"]

    async it "has a run method", collector:
        a = mock.Mock(name="a")
        b = mock.Mock(name="b")
        d = mock.Mock(name="d")

        task = Task.create(collector, instantiated_name="MyAmazingTask")

        post = pytest.helpers.AsyncMock(name="post")
        execute_task = pytest.helpers.AsyncMock(name="execute_task", return_value=d)

        with mock.patch.multiple(task, post=post, execute_task=execute_task):
            assert (await task.run(a=a, c=b)) is d
            execute_task.assert_called_once_with(a=a, c=b)
            post.assert_called_once_with((None, None, None), a=a, c=b)

            post.reset_mock()
            execute_task.reset_mock()
            error = ValueError("HI")
            execute_task.side_effect = error

            with assertRaises(ValueError, "HI"):
                await task.run(a=a, c=b)

            execute_task.assert_called_once_with(a=a, c=b)
            post.assert_called_once_with((ValueError, error, mock.ANY), a=a, c=b)

    it "has a shortcut to run in a loop", collector:
        got = []

        class T(Task):
            async def execute_task(s, **kwargs):
                fut = hp.create_future()
                fut.set_result(True)
                await fut
                got.append(kwargs)

        task = T.create(collector, instantiated_name="Thing")
        task.run_loop(wat=1, blah=2)

        assert got == [{"wat": 1, "blah": 2}]

    it "has order of cleanup and execution", FakeTime, MockedCallLater, collector:

        got = []
        m = None

        with FakeTime() as t:

            class T(Task):
                async def run(s, **kwargs):
                    global m
                    m = MockedCallLater(t)
                    await m.start()
                    try:
                        with mock.patch.object(s.photons_app.loop, "call_later", m._call_later):
                            await super().run(**kwargs)
                    finally:
                        s.photons_app.cleaners.append(m.finish)

                async def execute_task(s, **kwargs):
                    fut = hp.create_future()
                    got.append((time.time(), "first"))

                    async def wait():
                        try:
                            got.append((time.time(), "wait"))
                            await fut
                        except asyncio.CancelledError:
                            got.append((time.time(), "wait stopped"))

                    s.task_holder.add(wait())

                    async def sleeper():
                        await asyncio.sleep(2)
                        got.append((time.time(), "blink"))
                        await asyncio.sleep(8)
                        got.append((time.time(), "rested"))

                    s.task_holder.add(sleeper())

                    async def cleaner1():
                        got.append((time.time(), "cleaner1"))

                    s.photons_app.cleaners.append(cleaner1)

                    async def cleaner2():
                        await asyncio.sleep(1)
                        got.append((time.time(), "cleaner2"))

                    s.photons_app.cleaners.append(cleaner2)

                    await asyncio.sleep(3)
                    got.append((time.time(), "wait now"))

                    s.photons_app.loop.call_later(0.5, fut.cancel)

                async def post(s, exc_info, **kwargs):
                    got.append((time.time(), "post"))
                    await asyncio.sleep(1)
                    got.append((time.time(), "post sleep"))

            task = T.create(collector, instantiated_name="Thing")
            task.run_loop()

            assert got == [
                (0, "first"),
                (0, "wait"),
                (2.0, "blink"),
                (3.0, "wait now"),
                (3.0, "post"),
                (3.5, "wait stopped"),
                (4.0, "post sleep"),
                (10.0, "rested"),
                (10.0, "cleaner1"),
                (11.0, "cleaner2"),
            ]
