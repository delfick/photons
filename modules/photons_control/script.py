from photons_app.special import SpecialReference, HardCodedSerials, FoundSerials
from photons_app.errors import RunErrors
from photons_app import helpers as hp

from photons_transport.errors import FailedToFindDevice

from delfick_project.norms import sb
import asyncio
import logging
import sys

log = logging.getLogger("photons_control.script")


def squash(result):
    pass


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


def Pipeline(*messages, spread=0, short_circuit_on_error=False, synchronized=False):
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
        Specify the minimum time between sending each message

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
        min_wait = False
        if spread <= 0:
            min_wait = 0

        async with hp.tick(spread, min_wait=min_wait) as ticks:
            async for i, _ in ticks:
                if i > len(messages):
                    return

                t = yield messages[i - 1]
                success = await t
                if not success and short_circuit_on_error:
                    return

    if synchronized:
        m = FromGenerator(gen, reference_override=True)
    else:
        m = FromGeneratorPerSerial(gen)

    m.pipeline_messages = messages
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
        async with hp.tick(min_loop_time, min_wait=False, final_future=sender.stop_fut) as ticks:
            async for i, _ in ticks:
                try:
                    await (yield msg)
                finally:
                    if isinstance(reference, SpecialReference):
                        reference.reset()

                    if callable(on_done_loop):
                        try:
                            await on_done_loop()
                        except Repeater.Stop:
                            return
                        except asyncio.CancelledError:
                            raise
                        except Exception as error:
                            hp.add_error(kwargs["error_catcher"], error)

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


class FromGenerator:
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
            runner = self.runner_kls(self, sender.stop_fut, reference, sender, kwargs)

            error_catcher = kwargs.get("error_catcher")
            if self.error_catcher_override:
                error_catcher = self.error_catcher_override(runner.run_reference, error_catcher)

            do_raise = error_catcher is None
            if do_raise:
                error_catcher = []

            kwargs["error_catcher"] = error_catcher

            try:
                async with runner as results:
                    async for result in results:
                        yield result
            finally:
                if do_raise and error_catcher:
                    raise RunErrors(_errors=list(set(error_catcher)))

    class Runner(hp.AsyncCMMixin):
        class Done:
            pass

        class Value:
            pass

        class Unsuccessful(Exception):
            pass

        def __init__(self, item, stop_fut, reference, sender, kwargs):
            self.item = item
            self.kwargs = kwargs
            self.reference = reference
            self.sender = sender

            self.stop_fut = hp.ChildOfFuture(
                stop_fut, name="FromGenerator>Runner::__init__[stop_fut]"
            )

            self.streamer = hp.ResultStreamer(
                self.stop_fut,
                name="FromGenerator>Runner::__init__[streamer]",
                error_catcher=squash,
            )

        async def start(self):
            await self.streamer.start()
            return self

        async def finish(self, exc_typ=None, exc=None, tb=None):
            self.stop_fut.cancel()
            await self.streamer.finish(exc_typ, exc, tb)

        def __aiter__(self):
            return self.getter()

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

        async def getter(self):
            gen = self.item.generator(self.generator_reference, self.sender, **self.kwargs)
            await self.streamer.add_coroutine(self.consume(gen, self.streamer), context="consume")
            self.streamer.no_more_work()

            async for result in self.streamer:
                if not result.successful:
                    hp.add_error(self.error_catcher, result.value)
                elif result.context is self.Value:
                    yield result.value

        async def consume(self, gen, streamer):
            complete = None

            try:
                while True:
                    try:
                        msg = await gen.asend(complete)
                        if isinstance(msg, Exception):
                            hp.add_error(self.error_catcher, msg)
                            continue

                        if self.stop_fut.done():
                            break

                        complete = hp.create_future(name="FromGenerator>Runner::getter[complete]")
                        await streamer.add_generator(
                            self.retrieve_all(msg, complete), context=self.Value
                        )
                    except StopAsyncIteration:
                        break
            finally:
                exc_info = sys.exc_info()
                if exc_info[0] not in (None, asyncio.CancelledError):
                    hp.add_error(self.error_catcher, exc_info[1])

                await streamer.add_coroutine(
                    hp.stop_async_generator(
                        gen,
                        complete,
                        name="FromGenerator>Runner::consume[finally_stop_gen]",
                        exc=exc_info[1],
                    ),
                    force=True,
                )

                if exc_info[0] is not asyncio.CancelledError:
                    return False

        async def retrieve_all(self, msg, complete):
            try:
                async with hp.ResultStreamer(
                    self.stop_fut,
                    name="FromGenerator>Runner::retrieve_all[streamer]",
                    error_catcher=squash,
                ) as streamer:
                    for item in self.item.simplifier(msg):
                        await streamer.add_generator(self.retrieve(item), context="retrieve")
                    streamer.no_more_work()

                    async for result in streamer:
                        if result.value is hp.ResultStreamer.GeneratorComplete:
                            continue

                        if not result.successful:
                            if not isinstance(result.value, self.Unsuccessful):
                                hp.add_error(self.error_catcher, result.value)
                            if not complete.done():
                                complete.set_result(False)
                        else:
                            yield result.value
            finally:
                if not complete.done():
                    exc_info = sys.exc_info()
                    if exc_info[0] is None:
                        complete.set_result(True)
                    else:
                        complete.set_result(False)

        async def retrieve(self, item):
            i = {"success": True}

            def error(e):
                i["success"] = False
                hp.add_error(self.error_catcher, e)

            kwargs = dict(self.kwargs)
            kwargs["error_catcher"] = error

            async for info in item.run(self.run_reference, self.sender, **kwargs):
                yield info

            if not i["success"]:
                raise self.Unsuccessful()
