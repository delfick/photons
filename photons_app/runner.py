from photons_app.errors import ApplicationCancelled
from photons_app import helpers as hp

import platform
import asyncio
import logging
import signal

log = logging.getLogger("photons_app.runner")

async def runner(collector):
    """
    Create a coroutine for our task using the task_runner in collector

    Then wait for final_future to be finished.

    We also finish the final future ourselves when the task is complete or if we get a SIGTERM
    """
    loop = asyncio.get_event_loop()
    photons_app = collector.configuration["photons_app"]

    if platform.system() != "Windows":
        def stop_final_fut():
            photons_app.final_future.cancel()
        loop.add_signal_handler(signal.SIGTERM, stop_final_fut)

    def reporter(res):
        if photons_app.final_future.done():
            return

        if res.cancelled():
            photons_app.final_future.cancel()
            return

        exc = res.exception()
        if exc:
            photons_app.final_future.set_exception(exc)
            return

        res.result()
        photons_app.final_future.set_result(None)

    task = collector.configuration["photons_app"].chosen_task
    reference = collector.configuration["photons_app"].reference
    task_runner = collector.configuration["task_runner"]

    t = loop.create_task(task_runner(task, reference))
    t.add_done_callback(reporter)
    await photons_app.final_future

def run(collector):
    """
    Get the loop, then use runner with cleanup in a finally block
    """
    loop = collector.configuration["photons_app"].loop

    task = loop.create_task(runner(collector))
    task.add_done_callback(hp.silent_reporter)

    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        raise ApplicationCancelled()
    finally:
        log.debug("CLEANING UP")
        targets = collector.configuration["target_register"].target_values
        loop.run_until_complete(collector.configuration["photons_app"].cleanup(targets))
