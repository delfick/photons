from photons_app.errors import PhotonsAppError

from queue import Queue as NormalQueue, Empty as NormalEmpty
from delfick_project.logging import lc
from contextlib import contextmanager
from collections import deque
from functools import wraps
import threading
import traceback
import tempfile
import secrets
import asyncio
import logging
import time
import sys
import os

log = logging.getLogger("photons_app.helpers")

# Make vim be quiet
lc = lc

if sys.version_info >= (3, 7):
    from contextlib import asynccontextmanager
else:
    from photons_app.polyfill import asynccontextmanager


if hasattr(asyncio, "exceptions"):
    InvalidStateError = asyncio.exceptions.InvalidStateError
else:
    InvalidStateError = asyncio.futures.InvalidStateError


class Nope:
    """Used to say there was no value"""

    pass


def ensure_aexit(instance):
    """
    Used to make sure a manual async context manager calls ``__aexit__`` if
    ``__aenter__`` fails.

    Turns out if ``__aenter__`` raises an exception, then ``__aexit__`` doesn't
    get called, which is not how I thought that worked for a lot of context
    managers.

    Usage is as follows:

    .. code-block:: python

        from photons_app import helpers as hp


        class MyCM:
            async def __aenter__(self):
                async with hp.ensure_aexit(self):
                    return await self.start()

            async def start(self):
                ...

            async def __aexit__(self, exc_typ, exc, tb):
                await self.finish(exc_typ, exc, tb)

            async def finish(exc_typ=None, exc=None, tb=None):
                ...
    """

    @asynccontextmanager
    async def ensure_aexit_cm():
        try:
            yield
        finally:
            # aexit doesn't run if aenter raises an exception
            exc_info = sys.exc_info()
            if exc_info[1] is not None:
                await instance.__aexit__(*exc_info)
                raise

    return ensure_aexit_cm()


class AsyncCMMixin:
    async def __aenter__(self):
        async with ensure_aexit(self):
            return await self.start()

    async def start(self):
        raise NotImplementedError()

    async def __aexit__(self, exc_typ, exc, tb):
        return await self.finish(exc_typ, exc, tb)

    async def finish(self, exc_typ=None, exc=None, tb=None):
        raise NotImplementedError()


async def stop_async_generator(gen, provide=None, name=None, exc=None):
    try:
        try:
            await gen.athrow(exc or asyncio.CancelledError())
        except StopAsyncIteration:
            pass

        try:
            await gen.asend(provide)
        except StopAsyncIteration:
            pass
    finally:
        await gen.aclose()


def fut_to_string(f, with_name=True):
    if not isinstance(f, asyncio.Future):
        s = repr(f)
    else:
        s = ""
        if with_name:
            s = f"<Future#{getattr(f, 'name', None)}"
        if not f.done():
            s = f"{s}(pending)"
        elif f.cancelled():
            s = f"{s}(cancelled)"
        else:
            exc = f.exception()
            if exc:
                s = f"{s}(exception:{type(exc).__name__}:{exc})"
            else:
                s = f"{s}(result)"
        if with_name:
            s = f"{s}>"
    return s


class ATicker(AsyncCMMixin):
    """
    This object gives you an async generator that yields every ``every``
    seconds, taking into account how long it takes for your code to finish
    for the next yield.

    For example:

    .. code-block:: python

        from photons_app import helpers as hp

        import time


        start = time.time()
        timing = []

        async for _ in hp.ATicker(10):
            timing.append(time.time() - start)
            asyncio.sleep(8)
            if len(timing) >= 5:
                break

        assert timing == [0, 10, 20, 30, 40]

    The value that is yielded is a tuple of (iteration, time_till_next) where
    ``iteration`` is a counter of how many times we yield a value starting from
    1 and the ``time_till_next`` is the number of seconds till the next time we
    yield a value.

    You can use the shortcut :func:`tick` to create one of these, but if you
    do create this yourself, you can change the ``every`` value while you're
    iterating.

    .. code-block:: python

        from photons_app import helpers as hp


        ticker = hp.ATicker(10)

        done = 0

        async with ticker as ticks:
            async for _ in ticks:
                done += 1
                if done == 3:
                    # This will mean the next tick will be 20 seconds after the last
                    # tick and future ticks will be 20 seconds apart
                    ticker.change_after(20)
                elif done == 5:
                    # This will mean the next tick will be 40 seconds after the last
                    # tick, but ticks after that will go back to 20 seconds apart.
                    ticker.change_after(40, set_new_every=False)

    There are three other options:

    final_future
        If this future is completed then the iteration will stop

    max_iterations
        Iterations after this number will cause the loop to finish. By default
        there is no limit

    max_time
        After this many iterations the loop will stop. By default there is no
        limit

    min_wait
        The minimum amount of time to wait after a tick.

        If this is False then we will always just tick at the next expected time,
        otherwise we ensure this amount of time at a minimum between ticks

    pauser
        If not None, we use this as a semaphore in an async with to pause the ticks
    """

    class Stop(Exception):
        pass

    def __init__(
        self,
        every,
        *,
        final_future=None,
        max_iterations=None,
        max_time=None,
        min_wait=0.1,
        pauser=None,
        name=None,
    ):
        self.name = name
        self.every = every
        self.pauser = pauser
        self.max_time = max_time
        self.min_wait = min_wait
        self.max_iterations = max_iterations

        if self.every <= 0:
            self.every = 0
            if self.min_wait is False:
                self.min_wait = 0

        self.handle = None
        self.expected = None

        self.waiter = ResettableFuture(name=f"ATicker({self.name})::__init__[waiter]")
        self.final_future = ChildOfFuture(
            final_future
            or create_future(name=f"ATicker({self.name})::__init__[owned_final_future]"),
            name=f"ATicker({self.name})::__init__[final_future]",
        )

    async def start(self):
        self.gen = self.tick()
        return self

    def __aiter__(self):
        if not hasattr(self, "gen"):
            raise Exception(
                "The ticker must be used as a context manager before being used as an async iterator"
            )
        return self.gen

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if hasattr(self, "gen"):
            try:
                await stop_async_generator(
                    self.gen, exc=exc or self.Stop(), name=f"ATicker({self.name})::stop[stop_gen]"
                )
            except self.Stop:
                pass

        self.final_future.cancel()

    async def tick(self):
        final_handle = None
        if self.max_time:
            final_handle = asyncio.get_event_loop().call_later(
                self.max_time, self.final_future.cancel
            )

        try:
            async for info in self._tick():
                yield info
        finally:
            self.final_future.cancel()
            if final_handle:
                final_handle.cancel()
            self._change_handle()

    def change_after(self, every, *, set_new_every=True):
        old_every = self.every
        if set_new_every:
            self.every = every

        if self.expected is None:
            return

        last = self.expected - old_every

        expected = last + every
        if set_new_every:
            self.expected = expected

        diff = round(expected - time.time(), 3)
        self._change_handle()

        if diff <= 0:
            self.waiter.reset()
            self.waiter.set_result(True)
        else:
            self._change_handle(asyncio.get_event_loop().call_later(diff, self._waited))

    def _change_handle(self, handle=None):
        if self.handle:
            self.handle.cancel()
        self.handle = handle

    def _waited(self):
        self.waiter.reset()
        self.waiter.set_result(True)

    async def _wait_for_next(self):
        if self.pauser is None or not self.pauser.locked():
            return await wait_for_first_future(
                self.final_future,
                self.waiter,
                name=f"ATicker({self.name})::_wait_for_next[without_pause]",
            )

        async def pause():
            async with self.pauser:
                pass

        ts_final_future = ChildOfFuture(
            self.final_future, name=f"ATicker({self.name})::_wait_for_next[with_pause]"
        )

        async with TaskHolder(ts_final_future) as ts:
            ts.add(pause())
            ts.add_task(self.waiter)

    async def _tick(self):
        start = time.time()
        iteration = 0
        self.expected = start

        self._waited()

        while True:
            await self._wait_for_next()

            self.waiter.reset()
            if self.final_future.done():
                return

            if self.max_iterations is not None and iteration >= self.max_iterations:
                return

            now = time.time()
            if self.max_time is not None and now - start >= self.max_time:
                return

            if self.min_wait is False:
                diff = self.expected - now
                if diff == 0:
                    self.expected += self.every
                else:
                    while diff <= -self.every:
                        self.expected += self.every
                        diff = self.expected - now

                    while self.expected - now <= 0:
                        self.expected += self.every
            else:
                diff = self.min_wait
                if self.every > 0:
                    while self.expected - now < self.min_wait:
                        self.expected += self.every

                    diff = round(self.expected - now, 3)

            if diff == 0:
                diff = self.expected - now

            self._change_handle(asyncio.get_event_loop().call_later(diff, self._waited))

            if self.min_wait is not False or diff > 0:
                iteration += 1
                yield iteration, max([diff, 0])


