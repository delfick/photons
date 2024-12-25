
from contextlib import contextmanager
from unittest import mock

import pytest
from delfick_project.norms import Meta, dictobj, sb
from photons_app import helpers as hp
from photons_app.formatter import MergedOptionStringFormatter
from photons_control.script import FromGenerator
from photons_messages import protocol_register
from photons_transport.targets.base import Target
from photons_transport.targets.item import Item
from photons_transport.targets.script import ScriptRunner


@pytest.fixture()
def final_future():
    ff = hp.create_future()
    try:
        yield ff
    finally:
        ff.cancel()


@pytest.fixture()
def target(final_future):
    return Target.create({"protocol_register": protocol_register, "final_future": final_future})


class TestTarget:
    class TestCreate:
        async def test_it_works(self):
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

    class TestNormalise:
        async def test_it_gets_protocol_register_and_final_future_from_the_meta(self):
            protocol_register = mock.Mock(name="protocol_register")
            final_future = mock.Mock(name="final_future")
            config = {"protocol_register": protocol_register, "final_future": final_future}
            meta = Meta(config, []).at("transport")

            spec = Target.FieldSpec(formatter=MergedOptionStringFormatter)
            t = spec.normalise(meta, {})

            assert t.protocol_register is protocol_register
            assert t.final_future is final_future

    class TestUsage:

        class TestScript:

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

            async def test_it_says_items_is_None_if_we_simplify_to_an_empty_list(self, mocked_simplify, script, script_runner_kls, target):
                raw = mock.Mock(name="raw")

                with mocked_simplify() as simplify:
                    assert target.script(raw) is script

                simplify.assert_called_once_with(raw)
                script_runner_kls.assert_called_once_with(None, target=target)

            async def test_it_gives_items_as_just_that_item_if_list_is_one_item(self, mocked_simplify, script, script_runner_kls, target):
                raw = mock.Mock(name="raw")
                item = mock.Mock(name="item")

                with mocked_simplify(item) as simplify:
                    assert target.script(raw) is script

                simplify.assert_called_once_with(raw)
                script_runner_kls.assert_called_once_with(item, target=target)

            async def test_it_uses_a_FromGenerator_if_we_have_multiple_items(self, mocked_simplify, script, script_runner_kls, target):
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

        class TestMakeSender:
            async def test_it_creates_the_session(self, target):
                session = mock.Mock(name="session")
                target.session_kls = mock.Mock(name="session_kls", return_value=session)

                ret = await target.make_sender()
                assert ret is session

                target.session_kls.assert_called_once_with(target)

        class TestCloseSender:
            async def test_it_just_calls_finish_on_the_sender(self, target):
                sender = mock.Mock(name="sender")
                sender.finish = pytest.helpers.AsyncMock(name="finish")
                await target.close_sender(sender)
                sender.finish.assert_called_once_with()

        class TestSession:
            async def test_it_creates_and_closes_a_sender(self, target):
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

        class TestSimplify:

            @pytest.fixture()
            def item_kls(self):
                return mock.Mock(name="item_kls")

            @pytest.fixture(autouse=True)
            def attach_item_kls(self, item_kls, target):
                with mock.patch.object(target, "item_kls", item_kls):
                    yield

            async def test_it_uses_part_as_is_if_it_already_has_a_run_on_it(self, target):
                part = mock.Mock(name="part", spec=["run"])
                assert list(target.simplify(part)) == [part]

            async def test_it_simplifies_items_that_have_a_simplified_method(self, item_kls, target):
                simplified = mock.Mock(name="simplified", spec=[])
                part = mock.Mock(name="part", spec=["simplified"])
                part.simplified.return_value = simplified

                res = mock.Mock(name="res")
                item_kls.return_value = res

                assert list(target.simplify(part)) == [res]

                part.simplified.assert_called_once_with(target.simplify)
                item_kls.assert_called_once_with([simplified])

            async def test_it_splits_out_items_into_groups_with_pack_and_without_and_only_item_kls_for_groups_with_pack(self, item_kls, target):
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

            async def test_it_doesnt_separate_simplified_items_if_they_dont_have_a_run_method(self, item_kls, target):
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
