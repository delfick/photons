# coding: spec

from photons_script.script import Decider, ScriptRunnerIterator

from photons_app.errors import PhotonsAppError, BadRunWithResults
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import asynctest
import mock

describe AsyncTestCase, "Decider":
    async it "takes in a bunch of things":
        getter = mock.Mock(name="getter")
        decider = mock.Mock(name="decider")
        wanted = mock.Mock(name="wanted")
        simplifier = mock.Mock(name="simplifier")

        using = Decider(getter, decider, wanted
            , simplifier = simplifier
            )

        self.assertIs(using.getter, getter)
        self.assertIs(using.decider, decider)
        self.assertIs(using.wanted, wanted)
        self.assertIs(using.simplifier, simplifier)

    describe "Simplified":
        async it "simplifies the getter and returns a clone with result and new simplifier":
            getter = mock.Mock(name="getter")
            decider = mock.Mock(name="decider")
            wanted = mock.Mock(name="wanted")
            simplifier = mock.Mock(name="simplifier")

            using = Decider(getter, decider, wanted
                , simplifier = simplifier
                )

            simple_getter = mock.Mock(name="simple_getter")
            simplifier2 = mock.Mock(name="simplifier2", return_value=simple_getter)

            clone = using.simplified(simplifier2)
            self.assertEqual(clone.__class__, Decider)
            assert clone is not using

            simplifier2.assert_called_once_with(getter, chain=[])

            self.assertIs(clone.getter, simple_getter)
            self.assertIs(clone.simplifier, simplifier2)

            self.assertIs(clone.decider, decider)
            self.assertIs(clone.wanted, wanted)

    describe "Usage":
        async before_each:
            self.getter = mock.Mock(name="getter")
            self.decider = mock.Mock(name="decider")
            self.wanted = mock.Mock(name="wanted")
            self.simplifier = mock.Mock(name="simplifier")

            self.using = Decider(self.getter, self.decider, [self.wanted]
                , simplifier = self.simplifier
                )

        describe "do_getters":
            async it "runs the getters and collects the results by serial for those that match wanted":
                serial1 = "d073d5000000"
                serial2 = "d073d5000001"
                serial3 = "d073d5000002"

                pkt1 = mock.Mock(name="pkt1", serial=serial1)
                pkt1.__or__ = lambda s, o: True

                pkt2 = mock.Mock(name="pkt2", serial=serial2)
                pkt2.__or__ = lambda s, o: True

                pkt3 = mock.Mock(name="pkt3", serial=serial1)
                pkt3.__or__ = lambda s, o: True

                pkt4 = mock.Mock(name="pkt4", serial=serial3)
                pkt4.__or__ = lambda s, o: False

                def aitr(returns):
                    m = asynctest.mock.CoroutineMock(name="run_with")
                    async def run_with(*args, **kwargs):
                        m(*args, **kwargs)
                        for thing in returns:
                            yield thing

                    return m, run_with

                g1 = mock.Mock(name="g1")
                g1_run_with, g1.run_with = aitr([(pkt1, (), ()), (pkt2, (), ())])

                g2 = mock.Mock(name="g2")
                g2_run_with, g2.run_with = aitr([(pkt3, (), ()), (pkt4, (), ())])

                self.getter.__iter__ = lambda s: iter([g1, g2])

                a = mock.Mock(name="a")
                references = mock.Mock(name="references")
                args_for_run = mock.Mock(name="args_for_run")
                error_catcher = mock.Mock(name="error_catcher")

                results = await self.using.do_getters(references, args_for_run, {"a": a}, error_catcher)

                self.assertEqual(results
                    , { serial1: [pkt1, pkt3]
                      , serial2: [pkt2]
                      }
                    )

                g1_run_with.assert_called_once_with(references, args_for_run
                    , error_catcher = error_catcher
                    , a = a
                    )

                g2_run_with.assert_called_once_with(references, args_for_run
                    , error_catcher = error_catcher
                    , a = a
                    )

        describe "transform_got":
            async it "yields messages from transforming got messages using the decider function":
                y1 = mock.Mock(name="y1")
                y2 = mock.Mock(name="y2")
                y3 = mock.Mock(name="y3")
                y4 = mock.Mock(name="y4")
                y5 = mock.Mock(name="y5")

                g1 = mock.Mock(name="g1")
                g2 = mock.Mock(name="g2")
                g3 = mock.Mock(name="g3")
                g4 = mock.Mock(name="g4")
                g5 = mock.Mock(name="g5")

                ref1 = mock.Mock(name="ref1")
                ref2 = mock.Mock(name="ref2")
                ref3 = mock.Mock(name="ref3")
                references = [ref1, ref2, ref3]

                called = []
                def decider(reference, *args, **kwargs):
                    called.append(("decider", reference, args, kwargs))
                    for thing in {ref1: [y1, y2], ref2: [y3, y4, y5]}[reference]:
                        yield thing
                self.decider.side_effect = decider

                res = list(self.using.transform_got({ref1: [g1, g2, g3], ref2: [g4, g5]}, references))
                self.assertEqual(res, [y1, y2, y3, y4, y5])

                self.assertEqual(called
                    , [ ("decider", ref1, (g1, g2, g3), {})
                      , ("decider", ref2, (g4, g5), {})
                      ]
                    )

        describe "send_messages":
            async it "simplifies the messages and calls run_with on them":
                msg1 = mock.Mock(name="msg1")
                msg2 = mock.Mock(name="msg2")
                msg3 = mock.Mock(name="msg3")

                rep1 = mock.Mock(name="rep1")
                rep2 = mock.Mock(name="rep2")
                rep3 = mock.Mock(name="rep3")
                rep4 = mock.Mock(name="rep4")
                rep5 = mock.Mock(name="rep5")

                replies = {
                      msg1: [rep1]
                    , msg2: [rep2, rep3, rep4]
                    , msg3: [rep5]
                    }

                called = []

                class Wrap(object):
                    def __init__(self, msg):
                        self.msg = msg

                    async def run_with(self, *args, **kwargs):
                        called.append((self.msg, "run_with", args, kwargs))
                        for thing in replies[self.msg]:
                            yield thing

                def simplifier(msgs):
                    for msg in msgs:
                        yield Wrap(msg)

                a = mock.Mock(name='a')
                args_for_run = mock.Mock(name="args_for_run")
                error_catcher = mock.Mock(name="error_catcher")

                self.using.simplifier = simplifier
                res = []
                async for info in self.using.send_msgs([msg1, msg2, msg3], args_for_run, {"a": a}, error_catcher):
                    res.append(info)

                self.assertEqual(res, [rep1, rep2, rep3, rep4, rep5])

                self.assertEqual(called
                    , [ (msg1, "run_with", ([], args_for_run), dict(a=a, error_catcher=error_catcher, accept_found=True))
                      , (msg2, "run_with", ([], args_for_run), dict(a=a, error_catcher=error_catcher, accept_found=True))
                      , (msg3, "run_with", ([], args_for_run), dict(a=a, error_catcher=error_catcher, accept_found=True))
                      ]
                    )

        describe "run_with":
            async before_each:
                self.ref1 = mock.Mock(name="ref1")
                self.ref2 = mock.Mock(name="ref2")
                self.called = []

                class Item(object):
                    def __init__(self, thing):
                        self.thing = thing

                    async def run_with(s, *args, **kwargs):
                        self.called.append((s.thing, args, kwargs))
                        try:
                            for thing in s.thing.item_run_with():
                                yield thing
                        except PhotonsAppError as err:
                            kwargs["error_catcher"].append(err)

                class Target(object):
                    def script(s, raw):
                        return ScriptRunnerIterator(list(s.simplify(raw))[0], s)

                    def simplify(s, script_part, chain=None):
                        chain = [] if chain is None else chain

                        if type(script_part) is not list:
                            script_part = [script_part]

                        for p in script_part:
                            if getattr(p, "has_children", False) is True:
                                yield p.simplified(s.simplify, chain + [p.name])
                            else:
                                yield Item(p)

                self.target = Target()

            async it "doesn't raise errors if decider specifies error_catcher":
                error1 = PhotonsAppError("error1")
                self.getter.item_run_with.side_effect = error1

                references = [self.ref1, self.ref2]
                args_for_run = mock.Mock(name="args_for_run")

                errors = []
                script = self.target.script(self.using)
                await script.run_with_all(references, args_for_run, error_catcher=errors)
                self.assertEqual(errors, [error1])

            async it "raises errors if error_catcher gets given anything during getting":
                error1 = PhotonsAppError("error1")
                self.getter.item_run_with.side_effect = error1

                references = [self.ref1, self.ref2]
                args_for_run = mock.Mock(name="args_for_run")

                try:
                    script = self.target.script(self.using)
                    await script.run_with_all(references, args_for_run)
                    assert False, "expected an exception"
                except BadRunWithResults as error:
                    self.assertEqual(error.kwargs["results"], [])
                    self.assertEqual(error.errors, [error1])

            async it "raises errors if error_catcher gets given anything during sending result from decider":
                state1 = mock.Mock(name='state1', serial=self.ref1)
                state1.__or__ = lambda s, o: True
                self.getter.item_run_with.return_value = [(state1, (), ())]

                error2 = PhotonsAppError("failure")

                def decider(reference, state):
                    self.assertIs(state, state1)
                    self.assertIs(reference, self.ref1)
                    msg = mock.Mock(name="msg")
                    msg.item_run_with.side_effect = error2
                    yield msg
                self.decider.side_effect = decider

                references = [self.ref1]
                args_for_run = mock.Mock(name="args_for_run")

                try:
                    script = self.target.script(self.using)
                    await script.run_with_all(references, args_for_run)
                    assert False, "expected an exception"
                except BadRunWithResults as error:
                    self.assertEqual(error.kwargs["results"], [])
                    self.assertEqual(error.errors, [error2])

            async it "collects the results":
                state1 = mock.Mock(name='state1', serial=self.ref1)
                state1.__or__ = lambda s, o: True

                state2 = mock.Mock(name='state2', serial=self.ref2)
                state2.__or__ = lambda s, o: True

                self.getter.item_run_with.return_value = [(state1, (), ()), (state2, (), ())]

                rep1 = mock.Mock(name="rep1")
                rep2 = mock.Mock(name="rep2")

                decidermsg1 = mock.Mock(name="decidermsg1")
                decidermsg1.item_run_with.return_value = [(rep1, (), ())]

                decidermsg2 = mock.Mock(name="decidermsg2")
                decidermsg2.item_run_with.return_value = [(rep2, (), ())]

                def decider(reference, state):
                    yield {self.ref1: decidermsg1, self.ref2: decidermsg2}[reference]
                self.decider.side_effect = decider

                references = [self.ref1, self.ref2]
                args_for_run = mock.Mock(name="args_for_run")

                script = self.target.script(self.using)
                result = await script.run_with_all(references, args_for_run)

                self.assertEqual(result, [(rep1, (), ()), (rep2, (), ())])

                self.assertEqual(self.called
                    , [ (self.getter, ([self.ref1, self.ref2], args_for_run), mock.ANY)
                      , (decidermsg1, ([], args_for_run), mock.ANY)
                      , (decidermsg2, ([], args_for_run), mock.ANY)
                      ]
                    )