def tick(
    every,
    *,
    final_future=None,
    max_iterations=None,
    max_time=None,
    min_wait=0.1,
    name=None,
    pauser=None,
):
    """
    .. code-block:: python

        from photons_app import helpers as hp


        async with hp.tick(every) as ticks:
            async for i in ticks:
                yield i

        # Is a nicer way of saying

        async for i in hp.ATicker(every):
            yield i

    If you want control of the ticker during the iteration, then use
    :class:`ATicker` directly.
    """
    kwargs = {
        "final_future": final_future,
        "max_iterations": max_iterations,
        "max_time": max_time,
        "min_wait": min_wait,
        "pauser": pauser,
        "name": f"||tick({name})",
    }

    return ATicker(every, **kwargs)


class TaskHolder(AsyncCMMixin):
    """
    An object for managing asynchronous coroutines.

    Usage looks like:

    .. code-block:: python

        from photons_app import helpers as hp


        final_future = hp.create_future()

        async def something():
            await asyncio.sleep(5)

        with hp.TaskHolder(final_future) as ts:
            ts.add(something())
            ts.add(something())

    If you don't want to use the context manager, you can say:

    .. code-block:: python

        from photons_app import helpers as hp


        final_future = hp.create_future()

        async def something():
            await asyncio.sleep(5)

        ts = hp.TaskHolder(final_future)

        try:
            ts.add(something())
            ts.add(something())
        finally:
            await ts.finish()

    Once your block in the context manager is done the context manager won't
    exit until all coroutines have finished. During this time you may still
    use ``ts.add`` or ``ts.add_task`` on the holder.

    If the ``final_future`` is cancelled before all the tasks have completed
    then the tasks will be cancelled and properly waited on so their finally
    blocks run before the context manager finishes.

    ``ts.add`` will also return the task object that is made from the coroutine.

    ``ts.add`` also takes a ``silent=False`` parameter, that when True will
    not log any errors that happen. Otherwise errors will be logged.

    If you already have a task object, you can give it to the holder with
    ``ts.add_task(my_task)``.

    .. automethod:: add

    .. automethod:: add_task

    .. automethod:: finish
    """

    def __init__(self, final_future, *, name=None):
        self.name = name

        self.ts = []
        self.final_future = ChildOfFuture(
            final_future, name=f"TaskHolder({self.name})::__init__[final_future]"
        )

        self._cleaner = None
        self._cleaner_waiter = ResettableFuture(
            name=f"TaskHolder({self.name})::__init__[cleaner_waiter]"
        )

    def add(self, coro, *, silent=False):
        return self.add_task(async_as_background(coro, silent=silent))

    def _set_cleaner_waiter(self, res):
        self._cleaner_waiter.reset()
        self._cleaner_waiter.set_result(True)

    def add_task(self, task):
        if not self._cleaner:
            self._cleaner = async_as_background(self.cleaner())

            t = self._cleaner

            def remove_cleaner(res):
                if self._cleaner is t:
                    self._cleaner = None

            t.add_done_callback(remove_cleaner)

        task.add_done_callback(self._set_cleaner_waiter)
        self.ts.append(task)
        return task

    async def start(self):
        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if exc and not self.final_future.done():
            self.final_future.set_exception(exc)

        try:
            while any(not t.done() for t in self.ts):
                for t in self.ts:
                    if self.final_future.done():
                        t.cancel()

                if self.ts:
                    if self.final_future.done():
                        await wait_for_all_futures(
                            self.final_future,
                            *self.ts,
                            name=f"TaskHolder({self.name})::finish[wait_for_all_tasks]",
                        )
                    else:
                        await wait_for_first_future(
                            self.final_future,
                            *self.ts,
                            name=f"TaskHolder({self.name})::finish[wait_for_another_task]",
                        )

                    self.ts = [t for t in self.ts if not t.done()]
        finally:
            try:
                await self._final()
            finally:
                self.final_future.cancel()

    async def _final(self):
        if self._cleaner:
            self._cleaner.cancel()
            await wait_for_all_futures(
                self._cleaner, name=f"TaskHolder({self.name})::finish[finally_wait_for_cleaner]"
            )

        await wait_for_all_futures(
            async_as_background(self.clean()),
            name=f"TaskHolder({self.name})::finish[finally_wait_for_clean]",
        )

    @property
    def pending(self):
        return sum(1 for t in self.ts if not t.done())

    def __contains__(self, task):
        return task in self.ts

    def __iter__(self):
        return iter(self.ts)

    async def cleaner(self):
        while True:
            await self._cleaner_waiter
            self._cleaner_waiter.reset()
            await self.clean()

    async def clean(self):
        destroyed = []
        remaining = []
        for t in self.ts:
            if t.done():
                destroyed.append(t)
            else:
                remaining.append(t)

        await wait_for_all_futures(
            *destroyed, name=f"TaskHolder({self.name})::clean[wait_for_destroyed]"
        )
        self.ts = remaining


