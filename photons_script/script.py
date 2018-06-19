from photons_app.errors import RunErrors, BadRunWithResults, PhotonsAppError
from photons_app.special import SpecialReference
from photons_app import helpers as hp

from input_algorithms.spec_base import NotSpecified
from collections import defaultdict
import asyncio
import logging
import time

log = logging.getLogger("photons_script")

def add_error(catcher, error):
    """
    Adds an error to an error_catcher.

    This means if it's callable, we call_soon on the loop with it

    and if it's a list or set we add the error to it.
    """
    if callable(catcher):
        loop = asyncio.get_event_loop()
        loop.call_soon(catcher, error)
    elif type(catcher) is list:
        catcher.append(error)
    elif type(catcher) is set:
        catcher.add(error)

class InvalidScript(PhotonsAppError):
    desc = "Script is invalid"

class ATarget(object):
    """
    Use and cleanup a target.

    .. code-block:: python

        async with ATarget(target) as afr:
            ...

    Is equivalent to:

    .. code-block:: python

        afr = await target.args_for_run()
        ...
        await target.close_args_for_run(afr)
    """
    def __init__(self, target, **kwargs):
        self.kwargs = kwargs
        self.target = target

    async def __aenter__(self):
        self.args_for_run = await self.target.args_for_run(**self.kwargs)
        return self.args_for_run

    async def __aexit__(self, *args):
        if hasattr(self, "args_for_run"):
            await self.target.close_args_for_run(self.args_for_run)

class ScriptRunner(object):
    """
    Create a runner for our script.

    The ``script`` is an object with a ``run_with`` method on it.

    This helper will create the ``afr`` if none is passed in and clean it up if
    we created it.
    """
    def __init__(self, script, target):
        self.script = script
        self.target = target

    async def run_with(self, reference, args_for_run=NotSpecified, **kwargs):
        specified = True
        if args_for_run is NotSpecified:
            specified = False
            args_for_run = await self.target.args_for_run()
        try:
            return await self.script.run_with(reference, args_for_run, **kwargs)
        finally:
            if not specified:
                await self.target.close_args_for_run(args_for_run)

