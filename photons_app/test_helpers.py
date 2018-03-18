from photons_app.errors import PhotonsAppError

from delfick_error import DelfickErrorTestMixin
from asynctest import TestCase as AsyncTestCase
from unittest import TestCase
import asyncio
import mock

class BadTest(PhotonsAppError):
    desc = "bad test"

class FakeScript(object):
    def __init__(self, target, part):
        self.part = part
        self.target = target

    async def run_with(self, *args, **kwargs):
        return await self.target.run_with(self.part, *args, **kwargs)

class FakeScriptIterator(FakeScript):
    async def run_with(self, *args, **kwargs):
        async for info in self.target.run_with(self.part, *args, **kwargs):
            yield info

    async def run_with_all(self, *args, **kwargs):
        msgs = []
        async for msg in self.run_with(*args, **kwargs):
            msgs.append(msg)
        return msgs

class FakeTarget(object):
    def __init__(self, afr_maker=None):
        self.call = -1
        self.afr_maker = afr_maker
        self.expected_run_with = []

    async def args_for_run(self):
        return self.afr_maker()

    async def close_args_for_run(self, afr):
        afr.close()

    def script(self, part):
        return FakeScript(self, part)

    async def run_with(self, *args, **kwargs):
        self.call += 1
        call = mock.call(*args, **kwargs)
        if len(self.expected_run_with) < self.call:
            raise BadTest("Got an extra call to the target", got=repr(call))

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
                            print("\tGOT : {0}".format(c.payload.__class__))
                            print("\tWANT: {0}".format(w.payload.__class__))
                            if c.payload.__class__ == w.payload.__class__:
                                dictc = dict(c)
                                dictw = dict(w)
                                for k, v in dictc.items():
                                    if k not in dictw:
                                        print("\t\tGot key not in wanted: {0}".format(k))
                                    elif v != dictw[k]:
                                        print("\t\tkey {0} | got {1} | want {2}".format(k, v, dictw[k]))

                                for k in dictw:
                                    if k not in dictc:
                                        print("\t\tGot key in wanted but not in what we got: {0}".format(k))
                        else:
                            print("\tGOT : {0}".format(c))
                            print("\tWANT: {0}".format(w))

                ckwargs = call[2]
                wkwargs = wanted[2]
                if ckwargs != wkwargs:
                    print("\tKWARGS DIFFERENT")
                    print("\tGOT : {0}".format(ckwargs))
                    print("\tWANT: {0}".format(wkwargs))

                raise

        ret = self.expected_run_with[self.call][1]
        if isinstance(ret, Exception):
            raise ret
        return ret

    def expect_call(self, call, result):
        self.expected_run_with.append((call, result))

class FakeTargetIterator(FakeTarget):
    def script(self, part):
        return FakeScriptIterator(self, part)

    async def run_with(self, *args, **kwargs):
        for thing in await super(FakeTargetIterator, self).run_with(*args, **kwargs):
            yield thing

class TestCase(TestCase, DelfickErrorTestMixin):
    pass

class AsyncTestCase(AsyncTestCase, DelfickErrorTestMixin):
    async def wait_for(self, fut, timeout=1):
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError as error:
            assert False, "Failed to wait for future before timeout: {0}".format(error)