class ResultStreamer(AsyncCMMixin):
    """
    An async generator you can add tasks to and results will be streamed as they
    become available.

    To use this, you first create a streamer and give it a ``final_future`` and
    ``error_catcher``. If the ``final_future`` is cancelled, then the streamer
    will stop and any tasks it knows about will be cancelled.

    The ``error_catcher`` is a standard Photons error_catcher. If it's a list
    then exceptions will be added to it. If it's a function then it will be
    called with exceptions. Otherwise it is ignored. Note that if you don't
    specify ``exceptions_only_to_error_catcher=True`` then result objects will
    be given to the ``error_catcher`` rather than the exceptions themselves.

    Once you have a streamer you add tasks, coroutines or async generators
    to the streamer. Once you have no more of these to add to the streamer then
    you call ``streamer.no_more_work()`` so that when all remaining tasks have
    finished, the streamer will stop iterating results.

    The streamer will yield ``ResultStreamer.Result`` objects that contain
    the ``value`` from the task, a ``context`` object that you give to the
    streamer when you register a task and a ``successful`` boolean that is
    ``False`` when the result was from an exception.

    When you register a task/coroutine/generator you may specify an ``on_done``
    callback which will be called when it finishes. For tasks and coroutines
    this is called with the result from that task. For async generators it
    is either called with an exception Result if the generator did not exit
    successfully, or a success Result with a ``ResultStreamer.GeneratorComplete``
    instance.

    When you add an async generator, you may specify an ``on_each`` function
    that will be called for each value that is yielded from the generator.

    You may add tasks, coroutines and async generators while you are taking
    results from the streamer.

    For example:

    .. code-block:: python

        from photons_app import helpers as hp


        final_future = hp.create_future()

        def error_catcher(error_result):
            print(error_result)

        streamer = hp.ResultStreamer(final_future, error_catcher=error_catcher)
        await streamer.start()

        async def coro_function():
            await something
            await streamer.add_generator(generator2, context=SomeContext())
            return 20

        async def coro_function2():
            return 42

        async def generator():
            for i in range(3):
                yield i
                await something_else
            await streamer.add_coroutine(coro_function2())

        await streamer.add_coroutine(coro_function(), context=20)
        await streamer.add_generator(coro_function())

        async with streamer:
            async for result in streamer:
                print(result.value, result.context, result.successful)

    If you don't want to use the ``async with streamer`` then you must call
    ``await streamer.finish()`` when you are done to ensure everything is
    cleaned up.

    .. autoclass:: photons_app.helpers.ResultStreamer.Result

    .. automethod:: add_generator

    .. automethod:: add_coroutine

    .. automethod:: add_value

    .. automethod:: add_task

    .. automethod:: no_more_work

    .. automethod:: finish
    """

    class GeneratorStopper:
        pass

    class GeneratorComplete:
        pass

    class FinishedTask:
        pass

    class Result:
        """
        The object that the streamer will yield. This contains the ``value``
        being yielded, the ``context`` associated with the coroutine/generator
        this value comes from; and a ``successful`` boolean that says if this
        was an error.
        """

        def __init__(self, value, context, successful):
            self.value = value
            self.context = context
            self.successful = successful

        def __eq__(self, other):
            return (
                isinstance(other, self.__class__)
                and other.value == self.value
                and other.context == self.context
                and other.successful == self.successful
            )

        def __repr__(self):
            status = "success" if self.successful else "failed"
            return f"<Result {status}: {self.value}: {self.context}>"

    def __init__(
        self, final_future, *, error_catcher=None, exceptions_only_to_error_catcher=False, name=None
    ):
        self.name = name
        self.final_future = ChildOfFuture(
            final_future, name=f"ResultStreamer({self.name})::__init__[final_future]"
        )
        self.error_catcher = error_catcher
        self.exceptions_only_to_error_catcher = exceptions_only_to_error_catcher

        self.queue_future = ChildOfFuture(
            final_future, name=f"ResultStreamer({self.name})::__init__[queue_future]"
        )
        self.queue = Queue(
            self.queue_future,
            empty_on_finished=True,
            name=f"ResultStreamer({self.name})::__init__[queue]",
        )

        self.ts = TaskHolder(self.final_future, name=f"ResultStreamer({self.name})::__init__[ts]")

        self._registered = 0
        self.stop_on_completion = False

    async def start(self):
        return self

    def __aiter__(self):
        return self.retrieve()

    async def add_generator(self, gen, *, context=None, on_each=None, on_done=None):
        async def run():
            try:
                async for result in gen:
                    result = self.Result(result, context, True)
                    self.queue.append(result)
                    if on_each:
                        on_each(result)
            finally:
                await self.add_coroutine(
                    stop_async_generator(
                        gen,
                        name=f"ResultStreamer({self.name})::add_generator[stop_gen]",
                        exc=sys.exc_info()[1],
                    ),
                    context=self.GeneratorStopper,
                    force=True,
                )

            return self.GeneratorComplete

        task = await self.add_coroutine(run(), context=context, on_done=on_done)
        task.gen = gen

        if self.final_future.done():
            await cancel_futures_and_wait(
                task, name=f"ResultStreamer({self.name})::add_generator[already_stopped_task]"
            )
            await wait_for_first_future(
                async_as_background(gen.aclose()),
                name=f"ResultStreamer({self.name})::add_generator[already_stopped_gen]",
            )
            return task

        return task

    async def add_coroutine(self, coro, *, context=None, on_done=None, force=False):
        return await self.add_task(
            async_as_background(coro, silent=bool(self.error_catcher)),
            context=context,
            on_done=on_done,
            force=force,
        )

    async def add_value(self, value, *, context=None, on_done=None):
        async def return_value():
            return value

        return await self.add_coroutine(return_value(), context=context, on_done=on_done)

    async def add_task(self, task, *, context=None, on_done=None, force=False):
        if self.final_future.done():
            if force:
                await wait_for_all_futures(
                    task, name=f"ResultStreamer({self.name})::add_task[force_already_stopped]"
                )
            else:
                await cancel_futures_and_wait(
                    task, name=f"ResultStreamer({self.name})::add_task[already_stopped]"
                )
            return task

        def add_to_queue(res):
            successful = False

            if res.cancelled():
                value = asyncio.CancelledError()
            else:
                exc = res.exception()
                if exc:
                    traceback.clear_frames(exc.__traceback__)

                if exc:
                    value = exc
                else:
                    value = res.result()
                    successful = True

            result = self.Result(value, context, successful)

            if value is not self.GeneratorComplete:
                if not successful:
                    v = value if self.exceptions_only_to_error_catcher else result
                    if not isinstance(v, asyncio.CancelledError):
                        add_error(self.error_catcher, v)

                self.queue.append(result)

            if on_done:
                on_done(result)

            self.queue.append(self.FinishedTask)

        task.add_done_callback(add_to_queue)
        self.ts.add_task(task)
        self._registered += 1
        return task

    def no_more_work(self):
        self.stop_on_completion = True

    async def retrieve(self):
        if self.stop_on_completion and not self.ts.pending and self._registered == 0:
            return

        self.started = True

        async for nxt in self.queue:
            if nxt is self.FinishedTask:
                self._registered -= 1
            elif nxt.context is self.GeneratorStopper:
                continue
            else:
                yield nxt

            if self.stop_on_completion and not self.ts.pending and self._registered <= 0:
                return

    async def finish(self, exc_typ=None, exc=None, tb=None):
        self.final_future.cancel()

        try:
            await self.ts.finish(exc_typ, exc, tb)
        finally:
            if not self._registered:
                self.queue_future.cancel()
                await self.queue.finish()


