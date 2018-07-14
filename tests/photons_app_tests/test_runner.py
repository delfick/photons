# coding: spec

from photons_app.test_helpers import TestCase, AsyncTestCase
from photons_app.runner import run, runner, stop_everything

import asynctest
import platform
import asyncio
import signal
import mock
import nose
import os

describe TestCase, "run":
    it "runs the collector and runs stop_everything when that's done":
        called = []

        loop = asyncio.new_event_loop()

        uvloop = mock.Mock(name="uvloop")
        uvloop.create_task.side_effect = loop.create_task
        uvloop.run_until_complete.side_effect = loop.run_until_complete

        photons_app = mock.Mock(name="photons_app", uvloop=uvloop)
        configuration = {"photons_app": photons_app}
        collector = mock.Mock(name="collector", configuration=configuration)

        async def runner(c):
            self.assertIs(c, collector)
            called.append(1)

        def stop_everything(l, c):
            self.assertIs(l, uvloop)
            self.assertIs(c, collector)
            called.append(2)

        with mock.patch("photons_app.runner.runner", runner):
            with mock.patch("photons_app.runner.stop_everything", stop_everything):
                run(collector)

        self.assertEqual(called, [1, 2])

        uvloop.run_until_complete.assert_called_once_with(mock.ANY)

    it "calls stop_everything even if runner raise an exception":
        called = []

        loop = asyncio.new_event_loop()
        uvloop = mock.Mock(name="uvloop")
        uvloop.create_task.side_effect = loop.create_task
        uvloop.run_until_complete.side_effect = loop.run_until_complete

        photons_app = mock.Mock(name="photons_app", uvloop=uvloop)
        configuration = {"photons_app": photons_app}
        collector = mock.Mock(name="collector", configuration=configuration)

        async def runner(c):
            self.assertIs(c, collector)
            called.append(1)
            raise Exception("wat")

        def stop_everything(l, c):
            self.assertIs(l, uvloop)
            self.assertIs(c, collector)
            called.append(2)

        with self.fuzzyAssertRaisesError(Exception, "wat"):
            with mock.patch("photons_app.runner.runner", runner):
                with mock.patch("photons_app.runner.stop_everything", stop_everything):
                    run(collector)

        self.assertEqual(called, [1, 2])

        uvloop.run_until_complete.assert_called_once_with(mock.ANY)

describe AsyncTestCase, "runner":
    async it "cancels final_future if it gets a SIGTERM":
        if platform.system() == "Windows":
            raise nose.SkipTest()

        final = asyncio.Future()
        reference = mock.Mock(name="reference")
        chosen_task = mock.Mock(name="chosen_task")
        photons_app = mock.Mock(name="photons_app", chosen_task=chosen_task, final_future=final, reference=reference)
        task_runner = mock.Mock(name="task_runner")
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

describe TestCase, "stop_everything":
    it "calls cleanup on the photons_app and closes the loop":
        called = []
        t1 = mock.Mock(name="target1")
        t2 = mock.Mock(name="target2")
        target_register = mock.Mock(name="target_register", target_values=[t1, t2])

        loop = asyncio.new_event_loop()

        def cleanup(ts):
            self.assertEqual(ts, [t1, t2])
            called.append(1)

        cleanup = asynctest.mock.CoroutineMock(name="cleanup", side_effect=cleanup)
        photons_app = mock.Mock(name="photons_app", cleanup=cleanup)
        configuration = {"photons_app": photons_app, "target_register": target_register}
        collector = mock.Mock(name="collector", configuration=configuration)

        stop_everything(loop, collector)

        self.assertEqual(called, [1])
        cleanup.assert_called_once_with([t1, t2])

        assert loop.is_closed()
