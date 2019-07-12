from photons_app.errors import RunErrors, BadRunWithResults

from input_algorithms import spec_base as sb
import asyncio

class AFRWrapper:
    def __init__(self, target, args_for_run, kwargs=None):
        self.kwargs = kwargs
        self.target = target
        self.args_for_run = args_for_run
        self.owns_afr = self.args_for_run is sb.NotSpecified

    async def __aenter__(self):
        if self.owns_afr:
            self.args_for_run = await self.target.args_for_run()

        if self.kwargs is not None:
            if "limit" not in self.kwargs:
                self.kwargs["limit"] = 30

            if self.kwargs["limit"] is not None and not hasattr(self.kwargs["limit"], "acquire"):
                self.kwargs["limit"] = asyncio.Semaphore(self.kwargs["limit"])

        return self.args_for_run

    async def __aexit__(self, exc_type, exc, tb):
        if self.owns_afr:
            await self.target.close_args_for_run(self.args_for_run)

class ScriptRunner:
    """
    Create an runner for our script.

    The ``script`` is an object with a ``run_with`` method on it.

    This helper will create the ``afr`` if none is passed in and clean it up if
    we created it.
    """
    def __init__(self, script, target):
        self.script = script
        self.target = target

    async def run_with_all(self, *args, **kwargs):
        """Do a run_with but don't complete till all messages have completed"""
        results = []
        try:
            async for info in self.run_with(*args, **kwargs):
                results.append(info)
        except RunErrors as error:
            raise BadRunWithResults(results=results, _errors=error.errors)
        except Exception as error:
            raise BadRunWithResults(results=results, _errors=[error])
        else:
            return results

    async def run_with(self, reference, args_for_run=sb.NotSpecified, **kwargs):
        if self.script is None:
            return

        async with AFRWrapper(self.target, args_for_run, kwargs) as afr:
            async for thing in self.script.run_with(reference, afr, **kwargs):
                yield thing
