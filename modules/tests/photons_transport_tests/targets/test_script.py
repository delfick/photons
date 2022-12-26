# coding: spec

import asyncio
from unittest import mock

import pytest
from delfick_project.norms import sb
from photons_app import helpers as hp
from photons_app.errors import BadRunWithResults, PhotonsAppError
from photons_transport.targets.script import ScriptRunner, sender_wrapper


class Sem:
    def __init__(self, limit):
        self.limit = limit

    def __eq__(self, other):
        return isinstance(other, asyncio.Semaphore) and other._value == self.limit


describe "sender_wrapper":

    @pytest.fixture()
    def V(self):
        class V:
            called = []

            sender = mock.Mock(name="sender")

            res1 = mock.Mock(name="res1")
            res2 = mock.Mock(name="res2")

            @hp.memoized_property
            def script(s):
                class FakeScript:
                    async def run(fs, *args, **kwargs):
                        s.called.append(("run", args, kwargs))
                        yield s.res1
                        yield s.res2

                return FakeScript()

            @hp.memoized_property
            def target(s):
                class FakeTarget:
                    async def make_sender(fs, *args, **kwargs):
                        s.called.append(("make_sender", args, kwargs))
                        return s.sender

                    async def close_sender(fs, *args, **kwargs):
                        s.called.append(("close_sender", args, kwargs))

                return FakeTarget()

        return V()

    async it "does not impose a limit if limit is given as None", V:
        assert V.called == []

        a = mock.Mock(name="a")
        kwargs = {"b": a, "limit": None}
        sender = mock.NonCallableMock(name="sender")

        async with sender_wrapper(V.target, sender, kwargs) as result:
            assert result is sender

        assert kwargs == {"b": a, "limit": None}
        assert V.called == []

    async it "turns limit into a semaphore", V:
        a = mock.Mock(name="a")
        kwargs = {"b": a, "limit": 50}
        sender = mock.NonCallableMock(name="sender")

        async with sender_wrapper(V.target, sender, kwargs) as result:
            assert result is sender

        assert kwargs == {"b": a, "limit": Sem(50)}
        assert V.called == []

    async it "passes on limit if it has acquire", V:
        a = mock.Mock(name="a")
        limit = mock.NonCallableMock(name="limit", spec=["acquire"])
        kwargs = {"b": a, "limit": limit}
        sender = mock.NonCallableMock(name="sender")

        async with sender_wrapper(V.target, sender, kwargs) as result:
            assert result is sender

        assert kwargs == {"b": a, "limit": limit}
        assert V.called == []

    async it "passes on limit if it is already a Semaphore", V:
        a = mock.Mock(name="a")
        limit = asyncio.Semaphore(1)
        kwargs = {"b": a, "limit": limit}
        sender = mock.NonCallableMock(name="sender")

        async with sender_wrapper(V.target, sender, kwargs) as result:
            assert result is sender

        assert kwargs == {"b": a, "limit": limit}
        assert V.called == []

    async it "creates and closes the sender if none provided", V:
        a = mock.Mock(name="a")
        kwargs = {"b": a}

        async with sender_wrapper(V.target, sb.NotSpecified, kwargs) as sender:
            assert sender is V.sender
            V.called.append(("middle", kwargs))

        assert V.called == [
            ("make_sender", (), {}),
            ("middle", {"b": a, "limit": Sem(30)}),
            ("close_sender", (V.sender,), {}),
        ]

describe "ScriptRunner":

    @pytest.fixture()
    def V(self):
        class V:
            res1 = mock.Mock(name="res1")
            res2 = mock.Mock(name="res2")
            sender = mock.Mock(name="sender")
            called = []
            target = mock.Mock(name="target", spec=[])

            @hp.memoized_property
            def script(s):
                class FakeScript:
                    async def run(fs, *args, **kwargs):
                        s.called.append(("run", args, kwargs))
                        yield s.res1
                        yield s.res2

                return FakeScript()

            @hp.memoized_property
            def runner(s):
                return ScriptRunner(s.script, s.target)

            @hp.memoized_property
            def FakeTarget(s):
                class FakeTarget:
                    async def make_sender(fs, *args, **kwargs):
                        s.called.append(("make_sender", args, kwargs))
                        return s.sender

                    async def close_sender(fs, *args, **kwargs):
                        s.called.append(("close_sender", args, kwargs))

                return FakeTarget

        return V()

    async it "takes in script and target":
        script = mock.Mock(name="script")
        target = mock.Mock(name="target")

        runner = ScriptRunner(script, target)

        assert runner.script is script
        assert runner.target is target

    describe "run":
        async it "does nothing if no script":
            runner = ScriptRunner(None, mock.NonCallableMock(name="target"))
            reference = mock.Mock(name="reference")

            got = []
            async for info in runner.run(reference):
                got.append(info)

            assert got == []

        async it "calls run on the script", V:
            assert V.called == []

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            sender = mock.NonCallableMock(name="sender", spec=[])

            found = []
            async for info in V.runner.run(reference, sender, b=a):
                found.append(info)

            assert found == [V.res1, V.res2]
            assert V.called == [("run", (reference, sender), {"b": a, "limit": Sem(30)})]

        async it "can create a sender", V:
            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")

            V.runner.target = V.FakeTarget()

            found = []
            async for info in V.runner.run(reference, b=a):
                found.append(info)

            assert found == [V.res1, V.res2]
            assert V.called == [
                ("make_sender", (), {}),
                ("run", (reference, V.sender), {"b": a, "limit": Sem(30)}),
                ("close_sender", (V.sender,), {}),
            ]

    describe "run_all":
        async it "calls run on the script", V:
            assert V.called == []

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            sender = mock.NonCallableMock(name="sender", spec=[])

            found = await V.runner.run_all(reference, sender, b=a)

            assert found == [V.res1, V.res2]
            assert V.called == [("run", (reference, sender), {"b": a, "limit": Sem(30)})]

        async it "raises BadRunWithResults if we have risen exceptions", V:
            error1 = PhotonsAppError("failure")

            class FakeScript:
                async def run(s, *args, **kwargs):
                    V.called.append(("run", args, kwargs))
                    yield V.res1
                    raise error1

            runner = ScriptRunner(FakeScript(), V.FakeTarget())

            assert V.called == []

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")

            try:
                await runner.run_all(reference, b=a)
                assert False, "Expected error"
            except BadRunWithResults as error:
                assert error.kwargs["results"] == [V.res1]
                assert error.errors == [error1]

            assert V.called == [
                ("make_sender", (), {}),
                ("run", (reference, V.sender), {"b": a, "limit": Sem(30)}),
                ("close_sender", (V.sender,), {}),
            ]
