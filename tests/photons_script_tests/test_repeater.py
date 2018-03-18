# coding: spec

from photons_script.script import Repeater

from photons_app.errors import PhotonsAppError, RunErrors
from photons_app.test_helpers import AsyncTestCase
from photons_app.special import SpecialReference

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from input_algorithms import spec_base as sb
from collections import defaultdict
import asynctest
import asyncio
import mock
import time
import uuid

describe AsyncTestCase, "Repeater":
    async it "specifies has_children as True":
        self.assertIs(Repeater.has_children, True)

    async it "takes in a message and some options":
        msg = mock.Mock(name="msg")
        min_loop_time = mock.Mock(name='min_loop_time')
        on_done_loop = mock.Mock(name="on_done_loop")

        repeater = Repeater(msg, min_loop_time=min_loop_time, on_done_loop=on_done_loop)
        self.assertIs(repeater.msg, msg)
        self.assertIs(repeater.min_loop_time, min_loop_time)
        self.assertIs(repeater.on_done_loop, on_done_loop)

    async it "has some defaults":
        msg = mock.Mock(name="msg")

        repeater = Repeater(msg)
        self.assertIs(repeater.msg, msg)
        self.assertIs(repeater.min_loop_time, 30)
        self.assertIs(repeater.on_done_loop, None)

    describe "simplified":
        async it "uses the simplifier on the msg and returns a new Repeater with simplified msg":
            result = mock.Mock(name="result")
            FakeRepeater = mock.Mock(name="Repeater", return_value=result)

            child = mock.Mock(name="child")
            simplified = mock.Mock(name="simplified")

            action = lambda c, chain: {child: [simplified]}[c]
            simplifier = mock.Mock(name="simplifier", side_effect=action)

            min_loop_time = mock.Mock(name='min_loop_time')
            on_done_loop = asynctest.mock.CoroutineMock(name="on_done_loop")
            with mock.patch("photons_script.script.Repeater", FakeRepeater):
                repeater = Repeater(child, min_loop_time=min_loop_time, on_done_loop=on_done_loop)
                self.assertIs(repeater.simplified(simplifier), result)

            simplifier.assert_called_once_with(child, chain=[])
            FakeRepeater.assert_called_once_with([simplified], min_loop_time=min_loop_time, on_done_loop=on_done_loop)

    describe "run_with":
        async it "complains if error_catcher isn't a callable":
            msg = mock.Mock(name='msg')
            repeater = Repeater([msg])

            afr = mock.Mock(name="afr")
            references = mock.Mock(name='references')

            for ec in (None, [], sb.NotSpecified):
                with self.fuzzyAssertRaisesError(PhotonsAppError, "error_catcher must be specified as a callable when Repeater is used"):
                    async def doit():
                        kwargs = {}
                        if ec is not sb.NotSpecified:
                            kwargs["error_catcher"] = ec
                        async for _ in repeater.run_with(references, afr, **kwargs):
                            pass
                    await self.wait_for(doit())

        async it "repeatedly calls the msg":
            called = []

            r1 = mock.Mock(name="r1")
            r2 = mock.Mock(name="r2")
            r3 = mock.Mock(name="r3")
            r4 = mock.Mock(name="r4")
            r5 = mock.Mock(name="r5")
            r6 = mock.Mock(name="r6")

            results = [[r1, r2], [r3, r4], [r5, r6]]

            timings = {'last': None, "gaps": []}

            class Child(object):
                async def run_with(s, *args, **kwargs):
                    if timings['last'] is None:
                        timings['last'] = time.time()
                    else:
                        timings['gaps'].append(time.time() - timings['last'])

                    called.append(("run_with", args, kwargs))
                    for thing in results.pop(0):
                        yield thing

            a = mock.Mock(name="a")
            afr = mock.Mock(name="afr")

            def on_done_loop():
                called.append("done_loop")
            on_done_loop = asynctest.mock.CoroutineMock(name="on_done_loop", side_effect=on_done_loop)
            repeater = Repeater([Child()], min_loop_time=0.2, on_done_loop=on_done_loop)

            resets = []

            class Finder(SpecialReference):
                def reset(s):
                    resets.append(True)

            found = []
            references = Finder()
            error_catcher = mock.Mock(name='error_catcher')

            async def doit():
                async for info in repeater.run_with(references, afr, a=a, error_catcher=error_catcher):
                    found.append(info)
                    if len(found) == 6:
                        break
            await self.wait_for(doit())
            self.assertEqual(found, [r1, r2, r3, r4, r5, r6])

            self.assertEqual(called
                , [ ("run_with", (references, afr), {"a": a, "error_catcher": error_catcher})
                  , "done_loop"
                  , ("run_with", (references, afr), {"a": a, "error_catcher": error_catcher})
                  , "done_loop"
                  , ("run_with", (references, afr), {"a": a, "error_catcher": error_catcher})
                  ]
                )

            self.assertEqual(len(timings["gaps"]), 2)
            self.assertGreater(sum(timings["gaps"]) / 2, 0.1)
            self.assertEqual(resets, [True, True])

        async it "works with non special reference":
            called = []

            r1 = mock.Mock(name="r1")
            r2 = mock.Mock(name="r2")
            r3 = mock.Mock(name="r3")
            r4 = mock.Mock(name="r4")

            ref1 = mock.Mock(name="ref1")
            ref2 = mock.Mock(name="ref2")

            results = [[r1, r2], [r3, r4]]

            timings = {'last': None, "gaps": []}

            class Child(object):
                async def run_with(s, *args, **kwargs):
                    if timings['last'] is None:
                        timings['last'] = time.time()
                    else:
                        timings['gaps'].append(time.time() - timings['last'])

                    called.append(("run_with", args, kwargs))
                    for thing in results.pop(0):
                        yield thing

            a = mock.Mock(name="a")
            afr = mock.Mock(name="afr")
            repeater = Repeater([Child()], min_loop_time=0.2)

            found = []
            references = [ref1, ref2]
            error_catcher = mock.Mock(name='error_catcher')

            async def doit():
                async for info in repeater.run_with(references, afr, a=a, error_catcher=error_catcher):
                    found.append(info)
                    if len(found) == 4:
                        break
            await self.wait_for(doit())
            self.assertEqual(found, [r1, r2, r3, r4])

            self.assertEqual(called
                , [ ("run_with", (references, afr), {"a": a, "error_catcher": error_catcher})
                  , ("run_with", (references, afr), {"a": a, "error_catcher": error_catcher})
                  ]
                )

            self.assertEqual(len(timings["gaps"]), 1)
            self.assertGreater(timings["gaps"][0], 0.1)