@contextmanager
def just_log_exceptions(log, *, reraise=None, message="Unexpected error"):
    """
    A context manager that will catch all exceptions and just call::

        log.error(message, exc_info=sys.exc_info())

    Any class in reraise that matches the error will result in re raising the error

    For example:

    .. code-block:: python

        import logging
        import asyncio

        log = logging.getLogger("my_example")

        message = "That's not meant to happen"

        with just_log_exceptions(log, reraise=[asyncio.CancelledError], message=message):
            await do_something()
    """
    try:
        yield
    except Exception as error:
        if reraise and any(isinstance(error, r) for r in reraise):
            raise
        log.error(message, exc_info=sys.exc_info())


def add_error(catcher, error):
    """
    Adds an error to an error_catcher.

    This means if it's callable we call it with the error and if it's a ``list``
    or ``set`` we add the error to it.
    """
    if callable(catcher):
        catcher(error)
    elif type(catcher) is list:
        catcher.append(error)
    elif type(catcher) is set:
        catcher.add(error)


@contextmanager
def a_temp_file():
    """
    Yield the name of a temporary file and ensure it's removed after use

    .. code-block:: python

        with hp.a_temp_file() as fle:
            fle.write("hello")
            fle.flush()
            os.system("cat {0}".format(fle.name))
    """
    filename = None
    tmpfile = None
    try:
        tmpfile = tempfile.NamedTemporaryFile(delete=False)
        filename = tmpfile.name
        yield tmpfile
    finally:
        if tmpfile is not None:
            tmpfile.close()
        if filename and os.path.exists(filename):
            os.remove(filename)


def nested_dict_retrieve(data, keys, dflt):
    """
    Used to get a value deep in a nested dictionary structure

    For example

    .. code-block:: python

        data = {"one": {"two": {"three": "four"}}}

        nested_dict_retrieve(data, ["one", "two", "three"], 6) == "four"

        nested_dict_retrieve(data, ["one", "two"], 6) == {"three": "four"}

        nested_dict_retrieve(data, ["one", "four"], 6) == 6
    """
    if not keys:
        return data

    for key in keys[:-1]:
        if type(data) is not dict:
            return dflt

        if key not in data:
            return dflt

        data = data[key]

    if type(data) is not dict:
        return dflt

    last_key = keys[-1]
    if last_key not in data:
        return dflt

    return data[last_key]


def fut_has_callback(fut, callback):
    """
    Look at the callbacks on the future and return ``True`` if any of them
    are the provided ``callback``.
    """
    if not fut._callbacks:
        return False

    for cb in fut._callbacks:
        if type(cb) is tuple and cb:
            cb = cb[0]

        if cb == callback:
            return True

    return False


