# coding: spec

from photons_app.errors import PhotonsAppError, ApplicationCancelled, ApplicationStopped
from photons_app.tasks.tasks import Task, GracefulTask
from photons_app.collector import Collector
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from alt_pytest_asyncio.plugin import OverrideLoop
import asyncio
import pytest


@pytest.fixture()
def collector():
    with OverrideLoop(new_loop=False):
        collector = Collector()
        collector.prepare(None, {})
        yield collector


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
                    hp.get_event_loop().call_later(0.02, collector.photons_app.final_future.cancel)
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
                called.append(())

        class T(Task):
            @hp.memoized_property
            def task_holder(s):
                return TaskHolder(name="normal")

            async def execute_task(s, name, exc, **kwargs):
                called.append(("normal execute", name))
                if exc is not None:
                    raise exc

            async def post(s, exc_info, name, **kwargs):
                called.append(("normal post", name, getattr(exc_info[0], "__name__", exc_info[0])))

        class G(GracefulTask):
            @hp.memoized_property
            def task_holder(s):
                return TaskHolder(name="graceful")

            async def execute_task(s, name, exc, **kwargs):
                called.append(("graceful execute", name))
                if exc is not None:
                    raise exc

            async def post(s, exc_info, name, **kwargs):
                called.append(
                    ("graceful post", name, getattr(exc_info[0], "__name__", exc_info[0]))
                )

        for t in (T, G):
            with assertRaises(ApplicationCancelled):
                t.create(collector).run_loop(name="cancelled", exc=ApplicationCancelled())

            if t is T:
                with assertRaises(ApplicationStopped):
                    t.create(collector).run_loop(name="stopped", exc=ApplicationStopped())
            else:
                t.create(collector).run_loop(name="stopped", exc=ApplicationStopped())

            with assertRaises(ValueError):
                t.create(collector).run_loop(name="error", exc=ValueError("nope"))

            t.create(collector).run_loop(name="success", exc=None)

        assert called == [
            ("normal execute", "cancelled"),
            ("normal post", "cancelled", "ApplicationCancelled"),
            ("task_holder_exit", "normal", "ApplicationCancelled"),
            (),
            ("normal execute", "stopped"),
            ("normal post", "stopped", "ApplicationStopped"),
            ("task_holder_exit", "normal", "ApplicationStopped"),
            (),
            ("normal execute", "error"),
            ("normal post", "error", "ValueError"),
            ("task_holder_exit", "normal", "ValueError"),
            (),
            ("normal execute", "success"),
            ("normal post", "success", None),
            ("task_holder_exit", "normal", None),
            (),
            ("graceful execute", "cancelled"),
            ("graceful post", "cancelled", "ApplicationCancelled"),
            ("task_holder_exit", "graceful", "ApplicationCancelled"),
            (),
            ("graceful execute", "stopped"),
            ("graceful post", "stopped", "ApplicationStopped"),
            ("task_holder_exit", "graceful", None),
            (),
            ("graceful execute", "error"),
            ("graceful post", "error", "ValueError"),
            ("task_holder_exit", "graceful", "ValueError"),
            (),
            ("graceful execute", "success"),
            ("graceful post", "success", None),
            ("task_holder_exit", "graceful", None),
            (),
        ]
