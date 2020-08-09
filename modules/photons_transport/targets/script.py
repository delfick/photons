from photons_app.errors import RunErrors, BadRunWithResults

from photons_app import helpers as hp

from delfick_project.norms import sb
import traceback
import asyncio
import sys


class SenderWrapper:
    def __init__(self, target, sender, kwargs=None):
        self.kwargs = kwargs
        self.target = target
        self.sender = sender
        self.owns_sender = self.sender is sb.NotSpecified

    async def __aenter__(self):
        if self.owns_sender:
            self.sender = await self.target.make_sender()

        if self.kwargs is not None:
            if "limit" not in self.kwargs:
                self.kwargs["limit"] = 30

            if self.kwargs["limit"] is not None and not hasattr(self.kwargs["limit"], "acquire"):
                self.kwargs["limit"] = asyncio.Semaphore(self.kwargs["limit"])

        return self.sender

    async def __aexit__(self, exc_type, exc, tb):
        if self.owns_sender:
            await self.target.close_sender(self.sender)


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

        async with SenderWrapper(self.target, sender, kwargs) as sender:
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
