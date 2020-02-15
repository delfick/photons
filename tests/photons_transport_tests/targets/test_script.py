# coding: spec

from photons_transport.targets.script import AFRWrapper, ScriptRunner

from photons_app.errors import PhotonsAppError, BadRunWithResults
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from delfick_project.norms import sb
from unittest import mock
import asynctest
import asyncio


class Sem:
    def __init__(self, limit):
        self.limit = limit

    def __eq__(self, other):
        return isinstance(other, asyncio.Semaphore) and other._value == self.limit


describe AsyncTestCase, "AFRWrapper":
    async before_each:
        self.called = []

        self.afr = mock.Mock(name="afr")

        self.res1 = mock.Mock(name="res1")
        self.res2 = mock.Mock(name="res2")

        class FakeScript:
            async def run_with(s, *args, **kwargs):
                self.called.append(("run_with", args, kwargs))
                yield self.res1
                yield self.res2

        class FakeTarget:
            async def args_for_run(s, *args, **kwargs):
                self.called.append(("args_for_run", args, kwargs))
                return self.afr

            async def close_args_for_run(s, *args, **kwargs):
                self.called.append(("close_args_for_run", args, kwargs))

        self.script = FakeScript()
        self.target = FakeTarget()

    async it "does not impose a limit if limit is given as None":
        assert self.called == []

        a = mock.Mock(name="a")
        kwargs = {"b": a, "limit": None}
        args_for_run = mock.NonCallableMock(name="args_for_run")

        async with AFRWrapper(self.target, args_for_run, kwargs) as afr:
            assert afr is args_for_run

        assert kwargs == {"b": a, "limit": None}
        assert self.called == []

    async it "turns limit into a semaphore":
        a = mock.Mock(name="a")
        kwargs = {"b": a, "limit": 50}
        args_for_run = mock.NonCallableMock(name="args_for_run")

        async with AFRWrapper(self.target, args_for_run, kwargs) as afr:
            assert afr is args_for_run

        assert kwargs == {"b": a, "limit": Sem(50)}
        assert self.called == []

    async it "passes on limit if it has acquire":
        a = mock.Mock(name="a")
        limit = mock.NonCallableMock(name="limit", spec=["acquire"])
        kwargs = {"b": a, "limit": limit}
        args_for_run = mock.NonCallableMock(name="args_for_run")

        async with AFRWrapper(self.target, args_for_run, kwargs) as afr:
            assert afr is args_for_run

        assert kwargs == {"b": a, "limit": limit}
        assert self.called == []

    async it "passes on limit if it is already a Semaphore":
        a = mock.Mock(name="a")
        limit = asyncio.Semaphore(1)
        kwargs = {"b": a, "limit": limit}
        args_for_run = mock.NonCallableMock(name="args_for_run")

        async with AFRWrapper(self.target, args_for_run, kwargs) as afr:
            assert afr is args_for_run

        assert kwargs == {"b": a, "limit": limit}
        assert self.called == []

    async it "creates and closes the afr if none provided":
        a = mock.Mock(name="a")
        limit = asyncio.Semaphore(1)
        kwargs = {"b": a}

        async with AFRWrapper(self.target, sb.NotSpecified, kwargs) as afr:
            assert afr is self.afr
            self.called.append(("middle", kwargs))

        assert self.called == [
                ("args_for_run", (), {}),
                ("middle", {"b": a, "limit": Sem(30)}),
                ("close_args_for_run", (self.afr,), {}),
            ]

describe AsyncTestCase, "ScriptRunner":
    async before_each:
        self.called = []

        self.res1 = mock.Mock(name="res1")
        self.res2 = mock.Mock(name="res2")

        class FakeScript:
            async def run_with(s, *args, **kwargs):
                self.called.append(("run_with", args, kwargs))
                yield self.res1
                yield self.res2

        self.script = FakeScript()
        self.target = mock.Mock(name="target", spec=[])
        self.runner = ScriptRunner(self.script, self.target)

        self.afr = mock.Mock(name="afr")

        class FakeTarget:
            async def args_for_run(s, *args, **kwargs):
                self.called.append(("args_for_run", args, kwargs))
                return self.afr

            async def close_args_for_run(s, *args, **kwargs):
                self.called.append(("close_args_for_run", args, kwargs))

        self.FakeTarget = FakeTarget

    async it "takes in script and target":
        script = mock.Mock(name="script")
        target = mock.Mock(name="target")

        runner = ScriptRunner(script, target)

        assert runner.script is script
        assert runner.target is target

    describe "run_with":
        async it "does nothing if no script":
            runner = ScriptRunner(None, mock.NonCallableMock(name="target"))
            reference = mock.Mock(name="reference")

            got = []
            async for info in runner.run_with(reference):
                got.append(info)

            assert got == []

        async it "calls run_with on the script":
            assert self.called == []

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            args_for_run = mock.NonCallableMock(name="args_for_run", spec=[])

            found = []
            async for info in self.runner.run_with(reference, args_for_run=args_for_run, b=a):
                found.append(info)

            assert found == [self.res1, self.res2]
            assert self.called == [("run_with", (reference, args_for_run), {"b": a, "limit": Sem(30)})]

        async it "can create an args_for_run":
            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")

            self.runner.target = self.FakeTarget()

            found = []
            async for info in self.runner.run_with(reference, b=a):
                found.append(info)

            assert found == [self.res1, self.res2]
            assert self.called == [
                    ("args_for_run", (), {}),
                    ("run_with", (reference, self.afr), {"b": a, "limit": Sem(30)}),
                    ("close_args_for_run", (self.afr,), {}),
                ]

    describe "run_with_all":
        async it "calls run_with on the script":
            assert self.called == []

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            args_for_run = mock.NonCallableMock(name="args_for_run", spec=[])

            found = await self.runner.run_with_all(reference, args_for_run=args_for_run, b=a)

            assert found == [self.res1, self.res2]
            assert self.called == [("run_with", (reference, args_for_run), {"b": a, "limit": Sem(30)})]

        async it "raises BadRunWithResults if we have risen exceptions":
            error1 = PhotonsAppError("failure")

            class FakeScript:
                async def run_with(s, *args, **kwargs):
                    self.called.append(("run_with", args, kwargs))
                    yield self.res1
                    raise error1

            runner = ScriptRunner(FakeScript(), self.FakeTarget())

            assert self.called == []

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")

            try:
                await runner.run_with_all(reference, b=a)
                assert False, "Expected error"
            except BadRunWithResults as error:
                # self.assertEqual(error.kwargs["results"], [self.res1])
                # self.assertEqual(error.errors, [error1])
                pass

            assert self.called == [
                    ("args_for_run", (), {}),
                    ("run_with", (reference, self.afr), {"b": a, "limit": Sem(30)}),
                    ("close_args_for_run", (self.afr,), {}),
                ]
