# coding: spec

from photons_transport.target.script import ScriptRunner, ScriptRunnerIterator

from photons_app.errors import PhotonsAppError, BadRunWithResults
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import asyncio
import mock

describe AsyncTestCase, "ScriptRunner":
    async it "takes in script and target":
        script = mock.Mock(name="script")
        target = mock.Mock(name="target")

        runner = ScriptRunner(script, target)

        self.assertIs(runner.script, script)
        self.assertIs(runner.target, target)

    describe "run_with":
        async before_each:
            self.called = []

            self.afr = mock.Mock(name="afr")
            self.run_with_result = mock.Mock(name="run_with_result")

            class FakeScript(object):
                async def run_with(s, *args, **kwargs):
                    self.called.append(("run_with", args, kwargs))
                    return self.run_with_result

            class FakeTarget(object):
                async def args_for_run(s, *args, **kwargs):
                    self.called.append(("args_for_run", args, kwargs))
                    return self.afr

                async def close_args_for_run(s, *args, **kwargs):
                    self.called.append(("close_args_for_run", args, kwargs))

            self.script = FakeScript()
            self.target = FakeTarget()
            self.runner = ScriptRunner(self.script, self.target)

        async it "calls run_with on the script":
            self.assertEqual(self.called, [])

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            args_for_run = mock.NonCallableMock(name="args_for_run", spec=[])

            self.assertIs(await self.runner.run_with(reference, args_for_run=args_for_run, b=a), self.run_with_result)
            self.assertEqual(self.called
                , [ ("run_with", (reference, args_for_run), {"b": a})
                  ]
                )

        async it "creates and closes the afr if none provided":
            self.assertEqual(self.called, [])

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")

            self.assertIs(await self.runner.run_with([reference], b=a), self.run_with_result)
            self.assertEqual(self.called
                , [ ("args_for_run", (), {})
                  , ("run_with", ([reference], self.afr), {"b": a})
                  , ("close_args_for_run", (self.afr, ), {})
                  ]
                )

describe AsyncTestCase, "ScriptRunnerIterator":
    async it "takes in script and target":
        script = mock.Mock(name="script")
        target = mock.Mock(name="target")

        runner = ScriptRunnerIterator(script, target)

        self.assertIs(runner.script, script)
        self.assertIs(runner.target, target)

    async before_each:
        self.called = []

        self.afr = mock.Mock(name="afr")
        self.res1 = mock.Mock(name='res1')
        self.res2 = mock.Mock(name='res2')

        class FakeScript(object):
            async def run_with(s, *args, **kwargs):
                self.called.append(("run_with", args, kwargs))
                yield self.res1
                yield self.res2

        class FakeTarget(object):
            async def args_for_run(s, *args, **kwargs):
                self.called.append(("args_for_run", args, kwargs))
                return self.afr

            async def close_args_for_run(s, *args, **kwargs):
                self.called.append(("close_args_for_run", args, kwargs))

        self.script = FakeScript()
        self.target = FakeTarget()
        self.runner = ScriptRunnerIterator(self.script, self.target)

    describe "run_with":
        async it "calls run_with on the script":
            self.assertEqual(self.called, [])

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            args_for_run = mock.NonCallableMock(name="args_for_run", spec=[])

            found = []
            async for info in self.runner.run_with(reference, args_for_run=args_for_run, b=a):
                found.append(info)

            self.assertEqual(found, [self.res1, self.res2])
            self.assertEqual(self.called
                , [ ("run_with", (reference, args_for_run), {"b": a})
                  ]
                )

        async it "works when references is a list":
            self.assertEqual(self.called, [])

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            args_for_run = mock.NonCallableMock(name="args_for_run", spec=[])

            found = []
            async for info in self.runner.run_with([reference], args_for_run=args_for_run, b=a):
                found.append(info)

            self.assertEqual(found, [self.res1, self.res2])
            self.assertEqual(self.called
                , [ ("run_with", ([reference], args_for_run), {"b": a})
                  ]
                )

        async it "creates and closes the afr if none provided":
            self.assertEqual(self.called, [])

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")

            found = []
            async for info in self.runner.run_with([reference], b=a):
                found.append(info)

            self.assertEqual(found, [self.res1, self.res2])
            self.assertEqual(self.called
                , [ ("args_for_run", (), {})
                  , ("run_with", ([reference], self.afr), {"b": a})
                  , ("close_args_for_run", (self.afr, ), {})
                  ]
                )

    describe "run_with_all":
        async it "calls run_with on the script":
            self.assertEqual(self.called, [])

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            args_for_run = mock.NonCallableMock(name="args_for_run", spec=[])

            found = await self.runner.run_with_all(reference, args_for_run=args_for_run, b=a)

            self.assertEqual(found, [self.res1, self.res2])
            self.assertEqual(self.called
                , [ ("run_with", (reference, args_for_run), {"b": a})
                  ]
                )

        async it "raises BadRunWithResults if we have risen exceptions":
            error1 = PhotonsAppError("failure")

            class FakeScript(object):
                async def run_with(s, *args, **kwargs):
                    self.called.append(("run_with", args, kwargs))
                    yield self.res1
                    raise error1

            runner = ScriptRunnerIterator(FakeScript(), self.target)

            self.assertEqual(self.called, [])

            a = mock.Mock(name="a")
            reference = mock.Mock(name="reference")
            args_for_run = mock.NonCallableMock(name="args_for_run", spec=[])

            try:
                await runner.run_with_all(reference, args_for_run=args_for_run, b=a)
                assert False, "Expected error"
            except BadRunWithResults as error:
                self.assertEqual(error.kwargs["results"], [self.res1])
                self.assertEqual(error.errors, [error1])

            self.assertEqual(self.called
                , [ ("run_with", (reference, args_for_run), {"b": a})
                  ]
                )
