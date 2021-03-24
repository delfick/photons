# coding: spec

from photons_app.errors import PhotonsAppError, ApplicationCancelled
from photons_app.collector import Collector
from photons_app.tasks.tasks import Task
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
