from photons_app.errors import RunErrors, BadRunWithResults, PhotonsAppError

from input_algorithms import spec_base as sb
import asyncio

class InvalidScript(PhotonsAppError):
    desc = "Script is invalid"

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

        specified = True
        if args_for_run is sb.NotSpecified:
            specified = False
            args_for_run = await self.target.args_for_run()
        try:
            if "limit" not in kwargs:
                kwargs["limit"] = 30

            if kwargs["limit"] is not None and not hasattr(kwargs["limit"], "acquire"):
                kwargs["limit"] = asyncio.Semaphore(kwargs["limit"])

            async for thing in self.script.run_with(reference, args_for_run, **kwargs):
                yield thing
        finally:
            if not specified:
                await self.target.close_args_for_run(args_for_run)
