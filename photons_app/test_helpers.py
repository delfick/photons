from photons_app.errors import PhotonsAppError

from delfick_error import DelfickErrorTestMixin
from asynctest import TestCase as AsyncTestCase
from collections import defaultdict
from unittest import TestCase
from unittest import mock
import asyncio

class BadTest(PhotonsAppError):
    desc = "bad test"

class FakeScript(object):
    def __init__(self, target, part):
        self.part = part
        self.target = target

    async def run_with(self, *args, **kwargs):
        async for info in self.target.run_with(self.part, *args, **kwargs):
            yield info

    async def run_with_all(self, *args, **kwargs):
        msgs = []
        async for msg in self.run_with(*args, **kwargs):
            msgs.append(msg)
        return msgs

def print_packet_difference(one, two):
    if one != two:
        print("\tGOT : {0}".format(one.payload.__class__))
        print("\tWANT: {0}".format(two.payload.__class__))
        if one.payload.__class__ == two.payload.__class__:
            dictc = dict(one)
            dictw = dict(two)
            for k, v in dictc.items():
                if k not in dictw:
                    print("\t\tGot key not in wanted: {0}".format(k))
                elif v != dictw[k]:
                    print("\t\tkey {0} | got {1} | want {2}".format(k, v, dictw[k]))

            for k in dictw:
                if k not in dictc:
                    print("\t\tGot key in wanted but not in what we got: {0}".format(k))

class FakeTarget(object):
    def __init__(self, afr_maker=None):
        self.call = -1
        self.afr_maker = afr_maker
        self.expected_run_with = []

    async def args_for_run(self):
        return self.afr_maker()

    async def close_args_for_run(self, afr):
        afr.close()

    def session(self):
        info = {}

        class Session:
            async def __aenter__(s):
                afr = info["afr"] = await self.args_for_run()
                return afr

            async def __aexit__(s, exc_type, exc, tb):
                if "afr" in info:
                    await self.close_args_for_run(info["afr"])

        return Session()

    def script(self, part):
        return FakeScript(self, part)

    async def run_with(self, *args, **kwargs):
        self.call += 1
        call = mock.call(*args, **kwargs)

        def add_error(e, do_raise=True):
            if "error_catcher" in kwargs:
                if type(kwargs["error_catcher"]) is list:
                    kwargs["error_catcher"].append(e)
                else:
                    kwargs["error_catcher"](e)
                return True
            else:
                if do_raise:
                    raise e

        if len(self.expected_run_with) < self.call:
            add_error(BadTest("Got an extra call to the target", got=repr(call)))

        if self.expected_run_with[self.call][0] != call:
            try:
                TestCase().assertEqual(call, self.expected_run_with[self.call][0])
            except AssertionError as error:
                print("---- EXPECTED DIFFERENT CALL for call {0} ----".format(self.call))
                wanted = self.expected_run_with[self.call][0]

                cargs = call[1]
                wargs = wanted[1]
                for i, (c, w) in enumerate(zip(cargs, wargs)):
                    if c != w:
                        print("\tDIFFERENT: item {0}".format(i))

                        if hasattr(c, "pack") and hasattr(w, "pack"):
                            print_packet_difference(c, w)
                        else:
                            print("\tGOT : {0}".format(c))
                            print("\tWANT: {0}".format(w))

                ckwargs = call[2]
                wkwargs = wanted[2]
                if ckwargs != wkwargs:
                    print("\tKWARGS DIFFERENT")
                    print("\tGOT : {0}".format(ckwargs))
                    print("\tWANT: {0}".format(wkwargs))

                if not add_error(error):
                    raise

        ret = self.expected_run_with[self.call][1]
        if isinstance(ret, Exception):
            add_error(ret)
            raise ret
        else:
            for thing in ret:
                yield thing

    def expect_call(self, call, result):
        self.expected_run_with.append((call, result))

class TestCase(TestCase, DelfickErrorTestMixin):
    pass

class AsyncTestCase(AsyncTestCase, DelfickErrorTestMixin):
    async def wait_for(self, fut, timeout=1):
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError as error:
            assert False, "Failed to wait for future before timeout: {0}".format(error)

def with_timeout(func):
    """
    A decorator that returns an async function that runs the original function
    with a timeout

    It assumes you are decorating a method on a class with a ``wait_for`` method

    .. code-block:: python

        from photons_app.test_helpers import AsyncTestCase, with_timeout

        import asyncio

        class TestSomething(AsyncTestCase):
            @with_timeout
            async def test_waiting(self):
                # This will assert False cause the function takes too long
                await asyncio.sleep(20)
    """
    async def test(s):
        await s.wait_for(func(s))
    test.__name__ = func.__name__
    return test

def assertFutCallbacks(fut, *cbs):
    callbacks = fut._callbacks

    try:
        from contextvars import Context
    except ImportError:
        Context = None

    if not cbs:
        if Context is not None:
            if callbacks:
                assert len(callbacks) == 1, f"Expect only one context callback: got {callbacks}"
                assert isinstance(callbacks[0], Context), f"Expected just a context callback: got {callbacks}"
        else:
            assert callbacks == [], f"Expected no callbacks, got {callbacks}"

        return

    if not callbacks:
        assert False, f"expected callbacks, got {callbacks}"

    counts = defaultdict(lambda: 0)
    expected = defaultdict(lambda: 0)

    for cb in callbacks:
        if type(cb) is tuple:
            if len(cb) == 2 and Context and isinstance(cb[1], Context):
                cb = cb[0]
            else:
                assert False, f"Got a tuple instead of a callback, {cb} in {callbacks}"

        if not Context or not isinstance(cb, Context):
            counts[cb] += 1

    for cb in cbs:
        expected[cb] += 1

    for cb in cbs:
        msg = f"Expected {expected[cb]} instances of {cb}, got {counts[cb]} in {callbacks}"
        assert counts[cb] == expected[cb], msg
