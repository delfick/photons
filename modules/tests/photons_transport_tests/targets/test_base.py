# coding: spec

from photons_transport.targets.script import ScriptRunner
from photons_transport.targets.base import Target
from photons_transport.targets.item import Item

from photons_app.formatter import MergedOptionStringFormatter

from photons_control.script import FromGenerator
from photons_messages import protocol_register

from delfick_project.norms import dictobj, sb, Meta
from contextlib import contextmanager
from unittest import mock
import asyncio
import pytest


@pytest.fixture()
def final_future():
    ff = asyncio.Future()
    try:
        yield ff
    finally:
        ff.cancel()


@pytest.fixture()
def target(final_future):
    return Target.create({"protocol_register": protocol_register, "final_future": final_future,})


describe "Target":
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

        describe "script":

            @pytest.fixture()
            def script(self):
                return mock.Mock(name="script")

            @pytest.fixture()
            def script_runner_kls(self, script):
                return mock.Mock(name="script_runner_kls", return_value=script)

            @pytest.fixture(autouse=True)
            def attach_runner_kls(self, target, script_runner_kls):
                with mock.patch.object(target, "script_runner_kls", script_runner_kls):
                    yield

            @pytest.fixture()
            def mocked_simplify(self, target):
                @contextmanager
                def mocked_simplify(*results, onsecond=None):
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

                    with mock.patch.object(target, "simplify", simplify):
                        yield simplify

                return mocked_simplify

            async it "says items is None if we simplify to an empty list", mocked_simplify, script, script_runner_kls, target:
                raw = mock.Mock(name="raw")

                with mocked_simplify() as simplify:
                    assert target.script(raw) is script

                simplify.assert_called_once_with(raw)
                script_runner_kls.assert_called_once_with(None, target=target)

            async it "gives items as just that item if list is one item", mocked_simplify, script, script_runner_kls, target:
                raw = mock.Mock(name="raw")
                item = mock.Mock(name="item")

                with mocked_simplify(item) as simplify:
                    assert target.script(raw) is script

                simplify.assert_called_once_with(raw)
                script_runner_kls.assert_called_once_with(item, target=target)

            async it "uses a FromGenerator if we have multiple items", mocked_simplify, script, script_runner_kls, target:
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

                with mocked_simplify(item1, item2, onsecond=onsecond) as simplify:
                    assert target.script(raw) is script

                assert simplify.mock_calls == [mock.call(raw), mock.call(mock.ANY)]
                script_runner_kls.assert_called_once_with(finalitem, target=target)

                items = []
                async for thing in info["gen"]():
                    items.append(thing)
                assert items == [item1, item2]

        describe "make_sender":
            async it "creates the session", target:
                session = mock.Mock(name="session")
                target.session_kls = mock.Mock(name="session_kls", return_value=session)

                ret = await target.make_sender()
                assert ret is session

                target.session_kls.assert_called_once_with(target)

        describe "close_sender":
            async it "just calls finish on the sender", target:
                sender = mock.Mock(name="sender")
                sender.finish = pytest.helpers.AsyncMock(name="finish")
                await target.close_sender(sender)
                sender.finish.assert_called_once_with()

        describe "session":
            async it "creates and closes a sender", target:
                sender = mock.Mock(name="sender")
                make_sender = pytest.helpers.AsyncMock(name="sender", return_value=sender)
                close_sender = pytest.helpers.AsyncMock(name="close_sender")

                make_sender_patch = mock.patch.object(target, "make_sender", make_sender)
                close_sender_patch = mock.patch.object(target, "close_sender", close_sender)

                with make_sender_patch, close_sender_patch:
                    async with target.session() as a:
                        assert a is sender
                        make_sender.assert_called_once_with()
                        assert len(close_sender.mock_calls) == 0

                    make_sender.assert_called_once_with()
                    close_sender.assert_called_once_with(sender)

        describe "simplify":

            @pytest.fixture()
            def item_kls(self):
                return mock.Mock(name="item_kls")

            @pytest.fixture(autouse=True)
            def attach_item_kls(self, item_kls, target):
                with mock.patch.object(target, "item_kls", item_kls):
                    yield

            async it "uses part as is if it already has a run on it", target:
                part = mock.Mock(name="part", spec=["run"])
                assert list(target.simplify(part)) == [part]

            async it "simplifies items that have a simplified method", item_kls, target:
                simplified = mock.Mock(name="simplified", spec=[])
                part = mock.Mock(name="part", spec=["simplified"])
                part.simplified.return_value = simplified

                res = mock.Mock(name="res")
                item_kls.return_value = res

                assert list(target.simplify(part)) == [res]

                part.simplified.assert_called_once_with(target.simplify)
                item_kls.assert_called_once_with([simplified])

            async it "splits out items into groups with pack and without and only item_kls for groups with pack", item_kls, target:
                part11 = mock.Mock(name="part11", spec=[])
                part12 = mock.Mock(name="part12", spec=[])
                part13 = mock.Mock(name="part13", spec=[])

                part2 = mock.Mock(name="part2", spec=["simplified"])
                part2simplified = mock.Mock(name="part2simplified", spec=["run"])
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

                item_kls.side_effect = item_kls_init

                res = list(target.simplify([part11, part12, part13, part2, part31, part32]))
                assert res == [res1, part2simplified, res2]

                part2.simplified.assert_called_once_with(target.simplify)

                assert item_kls.mock_calls == [
                    mock.call([part11, part12, part13]),
                    mock.call([part31, part32]),
                ]

            async it "doesn't separate simplified items if they don't have a run method", item_kls, target:
                part11 = mock.Mock(name="part11", spec=[])
                part12 = mock.Mock(name="part12", spec=[])
                part13 = mock.Mock(name="part13", spec=[])

                part2 = mock.Mock(name="part2", spec=["simplified"])
                part2simplified = mock.Mock(name="part2simplified", spec=[])
                part2.simplified.return_value = part2simplified

                part31 = mock.Mock(name="part31", spec=[])
                part32 = mock.Mock(name="part32", spec=[])

                res1 = mock.Mock(name="res1")
                item_kls.return_value = res1

                res = list(target.simplify([part11, part12, part13, part2, part31, part32]))
                assert res == [res1]

                part2.simplified.assert_called_once_with(target.simplify)

                assert item_kls.mock_calls == [
                    mock.call([part11, part12, part13, part2simplified, part31, part32])
                ]
