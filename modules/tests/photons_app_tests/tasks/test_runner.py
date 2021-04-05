# coding: spec

from photons_app.errors import PhotonsAppError, ApplicationCancelled, ApplicationStopped
from photons_app.tasks.tasks import Task, GracefulTask
from photons_app.collector import Collector
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
import asyncio
import pytest


@pytest.fixture()
def collector():
    collector = Collector()
    collector.prepare(None, {})
    return collector


describe "Runner":
    it "runs cleanup functions when done", collector:
        called = []

        class T(Task):
            async def execute_task(self, collector, **kwargs):
                called.append(1)

                async def cleanup1():
                    called.append("c1a")
                    fut = hp.create_future()
                    fut.set_result(True)
                    await fut
                    called.append("c1b")

                async def cleanup2():
                    called.append("c2a")
                    fut = hp.create_future()
                    fut.set_result(True)
                    await fut
                    called.append("c2b")

                collector.photons_app.cleaners.extend([cleanup1, cleanup2])
                called.append(2)

        T.create(collector).run_loop(collector=collector)
        assert called == [1, 2, "c1a", "c1b", "c2a", "c2b"]

    it "runs cleanup functions even if we had an exception", collector:
        called = []

        class T(Task):
            async def execute_task(self, collector, **kwargs):
                called.append(1)

                async def cleanup1():
                    called.append("c1a")
                    fut = hp.create_future()
                    fut.set_result(True)
                    await fut
                    called.append("c1b")

                async def cleanup2():
                    called.append("c2a")
                    fut = hp.create_future()
                    fut.set_result(True)
                    await fut
                    called.append("c2b")

                collector.photons_app.cleaners.extend([cleanup1, cleanup2])
                called.append(2)
                try:
                    raise PhotonsAppError("YO")
                except:
                    fut = hp.create_future()
                    fut.set_result(True)
                    await fut
                    called.append(3)
                    raise
                finally:
                    called.append(4)

        with assertRaises(PhotonsAppError, "YO"):
            T.create(collector).run_loop(collector=collector)

        assert called == [1, 2, 3, 4, "c1a", "c1b", "c2a", "c2b"]

    it "cleans up after we finish task if it's cancelled outside", collector:

        called = []

        class T(Task):
            async def execute_task(self, collector, **kwargs):
                called.append(1)

                async def cleanup1():
                    called.append("c1a")
                    fut = hp.create_future()
                    fut.set_result(True)
                    await fut
                    called.append("c1b")

                async def cleanup2():
                    called.append("c2a")
                    fut = hp.create_future()
                    fut.set_result(True)
                    await fut
                    called.append("c2b")

                collector.photons_app.cleaners.extend([cleanup1, cleanup2])
                called.append(2)

                try:
                    asyncio.get_event_loop().call_later(
                        0.02, collector.photons_app.final_future.cancel
                    )
                    await asyncio.sleep(10)
                    called.append("unexpected")
                except:
                    fut = hp.create_future()
                    fut.set_result(True)
                    await fut
                    called.append(3)
                    raise
                finally:
                    called.append(4)

        with assertRaises(ApplicationCancelled):
            T.create(collector).run_loop(collector=collector)

        assert called == [1, 2, 3, 4, "c1a", "c1b", "c2a", "c2b"]

    it "exceptions stop the task_holder unless ApplicationStopped for a graceful task", collector:

        called = []

        class TaskHolder:
            def __init__(s, name):
                s.name = name

            async def __aenter__(s):
                return s

            async def __aexit__(s, exc_typ, exc, tb):
                called.append(("task_holder_exit", s.name, getattr(exc_typ, "__name__", exc_typ)))

        class T(Task):
            @hp.memoized_property
            def task_holder(s):
                return TaskHolder(name="normal")

            async def execute_task(s, name, exc, **kwargs):
                called.append(("execute", name))
                if exc is not None:
                    raise exc

        class G(GracefulTask):
            @hp.memoized_property
            def task_holder(s):
                return TaskHolder(name="graceful")

            async def execute_task(s, name, exc, **kwargs):
                called.append(("graceful execute", name))
                if exc is not None:
                    raise exc

        for t in (T, G):
            with assertRaises(ApplicationCancelled):
                t.create(collector).run_loop(name="cancelled", exc=ApplicationCancelled())

            with assertRaises(ApplicationStopped):
                t.create(collector).run_loop(name="stopped", exc=ApplicationStopped())

            with assertRaises(ValueError):
                t.create(collector).run_loop(name="error", exc=ValueError("nope"))

            t.create(collector).run_loop(name="success", exc=None)

        assert called == [
            ("execute", "cancelled"),
            ("task_holder_exit", "normal", "ApplicationCancelled"),
            ("execute", "stopped"),
            ("task_holder_exit", "normal", "ApplicationStopped"),
            ("execute", "error"),
            ("task_holder_exit", "normal", "ValueError"),
            ("execute", "success"),
            ("task_holder_exit", "normal", None),
            ("graceful execute", "cancelled"),
            ("task_holder_exit", "graceful", "ApplicationCancelled"),
            ("graceful execute", "stopped"),
            ("task_holder_exit", "graceful", None),
            ("graceful execute", "error"),
            ("task_holder_exit", "graceful", "ValueError"),
            ("graceful execute", "success"),
            ("task_holder_exit", "graceful", None),
        ]