class ScriptRunnerIterator(object):
    """
    Create an iterator runner for our script.

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

    async def run_with(self, reference, args_for_run=NotSpecified, **kwargs):
        specified = True
        if args_for_run is NotSpecified:
            specified = False
            args_for_run = await self.target.args_for_run()
        try:
            async for thing in self.script.run_with(reference, args_for_run, **kwargs):
                yield thing
        finally:
            if not specified:
                await self.target.close_args_for_run(args_for_run)

class Pipeline(object):
    """
    This Provides a ``run_with`` method that will send and wait for multiple
    messages to each ``reference``.

    For example:

    .. code-block:: python

        msg1 = MessageOne()
        msg2 = MessageTwo()

        reference1 = "d073d500000"
        reference2 = "d073d500001"

        async with ATarget(target) as afr:
            async for result in target.script(Pipeline(msg1, msg2)).run_with([reference1, reference2], afr):
                ....

    Is equivalent to:

    .. code-block:: python

        async with ATarget(target) as afr:
            async for result in target.script(msg1).run_with([reference1], afr):
                ...
            async for result in target.script(msg2).run_with([reference1], afr):
                ...
            async for result in target.script(msg1).run_with([reference2], afr):
                ...
            async for result in target.script(msg2).run_with([reference2], afr):
                ...

    This also takes in the following keyword arguments:

    spread
        Specify how much wait (in seconds) between each message per device

    short_circuit_on_error
        Stop trying to send messages to a device if we encounter an error.

        This will only effect sending messages to the device that had an error

    synchronized
        If this is set to False then each bulb gets it's own coroutine and so
        messages will go at different times depending on how slow/fast each bulb
        is.

        If this is set to True then we wait on the slowest bulb before going to
        the next message.
    """
    name = "Pipeline"
    has_children = True

    def __init__(self, *children, spread=0, short_circuit_on_error=False, synchronized=False):
        self.spread = spread
        self.children = children
        self.synchronized = synchronized
        self.short_circuit_on_error = short_circuit_on_error

    def simplified(self, simplifier, chain=None):
        chain = [] if chain is None else chain
        simple_children = []
        for child in self.children:
            simple_children.extend(simplifier(child, chain=chain))
        return Pipeline(*simple_children
            , spread = self.spread
            , synchronized = self.synchronized
            , short_circuit_on_error = self.short_circuit_on_error
            )

    async def run_children(self, queue, references, args_for_run, **kwargs):
        len_children = len(self.children)
        original_ec = kwargs["error_catcher"]

        data = {"found_error": False}

        def new_error_catcher(e):
            data["found_error"] = True
            add_error(original_ec, e)
        kwargs["error_catcher"] = new_error_catcher

        for i, child in enumerate(self.children):
            async for info in child.run_with(references, args_for_run, **kwargs):
                await queue.put(info)

            if self.short_circuit_on_error and data["found_error"]:
                break

            if self.spread and i < len_children - 1:
                await asyncio.sleep(self.spread)

    async def run_with(self, references, args_for_run, **kwargs):
        do_raise = kwargs.get("error_catcher") is None
        error_catcher = [] if do_raise else kwargs["error_catcher"]
        kwargs["error_catcher"] = error_catcher

        queue = asyncio.Queue()
        futs = []

        if isinstance(references, SpecialReference):
            try:
                _, references = await references.find(args_for_run, kwargs.get("broadcast", False), kwargs.get("find_timeout", 5))
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if do_raise:
                    raise
                add_error(error_catcher, error)
                return

        if type(references) is not list:
            references = [references]

        if not references:
            references = [[]]
        elif self.synchronized:
            references = [references]

        for reference in references:
            futs.append(hp.async_as_background(self.run_children(queue, reference, args_for_run, **kwargs), silent=True))

        class Done:
            pass

        async def wait_all():
            await asyncio.wait(futs, return_when=asyncio.ALL_COMPLETED)
            await queue.put(Done)
        waiter = hp.async_as_background(wait_all())

        try:
            while True:
                nxt = await queue.get()
                if nxt is Done:
                    break
                else:
                    yield nxt
        finally:
            waiter.cancel()
            for f in futs:
                f.cancel()

        if do_raise and error_catcher:
            raise RunErrors(_errors=list(set(error_catcher)))

class Decider(object):
    """
    This one is a complex beast used for determining what to do based on the
    response from a particular message.

    getter
        A list of messages that are sent to each ``reference``.

    decider
        A function that takes in ``(reference, received1, received2, ...)`` where
        each ``received`` is a reply from ``getter`` and yields messages to send
        to that reference.

    wanted
        A list of messages that we want to get back from the ``getter``. Any
        reply that doesn't match this message type is dropped before we call
        ``decider``

    .. automethod:: photons_script.script.Decider.run_with
    """
    name = "using"
    has_children = True

    def __init__(self, getter, decider, wanted, simplifier=None, get_timeout=1, send_timeout=1):
        self.decider = decider
        self.wanted = wanted
        self.getter = getter
        self.simplifier = simplifier
        self.get_timeout = get_timeout
        self.send_timeout = send_timeout

    def simplified(self, simplifier, chain=None):
        chain = [] if chain is None else chain
        return self.__class__(simplifier(self.getter, chain=chain)
            , self.decider, self.wanted
            , simplifier = simplifier
            , get_timeout = self.get_timeout
            , send_timeout = self.send_timeout
            )

    async def run_with(self, references, args_for_run, **kwargs):
        """
        For each msg in ``getter``, run it against all the references and
        collect all the reply packets per reference for all the packets that
        match the ``wanted`` message types.

        For each reference that has results from ``getter``, call ``decider`` with
        the reference and the replies from ``getter``. This function yields
        messages which we simplify and send.

        .. note:: The messages from decider must already have a target set on them

        Any errors are collected and if they have a serial, will be returned
        with the results.

        We raise the errors we find that don't have an associated serial.
        """
        do_raise = kwargs.get("error_catcher") is None
        error_catcher = [] if do_raise else kwargs["error_catcher"]

        got = await self.do_getters(references, args_for_run, kwargs, error_catcher)
        if type(references) not in (str, list):
            references = got.keys()

        if type(references) is str:
            references = [references]

        msgs = list(self.transform_got(got, references))

        async for info in self.send_msgs(msgs, args_for_run, kwargs, error_catcher):
            yield info

        if do_raise and error_catcher:
            raise RunErrors(_errors=list(set(error_catcher)))

    async def do_getters(self, references, args_for_run, kwargs, error_catcher):
        results = defaultdict(list)

        kw = {"find_timeout": self.get_timeout, "timeout": self.get_timeout, "error_catcher": error_catcher}
        kw.update(kwargs)

        for g in self.getter:
            async for pkt, _, _ in g.run_with(references, args_for_run, **kw):
                if self.wanted and not any(pkt | w for w in self.wanted):
                    continue
                results[pkt.serial].append(pkt)

        return results

    def transform_got(self, got, references):
        for reference in references:
            if reference in got:
                for msg in self.decider(reference, *got[reference]):
                    yield msg
            else:
                log.warning("Didn't find reference from getter %s\tavailable=%s", reference, list(got.keys()))

    async def send_msgs(self, msgs, args_for_run, kwargs, error_catcher):
        kw = {"timeout": self.send_timeout, "error_catcher": error_catcher, "accept_found": True}
        kw.update(kwargs)

        for g in self.simplifier(msgs):
            async for info in g.run_with([], args_for_run, **kw):
                yield info

class Repeater(object):
    """
    This Provides a ``run_with`` method that will repeat it's messages forever

    For example:

    .. code-block:: python

        msg1 = MessageOne()
        msg2 = MessageTwo()

        reference1 = "d073d500000"
        reference2 = "d073d500001"

        def error_catcher(e):
            print(e)

        async with ATarget(target) as afr:
            pipeline = Pipeline(msg1, msg2, spread=1)
            async for result in target.script(Repeater(pipeline, min_loop_time=20).run_with([reference1, reference2], afr, error_catcher=error_catcher):
                ....

    Is equivalent to:

    .. code-block:: python

        async with ATarget(target) as afr:
            while True:
                async for result in target.script(pipeline).run_with([reference1], afr):
                    ...
                await asyncio.sleep(20)

    Note that if references is a photons_app.special.SpecialReference then we call reset on it after every loop.

    Also error_catcher *must* be specified and be a callable that takes each error as they happen.

    Repeater takes in the following keyword arguments:

    min_loop_time
        The minimum amount of time a loop should take, in seconds.

        So if min_loop_time is 30 and the loop takes 10 seconds, then we'll wait 20 seconds before going again

    on_done_loop
        An async callable that is called with no arguments when a loop completes (before any sleep from min_loop_time)

        Note that if you raise ``Repeater.Stop()`` in this function then the Repeater will stop.
    """
    name = "Repeater"
    has_children = True

    class Stop(Exception):
        pass

    def __init__(self, msg, min_loop_time=30, on_done_loop=None):
        self.msg = msg
        self.on_done_loop = on_done_loop
        self.min_loop_time = min_loop_time

    def simplified(self, simplifier, chain=None):
        chain = [] if chain is None else chain
        simple_msg = list(simplifier(self.msg, chain=chain))
        return Repeater(simple_msg, min_loop_time=self.min_loop_time, on_done_loop=self.on_done_loop)

    async def run_with(self, references, args_for_run, **kwargs):
        error_catcher = kwargs.get("error_catcher")
        if not callable(error_catcher):
            raise PhotonsAppError("error_catcher must be specified as a callable when Repeater is used")

        while True:
            start = time.time()

            for m in self.msg:
                async for info in m.run_with(references, args_for_run, **kwargs):
                    yield info

            if isinstance(references, SpecialReference):
                references.reset()

            if callable(self.on_done_loop):
                try:
                    await self.on_done_loop()
                except Repeater.Stop:
                    break

            took = time.time() - start
            diff = self.min_loop_time - took
            if diff > 0:
                await asyncio.sleep(diff)
