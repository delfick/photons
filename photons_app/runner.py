from photons_app.errors import ApplicationCancelled

from functools import partial
import platform
import asyncio
import logging
import signal

log = logging.getLogger("photons_app.runner")

def on_done_task(final_future, res):
    if final_future.done():
        return

    if res.cancelled():
        final_future.cancel()
        return

    exc = res.exception()
    if exc:
        final_future.set_exception(exc)
        return

    res.result()
    final_future.set_result(None)

def run(collector):
    """
    Get the loop, then use runner with cleanup in a finally block
    """
    photons_app = collector.configuration["photons_app"]
    task_runner = collector.configuration["task_runner"]
    target_register = collector.configuration["target_register"]

    loop = photons_app.loop
    task = photons_app.chosen_task
    reference = photons_app.reference
    final_future = photons_app.final_future

    if platform.system() != "Windows":
        def stop_final_fut():
            final_future.cancel()
        loop.add_signal_handler(signal.SIGTERM, stop_final_fut)

    task = loop.create_task(task_runner(task, reference))
    task.add_done_callback(partial(on_done_task, final_future))

    async def wait():
        await final_future
    waiter = loop.create_task(wait())

    try:
        loop.run_until_complete(waiter)
    except asyncio.CancelledError:
        raise ApplicationCancelled()
    finally:
        log.debug("CLEANING UP")

        final_future.cancel()

        try:
            targets = target_register.used_targets
            loop.run_until_complete(photons_app.cleanup(targets))
            cancel_all_tasks(loop, task, waiter)
        finally:
            loop.close()
            del photons_app.loop
            del photons_app.final_future

def cancel_all_tasks(loop, *ignore_errors):
    if hasattr(asyncio.tasks, "all_tasks"):
        to_cancel = asyncio.tasks.all_tasks(loop)
    else:
        to_cancel = asyncio.Task.all_tasks(loop)

    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    gathered = asyncio.tasks.gather(*to_cancel, loop=loop, return_exceptions=True)
    loop.run_until_complete(gathered)

    for task in to_cancel:
        if task.cancelled():
            continue

        if task not in ignore_errors and task.exception() is not None:
            loop.call_exception_handler(
                  { 'message': 'unhandled exception during shutdown'
                  , 'exception': task.exception()
                  , 'task': task
                  }
                )
