# coding: spec

from photons_transport.target.target import TransportTarget

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.test_helpers import AsyncTestCase

from photons_script.script import InvalidScript

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from input_algorithms.meta import Meta
import asynctest
import binascii
import mock

describe AsyncTestCase, "TransportTarget":
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
            async it "returns us a ScriptRunnerIterator with simplified input":
                raw = mock.Mock(name="raw")
                simplified = mock.Mock(name="simpified")
                simplify = mock.Mock(name="simplify", return_value=[simplified])

                res = mock.Mock(name="res")
                FakeScriptRunnerIterator = mock.Mock(name="FakeScriptRunnerIterator", return_value=res)

                with mock.patch.object(self.target, "simplify", simplify):
                    with mock.patch("photons_transport.target.target.ScriptRunnerIterator", FakeScriptRunnerIterator):
                        self.assertIs(self.target.script(raw), res)

                simplify.assert_called_with(raw)
                FakeScriptRunnerIterator.assert_called_once_with(simplified, target=self.target)

            async it "groups simplified in a Pipeline if there are multiple simplified items":
                raw = mock.Mock(name="raw")
                simplified = mock.Mock(name="simpified")
                simplified2 = mock.Mock(name="simpified2")
                simplify = mock.Mock(name="simplify", return_value=[simplified, simplified2])

                res = mock.Mock(name="res")
                FakeScriptRunnerIterator = mock.Mock(name="FakeScriptRunnerIterator", return_value=res)

                pipeline = mock.Mock(name="pipeline")
                FakePipeline = mock.Mock(name="Pipeline", return_value=pipeline)

                with mock.patch.object(self.target, "simplify", simplify):
                    with mock.patch("photons_transport.target.target.ScriptRunnerIterator", FakeScriptRunnerIterator):
                        with mock.patch("photons_transport.target.target.Pipeline", FakePipeline):
                            self.assertIs(self.target.script(raw), res)

                simplify.assert_called_with(raw)
                FakePipeline.assert_called_with(simplified, simplified2)
                FakeScriptRunnerIterator.assert_called_once_with(pipeline, target=self.target)

        describe "args_for_run":
            async it "creates the bridge_kls and calls start on it":
                bridge = mock.Mock(name="bridge")
                bridge.start = asynctest.mock.CoroutineMock(name="start")
                self.bridge_kls.return_value = bridge

                ret = await self.target.args_for_run()
                self.assertIs(ret, bridge)

                self.bridge_kls.assert_called_once_with(self.final_future, self.target
                    , protocol_register=self.protocol_register, found=None, default_broadcast="255.255.255.255"
                    )

                bridge.start.assert_called_with()

            async it "passes on found to the bridge":
                found = mock.Mock(name="found")
                bridge = mock.Mock(name="bridge")
                bridge.start = asynctest.mock.CoroutineMock(name="start")
                self.bridge_kls.return_value = bridge

                ret = await self.target.args_for_run(found=found)
                self.assertIs(ret, bridge)

                self.bridge_kls.assert_called_once_with(self.final_future, self.target
                    , protocol_register=self.protocol_register, found=found, default_broadcast="255.255.255.255"
                    )

                bridge.start.assert_called_with()

        describe "close_args_for_run":
            async it "just calls finish on the args_for_run":
                args_for_run = mock.Mock(name="args_for_run")
                await self.target.close_args_for_run(args_for_run)
                args_for_run.finish.assert_called_once_with()

        describe "get_list":
            async it "uses find_devices on the args_for_run":
                a = mock.Mock(name="a")
                b = mock.Mock(name="b")

                serial1 = "d073d5000001"
                serial2 = "d073d5000002"
                serial3 = "d073d5000003"
                args_for_run = mock.Mock(name="args_for_run")

                find_devices = asynctest.mock.CoroutineMock(name="find_devices")
                find_devices.return_value = [
                    binascii.unhexlify(s) for s in (serial1, serial3, serial2)
                ]
                args_for_run.find_devices = find_devices

                self.assertEqual(
                      await self.target.get_list(args_for_run, a=a, b=b)
                    , [serial1, serial2, serial3]
                    )

                args_for_run.find_devices.assert_called_once_with("255.255.255.255", a=a, b=b)

            async it "uses passed in broadcast value":
                a = mock.Mock(name="a")
                b = mock.Mock(name="b")
                broadcast = mock.Mock(name="broadcast")

                serial1 = "d073d5000001"
                serial2 = "d073d5000002"
                serial3 = "d073d5000003"
                args_for_run = mock.Mock(name="args_for_run")

                find_devices = asynctest.mock.CoroutineMock(name="find_devices")
                find_devices.return_value = [
                    binascii.unhexlify(s) for s in (serial1, serial3, serial2)
                ]
                args_for_run.find_devices = find_devices

                self.assertEqual(
                      await self.target.get_list(args_for_run, broadcast, a=a, b=b)
                    , [serial1, serial2, serial3]
                    )

                args_for_run.find_devices.assert_called_once_with(broadcast, a=a, b=b)

        describe "device_forgetter":
            async it "returns the forget method of the args_for_run":
                forget = mock.Mock(name="forget")
                args_for_run = mock.Mock(name="args_for_run", forget=forget)
                self.assertIs(self.target.device_forgetter(args_for_run), forget)

        describe "find":
            async it "returns the find method of the args_for_run":
                find = mock.Mock(name="find")
                args_for_run = mock.Mock(name="args_for_run", find=find)
                self.assertIs(self.target.find(args_for_run), find)

        describe "simplify":
            async it "complains if it has no pack method or has_children":
                part = mock.Mock(name="part", has_children=False, spec=["has_chidren"])
                with self.fuzzyAssertRaisesError(InvalidScript, "Script part has no pack method!", parts=[part]):
                    list(self.target.simplify(part))

            async it "simplifies items that have chidren":
                res = mock.Mock(name="res")
                simplified = mock.Mock(name="simplified")
                part = mock.Mock(name="part", has_children=True)

                part.simplified.return_value = simplified
                self.item_kls.return_value = res

                self.assertEqual(list(self.target.simplify(part)), [res])

                part.simplified.assert_called_once_with(self.target.simplify, [part.name])
                self.item_kls.assert_called_once_with([simplified])

            async it "splits out items into groups with pack and without and only item_kls for groups with pack":
                part11 = mock.Mock(name="part11", pack=mock.Mock(name="pack"), has_children=False)
                part12 = mock.Mock(name="part12", pack=mock.Mock(name="pack"), has_children=False)
                part13 = mock.Mock(name="part13", pack=mock.Mock(name="pack"), has_children=False)

                part2 = mock.Mock(name="part2", has_children=True)
                part2simplified = mock.Mock(name="part2simplified", spec=[])
                part2.simplified.return_value = part2simplified

                part31 = mock.Mock(name="part31", pack=mock.Mock(name="pack"), has_children=False)
                part32 = mock.Mock(name="part32", pack=mock.Mock(name="pack"), has_children=False)

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

                part2.simplified.assert_called_once_with(self.target.simplify, [part2.name])

                self.assertEqual(self.item_kls.mock_calls
                    , [ mock.call([part11, part12, part13])
                      , mock.call([part31, part32])
                      ]
                    )

            async it "doesn't seperate simplified items if they have a pack method":
                part11 = mock.Mock(name="part11", pack=mock.Mock(name="pack"), has_children=False)
                part12 = mock.Mock(name="part12", pack=mock.Mock(name="pack"), has_children=False)
                part13 = mock.Mock(name="part13", pack=mock.Mock(name="pack"), has_children=False)

                part2 = mock.Mock(name="part2", has_children=True)
                part2simplified = mock.Mock(name="part2simplified", spec=["pack"])
                part2.simplified.return_value = part2simplified

                part31 = mock.Mock(name="part31", pack=mock.Mock(name="pack"), has_children=False)
                part32 = mock.Mock(name="part32", pack=mock.Mock(name="pack"), has_children=False)

                res1 = mock.Mock(name="res1")
                self.item_kls.return_value = res1

                res = list(self.target.simplify([part11, part12, part13, part2, part31, part32]))
                self.assertEqual(res, [res1])

                part2.simplified.assert_called_once_with(self.target.simplify, [part2.name])

                self.assertEqual(self.item_kls.mock_calls
                    , [ mock.call([part11, part12, part13, part2simplified, part31, part32])
                      ]
                    )