def async_as_background(coroutine, silent=False):
    """
    Create a task with :func:`reporter` as a done callback and return the created
    task. If ``silent=True`` then use :func:`silent_reporter`.

    This is useful because if a task exits with an exception, but nothing ever
    retrieves that exception then Python will print annoying warnings about this.

    .. code-block:: python

        from photons_app import helpers as hp


        async def my_func():
            await something()

        # Kick off the function in the background
        hp.async_as_background(my_func())
    """
    t = asyncio.get_event_loop().create_task(coroutine)
    if silent:
        t.add_done_callback(silent_reporter)
    else:
        t.add_done_callback(reporter)
    return t


async def async_with_timeout(coroutine, *, timeout=10, timeout_error=None, silent=False, name=None):
    """
    Run a coroutine as a task until it's complete or times out.

    If time runs out the task is cancelled.

    If timeout_error is defined, that is raised instead of asyncio.CancelledError
    on timeout.

    .. code-block:: python

        from photons_app.helpers import hp

        import asyncio


        async def my_coroutine():
            await asyncio.sleep(120)

        await hp.async_with_timeout(my_coroutine(), timeout=20)
    """
    f = create_future(name=f"||async_with_timeout({name})[final]")
    t = async_as_background(coroutine, silent=silent)

    def pass_result(res):
        if res.cancelled():
            f.cancel()
            return

        if res.exception() is not None:
            if not f.done():
                f.set_exception(t.exception())
            return

        if t.done() and not f.done():
            f.set_result(t.result())

    t.add_done_callback(pass_result)

    def set_timeout():
        if not t.done():
            if timeout_error and not f.done():
                f.set_exception(timeout_error)

            t.cancel()
            f.cancel()

    handle = asyncio.get_event_loop().call_later(timeout, set_timeout)
    try:
        return await f
    finally:
        handle.cancel()


def create_future(*, name=None, loop=None):
    future = (loop or asyncio.get_event_loop()).create_future()
    future.name = name
    future.add_done_callback(silent_reporter)
    return future


async def wait_for_all_futures(*futs, name=None):
    """
    Wait for all the futures to be complete and return without error regardless
    of whether the futures completed successfully or not.

    If there are no futures, nothing is done and we return without error.

    We determine all the futures are done when the number of completed futures
    is equal to the number of futures we started with. This is to ensure if a
    future is special and calling done() after the future callback has been
    called is not relevant anymore, we still count the future as done.
    """
    if not futs:
        return

    waiter = create_future(name=f"||wait_for_all_futures({name})[waiter]")

    unique = {id(fut): fut for fut in futs}.values()
    complete = {}

    def done(res):
        complete[id(res)] = True
        if not waiter.done() and len(complete) == len(unique):
            waiter.set_result(True)

    for fut in unique:
        fut.add_done_callback(done)

    try:
        await waiter
    finally:
        for fut in unique:
            fut.remove_done_callback(done)


async def wait_for_first_future(*futs, name=None):
    """
    Return without error when the first future to be completed is done.
    """
    if not futs:
        return

    waiter = create_future(name=f"||wait_for_first_future({name})[waiter]")
    unique = {id(fut): fut for fut in futs}.values()

    def done(res):
        if not waiter.done():
            waiter.set_result(True)

    for fut in unique:
        fut.add_done_callback(done)

    try:
        await waiter
    finally:
        for fut in unique:
            fut.remove_done_callback(done)


async def cancel_futures_and_wait(*futs, name=None):
    """
    Cancel the provided futures and wait for them all to finish. We will still
    await the futures if they are all already done to ensure no warnings about
    futures being destroyed while still pending.
    """
    if not futs:
        return

    waiting = []

    for fut in futs:
        if not fut.done():
            fut.cancel()
            waiting.append(fut)

    await wait_for_all_futures(
        *waiting, name=f"||cancel_futures_and_wait({name})[wait_for_everything]"
    )


class memoized_property:
    """
    Decorator to make a descriptor that memoizes it's value

    .. code-block:: python

        from photons_app import helpers as hp


        class MyClass:
            @hp.memoized_property
            def thing(self):
                return expensive_operation()

        obj = MyClass()

        # Get us the result of expensive operation
        print(obj.thing)

        # And we get the result again but minus the expensive operation
        print(obj.thing)

        # We can set our own value
        object.thing = "overridden"
        assert object.thing == "overridden"

        # And we can delete what is cached
        del object.thing
        assert object.thing == "<result from calling expensive_operation() again>"
    """

    class Empty:
        pass

    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__
        self.cache_name = "_{0}".format(self.name)

    def __get__(self, instance=None, owner=None):
        if instance is None:
            return self

        if getattr(instance, self.cache_name, self.Empty) is self.Empty:
            setattr(instance, self.cache_name, self.func(instance))
        return getattr(instance, self.cache_name)

    def __set__(self, instance, value):
        setattr(instance, self.cache_name, value)

    def __delete__(self, instance):
        if hasattr(instance, self.cache_name):
            delattr(instance, self.cache_name)


def silent_reporter(res):
    """
    A generic reporter for asyncio tasks that doesn't log errors.

    For example:

    .. code-block:: python

        t = loop.create_task(coroutine())
        t.add_done_callback(hp.silent_reporter)

    This means that exceptions are **not** logged to the terminal and you won't
    get warnings about tasks not being looked at when they finish.

    This method will return ``True`` if there was no exception and ``None``
    otherwise.

    It also handles and silences ``asyncio.CancelledError``.
    """
    if not res.cancelled():
        exc = res.exception()
        if not exc:
            res.result()
            return True


def reporter(res):
    """
    A generic reporter for asyncio tasks.

    For example:

    .. code-block:: python

        t = loop.create_task(coroutine())
        t.add_done_callback(hp.reporter)

    This means that exceptions are logged to the terminal and you won't
    get warnings about tasks not being looked at when they finish.

    This method will return ``True`` if there was no exception and ``None``
    otherwise.

    It also handles and silences ``asyncio.CancelledError``.
    """
    if not res.cancelled():
        exc = res.exception()
        if exc:
            if not isinstance(exc, KeyboardInterrupt):
                log.exception(exc, exc_info=(type(exc), exc, exc.__traceback__))
        else:
            res.result()
            return True


