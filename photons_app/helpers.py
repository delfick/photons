"""Some useful, common helper functionalities"""

from photons_app.errors import PhotonsAppError

from contextlib import contextmanager
from delfick_logging import lc
from queue import Queue, Empty
from functools import wraps
import threading
import tempfile
import asyncio
import logging
import uuid
import sys
import os

log = logging.getLogger("photons_app.helpers")

# Make vim be quiet
lc = lc

class Nope:
    """Used to say there was no value"""
    pass

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
    if not fut._callbacks:
        return False

    for cb in fut._callbacks:
        if type(cb) is tuple and cb:
            cb = cb[0]

        if cb == callback:
            return True

    return False

def async_as_normal(func):
    """
    Return a function that creates a task on the provided loop using the
    provided func and add reporter as a done callback

    .. code-block:: python

        # Define my async function
        async def my_func(a, b):
            await something(a, b)

        # Create a callable that will start the async function in the background
        func = hp.async_as_normal(my_func)

        # start the async job
        func(1, b=6)
    """
    @wraps(func)
    def normal(*args, **kwargs):
        coroutine = func(*args, **kwargs)
        t = asyncio.get_event_loop().create_task(coroutine)
        t.add_done_callback(reporter)
        return t
    return normal

def async_as_background(coroutine, silent=False):
    """
    Create a task with reporter as a done callback using provided loop and
    coroutine and return the new task.

    .. code-block:: python

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

async def async_with_timeout(coroutine, timeout=10, timeout_error=None, silent=False):
    """
    Run a coroutine as a task until it's complete or times out

    If time runs out the task is cancelled

    If timeout_error is defined, that is raised instead of asyncio.CancelledError on timeout
    """
    f = asyncio.Future()
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

    asyncio.get_event_loop().call_later(timeout, set_timeout)
    return await f

class memoized_property(object):
    """
    Decorator to make a descriptor that memoizes it's value

    .. code-block:: python

        class MyClass(object):
            @hp.memoized_property
            def thing(self):
                return expensive_operation()

        obj = MyClass()

        # Get us the result of expensive operation
        print(obj.thing)

        # And we get the result again but minus the expensive operation
        print(obj.thing)
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

    This means that exceptions are *not* logged to the terminal and you won't
    get warnings about tasks not being looked at when they finish.

    This method will return True if there was no exception and None otherwise.

    It also handles and silences CancelledError.
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

    This method will return True if there was no exception and None otherwise.

    It also handles and silences CancelledError.
    """
    if not res.cancelled():
        exc = res.exception()
        if exc:
            log.exception(exc, exc_info=(type(exc), exc, exc.__traceback__))
        else:
            res.result()
            return True

def transfer_result(fut, errors_only=False):
    """
    Return a done_callback that transfers the result/errors/cancellation to fut

    If errors_only is True then it will not transfer a result to fut
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
        if len(errors) is 1:
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

