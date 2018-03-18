# coding: spec

from photons_script.script import Pipeline

from photons_app.errors import PhotonsAppError, RunErrors
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from collections import defaultdict
import asyncio
import mock
import time
import uuid

describe AsyncTestCase, "Pipeline":
    async it "specifies has_children as True":
        self.assertIs(Pipeline.has_children, True)

    async it "takes in messages":
        msg1 = mock.Mock(name="msg1")
        msg2 = mock.Mock(name="msg2")
        msg3 = mock.Mock(name="msg3")

        pipeline = Pipeline(msg1, msg2, msg3)
        self.assertEqual(pipeline.children, (msg1, msg2, msg3))

    describe "simplified":
        async it "uses the simplifier on each child and returns a new Pipeline with simplified children":
            result = mock.Mock(name="result")
            FakePipeline = mock.Mock(name="Pipeline", return_value=result)

            c1 = mock.Mock(name="c1")
            c2 = mock.Mock(name="c2")
            c3 = mock.Mock(name="c3")

            o1 = mock.Mock(name="o1")
            o2 = mock.Mock(name="o2")
            o3 = mock.Mock(name="o3")
            o4 = mock.Mock(name="o4")

            action = lambda c, chain: {c1: [o1], c2: [o2], c3: [o3, o4]}[c]
            simplifier = mock.Mock(name="simplifier", side_effect=action)

            spread = mock.Mock(name='spread')
            synchronized = mock.Mock(name="synchronized")
            short_circuit_on_error = mock.Mock(name='short_circuit_on_error')
            with mock.patch("photons_script.script.Pipeline", FakePipeline):
                pipeline = Pipeline(c1, c2, c3
                    , short_circuit_on_error = short_circuit_on_error
                    , synchronized = synchronized
                    , spread = spread
                    )
                self.assertIs(pipeline.simplified(simplifier), result)

            self.assertEqual(simplifier.mock_calls
                , [ mock.call(c1, chain=[])
                  , mock.call(c2, chain=[])
                  , mock.call(c3, chain=[])
                  ]
                )

            FakePipeline.assert_called_once_with(o1, o2, o3, o4
                , spread = spread
                , synchronized = synchronized
                , short_circuit_on_error = short_circuit_on_error
                )

    describe "run_with":
        describe "without references":
            async it "returns a list from all children, in order of the children":
                called = []

                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")
                r5 = mock.Mock(name="r5")

                results1 = [r1, r2]
                results2 = [r3, r4, r5]

                class Child1(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with1", args, kwargs))
                        await asyncio.sleep(0.02)
                        called.append(("after_sleep1", ))
                        for thing in results1:
                            yield thing

                class Child2(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with2", args, kwargs))
                        await asyncio.sleep(0.01)
                        called.append(("after_sleep2", ))
                        for thing in results2:
                            yield thing

                a = mock.Mock(name="a")
                afr = mock.Mock(name="afr")
                pipeline = Pipeline(Child1(), Child2())

                found = []

                async def doit():
                    async for info in pipeline.run_with([], afr, a=a):
                        found.append(info)
                await self.wait_for(doit())
                self.assertEqual(found, [r1, r2, r3, r4, r5])

                self.assertEqual(called
                    , [ ("run_with1", ([], afr), {"a": a, "error_catcher": mock.ANY})
                      , ("after_sleep1", )
                      , ("run_with2", ([], afr), {"a": a, "error_catcher": mock.ANY})
                      , ("after_sleep2", )
                      ]
                    )

            async it "doesn't continue after an error if short_circuit_on_error":
                called = []
                afr = mock.Mock(name="afr")

                error1 = PhotonsAppError("Failure")
                result1 = str(uuid.uuid1())
                result3 = str(uuid.uuid1())

                class Child1(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with1", args, kwargs))
                        yield result1

                class Child2(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with2", args, kwargs))
                        kwargs["error_catcher"](error1)
                        if False:
                            yield None

                class Child3(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with3", args, kwargs))
                        yield result3

                pipeline = Pipeline(Child1(), Child2(), Child3(), short_circuit_on_error=True)

                errors = []
                found = []

                async def doit():
                    async for info in pipeline.run_with([], afr, error_catcher=errors):
                        found.append(info)
                await self.wait_for(doit())
                self.assertEqual(found, [result1])

                self.assertEqual(called
                    , [ ("run_with1", ([], afr), {"error_catcher": mock.ANY})
                      , ("run_with2", ([], afr), {"error_catcher": mock.ANY})
                      ]
                    )
                self.assertEqual(errors, [error1])

            async it "doesn't raise errors if we specify an error_catcher":
                called = []
                afr = mock.Mock(name="afr")

                error1 = PhotonsAppError("Failure")
                result2 = str(uuid.uuid1())

                class Child1(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with1", args, kwargs))
                        kwargs["error_catcher"](error1)
                        if False:
                            yield None

                class Child2(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with2", args, kwargs))
                        yield result2

                pipeline = Pipeline(Child1(), Child2())

                errors = []
                found = []

                async def doit():
                    async for info in pipeline.run_with([], afr, error_catcher=errors):
                        found.append(info)
                await self.wait_for(doit())
                self.assertEqual(found, [result2])

                self.assertEqual(called
                    , [ ("run_with1", ([], afr), {"error_catcher": mock.ANY})
                      , ("run_with2", ([], afr), {"error_catcher": mock.ANY})
                      ]
                    )
                self.assertEqual(errors, [error1])

            async it "raises errors if we don't include an error_catcher":
                called = []
                afr = mock.Mock(name="afr")

                error1 = PhotonsAppError("Failure")
                result2 = str(uuid.uuid1())

                class Child1(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with1", args, kwargs))
                        kwargs["error_catcher"](error1)
                        if False:
                            yield None

                class Child2(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with2", args, kwargs))
                        yield result2

                pipeline = Pipeline(Child1(), Child2())

                found = []

                async def doit():
                    try:
                        async for info in pipeline.run_with([], afr):
                            found.append(info)
                        assert False, "Expected an exception"
                    except RunErrors as err:
                        self.assertIs(err.errors[0], error1)
                        self.assertEqual(len(err.errors), 1)
                await self.wait_for(doit())

                self.assertEqual(found, [result2])
                self.assertEqual(called
                    , [ ("run_with1", ([], afr), {"error_catcher": mock.ANY})
                      , ("run_with2", ([], afr), {"error_catcher": mock.ANY})
                      ]
                    )

        describe "with references":
            async it "can have wait between messages per devie":
                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")

                ref1 = mock.Mock(name="ref1")
                ref2 = mock.Mock(name="ref2")

                class Child(object):
                    def __init__(s, r):
                        s.r = r

                    async def run_with(s, references, *args, **kwargs):
                        yield (time.time(), references, s.r)

                a = mock.Mock(name="a")
                afr = mock.Mock(name="afr")
                pipeline = Pipeline(Child(r1), Child(r2), Child(r3), spread=0.2)
                by_reference_last = {}
                by_reference_timing = defaultdict(list)
                by_reference_msgs = defaultdict(list)

                async def doit():
                    async for info in pipeline.run_with([ref1, ref2], afr):
                        if info[1] not in by_reference_last:
                            by_reference_last[info[1]] = info[0]
                        else:
                            by_reference_timing[info[1]].append(info[0] - by_reference_last[info[1]])
                        by_reference_msgs[info[1]].append(info[2])
                await self.wait_for(doit())

                self.assertEqual(dict(by_reference_msgs)
                    , { ref1: [r1, r2, r3]
                      , ref2: [r1, r2, r3]
                      }
                    )

                for r, timings in by_reference_timing.items():
                    self.assertEqual(len(timings), 2)
                    self.assertGreater(sum(timings) / len(timings), 0.1)

            async it "isn't slowed down by slow references":
                called = []

                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")
                r5 = mock.Mock(name="r5")

                ref1 = mock.Mock(name="ref1")
                ref2 = mock.Mock(name="ref2")

                results1 = {ref1: [r1], ref2: [r2]}
                results2 = {ref1: [r3, r4], ref2: [r5]}

                class Child1(object):
                    async def run_with(s, references, *args, **kwargs):
                        called.append(("run_with1", references, args, kwargs))
                        if references is ref1:
                            await asyncio.sleep(0.1)

                        for r in results1[references]:
                            yield (references, r)

                class Child2(object):
                    async def run_with(s, references, *args, **kwargs):
                        called.append(("run_with2", references, args, kwargs))
                        if references is ref1:
                            await asyncio.sleep(0.1)

                        for r in results2[references]:
                            yield (references, r)

                a = mock.Mock(name="a")
                afr = mock.Mock(name="afr")
                pipeline = Pipeline(Child1(), Child2())
                res = []

                async def doit():
                    async for info in pipeline.run_with([ref1, ref2], afr, a=a):
                        res.append(info)
                await self.wait_for(doit())

                self.assertEqual(res
                    , [ (ref2, r2), (ref2, r5)
                      , (ref1, r1), (ref1, r3), (ref1, r4)
                      ]
                    )

                self.assertEqual(called
                    , [ ("run_with1", ref1, (afr, ), {"a": a, "error_catcher": mock.ANY})
                      , ("run_with1", ref2, (afr, ), {"a": a, "error_catcher": mock.ANY})
                      , ("run_with2", ref2, (afr, ), {"a": a, "error_catcher": mock.ANY})
                      , ("run_with2", ref1, (afr, ), {"a": a, "error_catcher": mock.ANY})
                      ]
                    )

            async it "returns a list of everything that it finds":
                called = []

                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")
                r5 = mock.Mock(name="r5")

                ref1 = mock.Mock(name="ref1")
                ref2 = mock.Mock(name="ref2")

                results1 = [r1, r2]
                results2 = [r3, r4, r5]

                class Child1(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with1", args, kwargs))
                        await asyncio.sleep(0.02)
                        called.append(("after_sleep1", ))
                        for r in results1:
                            yield (args[0], r)

                class Child2(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with2", args, kwargs))
                        await asyncio.sleep(0.01)
                        called.append(("after_sleep2", ))
                        for r in results2:
                            yield (args[0], r)

                a = mock.Mock(name="a")
                afr = mock.Mock(name="afr")
                pipeline = Pipeline(Child1(), Child2())
                res = []

                async def doit():
                    async for info in pipeline.run_with([ref1, ref2], afr, a=a):
                        res.append(info)
                await self.wait_for(doit())

                self.assertEqual(res
                    , [ (ref1, r1), (ref1, r2), (ref2, r1), (ref2, r2)
                      , (ref1, r3), (ref1, r4), (ref1, r5)
                      , (ref2, r3), (ref2, r4), (ref2, r5)
                      ]
                    )

                self.assertEqual(called
                    , [ ("run_with1", (ref1, afr), {"a": a, "error_catcher": mock.ANY})
                      , ("run_with1", (ref2, afr), {"a": a, "error_catcher": mock.ANY})
                      , ("after_sleep1", )
                      , ("run_with2", (ref1, afr), {"a": a, "error_catcher": mock.ANY})
                      , ("after_sleep1", )
                      , ("run_with2", (ref2, afr), {"a": a, "error_catcher": mock.ANY})
                      , ("after_sleep2", )
                      , ("after_sleep2", )
                      ]
                    )

            async it "does not split up references if synchronized is True":
                called = []

                r1 = mock.Mock(name="r1")
                r2 = mock.Mock(name="r2")
                r3 = mock.Mock(name="r3")
                r4 = mock.Mock(name="r4")
                r5 = mock.Mock(name="r5")

                ref1 = mock.Mock(name="ref1")
                ref2 = mock.Mock(name="ref2")

                results1 = [r1, r2]
                results2 = [r3, r4, r5]

                class Child1(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with1", args, kwargs))
                        await asyncio.sleep(0.02)
                        called.append(("after_sleep1", ))
                        for r in results1:
                            yield (args[0], r)

                class Child2(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with2", args, kwargs))
                        await asyncio.sleep(0.01)
                        called.append(("after_sleep2", ))
                        for r in results2:
                            yield (args[0], r)

                a = mock.Mock(name="a")
                afr = mock.Mock(name="afr")
                pipeline = Pipeline(Child1(), Child2(), synchronized=True)
                res = []

                async def doit():
                    async for info in pipeline.run_with([ref1, ref2], afr, a=a):
                        res.append(info)
                await self.wait_for(doit())

                self.assertEqual(res
                    , [ ([ref1, ref2], r1), ([ref1, ref2], r2)
                      , ([ref1, ref2], r3), ([ref1, ref2], r4), ([ref1, ref2], r5)
                      ]
                    )

                self.assertEqual(called
                    , [ ("run_with1", ([ref1, ref2], afr), {"a": a, "error_catcher": mock.ANY})
                      , ("after_sleep1", )
                      , ("run_with2", ([ref1, ref2], afr), {"a": a, "error_catcher": mock.ANY})
                      , ("after_sleep2", )
                      ]
                    )

            async it "raises errors if we don't specify an error catcher":
                called = []
                afr = mock.Mock(name="afr")

                error1 = PhotonsAppError("Failure1")
                error2 = PhotonsAppError("Failure2")

                result1 = mock.Mock(name="result1")

                ref1 = mock.Mock(name="ref1")
                ref2 = mock.Mock(name="ref2")

                class Child1(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with1", args, kwargs))
                        kwargs["error_catcher"]({ref1: error1, ref2: error2}[args[0]])
                        if False:
                            yield None

                class Child2(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with2", args, kwargs))
                        yield result1

                pipeline = Pipeline(Child1(), Child2())

                found = []

                async def doit():
                    try:
                        async for info in pipeline.run_with([ref1, ref2], afr):
                            found.append(info)
                        assert False, "Expected an exception"
                    except RunErrors as err:
                        self.assertEqual(set(err.errors), set([error1, error2]))
                        self.assertEqual(len(err.errors), 2)
                await self.wait_for(doit())

                self.assertEqual(found, [result1, result1])
                self.assertEqual(called
                    , [ ("run_with1", (ref1, afr), {"error_catcher": mock.ANY})
                      , ("run_with2", (ref1, afr), {"error_catcher": mock.ANY})
                      , ("run_with1", (ref2, afr), {"error_catcher": mock.ANY})
                      , ("run_with2", (ref2, afr), {"error_catcher": mock.ANY})
                      ]
                    )

            async it "doesn't raise errors if we provide an error_catcher":
                called = []
                afr = mock.Mock(name="afr")

                error1 = PhotonsAppError("Failure1")
                error2 = PhotonsAppError("Failure2")

                ref1 = mock.Mock(name="ref1")
                ref2 = mock.Mock(name="ref2")

                class Child1(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with1", args, kwargs))
                        kwargs["error_catcher"]({ref1: error1, ref2: error2}[args[0]])
                        if None:
                            yield None

                class Child2(object):
                    async def run_with(s, *args, **kwargs):
                        called.append(("run_with2", args, kwargs))
                        yield str(uuid.uuid1())

                pipeline = Pipeline(Child1(), Child2())

                errors = []
                async for _ in pipeline.run_with([ref1, ref2], afr, error_catcher=errors):
                    pass

                self.assertEqual(called
                    , [ ("run_with1", (ref1, afr), {"error_catcher": mock.ANY})
                      , ("run_with2", (ref1, afr), {"error_catcher": mock.ANY})
                      , ("run_with1", (ref2, afr), {"error_catcher": mock.ANY})
                      , ("run_with2", (ref2, afr), {"error_catcher": mock.ANY})
                      ]
                    )
                self.assertEqual(errors, [error1, error2])