def transfer_result(fut, errors_only=False, process=None):
    """
    Return a ``done_callback`` that transfers the result, errors or cancellation
    to the provided future.

    If errors_only is ``True`` then it will not transfer a successful result
    to the provided future.

    .. code-block:: python

        from photons_app import helpers as hp

        import asyncio


        async def my_coroutine():
            return 2

        fut = hp.create_future()
        task = hp.async_as_background(my_coroutine())
        task.add_done_callback(hp.transfer_result(fut))

        assert (await fut) == 2

    If process is provided, then when the coroutine is done, process will be
    called with the result of the coroutine and the future that result is being
    transferred to.
    """

    def transfer(res):
        if res.cancelled():
            fut.cancel()
            return

        exc = res.exception()

        if fut.done():
            return

        if exc is not None:
            fut.set_exception(exc)
            return

        if not errors_only:
            fut.set_result(res.result())

        if process:
            process(res, fut)

    return transfer


def noncancelled_results_from_futs(futs):
    """
    Get back (exception, results) from a list of futures

    exception
        A single exception if all the errors are the same type
        or if there is only one exception

        otherwise it is None

    results
        A list of the results that exist
    """
    errors = set()
    results = []
    for f in futs:
        if f.done() and not f.cancelled():
            exc = f.exception()
            if exc:
                errors.add(exc)
            else:
                results.append(f.result())

    if errors:
        errors = list(errors)
        if len(errors) == 1:
            errors = errors[0]
        else:
            errors = PhotonsAppError(_errors=errors)
    else:
        errors = None

    return (errors, results)


def find_and_apply_result(final_fut, available_futs):
    """
    Find a result in available_futs with a result or exception and set that
    result/exception on both final_fut, and all the settable futs
    in available_futs.

    As a bonus, if final_fut is set, then we set that result/exception on
    available_futs.

    and if final_fut is cancelled, we cancel all the available futs

    Return True if we've changed final_fut
    """
    if final_fut.cancelled():
        for f in available_futs:
            f.cancel()
        return False

    if final_fut.done():
        current_exc = final_fut.exception()
        if current_exc:
            for f in available_futs:
                if not f.done():
                    f.set_exception(current_exc)
            return False

    errors, results = noncancelled_results_from_futs(available_futs)
    if errors:
        for f in available_futs:
            if not f.done() and not f.cancelled():
                f.set_exception(errors)
        if not final_fut.done():
            final_fut.set_exception(errors)
            return True
        return False

    if results:
        res = results[0]
        for f in available_futs:
            if not f.done() and not f.cancelled():
                f.set_result(res)
        if not final_fut.done():
            final_fut.set_result(res)
            return True
        return False

    for f in available_futs:
        if f.cancelled():
            final_fut.cancel()
            return True

    return False


class ResettableFuture:
    """
    A future object with a ``reset()`` function that resets it

    Usage:

    .. code-block:: python

        fut = ResettableFuture()
        fut.set_result(True)
        await fut == True

        fut.reset()
        fut.set_result(False)
        await fut == False

    Calling reset on one of these will do nothing if it already isn't resolved.

    Calling reset on a resolved future will also remove any registered done
    callbacks.
    """

    _asyncio_future_blocking = False

    def __init__(self, name=None):
        self.name = name
        self.fut = create_future(name=f"ResettableFuture({self.name})::__init__[fut]")

    def reset(self, force=False):
        if force:
            self.fut.cancel()

        if not self.fut.done():
            return

        self.fut = create_future(name=f"ResettableFuture({self.name})::reset[fut]")

    @property
    def _callbacks(self):
        return self.fut._callbacks

    def set_result(self, data):
        self.fut.set_result(data)

    def set_exception(self, exc):
        self.fut.set_exception(exc)

    def cancel(self):
        self.fut.cancel()

    def result(self):
        return self.fut.result()

    def done(self):
        return self.fut.done()

    def cancelled(self):
        return self.fut.cancelled()

    def exception(self):
        return self.fut.exception()

    def add_done_callback(self, func):
        self.fut.add_done_callback(func)

    def remove_done_callback(self, func):
        self.fut.remove_done_callback(func)

    def __repr__(self):
        return f"<ResettableFuture#{self.name}({fut_to_string(self.fut, with_name=False)})>"

    def __await__(self):
        return (yield from self.fut)

    __iter__ = __await__


class ChildOfFuture:
    """
    Create a future that also considers the status of it's parent.

    So if the parent is cancelled, then this future is cancelled.
    If the parent raises an exception, then that exception is given to this result

    The special case is if the parent receives a result, then this future is
    cancelled.

    The recommended use is with it's context manager::

        from photons_app import helpers as hp

        parent_fut = hp.create_future()

        with hp.ChildOfFuture(parent_fut):
            ...

    If you don't use the context manager then ensure you resolve the future when
    you no longer need it (i.e. ``fut.cancel()``) to avoid a memory leak.
    """

    _asyncio_future_blocking = False

    def __init__(self, original_fut, *, name=None):
        self.name = name
        self.fut = create_future(name=f"ChildOfFuture({self.name})::__init__[fut]")
        self.original_fut = original_fut

        self.fut.add_done_callback(self.remove_parent_done)
        self.original_fut.add_done_callback(self.parent_done)

    def __enter__(self):
        return self

    def __exit__(self, exc_typ, exc, tb):
        self.cancel()

    def parent_done(self, res):
        if self.fut.done():
            return

        if res.cancelled():
            self.fut.cancel()
            return

        exc = res.exception()
        if exc:
            self.fut.set_exception(exc)
        else:
            self.fut.cancel()

    def remove_parent_done(self, ret):
        self.original_fut.remove_done_callback(self.parent_done)

    @property
    def _callbacks(self):
        return self.fut._callbacks

    def set_result(self, data):
        if self.original_fut.done():
            self.original_fut.set_result(data)
        self.fut.set_result(data)

    def set_exception(self, exc):
        if self.original_fut.done():
            self.original_fut.set_exception(exc)
        self.fut.set_exception(exc)

    def cancel(self):
        self.fut.cancel()

    def result(self):
        if self.original_fut.done() or self.original_fut.cancelled():
            if self.original_fut.cancelled():
                return self.original_fut.result()
            else:
                self.fut.cancel()
        if self.fut.done() or self.fut.cancelled():
            return self.fut.result()
        return self.original_fut.result()

    def done(self):
        return self.fut.done() or self.original_fut.done()

    def cancelled(self):
        if self.fut.cancelled() or self.original_fut.cancelled():
            return True

        # We cancel fut if original_fut gets a result
        if self.original_fut.done() and not self.original_fut.exception():
            self.fut.cancel()
            return True

        return False

    def exception(self):
        if self.fut.done() and not self.fut.cancelled():
            exc = self.fut.exception()
            if exc is not None:
                return exc

        if self.original_fut.done() and not self.original_fut.cancelled():
            exc = self.original_fut.exception()
            if exc is not None:
                return exc

        if self.fut.cancelled() or self.fut.done():
            return self.fut.exception()

        return self.original_fut.exception()

    def cancel_parent(self):
        if hasattr(self.original_fut, "cancel_parent"):
            self.original_fut.cancel_parent()
        else:
            self.original_fut.cancel()

    def add_done_callback(self, func):
        self.fut.add_done_callback(func)

    def remove_done_callback(self, func):
        self.fut.remove_done_callback(func)

    def __repr__(self):
        return f"<ChildOfFuture#{self.name}({fut_to_string(self.fut, with_name=False)}){fut_to_string(self.original_fut)}>"

    def __await__(self):
        return (yield from self.fut)

    __iter__ = __await__


