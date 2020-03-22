# coding: spec

from photons_device_finder import DeviceFinderLoops, Done, InfoPoints, Filter

from photons_app.errors import FoundNoDevices
from photons_app.special import FoundSerials
from photons_app import helpers as hp

from photons_control.script import FromGenerator
from photons_messages import DeviceMessages

from unittest import mock
import binascii
import asyncio
import pytest

describe "DeviceFinderLoops":
    async it "sets itself up":
        target = mock.Mock(name="target")
        service_search_interval = mock.Mock(name="service_search_interval")
        information_search_interval = mock.Mock(name="information_search_interval")

        store = mock.Mock(name="store")
        FakeInfoStore = mock.Mock(name="InfoStore", return_value=store)

        with mock.patch("photons_device_finder.InfoStore", FakeInfoStore):
            loops = DeviceFinderLoops(
                target,
                service_search_interval=service_search_interval,
                information_search_interval=information_search_interval,
            )

        assert loops.target is target
        assert type(loops.queue) is asyncio.Queue
        assert type(loops.finished) is asyncio.Event
        assert loops.service_search_interval is service_search_interval
        assert loops.information_search_interval is information_search_interval

        FakeInfoStore.assert_called_once_with(loops)

    describe "functionality":

        @pytest.fixture()
        def V(self):
            class V:
                afr = mock.Mock(name="afr")

                @hp.memoized_property
                def target(s):
                    target = mock.Mock(name="target")
                    target.args_for_run = pytest.helpers.AsyncMock(
                        name="args_for_run", return_value=s.afr
                    )
                    target.close_args_for_run = pytest.helpers.AsyncMock(name="close_args_for_run")
                    return target

                @hp.memoized_property
                def loops(s):
                    return DeviceFinderLoops(s.target)

            return V()

        describe "args_for_run":
            async it "gets args_for_run from the target", V:
                assert (await V.loops.args_for_run()) is V.afr
                V.target.args_for_run.assert_called_once_with()

            async it "only does it once", V:
                called = []

                async def args_for_run():
                    called.append(1)
                    await asyncio.sleep(0.3)
                    return V.afr

                V.target.args_for_run.side_effect = args_for_run

                fut1 = hp.async_as_background(V.loops.args_for_run())
                fut2 = hp.async_as_background(V.loops.args_for_run())
                fut3 = hp.async_as_background(V.loops.args_for_run())

                assert (await fut1) is V.afr
                assert (await fut2) is V.afr
                assert (await fut3) is V.afr

                assert called == [1]

        describe "start":
            async it "makes sure we have an afr and starts the loops", V:
                called = []
                quickstart = mock.Mock(name="quickstart")

                async def findings():
                    await asyncio.sleep(0.3)
                    called.append(1)

                async def raw_search_loop(q):
                    await asyncio.sleep(0.3)
                    assert q is quickstart
                    called.append(2)

                finding_loop = pytest.helpers.AsyncMock(name="finding_loop", side_effect=findings)
                ensure_interpreting = mock.Mock(name="ensure_interpreting")
                raw_search_loop = pytest.helpers.AsyncMock(
                    name="raw_search_loop", side_effect=raw_search_loop
                )

                with mock.patch.multiple(
                    V.loops,
                    finding_loop=finding_loop,
                    ensure_interpreting=ensure_interpreting,
                    raw_search_loop=raw_search_loop,
                ):
                    await V.loops.start(quickstart=quickstart)
                    assert called == []

                ensure_interpreting.assert_called_once_with()
                V.target.args_for_run.assert_called_once_with()

                await V.loops.findings
                await V.loops.service_search
                assert set(called) == set([1, 2])

        describe "finish":
            async it "sets finished and adds Done to the queue", V:
                assert not V.loops.finished.is_set()
                await V.loops.finish()
                assert V.loops.finished.is_set()
                assert (await V.loops.queue.get()) is Done

            async it "cancels findings, interpreting and service_search; and finishes the store", V:
                store = mock.Mock(name="store")
                findings = asyncio.Future()
                interpreting = asyncio.Future()
                service_search = asyncio.Future()

                V.loops.findings = findings
                V.loops.interpreting = interpreting
                V.loops.service_search = service_search
                V.loops.store = store

                await V.loops.finish()

                assert findings.cancelled()
                assert interpreting.cancelled()
                assert service_search.cancelled()
                store.finish.assert_called_once_with()

            async it "cancels the afr_fut if it isn't done yet", V:
                afr_fut = asyncio.Future()
                V.loops.afr_fut = afr_fut
                await V.loops.finish()
                assert afr_fut.cancelled()

            async it "closes the afr if afr_fut is done", V:
                afr_fut = asyncio.Future()
                afr_fut.set_result(V.afr)
                V.loops.afr_fut = afr_fut

                await V.loops.finish()

                V.target.close_args_for_run.assert_called_once_with(V.afr)

        describe "ensure_interpreting":
            async it "sets interpreting to a task of the interpret_loop", V:
                called = []

                async def interpreting():
                    await asyncio.sleep(0.1)
                    called.append(1)

                interpret_loop = pytest.helpers.AsyncMock(
                    name="interpret_loop", side_effect=interpreting
                )

                with mock.patch.object(V.loops, "interpret_loop", interpret_loop):
                    V.loops.ensure_interpreting()
                    assert called == []

                await V.loops.interpreting
                assert called == [1]

        describe "add_new_device":
            async it "sends all the InfoPoints to the device", V:
                serial = "d073d5000001"
                target = binascii.unhexlify(serial)

                async def send_to_device(s, m):
                    assert s == serial
                    assert type(m) is FromGenerator
                    assert [c.as_dict() for c in m.pipeline_children] == [
                        e.value.msg.as_dict() for e in InfoPoints
                    ]
                    assert m.pipeline_spread == 0.2

                send_to_device = pytest.helpers.AsyncMock(
                    name="send_to_device", side_effect=send_to_device
                )

                with mock.patch.object(V.loops, "send_to_device", send_to_device):
                    await V.loops.add_new_device(target)

                send_to_device.assert_called_once_with(serial, mock.ANY)

        describe "refresh_from_filter":
            async it "resets appropriate points and gets information before using found_from_filter", V:
                res = mock.Mock(name="res")
                filtr = mock.Mock(name="filtr")
                for_info = mock.Mock(name="for_info")
                find_timeout = mock.Mock(name="find_timeout")

                msg1 = mock.Mock(name="msg1")
                msg2 = mock.Mock(name="msg2")

                _msgs_from_filter = mock.Mock(name="_msgs_from_filter", return_value=[msg1, msg2])
                send_to_device = pytest.helpers.AsyncMock(name="send_to_device")
                _update_found = pytest.helpers.AsyncMock(name="_update_found")
                found_from_filter = pytest.helpers.AsyncMock(
                    name="found_from_filter", return_value=res
                )

                with mock.patch.multiple(
                    V.loops,
                    _msgs_from_filter=_msgs_from_filter,
                    send_to_device=send_to_device,
                    _update_found=_update_found,
                ):
                    with mock.patch.object(V.loops.store, "found_from_filter", found_from_filter):
                        coro = V.loops.refresh_from_filter(
                            filtr, for_info=for_info, find_timeout=find_timeout
                        )
                        assert (await coro) is res

                _msgs_from_filter.assert_called_once_with(filtr, do_reset=True, for_info=for_info)

                class IsFoundSerials:
                    def __eq__(self, other):
                        return isinstance(other, FoundSerials)

                send_to_device.assert_called_once_with(
                    IsFoundSerials(), [msg1, msg2], find_timeout=find_timeout
                )
                _update_found.assert_called_once_with(IsFoundSerials(), find_timeout)
                found_from_filter.assert_called_once_with(filtr, for_info=for_info)

            async it "works with an actual filter", V:
                filtr = Filter.from_kwargs(label="kitchen")

                refs = []

                async def send_to_device(ref, msgs, find_timeout=5):
                    assert [m.as_dict() for m in msgs] == [
                        InfoPoints.LIGHT_STATE.value.msg.as_dict()
                    ]
                    refs.append((1, ref))

                async def _update_found(ref, find_timeout):
                    refs.append((2, ref))

                send_to_device = pytest.helpers.AsyncMock(
                    name="send_to_device", side_effect=send_to_device
                )
                _update_found = pytest.helpers.AsyncMock(
                    name="_update_found", side_effect=_update_found
                )

                res = mock.Mock(name="res")
                found_from_filter = pytest.helpers.AsyncMock(
                    name="found_from_filter", return_value=res
                )

                with mock.patch.object(V.loops.store, "found_from_filter", found_from_filter):
                    with mock.patch.multiple(
                        V.loops, send_to_device=send_to_device, _update_found=_update_found
                    ):
                        coro = V.loops.refresh_from_filter(filtr)
                        assert (await coro) is res

                assert [i for i, _ in refs] == [1, 2]
                assert refs[0][1] is refs[1][1]
                assert type(refs[0][1]) is FoundSerials

                found_from_filter.assert_called_once_with(filtr, for_info=False)

        describe "_msgs_from_filter":
            async it "yields all the points if for_info", V:
                filtr = Filter.from_kwargs()
                assert filtr.matches_all
                expected = [e.value.msg.as_dict() for e in InfoPoints]
                got = [m.as_dict() for m in V.loops._msgs_from_filter(filtr, for_info=True)]
                assert got == expected

            async it "yields nothing if matches_all and not for_info", V:
                filtr = Filter.from_kwargs()
                assert filtr.matches_all
                got = [m.as_dict() for m in V.loops._msgs_from_filter(filtr, for_info=False)]
                assert got == []

            async it "yields appropriate msgs for what's on the filtr", V:
                filtr = Filter.from_kwargs(label="kitchen", group_name="one")
                assert not filtr.matches_all
                expected = [
                    e.value.msg.as_dict() for e in [InfoPoints.LIGHT_STATE, InfoPoints.GROUP]
                ]
                got = [m.as_dict() for m in V.loops._msgs_from_filter(filtr)]
                assert got == expected

            async it "resets the appropriate points", V:
                filtr = Filter.from_kwargs(group_id="123", group_name="one")
                assert not filtr.matches_all
                for e in InfoPoints:
                    V.loops.store.futures[e].set_result(True)

                expected = [e.value.msg.as_dict() for e in [InfoPoints.GROUP]]
                got = [m.as_dict() for m in V.loops._msgs_from_filter(filtr, do_reset=True)]
                assert got == expected

                for e in InfoPoints:
                    if e is InfoPoints.GROUP:
                        assert not V.loops.store.futures[e].done()
                    else:
                        assert V.loops.store.futures[e].done()

        describe "_update_found":
            async it "uses the reference to find devices and update store", V:
                found = mock.Mock(name="found")
                find_timeout = mock.Mock(name="find_timeout")

                reference = mock.Mock(name="reference")
                reference.find = pytest.helpers.AsyncMock(name="find", return_value=(found, []))

                update_found = mock.Mock(name="update_found")
                with mock.patch.object(V.loops.store, "update_found", update_found):
                    await V.loops._update_found(reference, find_timeout)

                reference.find.assert_called_once_with(V.afr, timeout=find_timeout)
                update_found.assert_called_once_with(found)

        describe "raw_search_loop":
            async it "keeps searching and updating the store till finished", V:
                V.loops.service_search_interval = 0.01

                found1 = mock.Mock(name="found1")
                found2 = mock.Mock(name="found2")
                found3 = mock.Mock(name="found2")

                error1 = Exception("WAT")

                rets = [found1, FoundNoDevices(), found2, error1, found3]

                async def find_devices(ignore_lost=False):
                    assert ignore_lost is True
                    res = rets.pop(0)
                    if not rets:
                        await V.loops.finish()

                    if isinstance(res, Exception):
                        raise res
                    else:
                        return res

                V.afr.find_devices = pytest.helpers.AsyncMock(
                    name="find_devices", side_effect=find_devices
                )

                update_found = mock.Mock(name="update_found")
                with mock.patch.object(V.loops.store, "update_found", update_found):
                    await V.loops.raw_search_loop()

                assert len(V.afr.find_devices.mock_calls) == 5
                assert update_found.mock_calls == [
                    mock.call(found1, query_new_devices=False),
                    mock.call(found2, query_new_devices=True),
                    mock.call(found3, query_new_devices=True),
                ]

        describe "finding_loop":
            async it "uses a Repeater", V:
                called = []

                V.afr.find_devices = pytest.helpers.AsyncMock(name="find_devices")
                V.afr.find_devices.return_value = {
                    binascii.unhexlify("d073d5000001"): (set(), None)
                }

                async def send_to_device(ref, msg):
                    assert isinstance(ref, FoundSerials)
                    assert isinstance(msg, FromGenerator)

                    gen = msg.generator(ref, V.afr)
                    pipeline = await gen.asend(None)
                    expected = [e.value.msg.as_dict() for e in InfoPoints]
                    got = [m.as_dict() for m in pipeline.pipeline_children]
                    assert got == expected
                    assert pipeline.pipeline_spread == 1
                    assert pipeline.pipeline_short_circuit_on_error == True
                    called.append(1)

                send_to_device = pytest.helpers.AsyncMock(
                    name="send_to_device", side_effect=send_to_device
                )

                with mock.patch.object(V.loops, "send_to_device", send_to_device):
                    await V.loops.finding_loop()

                assert called == [1]

        describe "interpret_loop":
            async it "keeps interpreting off the loop till nxt is Done", V:
                msg1 = mock.Mock(name="msg1")
                msg2 = mock.Mock(name="msg1")
                msg3 = mock.Mock(name="msg1")
                msg4 = mock.Mock(name="msg1")
                msg5 = mock.Mock(name="msg1")

                def interpret(nxt):
                    if nxt is msg2:
                        raise Exception("WAT")

                interpret = mock.Mock(name="interpret", side_effect=interpret)

                with mock.patch.object(V.loops, "interpret", interpret):
                    t = hp.async_as_background(V.loops.interpret_loop())

                    await V.loops.queue.put(msg1)
                    await V.loops.queue.put(msg2)
                    await V.loops.queue.put(msg3)
                    await V.loops.queue.put(Done)
                    await V.loops.queue.put(msg4)
                    await V.loops.queue.put(msg5)

                    await t

                assert interpret.mock_calls == [mock.call(m) for m in [msg1, msg2, msg3]]

                assert (await V.loops.queue.get()) is msg4

            async it "stops when finished is set", V:
                msg1 = mock.Mock(name="msg1")
                msg2 = mock.Mock(name="msg1")
                msg3 = mock.Mock(name="msg1")
                msg4 = mock.Mock(name="msg1")

                def interpret(nxt):
                    if nxt is msg3:
                        V.loops.finished.set()

                interpret = mock.Mock(name="interpret", side_effect=interpret)

                with mock.patch.object(V.loops, "interpret", interpret):
                    t = hp.async_as_background(V.loops.interpret_loop())

                    await V.loops.queue.put(msg1)
                    await V.loops.queue.put(msg2)
                    await V.loops.queue.put(msg3)
                    await V.loops.queue.put(msg4)

                    await t

                assert interpret.mock_calls == [mock.call(m) for m in [msg1, msg2, msg3]]

                assert (await V.loops.queue.get()) is msg4

        describe "intepret":
            async it "does nothing if item isn't a LIFXPacket", V:

                class Thing:
                    pass

                add = mock.Mock(name="add")

                with mock.patch.object(V.loops.store, "add", add):
                    V.loops.interpret(Thing())

                assert len(add.mock_calls) == 0

            async it "adds to the store if it's a LIFXPacket", V:
                msg = DeviceMessages.StateGroup(group="123", label="one", updated_at=1)
                add = mock.Mock(name="add")

                with mock.patch.object(V.loops.store, "add", add):
                    V.loops.interpret(msg)

                add.assert_called_once_with(msg)
