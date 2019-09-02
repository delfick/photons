# coding: spec

from photons_device_finder import InfoStore, InfoPoints, Collections, Device, Filter

from photons_app.test_helpers import AsyncTestCase
from photons_app.errors import TimedOut
from photons_app import helpers as hp

from photons_transport.comms.base import Found

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from input_algorithms import spec_base as sb
from unittest import mock
import asynctest
import binascii
import asyncio
import time

describe AsyncTestCase, "InfoStore":
    describe "init":
        async it "sets up some things":
            loops = mock.Mock(name="loops")
            store = InfoStore(loops)
            self.assertIs(store.device_finder_loops, loops)

            self.assertEqual(type(store.found), hp.ResettableFuture)

            self.assertEqual(len(store.futures), 5)
            for point in InfoPoints:
                self.assertEqual(type(store.futures[point]), hp.ResettableFuture)

            self.assertEqual(store.last_touch, {})
            self.assertEqual(type(store.collections), Collections)
            self.assertEqual(dict(store.by_target), {})
            self.assertEqual(dict(store.tasks_by_target), {})

            new_device = store.by_target[binascii.unhexlify("d073d5000001")]
            self.assertEqual(type(new_device), Device)
            self.assertEqual(new_device.serial, "d073d5000001")
            self.assertEqual(type(store.device_spec.empty_normalise(serial="d073d5000001")), Device)

    describe "functionality":
        async before_each:
            self.loops = mock.Mock(name="loops")
            self.store = InfoStore(self.loops)

        def pretend_services(self):
            transport = mock.Mock(name="transport")
            transport.close = asynctest.mock.CoroutineMock(name="close")
            return {"UDP": transport}

        describe "finish":
            async it "cancels everything in tasks_by_target":
                target1 = mock.Mock(name="target1")
                target2 = mock.Mock(name="target2")
                target3 = mock.Mock(name="target3")

                task1 = mock.Mock(name="task1")
                task2 = mock.Mock(name="task2")
                task3 = mock.Mock(name="task3")

                self.store.tasks_by_target[target1] = task1
                self.store.tasks_by_target[target2] = task2
                self.store.tasks_by_target[target3] = task3

                self.assertEqual(len(task1.mock_calls), 0)
                self.assertEqual(len(task2.mock_calls), 0)
                self.assertEqual(len(task3.mock_calls), 0)

                self.store.finish()

                task1.cancel.assert_called_once_with()
                task2.cancel.assert_called_once_with()
                task3.cancel.assert_called_once_with()

        describe "reset_point":
            async it "resets the appropriate future":
                for point in InfoPoints:
                    self.store.futures[point].set_result(True)
                    assert self.store.futures[point].done()
                    self.store.reset_point(point)
                    assert not self.store.futures[point].done()

                for point in InfoPoints:
                    for p in InfoPoints:
                        self.store.futures[p].reset()
                        self.store.futures[p].set_result(True)

                    self.store.reset_point(point)
                    for p, fut in self.store.futures.items():
                        if p is point:
                            assert not self.store.futures[p].done()
                        else:
                            assert self.store.futures[p].done()

            async it "ignores points it doesn't know about":
                self.store.reset_point(1)
                assert True, "it didn't complain"

        describe "adding packets":
            async it "sets pkt on the device":
                target = binascii.unhexlify("d073d5000001")
                device = mock.Mock(name="device")
                device.set_from_pkt.return_value = InfoPoints.LIGHT_STATE
                pkt = mock.Mock(name="pkt", target=target)
                self.store.by_target[target] = device

                done = asyncio.Future()

                def set_future_done(typ, touch):
                    self.assertIs(typ, InfoPoints.LIGHT_STATE)
                    self.assertEqual(self.store.last_touch[typ], touch)
                    done.set_result(True)

                start = time.time()
                with mock.patch.object(self.store, "set_future_done", set_future_done):
                    self.store.add(pkt)

                await self.wait_for(done)
                self.assertGreater(time.time() - start, 0.2)
                device.set_from_pkt.assert_called_once_with(pkt, self.store.collections)

            async it "doesn't call set_future_done if the future is already done":
                target = binascii.unhexlify("d073d5000001")
                device = mock.Mock(name="device")
                device.set_from_pkt.return_value = InfoPoints.LIGHT_STATE
                pkt = mock.Mock(name="pkt", target=target)
                self.store.by_target[target] = device
                self.store.futures[InfoPoints.LIGHT_STATE].set_result(True)

                call_later = mock.Mock(name="call_later")
                with mock.patch.object(self.loop, "call_later", call_later):
                    self.store.add(pkt)

                device.set_from_pkt.assert_called_once_with(pkt, self.store.collections)
                self.assertEqual(len(call_later.mock_calls), 0)

        describe "set_future_done":
            async it "sets result if last_touch equals touch":
                touch = mock.Mock(name="touch")
                typ = InfoPoints.LIGHT_STATE
                self.store.last_touch[typ] = touch

                assert not self.store.futures[typ].done()
                self.store.set_future_done(typ, touch)
                assert self.store.futures[typ].done()

            async it "does not set result if last_touch is not provided touch touch":
                touch1 = mock.Mock(name="touch1")
                touch2 = mock.Mock(name="touch2")

                typ = InfoPoints.LIGHT_STATE
                self.store.last_touch[typ] = touch1

                assert not self.store.futures[typ].done()
                self.store.set_future_done(typ, touch2)
                assert not self.store.futures[typ].done()

        describe "info_for":
            async it "returns as_dict of matching devices minus NotSpecified fields":
                device1 = mock.Mock(name="device1")
                device2 = mock.Mock(name="device2")
                device3 = mock.Mock(name="device3")

                device1.as_dict.return_value = {"one": "two"}
                device2.as_dict.return_value = {"three": sb.NotSpecified}
                device3.as_dict.return_value = {"four": "five", "six": sb.NotSpecified}

                # Deliberately leave out "d074" from by_target
                uh = lambda t: binascii.unhexlify(t)
                targets = [uh(t) for t in ("d071", "d072", "d073", "d074")]
                self.store.by_target[uh("d071")] = device1
                self.store.by_target[uh("d072")] = device2
                self.store.by_target[uh("d073")] = device3

                result = self.store.info_for(targets)
                self.assertEqual(result, {"d071": {"one": "two"}, "d073": {"four": "five"}})

                device1.as_dict.assert_called_once_with()
                device2.as_dict.assert_called_once_with()
                device3.as_dict.assert_called_once_with()

        describe "update_found":
            async it "removes devices that don't exist anymore":
                self.store.by_target["one"] = True
                self.store.by_target["two"] = True
                self.store.by_target["three"] = True

                self.store.update_found({"three": mock.Mock(name="services")})

                self.assertEqual(list(self.store.by_target.keys()), ["three"])

            async it "sets or resets found":
                t1 = binascii.unhexlify("d073d5000001")
                t2 = binascii.unhexlify("d073d5000002")
                found = Found()
                found[t1] = self.pretend_services()

                self.store.update_found(found, query_new_devices=False)
                self.assertEqual(await self.wait_for(self.store.found), found)

                found2 = {t2: mock.Mock(name="services")}
                self.store.update_found(found2, query_new_devices=False)
                self.assertEqual(await self.wait_for(self.store.found), found2)

            async it "can query new devices":
                t1 = binascii.unhexlify("d073d5000001")
                t2 = binascii.unhexlify("d073d5000002")
                t3 = binascii.unhexlify("d073d5000003")

                self.store.by_target[t3] = mock.Mock(name="five")
                found = Found()
                found[t1] = self.pretend_services()
                found[t2] = self.pretend_services()
                found[t3] = self.pretend_services()

                futs = {t1: asyncio.Future(), t2: asyncio.Future()}

                async def add_new_device(t):
                    futs[t].set_result(True)

                self.loops.add_new_device = add_new_device
                self.store.update_found(found)

                await self.wait_for(asyncio.wait(futs.values()))

            async it "stores a task in tasks_by_target until it is finished":
                t1 = binascii.unhexlify("d073d5000001")
                t2 = binascii.unhexlify("d073d5000002")
                t3 = binascii.unhexlify("d073d5000003")
                found = Found()
                found[t1] = self.pretend_services()
                found[t2] = self.pretend_services()
                found[t3] = self.pretend_services()

                futs = {t1: asyncio.Future(), t2: asyncio.Future()}

                async def add_new_device(t):
                    await asyncio.sleep(0.1)
                    futs[t].set_result(True)

                self.loops.add_new_device = add_new_device
                self.store.update_found(found)

                self.assertEqual(len(self.store.tasks_by_target), 3)
                await self.wait_for(asyncio.wait(futs.values()))
                await asyncio.sleep(0.01)
                self.assertEqual(len(self.store.tasks_by_target), 0)

        describe "cleanup_task":
            async it "removes the task if it matches":
                target = mock.Mock(name="target")

                async def blah():
                    pass

                task = self.loop.create_task(blah())
                self.store.tasks_by_target[target] = task
                self.store.cleanup_task(target, task, None)
                self.assertEqual(self.store.tasks_by_target, {})

            async it "does not remove if task does not matche":
                target = mock.Mock(name="target")

                async def blah():
                    pass

                task = self.loop.create_task(blah())
                self.store.tasks_by_target[target] = task

                async def meh():
                    pass

                task2 = self.loop.create_task(meh())
                self.store.tasks_by_target[target] = task2

                self.store.cleanup_task(target, task, None)
                self.assertEqual(self.store.tasks_by_target, {target: task2})

                self.store.cleanup_task(target, task2, None)
                self.assertEqual(self.store.tasks_by_target, {})

            async it "does nothing if the target isn't in tasks_by_target":
                target = mock.Mock(name="target")
                task = mock.Mock(name="task")
                self.assertEqual(self.store.tasks_by_target, {})

                self.store.cleanup_task(target, task, None)
                self.assertEqual(self.store.tasks_by_target, {})

        describe "found_from_filter":
            async it "waits on points from filtr and removes found that doesn't match":
                found = Found()
                found["d073d5000001"] = self.pretend_services()
                found["d073d5000002"] = self.pretend_services()
                found["d073d5000003"] = self.pretend_services()

                one = mock.Mock(name="one_device")
                one.matches.return_value = False

                two = mock.Mock(name="two_device")
                two.matches.return_value = True

                self.store.by_target[binascii.unhexlify("d073d5000001")] = one
                self.store.by_target[binascii.unhexlify("d073d5000002")] = two

                ts = []
                called = []

                async def set_light_state():
                    called.append("set_light_state")
                    self.store.futures[InfoPoints.LIGHT_STATE].set_result(True)
                    self.store.found.set_result(found)

                async def set_group_state():
                    called.append("set_group_state")
                    self.store.futures[InfoPoints.GROUP].set_result(True)
                    ts.append(hp.async_as_background(set_light_state()))

                async def start_chain():
                    called.append("start_chain")
                    await asyncio.sleep(0.1)
                    ts.append(hp.async_as_background(set_group_state()))

                filtr = mock.Mock(
                    name="filtr",
                    points=[InfoPoints.LIGHT_STATE, InfoPoints.GROUP],
                    matches_all=False,
                )
                ts.append(hp.async_as_background(start_chain()))

                res = await self.wait_for(self.store.found_from_filter(filtr))
                self.assertEqual(called, ["start_chain", "set_group_state", "set_light_state"])
                for t in ts:
                    await t
                want = Found()
                want["d073d5000002"] = found["d073d5000002"]
                self.assertEqual(res, want)

                one.matches.assert_called_once_with(filtr)
                two.matches.assert_called_once_with(filtr)

                self.assertEqual(await self.wait_for(self.store.found), found)

            async it "matches all found if filtr.matches_all":
                found = Found()
                found["d073d5000001"] = self.pretend_services()
                found["d073d5000002"] = self.pretend_services()
                found["d073d5000003"] = self.pretend_services()

                one = mock.Mock(name="one_device")
                two = mock.Mock(name="two_device")

                self.store.by_target["d073d5000001"] = one
                self.store.by_target["d073d5000002"] = two

                async def set_light_state():
                    self.store.futures[InfoPoints.LIGHT_STATE].set_result(True)
                    self.store.found.set_result(found)

                async def set_group_state():
                    self.store.futures[InfoPoints.GROUP].set_result(True)
                    hp.async_as_background(set_light_state())

                async def start_chain():
                    await asyncio.sleep(0.1)
                    hp.async_as_background(set_group_state())

                filtr = mock.Mock(
                    name="filtr",
                    points=[InfoPoints.LIGHT_STATE, InfoPoints.GROUP],
                    matches_all=True,
                )
                hp.async_as_background(start_chain())

                res = await self.wait_for(self.store.found_from_filter(filtr))
                want = Found()
                want["d073d5000001"] = found["d073d5000001"]
                want["d073d5000002"] = found["d073d5000002"]
                self.assertEqual(res, want)

                self.assertEqual(len(one.matches.mock_calls), 0)
                self.assertEqual(len(two.matches.mock_calls), 0)

                self.assertEqual(await self.wait_for(self.store.found), found)

            async it "waits on all points if for_info":
                found1 = Found()
                found1["d073d5000004"] = self.pretend_services()

                found2 = Found()
                found2["d073d5000001"] = self.pretend_services()
                found2["d073d5000002"] = self.pretend_services()
                found2["d073d5000003"] = self.pretend_services()

                one = mock.Mock(name="one_device")
                two = mock.Mock(name="two_device")

                self.store.by_target["d073d5000001"] = one
                self.store.by_target["d073d5000002"] = two

                done = asyncio.Future()
                ts = []
                called = []

                async def set_rest_state():
                    called.append("set_rest_state")
                    for point in InfoPoints:
                        if point not in (InfoPoints.LIGHT_STATE, InfoPoints.GROUP):
                            self.store.futures[point].set_result(True)
                        self.store.found.reset()
                        self.store.found.set_result(found2)

                    # We do an await here and set done so that we can be sure that
                    # found_from_filter did wait for LIGHT_STATE to finish
                    await asyncio.sleep(0.1)
                    self.store.futures[InfoPoints.LIGHT_STATE].set_result(True)
                    done.set_result(True)
                    called.append("done")

                async def set_group_state():
                    called.append("set_group_state")
                    self.store.futures[InfoPoints.GROUP].set_result(True)

                    # Set found to make sure we aren't just waiting on found
                    # but are waiting for all the info points first
                    self.store.found.set_result(found1)
                    ts.append(hp.async_as_background(set_rest_state()))

                async def start_chain():
                    called.append("start_chain")
                    await asyncio.sleep(0.1)
                    ts.append(hp.async_as_background(set_group_state()))

                filtr = mock.Mock(
                    name="filtr",
                    points=[InfoPoints.LIGHT_STATE, InfoPoints.GROUP],
                    matches_all=True,
                )
                ts.append(hp.async_as_background(start_chain()))

                res = await self.wait_for(self.store.found_from_filter(filtr))
                self.assertEqual(
                    called, ["start_chain", "set_group_state", "set_rest_state", "done"]
                )
                self.assertEqual(done.result(), True)
                await done
                for t in ts:
                    await t

                want = Found()
                want["d073d5000001"] = found2["d073d5000001"]
                want["d073d5000002"] = found2["d073d5000002"]
                self.assertEqual(res, want)

                self.assertEqual(await self.wait_for(self.store.found), found2)

            async it "complains if we timeout waitig for info points":
                filtr = Filter.empty()
                with self.fuzzyAssertRaisesError(
                    TimedOut, "Waiting for information to be available"
                ):
                    await self.store.found_from_filter(filtr, find_timeout=0.1)