class SyncQueue:
    """
    A simple wrapper around the standard library non async queue.

    Usage is:

    .. code-block:: python

        from photons_app import helpers as hp

        queue = hp.SyncQueue()

        async def results():
            for result in queue:
                print(result)

        ...

        queue.append(something)
        queue.append(another)
    """

    def __init__(self, final_future, *, timeout=0.05, empty_on_finished=False, name=None):
        self.name = name
        self.timeout = timeout
        self.collection = NormalQueue()
        self.final_future = ChildOfFuture(
            final_future, name=f"SyncQueue({self.name})::__init__[final_future]"
        )
        self.empty_on_finished = empty_on_finished

    def append(self, item):
        self.collection.put(item)

    def finish(self, exc_typ=None, exc=None, tb=None):
        self.final_future.cancel()

    def __iter__(self):
        return iter(self.get_all())

    def get_all(self):
        while True:
            if self.final_future.done():
                break

            try:
                nxt = self.collection.get(timeout=self.timeout)
            except NormalEmpty:
                continue
            else:
                if self.final_future.done():
                    break

                yield nxt

        if self.final_future.done() and self.empty_on_finished:
            for nxt in self.remaining():
                yield nxt

    def remaining(self):
        while True:
            if not self.collection.empty():
                yield self.collection.get(block=False)
            else:
                break


class Queue:
    """
    A custom async queue class.

    Usage is:

    .. code-block:: python

        from photons_app import helpers as hp

        final_future = hp.create_future()
        queue = hp.Queue(final_future)

        async def results():
            # This will continue forever until final_future is done
            async for result in queue:
                print(result)

        ...

        queue.append(something)
        queue.append(another)

    Note that the main difference between this and the standard library
    asyncio.Queue is that this one does not have the ability to impose limits.
    """

    class Done:
        pass

    def __init__(self, final_future, *, empty_on_finished=False, name=None):
        self.name = name
        self.waiter = ResettableFuture(name=f"Queue({self.name})::__init__[waiter]")
        self.collection = deque()
        self.final_future = ChildOfFuture(
            final_future, name=f"Queue({self.name})::__init__[final_future]"
        )
        self.empty_on_finished = empty_on_finished

        self.stop = False
        self.final_future.add_done_callback(self._stop_waiter)

    def _stop_waiter(self, res):
        self.waiter.reset()
        self.waiter.set_result(True)

    async def finish(self, exc_typ=None, exc=None, tb=None):
        self.final_future.cancel()

    def append(self, item):
        self.collection.append(item)
        if not self.waiter.done():
            self.waiter.set_result(True)

    def __aiter__(self):
        return self.get_all()

    async def get_all(self):
        if not self.collection:
            self.waiter.reset()

        while True:
            await wait_for_first_future(
                self.final_future,
                self.waiter,
                name=f"Queue({self.name})::_get_and_wait[wait_for_next_value]",
            )

            if self.final_future.done() and not self.empty_on_finished:
                break

            if self.final_future.done() and not self.collection:
                break

            if not self.collection:
                continue

            nxt = self.collection.popleft()
            if nxt is self.Done:
                break

            if not self.collection:
                self.waiter.reset()

            yield nxt

    def remaining(self):
        while self.collection:
            yield self.collection.popleft()


