# coding: spec

from photons_transport.base.target import TransportTarget
from photons_transport.base.script import InvalidScript

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.test_helpers import AsyncTestCase

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from unittest import mock
import asynctest
import binascii

describe AsyncTestCase, "TransportTarget":
    describe "create":
        async it "works":
            protocol_register = mock.Mock(name="protocol_register")
            final_future = mock.Mock(name="final_future")
            config = {
                  "protocol_register": protocol_register
                , "final_future": final_future
                }

            class T(TransportTarget):
                one = dictobj.Field(sb.integer_spec)

            t = T.create(config, {"one": 20})

            self.assertIs(t.protocol_register, protocol_register)
            self.assertIs(t.final_future, final_future)
            self.assertEqual(t.default_broadcast, "255.255.255.255")
            self.assertEqual(t.one, 20)

    describe "normalise":
        async it "gets protocol_register and final_fut from the meta":
            protocol_register = mock.Mock(name="protocol_register")
            final_future = mock.Mock(name="final_future")
            config = {
                  "protocol_register": protocol_register
                , "final_future": final_future
                }
            meta = Meta(config, []).at("transport")

            spec = TransportTarget.FieldSpec(formatter=MergedOptionStringFormatter)
            t = spec.normalise(meta, {})

            self.assertIs(t.protocol_register, protocol_register)
            self.assertIs(t.final_future, final_future)
            self.assertEqual(t.default_broadcast, "255.255.255.255")

    describe "Usage":
        async before_each:
            self.protocol_register = mock.Mock(name="protocol_register")
            self.final_future = mock.Mock(name="final_future")
            self.item_kls = mock.Mock(name="item_kls")
            self.bridge_kls = mock.Mock(name="bridge_kls")

            class Transport(TransportTarget):
                item_kls = lambda s: self.item_kls
                bridge_kls = lambda s: self.bridge_kls

            config = {
                  "protocol_register": self.protocol_register
                , "final_future": self.final_future
                }
            meta = Meta(config, []).at("target")
            spec = Transport.FieldSpec(formatter=MergedOptionStringFormatter)
            self.target = spec.normalise(meta, {})

        describe "script":
            async it "returns us a ScriptRunner with simplified input":
                raw = mock.Mock(name="raw")
                simplified = mock.Mock(name="simpified")
                simplify = mock.Mock(name="simplify", return_value=[simplified])

                res = mock.Mock(name="res")
                FakeScriptRunner = mock.Mock(name="FakeScriptRunner", return_value=res)

                with mock.patch.object(self.target, "simplify", simplify):
                    with mock.patch("photons_transport.base.target.ScriptRunner", FakeScriptRunner):
                        self.assertIs(self.target.script(raw), res)

                simplify.assert_called_with(raw)
                FakeScriptRunner.assert_called_once_with(simplified, target=self.target)

        describe "args_for_run":
            async it "creates the bridge_kls and calls start on it":
                bridge = mock.Mock(name="bridge")
                bridge.start = asynctest.mock.CoroutineMock(name="start")
                self.bridge_kls.return_value = bridge

                ret = await self.target.args_for_run()
                self.assertIs(ret, bridge)

                self.bridge_kls.assert_called_once_with(self.final_future, self.target
                    , protocol_register=self.protocol_register, default_broadcast="255.255.255.255"
                    )

                bridge.start.assert_called_with()

        describe "close_args_for_run":
            async it "just calls finish on the args_for_run":
                args_for_run = mock.Mock(name="args_for_run")
                args_for_run.finish = asynctest.mock.CoroutineMock(name="finish")
                await self.target.close_args_for_run(args_for_run)
                args_for_run.finish.assert_called_once_with()

        describe "session":
            async it "creates and closes an args_for_run":
                afr = mock.Mock(name="afr")
                args_for_run = asynctest.mock.CoroutineMock(name="args_for_run", return_value=afr)
                close_args_for_run = asynctest.mock.CoroutineMock(name="close_args_for_run")

                args_for_run_patch = mock.patch.object(self.target, "args_for_run", args_for_run)
                close_args_for_run_patch = mock.patch.object(self.target, "close_args_for_run", close_args_for_run)

                with args_for_run_patch, close_args_for_run_patch:
                    async with self.target.session() as a:
                        self.assertIs(a, afr)
                        args_for_run.assert_called_once_with()
                        self.assertEqual(len(close_args_for_run.mock_calls), 0)

                    args_for_run.assert_called_once_with()
                    close_args_for_run.assert_called_once_with(afr)

        describe "simplify":
            async it "uses part as is if it already has a run_with on it":
                part = mock.Mock(name="part", spec=["run_with"])
                self.assertEqual(list(self.target.simplify(part)), [part])

            async it "simplifies items that have a simplified method":
                simplified = mock.Mock(name="simplified", spec=[])
                part = mock.Mock(name="part", spec=["simplified"])
                part.simplified.return_value = simplified

                res = mock.Mock(name="res")
                self.item_kls.return_value = res

                self.assertEqual(list(self.target.simplify(part)), [res])

                part.simplified.assert_called_once_with(self.target.simplify)
                self.item_kls.assert_called_once_with([simplified])

            async it "splits out items into groups with pack and without and only item_kls for groups with pack":
                part11 = mock.Mock(name="part11", spec=[])
                part12 = mock.Mock(name="part12", spec=[])
                part13 = mock.Mock(name="part13", spec=[])

                part2 = mock.Mock(name="part2", spec=['simplified'])
                part2simplified = mock.Mock(name="part2simplified", spec=["run_with"])
                part2.simplified.return_value = part2simplified

                part31 = mock.Mock(name="part31", spec=[])
                part32 = mock.Mock(name="part32", spec=[])

                res1 = mock.Mock(name="res1")
                res2 = mock.Mock(name="res2")

                def item_kls_init(buf):
                    if buf == [part11, part12, part13]:
                        return res1
                    elif buf == [part31, part32]:
                        return res2
                    else:
                        assert False, "Unknown args to item_kls, {0}".format(buf)
                self.item_kls.side_effect = item_kls_init

                res = list(self.target.simplify([part11, part12, part13, part2, part31, part32]))
                self.assertEqual(res, [res1, part2simplified, res2])

                part2.simplified.assert_called_once_with(self.target.simplify)

                self.assertEqual(self.item_kls.mock_calls
                    , [ mock.call([part11, part12, part13])
                      , mock.call([part31, part32])
                      ]
                    )

            async it "doesn't seperate simplified items if they don't have a run_with method":
                part11 = mock.Mock(name="part11", spec=[])
                part12 = mock.Mock(name="part12", spec=[])
                part13 = mock.Mock(name="part13", spec=[])

                part2 = mock.Mock(name="part2", spec=["simplified"])
                part2simplified = mock.Mock(name="part2simplified", spec=[])
                part2.simplified.return_value = part2simplified

                part31 = mock.Mock(name="part31", spec=[])
                part32 = mock.Mock(name="part32", spec=[])

                res1 = mock.Mock(name="res1")
                self.item_kls.return_value = res1

                res = list(self.target.simplify([part11, part12, part13, part2, part31, part32]))
                self.assertEqual(res, [res1])

                part2.simplified.assert_called_once_with(self.target.simplify)

                self.assertEqual(self.item_kls.mock_calls
                    , [ mock.call([part11, part12, part13, part2simplified, part31, part32])
                      ]
                    )
