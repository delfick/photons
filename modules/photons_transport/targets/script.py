from photons_app.errors import RunErrors, BadRunWithResults

from photons_app import helpers as hp

from delfick_project.norms import sb
import traceback
import asyncio
import sys


@hp.asynccontextmanager
async def sender_wrapper(target, sender=sb.NotSpecified, kwargs=None):
    owns_sender = sender is sb.NotSpecified

    try:
        if owns_sender:
            sender = await target.make_sender()

        if kwargs is not None:
            if "limit" not in kwargs:
                kwargs["limit"] = 30

            if kwargs["limit"] is not None and not hasattr(kwargs["limit"], "acquire"):
                kwargs["limit"] = asyncio.Semaphore(kwargs["limit"])

        yield sender
    finally:
        if owns_sender:
            await target.close_sender(sender)


class ScriptRunner:
    """
    Create an runner for our script.

    The ``script`` is an object with a ``run`` method on it.

    This helper will create the ``sender`` if none is passed in and clean it up if
    we created it.
    """

    def __init__(self, script, target):
        self.script = script
        self.target = target

    async def run_all(self, *args, **kwargs):
        """Do a run but don't complete till all messages have completed"""
        results = []
        try:
            async for info in self.run(*args, **kwargs):
                results.append(info)
        except asyncio.CancelledError:
            raise
        except RunErrors as error:
            raise BadRunWithResults(results=results, _errors=error.errors)
        except Exception as error:
            raise BadRunWithResults(results=results, _errors=[error])
        else:
            return results

    # backwards compatibility
    run_with_all = run_all

    async def run(self, reference, sender=sb.NotSpecified, **kwargs):
        if self.script is None:
            return

        async with sender_wrapper(self.target, sender, kwargs) as sender:
            gen = self.script.run(reference, sender, **kwargs)

            try:
                async for nxt in gen:
                    yield nxt
            finally:
                exc = sys.exc_info()[1]
                if exc:
                    traceback.clear_frames(exc.__traceback__)
                await hp.stop_async_generator(gen, exc=exc)

    # backwards compatibility
    run_with = run