class ThreadToAsyncQueue(AsyncCMMixin):
    """
    A Queue for requesting data from some thread:

    .. code-block:: python

        from photons_app import helpers as hp


        class MyQueue(hp.ThreadToAsyncQueue):
            def create_args(self, thread_number, existing):
                if existing:
                    # Assuming you have a way of seeing if you should refresh the args
                    # Then this gives you an opportunity to do any shutdown logic for
                    # existing args and create new, or just return what exists already
                    if not should_refresh():
                        return existing

                    cleanup(existing)

                my_thread_thing = THING()
                return (my_thread_thing, )

        def onerror(exc):
            '''
            This is called on unexpected errors. The return of this function
            is ignored
            '''
            pass

        # If stop_fut is cancelled or has a result, then the queue will stop
        # But the thread will continue until queue.finish() is called
        queue = MyQueue(stop_fut, 10, onerror)
        await queue.start()

        def action(my_thread_thing):
            '''This runs in one of the threads'''
            return my_thread_thing.stuff()

        await queue.request(action)
        await queue.finish()

    .. automethod:: setup

    .. automethod:: create_args

    .. automethod:: wrap_request

    .. automethod:: request

    .. automethod:: start()

    .. automethod:: finish
    """

    def __init__(self, stop_fut, num_threads, onerror, *args, name=None, **kwargs):
        self.name = name
        self.loop = asyncio.get_event_loop()
        self.stop_fut = ChildOfFuture(
            stop_fut, name=f"ThreadToAsyncQueue({self.name})::__init__[stop_fut]"
        )

        self.queue = SyncQueue(
            self.stop_fut, empty_on_finished=True, name=f"ThreadToAsyncQueue({self.name})"
        )
        self.futures = {}
        self.onerror = onerror
        self.num_threads = num_threads

        self.result_queue = Queue(
            self.stop_fut, empty_on_finished=True, name=f"ThreadToAsyncQueue({self.name})"
        )
        self.setup(*args, **kwargs)

        self.future_setter = None
        self.finish_futures = []

    def setup(self, *args, **kwargs):
        """
        Hook for extra setup and takes in the extra unused positional and
        keyword arguments from instantiating this class.
        """

    async def finish(self, exc_typ=None, exc=None, tb=None):
        """Signal to the tasks to stop at the next available moment"""
        self.stop_fut.cancel()
        if self.future_setter:
            await wait_for_all_futures(
                self.future_setter, name=f"ThreadToAsyncQueue({self.name})::finish"
            )
        self.queue.finish()
        await self.result_queue.finish()
        await wait_for_all_futures(*self.finish_futures)

    def start(self, impl=None):
        """Start tasks to listen for requests made with the ``request`` method"""
        ready = []
        for thread_number, _ in enumerate(range(self.num_threads)):
            fut = create_future(name=f"ThreadToAsyncQueue({self.name})::start[ready_fut]")
            ffut = create_future(name=f"ThreadToAsyncQueue({self.name})::start[finish_fut]")
            self.finish_futures.append(ffut)
            ready.append(fut)
            thread = threading.Thread(target=self.listener, args=(thread_number, fut, ffut, impl))
            thread.start()
        self.future_setter = async_as_background(self.set_futures())
        return asyncio.gather(*ready)

    def request(self, func):
        """
        Make a request and get back a future representing the result of that
        request.

        The ``func`` provided will be called in one of our threads and provided
        the ``args`` provided by :meth:`create_args`.

        .. code-block:: python

            from photons_app import helpers as hp


            class MyQueue(hp.ThreadToAsyncQueue):
                def create_args(self, thread_number, existing):
                    return ("a", "b")

            queue = MyQueue(...)
            await queue.start()

            def action(letter1, letter2):
                assert letter1 == "a"
                assert letter1 == "b"
                return "c"

            assert (await queue.request(action)) == "c"
        """
        if self.stop_fut.done():
            fut = create_future(name=f"ThreadToAsyncQueue({self.name})::request[result_cancelled]")
            fut.cancel()
            return fut

        key = secrets.token_urlsafe(16)
        fut = create_future(name=f"ThreadToAsyncQueue({self.name})::request[result_fut]")
        self.futures[key] = fut
        self.queue.append((key, func))
        return fut

    async def set_futures(self):
        """Get results from the result_queue and set that result on the appropriate future"""
        async for res in self.result_queue:
            if not res:
                continue

            if isinstance(res, tuple) and len(res) == 3:
                key, result, exception = res
            else:
                error = PhotonsAppError("Unknown item on queue", got=res)
                self.onerror(error)
                continue

            try:
                self.find_and_set_future(key, result, exception)
            except asyncio.CancelledError:
                break
            except KeyboardInterrupt:
                raise
            except:
                exc_info = sys.exc_info()
                self.onerror(exc_info)
                log.error(exc_info[1], exc_info=exc_info)

    def find_and_set_future(self, key, result, exception):
        """Find and set future for this key to provided result or exception"""
        if key in self.futures:
            fut = self.futures.pop(key)
            if not fut.done() and not fut.cancelled():
                if result is Nope:
                    fut.set_exception(exception)
                else:
                    fut.set_result(result)

    def process(self, key, proc):
        """Process a request"""
        result = Nope
        exception = Nope
        try:
            result = proc()
        except Exception as error:
            exception = error
            self.onerror(sys.exc_info())

        try:
            self.loop.call_soon_threadsafe(self.result_queue.append, (key, result, exception))
        except RuntimeError:
            log.error(
                PhotonsAppError(
                    "Failed to put result onto the loop because it was closed",
                    key=key,
                    result=result,
                    exception=exception,
                )
            )

    def listener(self, thread_number, ready_fut, finish_fut, impl=None):
        """Start the thread!"""
        args = self.create_args(thread_number, existing=None)
        self.loop.call_soon_threadsafe(ready_fut.set_result, True)
        try:
            self._listener(thread_number, impl, args)
        finally:
            self.loop.call_soon_threadsafe(finish_fut.set_result, True)

    def create_args(self, thread_number, existing):
        """
        Hook to return extra args to give to functions when the are requested

        This is called once when the queue is started and then subsequently
        before every request.

        It must return ``None`` or a tuple of arguments to pass into request
        functions.
        """

    def _listener(self, thread_number, impl, args):
        """Forever, with error catching, get nxt request of the queue and process"""
        for nxt in self.queue:
            try:
                args = self.create_args(thread_number, existing=args)
                if args is None:
                    args = ()

                (impl or self.listener_impl)(nxt, *args)
            except KeyboardInterrupt:
                raise
            except:
                exc_info = sys.exc_info()
                log.error(exc_info[1], exc_info=exc_info)
                self.onerror(exc_info)

    def wrap_request(self, proc, args):
        """
        Hook to return a function that will perform the work

        This takes in the ``proc``, which is the function you give to
        :meth:`request` and the ``args`` returned from :meth:`create_args`.

        By default this says:

        .. code-block:: python

            def wrapped():
                return proc(*args)

            return wrapped
        """

        def wrapped():
            return proc(*args)

        return wrapped

    def listener_impl(self, nxt, *args):
        """Just call out to process"""
        if isinstance(nxt, tuple) and len(nxt) == 2:
            key, proc = nxt
            self.process(key, wraps(proc)(self.wrap_request(proc, args)))
        else:
            error = PhotonsAppError("Unknown item in the queue", got=nxt)
            self.onerror(error)
            log.error(error)