class ResettableFuture(object):
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

    This also supports an ``on_creation`` store that holds functions to be called
    when a new result is set.

    Usage:

    .. code-block:: python

        fut = ResettableFuture()
        def do_something(val):
            # Note that this callback is _not_ async
            print(val)
        fut.on_creation(do_something)
    """
    _asyncio_future_blocking = False

    def __init__(self, info=None):
        if info is None:
            self.reset()
        else:
            self.info = info
        self.creationists = []
        self.reset_fut = asyncio.Future()

    @property
    def _loop(self):
        return asyncio.get_event_loop()

    def reset(self):
        if hasattr(self, "reset_fut"):
            if not self.reset_fut.done():
                self.reset_fut.set_result(True)
        done_callbacks = getattr(self, "info", {}).get("done_callbacks", [])
        self.info = {"fut": asyncio.Future(), "done_callbacks": done_callbacks}
        for cb in done_callbacks:
            self.info["fut"].add_done_callback(cb)

    @property
    def _callbacks(self):
        return self.info["fut"]._callbacks

    def set_result(self, data):
        self.info["fut"].set_result(data)
        for func in self.creationists:
            func(data)

    def result(self):
        return self.info["fut"].result()

    def done(self):
        return self.info["fut"].done()

    def cancelled(self):
        return self.info["fut"].cancelled()

    def exception(self):
        return self.info["fut"].exception()

    def cancel(self):
        self.info["fut"].cancel()

    def ready(self):
        return self.done() and not self.cancelled()

    def settable(self):
        return not self.done() and not self.cancelled()

    def finished(self):
        return self.done() or self.cancelled()

    def set_exception(self, exc):
        self.info["fut"].set_exception(exc)

    def on_creation(self, func):
        self.creationists.append(func)

    def add_done_callback(self, func):
        self.info["done_callbacks"].append(func)
        return self.info["fut"].add_done_callback(func)

    def remove_done_callback(self, func):
        if func in self.info["done_callbacks"]:
            self.info["done_callbacks"] = [cb for cb in self.info["done_callbacks"] if cb != func]
        return self.info["fut"].remove_done_callback(func)

    def freeze(self):
        fut = ResettableFuture({k: v for k, v in self.info.items()})
        fut.creationists = list(self.creationists)
        return fut

    def __repr__(self):
        return "<ResettableFuture: {0}>".format(repr(self.info["fut"]))

    def __await__(self):
        while True:
            if self.done() or self.cancelled():
                return (yield from self.info["fut"])

            waiter = asyncio.wait([self.info["fut"], self.reset_fut], return_when=asyncio.FIRST_COMPLETED)
            if hasattr(waiter, "__await__"):
                yield from waiter.__await__()
            else:
                yield from waiter

            if self.reset_fut.done():
                self.reset_fut = asyncio.Future()
    __iter__ = __await__

class ChildOfFuture(object):
    """
    Create a future that also considers the status of it's parent.

    So if the parent is cancelled, then this future is cancelled.
    If the parent raises an exception, then that exception is given to this result

    The special case is if the parent receives a result, then this future is
    cancelled.
    """
    _asyncio_future_blocking = False

    def __init__(self, original_fut):
        self.this_fut = asyncio.Future()
        self.original_fut = original_fut
        self.done_callbacks = []

    @property
    def _loop(self):
        return asyncio.get_event_loop()

    @property
    def _callbacks(self):
        return self.this_fut._callbacks

    def set_result(self, data):
        if self.original_fut.cancelled():
            raise asyncio.futures.InvalidStateError("CANCELLED: {!r}".format(self.original_fut))
        self.this_fut.set_result(data)

    def result(self):
        if self.original_fut.done() or self.original_fut.cancelled():
            if self.original_fut.cancelled():
                return self.original_fut.result()
            else:
                self.this_fut.cancel()
        if self.this_fut.done() or self.this_fut.cancelled():
            return self.this_fut.result()
        return self.original_fut.result()

    def done(self):
        return self.this_fut.done() or self.original_fut.done()

    def cancelled(self):
        if self.this_fut.cancelled() or self.original_fut.cancelled():
            return True

        # We cancel this_fut if original_fut gets a result
        if self.original_fut.done() and not self.original_fut.exception():
            self.this_fut.cancel()
            return True

        return False

    def exception(self):
        if self.this_fut.done() and not self.this_fut.cancelled():
            exc = self.this_fut.exception()
            if exc is not None:
                return exc

        if self.original_fut.done() and not self.original_fut.cancelled():
            exc = self.original_fut.exception()
            if exc is not None:
                return exc

        if self.this_fut.cancelled() or self.this_fut.done():
            return self.this_fut.exception()

        return self.original_fut.exception()

    def cancel_parent(self):
        if hasattr(self.original_fut, "cancel_parent"):
            self.original_fut.cancel_parent()
        else:
            self.original_fut.cancel()

    def cancel(self):
        self.this_fut.cancel()

    def ready(self):
        return self.done() and not self.cancelled()

    def settable(self):
        return not self.done() and not self.cancelled()

    def finished(self):
        return self.done() or self.cancelled()

    def set_exception(self, exc):
        self.this_fut.set_exception(exc)

    def add_done_callback(self, func):
        if func not in self.done_callbacks:
            self.done_callbacks.append(func)

        if not fut_has_callback(self.this_fut, self._done_cb):
            self.this_fut.add_done_callback(self._done_cb)
        if not fut_has_callback(self.original_fut, self._parent_done_cb):
            self.original_fut.add_done_callback(self._parent_done_cb)

    def remove_done_callback(self, func):
        if func in self.done_callbacks:
            self.done_callbacks = [cb for cb in self.done_callbacks if cb != func]
        if not self.done_callbacks:
            self.this_fut.remove_done_callback(self._done_cb)
            self.original_fut.remove_done_callback(self._parent_done_cb)

    def _done_cb(self, *args, **kwargs):
        try:
            cbs = list(self.done_callbacks)
            for cb in cbs:
                cb(*args, **kwargs)
                self.remove_done_callback(cb)
        finally:
            self.original_fut.remove_done_callback(self._parent_done_cb)

    def _parent_done_cb(self, *args, **kwargs):
        if not self.this_fut.done() and not self.this_fut.cancelled():
            self._done_cb(*args, **kwargs)

    def __repr__(self):
        return "<ChildOfFuture: {0} |:| {1}>".format(repr(self.original_fut), repr(self.this_fut))

    def __await__(self):
        while True:
            if self.original_fut.done() and not self.original_fut.cancelled() and not self.original_fut.exception():
                self.this_fut.cancel()

            if self.this_fut.done():
                if hasattr(self, "waiter"):
                    del self.waiter
                return (yield from self.this_fut)

            if self.original_fut.done():
                if hasattr(self, "waiter"):
                    del self.waiter
                return (yield from self.original_fut)

            if hasattr(self, "waiter"):
                if self.waiter.cancelled() or self.waiter.done():
                    self.waiter = None

            if not getattr(self, "waiter", None):
                self.waiter = asyncio.ensure_future(asyncio.wait([self.original_fut, self.this_fut], return_when=asyncio.FIRST_COMPLETED))

            yield from self.waiter
    __iter__ = __await__

class ThreadToAsyncQueue(object):
    """
    A Queue for requesting data from some thread:

    .. code-block:: python

        class MyQueue(ThreadToAsyncQueue):
            def start_thread(self):
                '''This is called for each thread that is started'''
                my_thread_thing = THING()
                return (my_thread_thing, )

        def onerror(exc):
            # Some unexpected error, do something with it here
            # Like talk to bugsnag or sentry
            # The return value is discarded
            pass

        # If stop_fut is cancelled or has a result, then the queue will stop
        # But the thread will continue until queue.finish() is called
        queue = ThreadToAsyncQueue(stop_fut, 10, onerror)
        await queue.start()

        def action(my_thread_thing):
            '''This runs in one of the threads'''
            return my_thread_thing.stuff()

        await queue.request(action)
        await queue.finish()
    """
    def __init__(self, stop_fut, num_threads, onerror, *args, **kwargs):
        self.loop = asyncio.get_event_loop()
        self.queue = Queue()
        self.futures = {}
        self.onerror = onerror
        self.subiters = []
        self.stop_fut = ChildOfFuture(stop_fut)
        self.num_threads = num_threads

        self.result_queue = asyncio.Queue()
        self.setup(*args, **kwargs)

    def setup(self, *args, **kwargs):
        """Hook for extra setup"""

    async def finish(self):
        """Signal to the tasks to stop at the next available moment"""
        self.stop_fut.cancel()
        await self.result_queue.put(None)

    def start(self, impl=None):
        """Start tasks to listen for requests made with the ``request`` method"""
        ready = []
        for index, _ in enumerate(range(self.num_threads)):
            fut = asyncio.Future()
            ready.append(fut)
            thread = threading.Thread(target=self.listener, args=(fut, impl))
            thread.start()
        async_as_background(self.set_futures())
        return asyncio.gather(*ready)

    def request(self, func):
        """Make a request and get back a future representing the result of that request"""
        key = str(uuid.uuid1())
        fut = asyncio.Future()
        self.futures[key] = fut
        self.queue.put((key, func))
        return fut

    async def set_futures(self):
        """Get results from the result_queue and set that result on the appropriate future"""
        while True:
            res = await self.result_queue.get()
            if self.stop_fut.finished():
                break

            if not res:
                continue

            if type(res) is tuple and len(res) is 3:
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
            self.loop.call_soon_threadsafe(self.result_queue.put_nowait, (key, result, exception))
        except RuntimeError:
            log.error(PhotonsAppError("Failed to put result onto the loop because it was closed", key=key, result=result, exception=exception))

    def listener(self, ready_fut, impl=None):
        """Start the thread!"""
        args = self.start_thread()
        self.loop.call_soon_threadsafe(ready_fut.set_result, True)
        self._listener(impl, args or ())

    def start_thread(self):
        """Hook to return extra args to give to functions when the are requested"""

    def _listener(self, impl, args):
        """Forever, with error catching, get nxt request of the queue and process"""
        while True:
            if self.stop_fut.finished():
                break

            try:
                nxt = self.queue.get(timeout=0.05)
            except Empty:
                continue
            else:
                if self.stop_fut.finished():
                    break

                try:
                    (impl or self.listener_impl)(nxt, *args)
                except KeyboardInterrupt:
                    raise
                except:
                    exc_info = sys.exc_info()
                    log.error(exc_info[1], exc_info=exc_info)
                    self.onerror(exc_info)

    def wrap_request(self, proc, args):
        """Return a function that will perform the work"""
        def wrapped():
            return proc(*args)
        return wrapped

    def listener_impl(self, nxt, *args):
        """Just call out to process"""
        if type(nxt) is tuple and len(nxt) is 2:
            key, proc = nxt
            self.process(key, wraps(proc)(self.wrap_request(proc, args)))
        else:
            error = PhotonsAppError("Unknown item in the queue", got=nxt)
            self.onerror(error)
            log.error(error)
