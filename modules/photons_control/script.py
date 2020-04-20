from photons_app.special import SpecialReference, HardCodedSerials, FoundSerials
from photons_app.errors import RunErrors
from photons_app import helpers as hp

from photons_transport.errors import FailedToFindDevice

from delfick_project.norms import sb
import asyncio
import logging
import time

log = logging.getLogger("photons_control.script")


async def find_serials(reference, sender, timeout):
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

    found, serials = await reference.find(sender, timeout=timeout)
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

        async with target.session() as sender:
            async for result in sender(Pipeline(msg1, msg2), [reference1, reference2]):
                ....

    Is equivalent to:

    .. code-block:: python

        async with target.session() as sender:
            async for result in sender(msg1, [reference1]):
                ...
            async for result in sender(msg2, [reference1]):
                ...
            async for result in sender(msg1, [reference2]):
                ...
            async for result in sender(msg2, [reference2]):
                ...

    This also takes in the following keyword arguments:

    spread
        Specify how much wait (in seconds) between each message per device

    short_circuit_on_error
        Stop trying to send messages to a device if we encounter an error.

        This will only effect sending messages to the device that had an error

    synchronized
        If this is set to ``False`` then each bulb gets it's own coroutine and
        so messages will go at different times depending on how slow/fast each
        bulb is.

        If this is set to ``True`` then we wait on the slowest bulb before going
        to the next message.
    """

    async def gen(reference, sender, **kwargs):
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

        async with target.session() as sender:
            pipeline = Pipeline(msg1, msg2, spread=1)
            repeater = Repeater(pipeline, min_loop_time=20)
            async for result in sender(repeater, reference, error_catcher=error_catcher):
                ....

    Is equivalent to:

    .. code-block:: python

        async with target.session() as sender:
            while True:
                start = time.time()
                async for result in sender(pipeline, reference):
                    ...
                await asyncio.sleep(20 - (time.time() - start))

    Note that if references is a
    :ref:`SpecialReference <special_reference_objects>` then we call reset on
    it after every loop.

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

    async def gen(reference, sender, **kwargs):
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


def FromGeneratorPerSerial(inner_gen, **generator_kwargs):
    """
    Same as a FromGenerator except it will call your inner_gen per serial in
    the reference given to the send api.

    This handles resolving the reference into serials and complaining if a serial
    does not exist
    """

    async def gen(reference, sender, **kwargs):
        serials, missing = await find_serials(
            reference, sender, timeout=kwargs.get("find_timeout", 20)
        )
        for serial in missing:
            yield FailedToFindDevice(serial=serial)

        yield [
            FromGenerator(inner_gen, reference_override=serial, **generator_kwargs)
            for serial in serials
        ]

    return FromGenerator(gen)


class FromGenerator(object):
    """
    FromGenerator let's you determine what messages to send in an async generator.

    For example:

    .. code-block:: python

        async def gen(reference, sender, **kwargs):
            get_power = DeviceMessages.GetPower()

            for pkt in sender(get_power, reference, **kwargs):
                if pkt | DeviceMessages.StatePower:
                    if pkt.level == 0:
                        yield DeviceMessages.SetPower(level=65535, target=pkt.serial)
                    else:
                        yield DeviceMessages.SetPower(level=0, target=pkt.serial)

        msg = FromGenerator(gen)
        await target.send(msg, "d073d5000001")

    The reference your generator will receive will either be the reference from
    the :ref:`sender <sender_interface>` API or the ``reference_override``
    you supply to the ``FromGenerator``. If ``reference_override`` is ``True``
    then you'll get the reference from the ``sender``.

    If you don't specify ``reference_override`` then the messages you yield
    must have an explicit target, otherwise they won't go anyway (unless you
    supplied ``broadcast=True`` to the ``sender``).

    If you say ``reference_override=True`` then messages that don't have an
    explicit ``target`` will go to the ``reference`` given to you.

    Finally, if ``reference_override`` is anything else, that's the reference
    your generator will get and also the default reference the yielded message
    will go to.

    The ``**kwargs`` your generator gets is passed down to you through the
    :ref:`sender <sender_interface>` API. For example:

    .. code-block:: python

        from photons_control.script import FromGenerator
        from photons_messages import DeviceMessages


        async def my_action(target, reference):
            errors = []

            async def gen(reference, sender, **kwargs):
                assert kwargs ==  {"message_timeout": 10, "error_catcher": errors}
                yield DeviceMessages.SetPower(level=0)

            msg = FromGenerator(gen, reference_override=True)
            await target.send(msg, "d073d5000001", message_timeout=10, error_catcher=errors)

    The return value from yield will be a future that resolves to ``True`` if the
    message(s) were sent without error, and ``False`` if they were sent with error.

    .. code-block:: python

        async def gen(reference, sender, **kwargs):
            f = yield [
                DeviceMessages.SetPower(level=65535),
                LightMessages.SetInfrared(brightness=65535)
            ]

            result = await f
            # result will be True if both of those messages were sent and got
            # a reply. If either timed out, then result will be False

    If you want to gather information before yielding messages to send, then
    you can use the ``sender`` like you normally would. The benefit of yielding
    messages instead of using the ``sender`` is that all the messages will
    be sent in parallel to your devices and you can control the flow of those
    messages based on the future that yielding returns.
    """

    def __init__(self, generator, *, reference_override=None, error_catcher_override=None):
        self.generator = generator
        self.reference_override = reference_override
        self.error_catcher_override = error_catcher_override

    def simplified(self, simplifier, chain=None):
        return self.Item(
            simplifier,
            self.generator,
            self.Runner,
            self.reference_override,
            self.error_catcher_override,
        )

    class Item:
        def __init__(self, simplifier, generator, runner_kls, reference_override, catcher_override):
            self.generator = generator
            self.runner_kls = runner_kls
            self.simplifier = simplifier
            self.reference_override = reference_override
            self.error_catcher_override = catcher_override

        async def run(self, reference, sender, **kwargs):
            runner = self.runner_kls(self, reference, sender, kwargs)

            error_catcher = kwargs.get("error_catcher")
            if self.error_catcher_override:
                error_catcher = self.error_catcher_override(runner.run_reference, error_catcher)

            do_raise = error_catcher is None
            if do_raise:
                error_catcher = []

            kwargs["error_catcher"] = error_catcher

            try:
                async for result in runner:
                    yield result
            except asyncio.CancelledError:
                await runner.finish(cancelled=True)
                raise
            finally:
                await runner.finish()

            if do_raise and error_catcher:
                raise RunErrors(_errors=list(set(error_catcher)))

    class Runner:
        class Done:
            pass

        def __init__(self, item, reference, sender, kwargs):
            self.item = item
            self.kwargs = kwargs
            self.stop_fut = asyncio.Future()
            self.reference = reference
            self.sender = sender

            self.ts = []
            self.queue = asyncio.Queue()

        @property
        def error_catcher(self):
            return self.kwargs.get("error_catcher")

        @property
        def generator_reference(self):
            if self.item.reference_override in (None, True):
                return self.reference
            return self.item.reference_override

        @property
        def run_reference(self):
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

        async def finish(self, cancelled=False):
            if cancelled:
                for t in self.ts:
                    t.cancel()

            await self.wait_for_ts()

            self.stop_fut.cancel()

            try:
                await self.queue.put(self.Done)
            except:
                pass

            await self._stop_ts(cancelled=cancelled)

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

        async def _stop_ts(self, cancelled=False):
            d = None
            try:
                if hasattr(self, "getter_t"):
                    if cancelled:
                        self.getter_t.cancel()
                    d, _ = await asyncio.wait([self.getter_t])
            except asyncio.CancelledError:
                raise
            else:
                if d:
                    exc = list(d)[0].exception()
                    if exc:
                        hp.add_error(self.error_catcher, exc)

        async def getter(self):
            gen = self.item.generator(self.generator_reference, self.sender, **self.kwargs)
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
                async for info in item.run(self.run_reference, self.sender, **kwargs):
                    await self.queue.put(info)
            finally:
                if not f.done():
                    f.set_result(i["success"])

        def complete_on_all_done(self, fs, complete):
            def finish(res):
                if complete.done():
                    return

                if res.cancelled():
                    for f in fs:
                        f.cancel()
                    complete.cancel()
                    return

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
