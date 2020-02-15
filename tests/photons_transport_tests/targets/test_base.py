# coding: spec

from photons_transport.targets.script import ScriptRunner
from photons_transport.targets.base import Target
from photons_transport.targets.item import Item

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.test_helpers import AsyncTestCase

from photons_control.script import FromGenerator

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from delfick_project.norms import dictobj, sb, Meta
from contextlib import contextmanager
from unittest import mock
import asynctest
import binascii

describe AsyncTestCase, "Target":
    describe "create":
        async it "works":
            protocol_register = mock.Mock(name="protocol_register")
            final_future = mock.Mock(name="final_future")
            config = {"protocol_register": protocol_register, "final_future": final_future}

            class T(Target):
                one = dictobj.Field(sb.integer_spec)

            t = T.create(config, {"one": 20})

            assert t.protocol_register is protocol_register
            assert t.final_future is final_future
            assert t.one == 20

            assert t.item_kls is Item
            assert t.script_runner_kls is ScriptRunner

    describe "normalise":
        async it "gets protocol_register and final_future from the meta":
            protocol_register = mock.Mock(name="protocol_register")
            final_future = mock.Mock(name="final_future")
            config = {"protocol_register": protocol_register, "final_future": final_future}
            meta = Meta(config, []).at("transport")

            spec = Target.FieldSpec(formatter=MergedOptionStringFormatter)
            t = spec.normalise(meta, {})

            assert t.protocol_register is protocol_register
            assert t.final_future is final_future

    describe "Usage":
        async before_each:
            self.protocol_register = mock.Mock(name="protocol_register")
            self.final_future = mock.Mock(name="final_future")

            config = {
                "protocol_register": self.protocol_register,
                "final_future": self.final_future,
            }
            self.target = Target.create(config)

        describe "script":
            async before_each:
                self.script = mock.Mock(name="script")
                self.script_runner_kls = mock.Mock(
                    name="script_runner_kls", return_value=self.script
                )
                self.target.script_runner_kls = self.script_runner_kls

            @contextmanager
            def mocked_simplify(self, *results, onsecond=None):
                first = True

                def simplify(r):
                    nonlocal first
                    if first:
                        first = False
                        for rr in results:
                            yield rr
                    else:
                        for rr in onsecond(r):
                            yield rr

                simplify = mock.Mock(name="simplify", side_effect=simplify)

                with mock.patch.object(self.target, "simplify", simplify):
                    yield simplify

            async it "says items is None if we simplify to an empty list":
                raw = mock.Mock(name="raw")

                with self.mocked_simplify() as simplify:
                    assert self.target.script(raw) is self.script

                simplify.assert_called_once_with(raw)
                self.script_runner_kls.assert_called_once_with(None, target=self.target)

            async it "gives items as just that item if list is one item":
                raw = mock.Mock(name="raw")
                item = mock.Mock(name="item")

                with self.mocked_simplify(item) as simplify:
                    assert self.target.script(raw) is self.script

                simplify.assert_called_once_with(raw)
                self.script_runner_kls.assert_called_once_with(item, target=self.target)

            async it "uses a FromGenerator if we have multiple items":
                raw = mock.Mock(name="raw")
                item1 = mock.Mock(name="item1")
                item2 = mock.Mock(name="item2")
                finalitem = mock.Mock(name="finalitem")

                info = {"gen": None}

                def onsecond(r):
                    assert isinstance(r, FromGenerator)
                    assert r.reference_override
                    info["gen"] = r.generator
                    yield finalitem

                with self.mocked_simplify(item1, item2, onsecond=onsecond) as simplify:
                    assert self.target.script(raw) is self.script

                assert simplify.mock_calls == [mock.call(raw), mock.call(mock.ANY)]
                self.script_runner_kls.assert_called_once_with(finalitem, target=self.target)

                items = []
                async for thing in info["gen"]():
                    items.append(thing)
                assert items == [item1, item2]

        describe "args_for_run":
            async it "creates the session":
                session = mock.Mock(name="session")
                self.target.session_kls = mock.Mock(name="session_kls", return_value=session)

                ret = await self.target.args_for_run()
                assert ret is session

                self.target.session_kls.assert_called_once_with(self.target)

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
                close_args_for_run_patch = mock.patch.object(
                    self.target, "close_args_for_run", close_args_for_run
                )

                with args_for_run_patch, close_args_for_run_patch:
                    async with self.target.session() as a:
                        assert a is afr
                        args_for_run.assert_called_once_with()
                        assert len(close_args_for_run.mock_calls) == 0

                    args_for_run.assert_called_once_with()
                    close_args_for_run.assert_called_once_with(afr)

        describe "simplify":
            async before_each:
                self.item_kls = mock.Mock(name="item_kls")
                self.target.item_kls = self.item_kls

            async it "uses part as is if it already has a run_with on it":
                part = mock.Mock(name="part", spec=["run_with"])
                assert list(self.target.simplify(part)) == [part]

            async it "simplifies items that have a simplified method":
                simplified = mock.Mock(name="simplified", spec=[])
                part = mock.Mock(name="part", spec=["simplified"])
                part.simplified.return_value = simplified

                res = mock.Mock(name="res")
                self.item_kls.return_value = res

                assert list(self.target.simplify(part)) == [res]

                part.simplified.assert_called_once_with(self.target.simplify)
                self.item_kls.assert_called_once_with([simplified])

            async it "splits out items into groups with pack and without and only item_kls for groups with pack":
                part11 = mock.Mock(name="part11", spec=[])
                part12 = mock.Mock(name="part12", spec=[])
                part13 = mock.Mock(name="part13", spec=[])

                part2 = mock.Mock(name="part2", spec=["simplified"])
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
                assert res == [res1, part2simplified, res2]

                part2.simplified.assert_called_once_with(self.target.simplify)

                assert self.item_kls.mock_calls == [mock.call([part11, part12, part13]), mock.call([part31, part32])]

            async it "doesn't separate simplified items if they don't have a run_with method":
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
                assert res == [res1]

                part2.simplified.assert_called_once_with(self.target.simplify)

                assert self.item_kls.mock_calls == [mock.call([part11, part12, part13, part2simplified, part31, part32])]
