from photons_app.special import SpecialReference, HardCodedSerials, FoundSerials
from photons_app.errors import RunErrors
from photons_app import helpers as hp

from photons_transport.errors import FailedToFindDevice

from input_algorithms import spec_base as sb
import asyncio
import logging
import time

log = logging.getLogger("photons_control.script")

async def find_serials(reference, args_for_run, timeout):
    """
    Return (serials, missing) for all the serials that can be found in the
    provided reference

    If the reference is an empty string, a single underscore or None then we
    find all devices on the network

    if it is a string or a list of strings, we treat those strings as the serials
    to find.

    Otherwise we assume it's a special reference
    """
    if not isinstance(reference, SpecialReference):
        if reference in ("", "_", None, sb.NotSpecified):
            reference = FoundSerials()
        else:
            if isinstance(reference, str):
                reference = reference.split(",")
            reference = HardCodedSerials(reference)

    found, serials = await reference.find(args_for_run, timeout=timeout)
    missing = reference.missing(found)
    return serials, missing

def Pipeline(*children, spread=0, short_circuit_on_error=False, synchronized=False):
    """
    This allows you to send messages in order, so that each message isn't sent
    until the previous message gets a reply or times out.

    For example:

    .. code-block:: python

        msg1 = MessageOne()
        msg2 = MessageTwo()

        reference1 = "d073d500000"
        reference2 = "d073d500001"

        async with target.session() as afr:
            async for result in target.script(Pipeline(msg1, msg2)).run_with([reference1, reference2], afr):
                ....

    Is equivalent to:

    .. code-block:: python

        async with target.session() as afr:
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
    async def gen(reference, args_for_run, **kwargs):
        for i, child in enumerate(children):
            if i > 0:
                await asyncio.sleep(spread)

            t = yield child
            success = await t
            if not success and short_circuit_on_error:
                break

    if synchronized:
        m = FromGenerator(gen, reference_override=True)
    else:
        m = FromGeneratorPerSerial(gen)

    m.pipeline_children = children
    m.pipeline_spread = spread
    m.pipeline_short_circuit_on_error = short_circuit_on_error

    return m

def Repeater(msg, min_loop_time=30, on_done_loop=None):
    """
    This will send the provided msg in an infinite loop

    For example:

    .. code-block:: python

        msg1 = MessageOne()
        msg2 = MessageTwo()

        reference = ["d073d500000", "d073d500001"]

        def error_catcher(e):
            print(e)

        async with target.session() as afr:
            pipeline = Pipeline(msg1, msg2, spread=1)
            repeater = Repeater(pipeline, min_loop_time=20)
            async for result in target.script(repeater).run_with(reference, afr, error_catcher=error_catcher):
                ....

    Is equivalent to:

    .. code-block:: python

        async with target.session() as afr:
            while True:
                start = time.time()
                async for result in target.script(pipeline).run_with(reference, afr):
                    ...
                await asyncio.sleep(20 - (time.time() - start))

    Note that if references is a photons_app.special.SpecialReference then we
    call reset on it after every loop.

    Also it is highly recommended that error_catcher is a callable that takes
    each error as they happen.

    Repeater takes in the following keyword arguments:

    min_loop_time
        The minimum amount of time a loop should take, in seconds.

        So if min_loop_time is 30 and the loop takes 10 seconds, then we'll wait
        20 seconds before going again

    on_done_loop
        An async callable that is called with no arguments when a loop completes
        (before any sleep from min_loop_time)

        Note that if you raise ``Repeater.Stop()`` in this function then the
        Repeater will stop.
    """
    async def gen(reference, args_for_run, **kwargs):
        while True:
            start = time.time()
            f = yield msg
            await f

            if isinstance(reference, SpecialReference):
                reference.reset()

            if callable(on_done_loop):
                try:
                    await on_done_loop()
                except Repeater.Stop:
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    hp.add_error(kwargs["error_catcher"], error)

            took = time.time() - start
            diff = min_loop_time - took
            if diff > 0:
                await asyncio.sleep(diff)

    m = FromGenerator(gen, reference_override=True)
    m.repeater_msg = msg
    m.repeater_on_done_loop = on_done_loop
    m.repeater_min_loop_time = min_loop_time
    return m

class Stop(Exception):
    pass
Repeater.Stop = Stop

def FromGeneratorPerSerial(inner_gen):
    """
    Same as a FromGenerator except it will call your inner_gen per serial in
    the reference given to run_with.

    This handles resolving the reference into serials and complaining if a serial
    does not exist
    """
    async def gen(reference, args_for_run, **kwargs):
        serials, missing = await find_serials(reference, args_for_run, timeout=kwargs.get("find_timeout", 20))
        for serial in missing:
            yield FailedToFindDevice(serial=serial)

        yield [FromGenerator(inner_gen, reference_override=serial) for serial in serials]
    return FromGenerator(gen)

class FromGenerator(object):
    """
    FromGenerator let's you determine what messages to send in an async generator.

    For example:

    .. code-block:: python

        async def gen(reference, afr, **kwargs):
            get_power = DeviceMessages.GetPower()

            for pkt, _, _ in afr.transport_target.script(get_power).run_with(reference, afr, **kwargs):
                if pkt | DeviceMessages.StatePower:
                    if pkt.level == 0:
                        yield DeviceMessages.SetPower(level=65535, target=pkt.serial)
                    else:
                        yield DeviceMessages.SetPower(level=0, target=pkt.serial)

        msg = FromGenerator(gen)
        await target.script(msg).run_with_all("d073d5000001")

    Note that all messages you yield from the generator must already have target
    set on them.

    The generator function receives the reference supplied to the run_with as well
    as the afr object and any keyword arguments that were passed into run_with.

    All messages that are yielded from the generator are sent in parallel

    The return value from yield will be a future that resolves to True if the
    message(s) were sent without error, and False if they were sent with error.
    """
    def __init__(self, generator, *, reference_override=None):
        self.generator = generator
        self.reference_override = reference_override

    def simplified(self, simplifier, chain=None):
        return self.Item(simplifier, self.generator, self.Runner, self.reference_override)

    class Item:
        def __init__(self, simplifier, generator, runner_kls, reference_override):
            self.generator = generator
            self.runner_kls = runner_kls
            self.simplifier = simplifier
            self.reference_override = reference_override

        async def run_with(self, reference, args_for_run, **kwargs):
            do_raise = kwargs.get("error_catcher") is None
            error_catcher = [] if do_raise else kwargs["error_catcher"]
            kwargs["error_catcher"] = error_catcher

            runner = self.runner_kls(self, reference, args_for_run, kwargs)

            try:
                async for result in runner:
                    yield result
            finally:
                await runner.finish()

            if do_raise and error_catcher:
                raise RunErrors(_errors=list(set(error_catcher)))

    class Runner:
        class Done:
            pass

        def __init__(self, item, reference, args_for_run, kwargs):
            self.item = item
            self.kwargs = kwargs
            self.stop_fut = asyncio.Future()
            self.reference = reference
            self.args_for_run = args_for_run
            self.error_catcher = kwargs["error_catcher"]

            self.ts = []
            self.queue = asyncio.Queue()

        @property
        def generator_reference(self):
            if self.item.reference_override in (None, True):
                return self.reference
            return self.item.reference_override

        @property
        def run_with_reference(self):
            if self.item.reference_override is True:
                return self.reference
            elif self.item.reference_override is not None:
                return self.item.reference_override

        async def wait_for_ts(self):
            for t in self.ts:
                if not t.done():
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass
                    except Exception as error:
                        hp.add_error(self.error_catcher, error)

        async def finish(self):
            await self.wait_for_ts()

            self.stop_fut.cancel()

            try:
                await self.queue.put(self.Done)
            except:
                pass

            await self._stop_ts()

        def __aiter__(self):
            self.getter_t = hp.async_as_background(self.getter())

            def on_finish(res):
                hp.async_as_background(self.queue.put(self.Done))
            self.getter_t.add_done_callback(on_finish)

            return self

        async def __anext__(self):
            nxt = await self.queue.get()

            if nxt is self.Done or self.stop_fut.done():
                raise StopAsyncIteration

            return nxt

        async def _stop_ts(self):
            try:
                if hasattr(self, "getter_t"):
                    await self.getter_t
            except asyncio.CancelledError:
                pass
            except Exception as error:
                hp.add_error(self.error_catcher, error)
                return

        async def getter(self):
            gen = self.item.generator(self.generator_reference, self.args_for_run, **self.kwargs)
            complete = None

            while True:
                try:
                    msg = await gen.asend(complete)
                    if isinstance(msg, Exception):
                        hp.add_error(self.error_catcher, msg)
                        continue

                    if self.stop_fut.done():
                        break

                    complete = asyncio.Future()

                    f_for_items = []
                    for item in self.item.simplifier(msg):
                        f = asyncio.Future()
                        f_for_items.append(f)
                        t = hp.async_as_background(self.retrieve(item, f))
                        self.ts.append(t)

                    self.complete_on_all_done(f_for_items, complete)
                    self.ts = [t for t in self.ts if not t.done()]
                except StopAsyncIteration:
                    break

            await self.wait_for_ts()

        async def retrieve(self, item, f):
            i = {"success": True}

            def pass_on_error(e):
                i["success"] = False
                hp.add_error(self.error_catcher, e)

            kwargs = dict(self.kwargs)
            kwargs["error_catcher"] = pass_on_error

            try:
                async for info in item.run_with(self.run_with_reference, self.args_for_run, **kwargs):
                    await self.queue.put(info)
            finally:
                if not f.done():
                    f.set_result(i["success"])

        def complete_on_all_done(self, fs, complete):
            def finish(res):
                if complete.done():
                    return

                if res.cancelled():
                    complete.cancel()

                for f in fs:
                    if f.cancelled():
                        complete.cancel()
                        return

                    exc = f.exception()
                    if exc is not None:
                        complete.set_result(False)
                        return
                    elif f.result() is False:
                        complete.set_result(False)
                        return

                complete.set_result(True)
            waiter = hp.async_as_background(asyncio.wait(fs))
            waiter.add_done_callback(finish)
