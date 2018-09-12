# coding: spec

from photons_app.test_helpers import TestCase, AsyncTestCase
from photons_app.runner import run, runner

import asynctest
import platform
import asyncio
import signal
import mock
import nose
import os

describe TestCase, "run":
    it "runs the collector and runs cleanup when that's done":
        info = {"cleaned": False, "ran": False}

        loop = asyncio.new_event_loop()
        final_future = asyncio.Future(loop=loop)

        target_register = mock.Mock(name='target_register')

        async def cleanup(tr):
            self.assertEqual(tr, target_register.target_values)
            await asyncio.sleep(0.01)
            info["cleaned"] = True

        async def task_runner(*args):
            await asyncio.sleep(0.01)
            info["ran"] = True
        task_runner = mock.Mock(name="task_runner", side_effect=task_runner)

        photons_app = mock.Mock(name="photons_app", loop=loop, chosen_task="task", reference="reference", final_future=final_future)
        photons_app.cleanup.side_effect = cleanup

        configuration = {"photons_app": photons_app, "target_register": target_register, "task_runner": task_runner}
        collector = mock.Mock(name="collector", configuration=configuration)

        run(collector)
        self.assertEqual(info, {"cleaned": True, "ran": True})

    it "cleans up even if runner raise an exception":
        info = {"cleaned": False, "ran": False}

        loop = asyncio.new_event_loop()
        final_future = asyncio.Future(loop=loop)

        target_register = mock.Mock(name='target_register')

        async def cleanup(tr):
            self.assertEqual(tr, target_register.target_values)
            await asyncio.sleep(0.01)
            info["cleaned"] = True

        async def task_runner(*args):
            await asyncio.sleep(0.01)
            info["ran"] = True
            raise ValueError("Nope")
        task_runner = mock.Mock(name="task_runner", side_effect=task_runner)

        photons_app = mock.Mock(name="photons_app", loop=loop, chosen_task="task", reference="reference", final_future=final_future)
        photons_app.cleanup.side_effect = cleanup

        configuration = {"photons_app": photons_app, "target_register": target_register, "task_runner": task_runner}
        collector = mock.Mock(name="collector", configuration=configuration)

        with self.fuzzyAssertRaisesError(ValueError, "Nope"):
            run(collector)

        self.assertEqual(info, {"cleaned": True, "ran": True})

describe AsyncTestCase, "runner":
    async it "cancels final_future if it gets a SIGTERM":
        if platform.system() == "Windows":
            raise nose.SkipTest()

        final = asyncio.Future()
        reference = mock.Mock(name="reference")
        chosen_task = mock.Mock(name="chosen_task")
        photons_app = mock.Mock(name="photons_app", chosen_task=chosen_task, final_future=final, reference=reference)

        async def sleep(*args, **kwargs):
            await asyncio.sleep(2)
        task_runner = asynctest.mock.CoroutineMock(name="task_runner", side_effect=sleep)

        configuration = {"photons_app": photons_app, "task_runner": task_runner}
        collector = mock.Mock(name="collector", configuration=configuration)

        t = self.loop.create_task(runner(collector))
        await asyncio.sleep(0)
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.sleep(0)

        with self.fuzzyAssertRaisesError(asyncio.CancelledError):
            await self.wait_for(t)

        assert final.cancelled()
        task_runner.assert_called_once_with(chosen_task, reference)

    async it "sets exception on final future if one is risen":
        final = asyncio.Future()
        error = Exception("wat")
        reference = mock.Mock(name="reference")
        chosen_task = mock.Mock(name="chosen_task")
        photons_app = mock.Mock(name="photons_app", chosen_task=chosen_task, final_future=final, reference=reference)
        task_runner = asynctest.mock.CoroutineMock(name="task_runner", side_effect=error)
        configuration = {"photons_app": photons_app, "task_runner": task_runner}
        collector = mock.Mock(name="collector", configuration=configuration)

        t = self.loop.create_task(runner(collector))
        with self.fuzzyAssertRaisesError(Exception, "wat"):
            await self.wait_for(t)

        self.assertEqual(final.exception(), error)
        task_runner.assert_called_once_with(chosen_task, reference)

    async it "sets exception on final future if one is risen unless it's already cancelled":
        final = asyncio.Future()
        error = Exception("wat")
        reference = mock.Mock(name="reference")
        chosen_task = mock.Mock(name="chosen_task")
        photons_app = mock.Mock(name="photons_app", chosen_task=chosen_task, final_future=final, reference=reference)

        def tr(*args, **kwargs):
            final.cancel()
            raise error
        task_runner = asynctest.mock.CoroutineMock(name="task_runner", side_effect=tr)

        configuration = {"photons_app": photons_app, "task_runner": task_runner}
        collector = mock.Mock(name="collector", configuration=configuration)

        t = self.loop.create_task(runner(collector))
        with self.fuzzyAssertRaisesError(asyncio.CancelledError):
            await self.wait_for(t)

        assert final.cancelled()
        task_runner.assert_called_once_with(chosen_task, reference)

    async it "doesn't fail if the final_future is already cancelled when the task finishes":
        final = asyncio.Future()
        reference = mock.Mock(name="reference")
        chosen_task = mock.Mock(name="chosen_task")
        photons_app = mock.Mock(name="photons_app", chosen_task=chosen_task, final_future=final, reference=reference)

        def tr(*args, **kwargs):
            final.cancel()
        task_runner = asynctest.mock.CoroutineMock(name="task_runner", side_effect=tr)

        configuration = {"photons_app": photons_app, "task_runner": task_runner}
        collector = mock.Mock(name="collector", configuration=configuration)

        t = self.loop.create_task(runner(collector))
        with self.fuzzyAssertRaisesError(asyncio.CancelledError):
            await self.wait_for(t)

        assert final.cancelled()
        task_runner.assert_called_once_with(chosen_task, reference)

    async it "doesn't fail if the final_future is already done when the task finishes":
        final = asyncio.Future()
        reference = mock.Mock(name="reference")
        chosen_task = mock.Mock(name="chosen_task")
        photons_app = mock.Mock(name="photons_app", chosen_task=chosen_task, final_future=final, reference=reference)

        def tr(*args, **kwargs):
            final.set_result(True)
        task_runner = asynctest.mock.CoroutineMock(name="task_runner", side_effect=tr)

        configuration = {"photons_app": photons_app, "task_runner": task_runner}
        collector = mock.Mock(name="collector", configuration=configuration)

        t = self.loop.create_task(runner(collector))
        await self.wait_for(t)

        assert final.done()
        task_runner.assert_called_once_with(chosen_task, reference)
