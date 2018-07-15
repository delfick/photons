from photons_app import helpers as hp

import platform
import asyncio
import logging
import signal

log = logging.getLogger("photons_app.runner")

def stop_everything(loop, collector):
    """
    Call our cleanup functions and .finish on all our targets

    Then keep running the loop until everything is closed

    And then close the loop itself
    """
    # Ensure the loop is stopped so we can run run_until_complete below
    loop.stop()

    log.debug("CLEANING UP")
    try:
        targets = collector.configuration["target_register"].target_values
        loop.run_until_complete(collector.configuration["photons_app"].cleanup(targets))
    except RuntimeError:
        pass

    previous_num = None
    while True:
        num_left = len([t for t in asyncio.Task.all_tasks() if t._state not in ("CANCELLED", "FINISHED")])
        if previous_num == num_left:
            for task in asyncio.Task.all_tasks():
                task.cancel()
        previous_num = num_left

        if num_left > 0:
            log.debug("RUN LOOP AGAIN %s LEFT", num_left)

            def stopper():
                loop.stop()
            loop.call_later(0.1, stopper)
            loop.run_forever()
        else:
            break

    log.debug("EVERYTHING SHOULD BE STOPPED")

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
    Get the loop, then use runner with stop_everything in a finally block
    """
    loop = collector.configuration["photons_app"].uvloop

    task = loop.create_task(runner(collector))
    task.add_done_callback(hp.silent_reporter)

    try:
        loop.run_until_complete(task)
    finally:
        stop_everything(loop, collector)
