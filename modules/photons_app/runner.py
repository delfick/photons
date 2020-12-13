from photons_app.errors import ApplicationCancelled, ApplicationStopped
from photons_app.errors import UserQuit
from photons_app import helpers as hp

import platform
import asyncio
import logging
import signal
import sys

log = logging.getLogger("photons_app.runner")


def transfer_result(complete, pending):
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


def run(coro, photons_app, target_register):
    """
    Get the loop, then use runner with cleanup in a finally block
    """
    loop = photons_app.loop
    final_future = photons_app.final_future
    graceful_future = photons_app.graceful_final_future

    final_future.add_done_callback(hp.silent_reporter)
    graceful_future.add_done_callback(hp.silent_reporter)

    if platform.system() != "Windows":

        def stop_final_fut():
            if not final_future.done():
                final_future.set_exception(ApplicationStopped())

        loop.add_signal_handler(signal.SIGTERM, stop_final_fut)

    task = loop.create_task(coro)
    task.add_done_callback(hp.silent_reporter)

    async def wait():
        await hp.wait_for_first_future(
            final_future, graceful_future, task, name="||run>wait[wait_for_program_exit]"
        )

        if task.done():
            await task
        elif graceful_future.done():
            await graceful_future
        else:
            await final_future

    waiter = loop.create_task(wait())
    waiter.add_done_callback(hp.silent_reporter)

    try:
        loop.run_until_complete(waiter)
    except KeyboardInterrupt:
        significant_future = final_future
        if graceful_future.setup:
            significant_future = graceful_future

        if not significant_future.done():
            significant_future.set_exception(UserQuit())

        raise
    except asyncio.CancelledError:
        raise ApplicationCancelled()
    finally:
        log.debug("CLEANING UP")

        try:
            targets = target_register.used_targets

            # Make sure the main task is complete before we do cleanup activities
            # This is so anything that still needs to run doesn't stop because of
            # resources being stopped beneath it
            log.debug("Waiting for main task to finish")
            if not graceful_future.setup:
                task.cancel()

            try:
                loop.run_until_complete(
                    asyncio.tasks.gather(task, loop=loop, return_exceptions=True)
                )
            except KeyboardInterrupt:
                pass

            waiter.cancel()
            log.debug("Waiting for waiter task to finish")
            loop.run_until_complete(asyncio.tasks.gather(waiter, loop=loop, return_exceptions=True))

            # Perform cleanup duties so that resources are stopped appropriately
            log.debug("Running cleaners")
            loop.run_until_complete(photons_app.cleanup(targets))

            # Now make sure final_future is done
            task.cancel()
            graceful_future.cancel()
            transfer_result(None if not task.done() else task, final_future)
            transfer_result(graceful_future, final_future)

            # Cancel everything left
            # And ensure any remaining async generators are shutdown
            log.debug("Cancelling tasks and async generators")
            cancel_all_tasks(loop)
            loop.run_until_complete(shutdown_asyncgens(loop))
        finally:
            loop.close()
            del photons_app.loop
            del photons_app.final_future
            del photons_app.graceful_final_future


async def shutdown_asyncgens(loop):
    """Shutdown all active asynchronous generators."""
    if not len(loop._asyncgens):
        return

    closing_agens = list(loop._asyncgens)
    loop._asyncgens.clear()

    # I would do an asyncio.tasks.gather but it would appear that just causes
    # the asyncio loop to think it's shutdown, so I have to do them one at a time
    for ag in closing_agens:
        try:
            await hp.stop_async_generator(ag, name="||shutdown_asyncgens[wait_for_closing_agens]")
        except asyncio.CancelledError:
            pass
        except:
            exc = sys.exc_info()[1]
            loop.call_exception_handler(
                {
                    "message": "an error occurred during closing of asynchronous generator",
                    "exception": exc,
                    "asyncgen": ag,
                }
            )


def cancel_all_tasks(loop):
    if hasattr(asyncio.tasks, "all_tasks"):
        to_cancel = asyncio.tasks.all_tasks(loop)
    else:
        to_cancel = asyncio.Task.all_tasks(loop)

    to_cancel = [t for t in to_cancel if not t.done()]

    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    gathered = asyncio.tasks.gather(*to_cancel, loop=loop, return_exceptions=True)
    loop.run_until_complete(gathered)

    for task in to_cancel:
        if task.cancelled():
            continue

        if task.exception() is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during shutdown",
                    "exception": task.exception(),
                    "task": task,
                }
            )
