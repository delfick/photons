# coding: spec

from photons_device_finder import DeviceFinderLoops, Done, InfoPoints, Filter

from photons_app.test_helpers import AsyncTestCase
from photons_app.errors import FoundNoDevices
from photons_app.special import FoundSerials
from photons_app import helpers as hp

from photons_script.script import Pipeline, Repeater
from photons_device_messages import DeviceMessages

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import asynctest
import binascii
import asyncio
import mock

describe AsyncTestCase, "DeviceFinderLoops":
    async it "sets itself up":
        target = mock.Mock(name="target")
        service_search_interval = mock.Mock(name='service_search_interval')
        information_search_interval = mock.Mock(name="information_search_interval")

        store = mock.Mock(name='store')
        FakeInfoStore = mock.Mock(name="InfoStore", return_value=store)

        with mock.patch("photons_device_finder.InfoStore", FakeInfoStore):
            loops = DeviceFinderLoops(target
                , service_search_interval = service_search_interval
                , information_search_interval = information_search_interval
                )

        self.assertIs(loops.target, target)
        self.assertIs(type(loops.queue), asyncio.Queue)
        self.assertIs(type(loops.finished), asyncio.Event)
        self.assertIs(loops.service_search_interval, service_search_interval)
        self.assertIs(loops.information_search_interval, information_search_interval)

        FakeInfoStore.assert_called_once_with(loops)

    describe "functionality":
        async before_each:
            self.afr = mock.Mock(name='afr')
            self.target = mock.Mock(name="target")
            self.target.args_for_run = asynctest.mock.CoroutineMock(name='args_for_run', return_value=self.afr)
            self.target.close_args_for_run = asynctest.mock.CoroutineMock(name="close_args_for_run")
            self.loops = DeviceFinderLoops(self.target)

        describe "args_for_run":
            async it "gets args_for_run from the target":
                self.assertIs(await self.wait_for(self.loops.args_for_run()), self.afr)
                self.target.args_for_run.assert_called_once_with()

            async it "only does it once":
                called = []

                async def args_for_run():
                    called.append(1)
                    await asyncio.sleep(0.3)
                    return self.afr
                self.target.args_for_run.side_effect = args_for_run

                fut1 = hp.async_as_background(self.loops.args_for_run())
                fut2 = hp.async_as_background(self.loops.args_for_run())
                fut3 = hp.async_as_background(self.loops.args_for_run())

                self.assertIs(await self.wait_for(fut1), self.afr)
                self.assertIs(await self.wait_for(fut2), self.afr)
                self.assertIs(await self.wait_for(fut3), self.afr)

                self.assertEqual(called, [1])

        describe "start":
            async it "makes sure we have an afr and starts the loops":
                called = []
                quickstart = mock.Mock(name="quickstart")

                async def findings():
                    await asyncio.sleep(0.3)
                    called.append(1)

                async def raw_search_loop(q):
                    await asyncio.sleep(0.3)
                    self.assertIs(q, quickstart)
                    called.append(2)

                finding_loop = asynctest.mock.CoroutineMock(name="finding_loop", side_effect=findings)
                ensure_interpreting = mock.Mock(name='ensure_interpreting')
                raw_search_loop = asynctest.mock.CoroutineMock(name="raw_search_loop", side_effect=raw_search_loop)

                with mock.patch.multiple(self.loops
                    , finding_loop = finding_loop
                    , ensure_interpreting = ensure_interpreting
                    , raw_search_loop = raw_search_loop
                    ):
                    await self.loops.start(quickstart=quickstart)
                    self.assertEqual(called, [])

                ensure_interpreting.assert_called_once_with()
                self.target.args_for_run.assert_called_once_with()

                await self.wait_for(self.loops.findings)
                await self.wait_for(self.loops.service_search)
                self.assertEqual(set(called), set([1, 2]))

        describe "finish":
            async it "sets finished and adds Done to the queue":
                assert not self.loops.finished.is_set()
                await self.loops.finish()
                assert self.loops.finished.is_set()
                self.assertIs(await self.wait_for(self.loops.queue.get()), Done)

            async it "cancels findings, interpreting and service_search; and finishes the store":
                store = mock.Mock(name='store')
                findings = asyncio.Future()
                interpreting = asyncio.Future()
                service_search = asyncio.Future()

                self.loops.findings = findings
                self.loops.interpreting = interpreting
                self.loops.service_search = service_search
                self.loops.store = store

                await self.loops.finish()

                assert findings.cancelled()
                assert interpreting.cancelled()
                assert service_search.cancelled()
                store.finish.assert_called_once_with()

            async it "cancels the afr_fut if it isn't done yet":
                afr_fut = asyncio.Future()
                self.loops.afr_fut = afr_fut
                await self.loops.finish()
                assert afr_fut.cancelled()

            async it "closes the afr if afr_fut is done":
                afr_fut = asyncio.Future()
                afr_fut.set_result(self.afr)
                self.loops.afr_fut = afr_fut

                await self.wait_for(self.loops.finish())

                self.target.close_args_for_run.assert_called_once_with(self.afr)

        describe "ensure_interpreting":
            async it "sets interpreting to a task of the interpret_loop":
                called = []

                async def interpreting():
                    await asyncio.sleep(0.1)
                    called.append(1)

                interpret_loop = asynctest.mock.CoroutineMock(name="interpret_loop", side_effect=interpreting)

                with mock.patch.object(self.loops, "interpret_loop", interpret_loop):
                    self.loops.ensure_interpreting()
                    self.assertEqual(called, [])

                await self.wait_for(self.loops.interpreting)
                self.assertEqual(called, [1])

        describe "add_new_device":
            async it "sends all the InfoPoints to the device":
                serial = "d073d5000001"
                target = binascii.unhexlify(serial)

                async def send_to_device(s, m):
                    self.assertEqual(s, serial)
                    self.assertIs(type(m), Pipeline)
                    self.assertEqual(
                          [c.as_dict() for c in m.children]
                        , [e.value.msg.as_dict() for e in InfoPoints]
                        )
                    self.assertEqual(m.spread, 0.2)
                send_to_device = asynctest.mock.CoroutineMock(name="send_to_device"
                    , side_effect = send_to_device
                    )

                with mock.patch.object(self.loops, "send_to_device", send_to_device):
                    await self.loops.add_new_device(target)

                send_to_device.assert_called_once_with(serial, mock.ANY)

        describe "refresh_from_filter":
            async it "resets appropriate points and gets information before using found_from_filter":
                res = mock.Mock(name="res")
                filtr = mock.Mock(name='filtr')
                for_info = mock.Mock(name='for_info')
                find_timeout = mock.Mock(name='find_timeout')

                msg1 = mock.Mock(name="msg1")
                msg2 = mock.Mock(name="msg2")

                _msgs_from_filter = mock.Mock(name="_msgs_from_filter", return_value=[msg1, msg2])
                send_to_device = asynctest.mock.CoroutineMock(name="send_to_device")
                _update_found = asynctest.mock.CoroutineMock(name="_update_found")
                found_from_filter = asynctest.mock.CoroutineMock(name="found_from_filter", return_value=res)

                with mock.patch.multiple(self.loops
                    , _msgs_from_filter = _msgs_from_filter
                    , send_to_device = send_to_device
                    , _update_found = _update_found
                    ):
                    with mock.patch.object(self.loops.store, "found_from_filter", found_from_filter):
                        coro = self.loops.refresh_from_filter(filtr, for_info=for_info, find_timeout=find_timeout)
                        self.assertIs(await self.wait_for(coro), res)

                _msgs_from_filter.assert_called_once_with(filtr, do_reset=True, for_info=for_info)

                class IsFoundSerials:
                    def __eq__(self, other):
                        return isinstance(other, FoundSerials)
                send_to_device.assert_called_once_with(IsFoundSerials(), [msg1, msg2], find_timeout=find_timeout)
                _update_found.assert_called_once_with(IsFoundSerials(), find_timeout)
                found_from_filter.assert_called_once_with(filtr, for_info=for_info)

            async it "works with an actual filter":
                filtr = Filter.from_kwargs(label="kitchen")

                refs = []

                async def send_to_device(ref, msgs, find_timeout=5):
                    self.assertEqual(
                          [m.as_dict() for m in msgs]
                        , [InfoPoints.LIGHT_STATE.value.msg.as_dict()]
                        )
                    refs.append((1, ref))

                async def _update_found(ref, find_timeout):
                    refs.append((2, ref))

                send_to_device = asynctest.mock.CoroutineMock(name='send_to_device', side_effect=send_to_device)
                _update_found = asynctest.mock.CoroutineMock(name="_update_found", side_effect=_update_found)

                res = mock.Mock(name='res')
                found_from_filter = asynctest.mock.CoroutineMock(name="found_from_filter", return_value=res)

                with mock.patch.object(self.loops.store, "found_from_filter", found_from_filter):
                    with mock.patch.multiple(self.loops
                        , send_to_device = send_to_device
                        , _update_found = _update_found
                        ):
                        coro = self.loops.refresh_from_filter(filtr)
                        self.assertIs(await self.wait_for(coro), res)

                self.assertEqual([i for i, _ in refs], [1, 2])
                self.assertIs(refs[0][1], refs[1][1])
                self.assertIs(type(refs[0][1]), FoundSerials)

                found_from_filter.assert_called_once_with(filtr, for_info=False)

        describe "_msgs_from_filter":
            async it "yields all the points if for_info":
                filtr = Filter.from_kwargs()
                assert filtr.matches_all
                expected = [e.value.msg.as_dict() for e in InfoPoints]
                got = [m.as_dict() for m in self.loops._msgs_from_filter(filtr, for_info=True)]
                self.assertEqual(got, expected)

            async it "yields nothing if matches_all and not for_info":
                filtr = Filter.from_kwargs()
                assert filtr.matches_all
                got = [m.as_dict() for m in self.loops._msgs_from_filter(filtr, for_info=False)]
                self.assertEqual(got, [])

            async it "yields appropriate msgs for what's on the filtr":
                filtr = Filter.from_kwargs(label="kitchen", group_name="one")
                assert not filtr.matches_all
                expected = [e.value.msg.as_dict() for e in [InfoPoints.LIGHT_STATE, InfoPoints.GROUP]]
                got = [m.as_dict() for m in self.loops._msgs_from_filter(filtr)]
                self.assertEqual(got, expected)

            async it "resets the appropriate points":
                filtr = Filter.from_kwargs(group_id="123", group_name="one")
                assert not filtr.matches_all
                for e in InfoPoints:
                    self.loops.store.futures[e].set_result(True)

                expected = [e.value.msg.as_dict() for e in [InfoPoints.GROUP]]
                got = [m.as_dict() for m in self.loops._msgs_from_filter(filtr, do_reset=True)]
                self.assertEqual(got, expected)

                for e in InfoPoints:
                    if e is InfoPoints.GROUP:
                        assert not self.loops.store.futures[e].done()
                    else:
                        assert self.loops.store.futures[e].done()

        describe "_update_found":
            async it "uses the reference to find devices and update store":
                found = mock.Mock(name='found')
                find_timeout = mock.Mock(name="find_timeout")

                reference = mock.Mock(name="reference")
                reference.find = asynctest.mock.CoroutineMock(name="find", return_value=(found, []))

                update_found = mock.Mock(name="update_found")
                with mock.patch.object(self.loops.store, "update_found", update_found):
                    await self.wait_for(self.loops._update_found(reference, find_timeout))

                reference.find.assert_called_once_with(self.afr, True, find_timeout)
                update_found.assert_called_once_with(found)

        describe "raw_search_loop":
            async it "keeps searching and updating the store till finished":
                self.loops.service_search_interval = 0.01

                found1 = mock.Mock(name="found1")
                found2 = mock.Mock(name="found2")
                found3 = mock.Mock(name="found2")

                error1 = Exception("WAT")

                rets = [found1, FoundNoDevices(), found2, error1, found3]

                async def find_devices(b, ignore_lost=False):
                    self.assertIs(ignore_lost, True)
                    self.assertIs(b, self.afr.default_broadcast)
                    res = rets.pop(0)
                    if not rets:
                        await self.loops.finish()

                    if isinstance(res, Exception):
                        raise res
                    else:
                        return res
                self.afr.find_devices = asynctest.mock.CoroutineMock(name="find_devices", side_effect=find_devices)

                update_found = mock.Mock(name="update_found")
                with mock.patch.object(self.loops.store, "update_found", update_found):
                    await self.wait_for(self.loops.raw_search_loop())

                self.assertEqual(len(self.afr.find_devices.mock_calls), 5)
                self.assertEqual(update_found.mock_calls
                    , [ mock.call(found1, query_new_devices=False)
                      , mock.call(found2, query_new_devices=True)
                      , mock.call(found3, query_new_devices=True)
                      ]
                    )

        describe "finding_loop":
            async it "uses a Repeater":
                called = []

                async def send_to_device(ref, msg):
                    assert isinstance(ref, FoundSerials)
                    assert isinstance(msg, Repeater)
                    assert isinstance(msg.msg, Pipeline)
                    expected = [e.value.msg.as_dict() for e in InfoPoints]
                    got = [m.as_dict() for m in msg.msg.children]
                    self.assertEqual(got, expected)
                    self.assertEqual(msg.msg.spread, 1)
                    self.assertEqual(msg.msg.short_circuit_on_error, True)
                    called.append(1)

                send_to_device = asynctest.mock.CoroutineMock(name="send_to_device", side_effect=send_to_device)

                with mock.patch.object(self.loops, "send_to_device", send_to_device):
                    await self.wait_for(self.loops.finding_loop())

                self.assertEqual(called, [1])

        describe "interpret_loop":
            async it "keeps interpreting off the loop till nxt is Done":
                msg1 = mock.Mock(name="msg1")
                msg2 = mock.Mock(name="msg1")
                msg3 = mock.Mock(name="msg1")
                msg4 = mock.Mock(name="msg1")
                msg5 = mock.Mock(name="msg1")

                def interpret(nxt):
                    if nxt is msg2:
                        raise Exception("WAT")
                interpret = mock.Mock(name="interpret", side_effect=interpret)

                with mock.patch.object(self.loops, "interpret", interpret):
                    t = hp.async_as_background(self.loops.interpret_loop())

                    await self.wait_for(self.loops.queue.put(msg1))
                    await self.wait_for(self.loops.queue.put(msg2))
                    await self.wait_for(self.loops.queue.put(msg3))
                    await self.wait_for(self.loops.queue.put(Done))
                    await self.wait_for(self.loops.queue.put(msg4))
                    await self.wait_for(self.loops.queue.put(msg5))

                    await self.wait_for(t)

                self.assertEqual(interpret.mock_calls
                    , [ mock.call(m) for m in [msg1, msg2, msg3] ]
                    )

                self.assertIs(await self.wait_for(self.loops.queue.get()), msg4)

            async it "stops when finished is set":
                msg1 = mock.Mock(name="msg1")
                msg2 = mock.Mock(name="msg1")
                msg3 = mock.Mock(name="msg1")
                msg4 = mock.Mock(name="msg1")

                def interpret(nxt):
                    if nxt is msg3:
                        self.loops.finished.set()
                interpret = mock.Mock(name="interpret", side_effect=interpret)

                with mock.patch.object(self.loops, "interpret", interpret):
                    t = hp.async_as_background(self.loops.interpret_loop())

                    await self.wait_for(self.loops.queue.put(msg1))
                    await self.wait_for(self.loops.queue.put(msg2))
                    await self.wait_for(self.loops.queue.put(msg3))
                    await self.wait_for(self.loops.queue.put(msg4))

                    await self.wait_for(t)

                self.assertEqual(interpret.mock_calls
                    , [ mock.call(m) for m in [msg1, msg2, msg3] ]
                    )

                self.assertIs(await self.wait_for(self.loops.queue.get()), msg4)

        describe "intepret":
            async it "does nothing if item isn't a LIFXPacket":
                class Thing:
                    pass

                add = mock.Mock(name="add")

                with mock.patch.object(self.loops.store, "add", add):
                    self.loops.interpret(Thing())

                self.assertEqual(len(add.mock_calls), 0)

            async it "adds to the store if it's a LIFXPacket":
                msg = DeviceMessages.StateGroup(group="123", label="one", updated_at=1)
                add = mock.Mock(name="add")

                with mock.patch.object(self.loops.store, "add", add):
                    self.loops.interpret(msg)

                add.assert_called_once_with(msg)
