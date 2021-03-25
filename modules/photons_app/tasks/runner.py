from photons_app.errors import ApplicationCancelled, ApplicationStopped
from photons_app.errors import UserQuit
from photons_app import helpers as hp

import platform
import asyncio
import logging
import signal
import sys

log = logging.getLogger("photons_app.tasks.runner")


class Runner:
    def __init__(self, task, kwargs):
        self.task = task
        self.kwargs = kwargs

    def run_loop(self):
        photons_app = self.task.photons_app
        target_register = self.task.collector.configuration["target_register"]
        self.Run(self.task.run(**self.kwargs), photons_app, target_register).run()

    class Run:
        def __init__(self, coro, photons_app, target_register):
            self.coro = coro
            self.photons_app = photons_app
            self.target_register = target_register

            self.loop = self.photons_app.loop

        @property
        def significant_future(self):
            graceful_future = self.photons_app.graceful_final_future
            if graceful_future.setup:
                return graceful_future
            return self.photons_app.final_future

        def run(self):
            self.photons_app.final_future.add_done_callback(hp.silent_reporter)
            self.significant_future.add_done_callback(hp.silent_reporter)
            self.register_sigterm_handler(self.significant_future)

            task, waiter = self.make_waiter()

            try:
                self.loop.run_until_complete(waiter)
            except KeyboardInterrupt as error:
                self.got_keyboard_interrupt(error)
                raise
            except asyncio.CancelledError as error:
                self.got_cancelled(error)
                raise
            finally:
                log.debug("CLEANING UP")

                try:
                    self.final(task, waiter)
                finally:
                    self.final_close()

        def register_sigterm_handler(self, final_future):
            if platform.system() != "Windows":

                def stop_final_fut():
                    if not final_future.done():
                        final_future.set_exception(ApplicationStopped())

                self.loop.add_signal_handler(signal.SIGTERM, stop_final_fut)

        def make_waiter(self):
            task = self.loop.create_task(self.coro)
            task.add_done_callback(hp.silent_reporter)

            async def wait():
                wait = [self.photons_app.final_future, self.significant_future, task]
                await hp.wait_for_first_future(*wait, name="||run>wait[wait_for_program_exit]")

                if task.done():
                    await task

                if self.photons_app.final_future.done():
                    await self.photons_app.final_future

                if self.significant_future is self.photons_app.graceful_final_future:
                    if (
                        self.photons_app.graceful_final_future.setup
                        and self.significant_future.done()
                    ):
                        if self.significant_future.cancelled():
                            return

                        exc = self.significant_future.exception()
                        if isinstance(exc, ApplicationStopped):
                            return

                if self.significant_future.done():
                    await self.significant_future

            waiter = self.loop.create_task(wait())
            waiter.add_done_callback(hp.silent_reporter)

            return task, waiter

        def got_keyboard_interrupt(self, error):
            error = UserQuit()

            if not self.significant_future.done():
                try:
                    self.significant_future.set_exception(error)
                except RuntimeError:
                    pass

            raise error

        def got_cancelled(self, error):
            error = ApplicationCancelled()

            if not self.significant_future.done():
                try:
                    self.significant_future.set_exception(error)
                except RuntimeError:
                    pass

            raise error

        def transfer_result(self, complete, pending):
            if not complete.done():
                return

            if complete is None or complete.cancelled():
                if not pending.done():
                    pending.cancel()
                return

            exc = complete.exception()
            if exc:
                if not pending.done():
                    pending.set_exception(exc)
                return

            complete.result()

            if not pending.done():
                pending.set_result(None)

        def final(self, task, waiter):
            self.wait_for_main_task(task)
            self.wait_for_waiter(waiter)
            self.run_cleanup()
            self.ensure_finished_futures(task, waiter)
            self.ensure_all_tasks_cancelled()

        def wait_for_main_task(self, task):
            log.debug("Waiting for main task to finish")

            # If we're not using the graceful future then we assume the task won't stop by itself
            # The graceful future is about saying the task will stop by itself when you resolve graceful
            if not self.photons_app.graceful_final_future.setup:
                task.cancel()

            try:
                self.loop.run_until_complete(
                    asyncio.tasks.gather(task, loop=self.loop, return_exceptions=True)
                )
            except KeyboardInterrupt:
                pass
            except:
                pass
            finally:
                task.cancel()

        def wait_for_waiter(self, waiter):
            log.debug("Waiting for waiter task to finish")
            waiter.cancel()
            try:
                self.loop.run_until_complete(
                    asyncio.tasks.gather(waiter, loop=self.loop, return_exceptions=True)
                )
            except:
                pass

        def run_cleanup(self):
            log.debug("Running cleaners")
            targets = self.target_register.used_targets
            self.loop.run_until_complete(self.photons_app.cleanup(targets))

        def ensure_finished_futures(self, task, waiter):
            self.transfer_result(None if not task.done() else task, self.photons_app.final_future)

            if not self.significant_future.done():
                self.significant_future.cancel()
            self.transfer_result(self.significant_future, self.photons_app.final_future)

        def ensure_all_tasks_cancelled(self):
            log.debug("Cancelling tasks and async generators")
            self.cancel_all_tasks()
            self.loop.run_until_complete(self.shutdown_asyncgens())

        def final_close(self):
            self.loop.close()
            del self.photons_app.loop
            del self.photons_app.final_future

        def cancel_all_tasks(self):
            if hasattr(asyncio.tasks, "all_tasks"):
                to_cancel = asyncio.tasks.all_tasks(self.loop)
            else:
                to_cancel = asyncio.Task.all_tasks(self.loop)

            to_cancel = [t for t in to_cancel if not t.done()]

            if not to_cancel:
                return

            for task in to_cancel:
                task.cancel()

            gathered = asyncio.tasks.gather(*to_cancel, loop=self.loop, return_exceptions=True)
            self.loop.run_until_complete(gathered)

            for task in to_cancel:
                if task.cancelled():
                    continue

                if task.exception() is not None:
                    self.loop.call_exception_handler(
                        {
                            "message": "unhandled exception during shutdown",
                            "exception": task.exception(),
                            "task": task,
                        }
                    )

        async def shutdown_asyncgens(self):
            if not len(self.loop._asyncgens):
                return

            closing_agens = list(self.loop._asyncgens)
            self.loop._asyncgens.clear()

            # I would do an asyncio.tasks.gather but it would appear that just causes
            # the asyncio loop to think it's shutdown, so I have to do them one at a time
            for ag in closing_agens:
                try:
                    await hp.stop_async_generator(
                        ag, name="||shutdown_asyncgens[wait_for_closing_agens]"
                    )
                except asyncio.CancelledError:
                    pass
                except:
                    exc = sys.exc_info()[1]
                    self.loop.call_exception_handler(
                        {
                            "message": "an error occurred during closing of asynchronous generator",
                            "exception": exc,
                            "asyncgen": ag,
                        }
                    )
