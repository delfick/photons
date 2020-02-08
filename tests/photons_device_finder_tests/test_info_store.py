# coding: spec

from photons_device_finder import InfoStore, InfoPoints, Collections, Device, Filter

from photons_app.errors import TimedOut
from photons_app import helpers as hp

from photons_transport.comms.base import Found

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from unittest import mock
import asynctest
import binascii
import asyncio
import pytest
import time


@pytest.fixture()
def loop():
    return asyncio.get_event_loop()


describe "InfoStore":
    describe "init":
        async it "sets up some things":
            loops = mock.Mock(name="loops")
            store = InfoStore(loops)
            assert store.device_finder_loops is loops

            assert type(store.found) == hp.ResettableFuture

            assert len(store.futures) == 5
            for point in InfoPoints:
                assert type(store.futures[point]) == hp.ResettableFuture

            assert store.last_touch == {}
            assert type(store.collections) == Collections
            assert dict(store.by_target) == {}
            assert dict(store.tasks_by_target) == {}

            new_device = store.by_target[binascii.unhexlify("d073d5000001")]
            assert type(new_device) == Device
            assert new_device.serial == "d073d5000001"
            assert type(store.device_spec.empty_normalise(serial="d073d5000001")) == Device

    describe "functionality":

        @pytest.fixture()
        def loops(self):
            return mock.Mock(name="loops")

        @pytest.fixture()
        def store(self, loops):
            return InfoStore(loops)

        def pretend_services(self):
            transport = mock.Mock(name="transport")
            transport.close = asynctest.mock.CoroutineMock(name="close")
            return {"UDP": transport}

        describe "finish":
            async it "cancels everything in tasks_by_target", store:
                target1 = mock.Mock(name="target1")
                target2 = mock.Mock(name="target2")
                target3 = mock.Mock(name="target3")

                task1 = mock.Mock(name="task1")
                task2 = mock.Mock(name="task2")
                task3 = mock.Mock(name="task3")

                store.tasks_by_target[target1] = task1
                store.tasks_by_target[target2] = task2
                store.tasks_by_target[target3] = task3

                assert len(task1.mock_calls) == 0
                assert len(task2.mock_calls) == 0
                assert len(task3.mock_calls) == 0

                store.finish()

                task1.cancel.assert_called_once_with()
                task2.cancel.assert_called_once_with()
                task3.cancel.assert_called_once_with()

        describe "reset_point":
            async it "resets the appropriate future", store:
                for point in InfoPoints:
                    store.futures[point].set_result(True)
                    assert store.futures[point].done()
                    store.reset_point(point)
                    assert not store.futures[point].done()

                for point in InfoPoints:
                    for p in InfoPoints:
                        store.futures[p].reset()
                        store.futures[p].set_result(True)

                    store.reset_point(point)
                    for p, fut in store.futures.items():
                        if p is point:
                            assert not store.futures[p].done()
                        else:
                            assert store.futures[p].done()

            async it "ignores points it doesn't know about", store:
                store.reset_point(1)
                assert True, "it didn't complain"

        describe "adding packets":
            async it "sets pkt on the device", store:
                target = binascii.unhexlify("d073d5000001")
                device = mock.Mock(name="device")
                device.set_from_pkt.return_value = InfoPoints.LIGHT_STATE
                pkt = mock.Mock(name="pkt", target=target)
                store.by_target[target] = device

                done = asyncio.Future()

                def set_future_done(typ, touch):
                    assert typ is InfoPoints.LIGHT_STATE
                    assert store.last_touch[typ] == touch
                    done.set_result(True)

                start = time.time()
                with mock.patch.object(store, "set_future_done", set_future_done):
                    store.add(pkt)

                await done
                assert time.time() - start > 0.2
                device.set_from_pkt.assert_called_once_with(pkt, store.collections)

            async it "doesn't call set_future_done if the future is already done", loop, store:
                target = binascii.unhexlify("d073d5000001")
                device = mock.Mock(name="device")
                device.set_from_pkt.return_value = InfoPoints.LIGHT_STATE
                pkt = mock.Mock(name="pkt", target=target)
                store.by_target[target] = device
                store.futures[InfoPoints.LIGHT_STATE].set_result(True)

                call_later = mock.Mock(name="call_later")
                with mock.patch.object(loop, "call_later", call_later):
                    store.add(pkt)

                device.set_from_pkt.assert_called_once_with(pkt, store.collections)
                assert len(call_later.mock_calls) == 0

        describe "set_future_done":
            async it "sets result if last_touch equals touch", store:
                touch = mock.Mock(name="touch")
                typ = InfoPoints.LIGHT_STATE
                store.last_touch[typ] = touch

                assert not store.futures[typ].done()
                store.set_future_done(typ, touch)
                assert store.futures[typ].done()

            async it "does not set result if last_touch is not provided touch touch", store:
                touch1 = mock.Mock(name="touch1")
                touch2 = mock.Mock(name="touch2")

                typ = InfoPoints.LIGHT_STATE
                store.last_touch[typ] = touch1

                assert not store.futures[typ].done()
                store.set_future_done(typ, touch2)
                assert not store.futures[typ].done()

        describe "info_for":
            async it "returns as_dict of matching devices minus NotSpecified fields", store:
                device1 = mock.Mock(name="device1")
                device2 = mock.Mock(name="device2")
                device3 = mock.Mock(name="device3")

                device1.as_dict.return_value = {"one": "two"}
                device2.as_dict.return_value = {"three": sb.NotSpecified}
                device3.as_dict.return_value = {"four": "five", "six": sb.NotSpecified}

                # Deliberately leave out "d074" from by_target
                uh = lambda t: binascii.unhexlify(t)
                targets = [uh(t) for t in ("d071", "d072", "d073", "d074")]
                store.by_target[uh("d071")] = device1
                store.by_target[uh("d072")] = device2
                store.by_target[uh("d073")] = device3

                result = store.info_for(targets)
                assert result == {"d071": {"one": "two"}, "d073": {"four": "five"}}

                device1.as_dict.assert_called_once_with()
                device2.as_dict.assert_called_once_with()
                device3.as_dict.assert_called_once_with()

        describe "update_found":
            async it "removes devices that don't exist anymore", store:
                store.by_target["one"] = True
                store.by_target["two"] = True
                store.by_target["three"] = True

                store.update_found({"three": mock.Mock(name="services")})

                assert list(store.by_target.keys()) == ["three"]

            async it "sets or resets found", store:
                t1 = binascii.unhexlify("d073d5000001")
                t2 = binascii.unhexlify("d073d5000002")
                found = Found()
                found[t1] = self.pretend_services()

                store.update_found(found, query_new_devices=False)
                assert (await store.found) == found

                found2 = {t2: mock.Mock(name="services")}
                store.update_found(found2, query_new_devices=False)
                assert (await store.found) == found2

            async it "can query new devices", loops, store:
                t1 = binascii.unhexlify("d073d5000001")
                t2 = binascii.unhexlify("d073d5000002")
                t3 = binascii.unhexlify("d073d5000003")

                store.by_target[t3] = mock.Mock(name="five")
                found = Found()
                found[t1] = self.pretend_services()
                found[t2] = self.pretend_services()
                found[t3] = self.pretend_services()

                futs = {t1: asyncio.Future(), t2: asyncio.Future()}

                async def add_new_device(t):
                    futs[t].set_result(True)

                loops.add_new_device = add_new_device
                store.update_found(found)

                await asyncio.wait(futs.values())

            async it "stores a task in tasks_by_target until it is finished", loops, store:
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

                loops.add_new_device = add_new_device
                store.update_found(found)

                assert len(store.tasks_by_target) == 3
                await asyncio.wait(futs.values())
                await asyncio.sleep(0.01)
                assert len(store.tasks_by_target) == 0

        describe "cleanup_task":
            async it "removes the task if it matches", loop, store:
                target = mock.Mock(name="target")

                async def blah():
                    pass

                task = loop.create_task(blah())
                store.tasks_by_target[target] = task
                store.cleanup_task(target, task, None)
                assert store.tasks_by_target == {}

            async it "does not remove if task does not matche", loop, store:
                target = mock.Mock(name="target")

                async def blah():
                    pass

                task = loop.create_task(blah())
                store.tasks_by_target[target] = task

                async def meh():
                    pass

                task2 = loop.create_task(meh())
                store.tasks_by_target[target] = task2

                store.cleanup_task(target, task, None)
                assert store.tasks_by_target == {target: task2}

                store.cleanup_task(target, task2, None)
                assert store.tasks_by_target == {}

            async it "does nothing if the target isn't in tasks_by_target", store:
                target = mock.Mock(name="target")
                task = mock.Mock(name="task")
                assert store.tasks_by_target == {}

                store.cleanup_task(target, task, None)
                assert store.tasks_by_target == {}

        describe "found_from_filter":
            async it "waits on points from filtr and removes found that doesn't match", store:
                found = Found()
                found["d073d5000001"] = self.pretend_services()
                found["d073d5000002"] = self.pretend_services()
                found["d073d5000003"] = self.pretend_services()

                one = mock.Mock(name="one_device")
                one.matches.return_value = False

                two = mock.Mock(name="two_device")
                two.matches.return_value = True

                store.by_target[binascii.unhexlify("d073d5000001")] = one
                store.by_target[binascii.unhexlify("d073d5000002")] = two

                ts = []
                called = []

                async def set_light_state():
                    called.append("set_light_state")
                    store.futures[InfoPoints.LIGHT_STATE].set_result(True)
                    store.found.set_result(found)

                async def set_group_state():
                    called.append("set_group_state")
                    store.futures[InfoPoints.GROUP].set_result(True)
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

                res = await store.found_from_filter(filtr)
                assert called == ["start_chain", "set_group_state", "set_light_state"]
                for t in ts:
                    await t
                want = Found()
                want["d073d5000002"] = found["d073d5000002"]
                assert res == want

                one.matches.assert_called_once_with(filtr)
                two.matches.assert_called_once_with(filtr)

                assert (await store.found) == found

            async it "matches all found if filtr.matches_all", store:
                found = Found()
                found["d073d5000001"] = self.pretend_services()
                found["d073d5000002"] = self.pretend_services()
                found["d073d5000003"] = self.pretend_services()

                one = mock.Mock(name="one_device")
                two = mock.Mock(name="two_device")

                store.by_target["d073d5000001"] = one
                store.by_target["d073d5000002"] = two

                async def set_light_state():
                    store.futures[InfoPoints.LIGHT_STATE].set_result(True)
                    store.found.set_result(found)

                async def set_group_state():
                    store.futures[InfoPoints.GROUP].set_result(True)
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

                res = await store.found_from_filter(filtr)
                want = Found()
                want["d073d5000001"] = found["d073d5000001"]
                want["d073d5000002"] = found["d073d5000002"]
                assert res == want

                assert len(one.matches.mock_calls) == 0
                assert len(two.matches.mock_calls) == 0

                assert (await store.found) == found

            async it "waits on all points if for_info", store:
                found1 = Found()
                found1["d073d5000004"] = self.pretend_services()

                found2 = Found()
                found2["d073d5000001"] = self.pretend_services()
                found2["d073d5000002"] = self.pretend_services()
                found2["d073d5000003"] = self.pretend_services()

                one = mock.Mock(name="one_device")
                two = mock.Mock(name="two_device")

                store.by_target["d073d5000001"] = one
                store.by_target["d073d5000002"] = two

                done = asyncio.Future()
                ts = []
                called = []

                async def set_rest_state():
                    called.append("set_rest_state")
                    for point in InfoPoints:
                        if point not in (InfoPoints.LIGHT_STATE, InfoPoints.GROUP):
                            store.futures[point].set_result(True)
                        store.found.reset()
                        store.found.set_result(found2)

                    # We do an await here and set done so that we can be sure that
                    # found_from_filter did wait for LIGHT_STATE to finish
                    await asyncio.sleep(0.1)
                    store.futures[InfoPoints.LIGHT_STATE].set_result(True)
                    done.set_result(True)
                    called.append("done")

                async def set_group_state():
                    called.append("set_group_state")
                    store.futures[InfoPoints.GROUP].set_result(True)

                    # Set found to make sure we aren't just waiting on found
                    # but are waiting for all the info points first
                    store.found.set_result(found1)
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

                res = await store.found_from_filter(filtr)
                assert called == ["start_chain", "set_group_state", "set_rest_state", "done"]
                assert done.result() == True
                await done
                for t in ts:
                    await t

                want = Found()
                want["d073d5000001"] = found2["d073d5000001"]
                want["d073d5000002"] = found2["d073d5000002"]
                assert res == want

                assert (await store.found) == found2

            async it "complains if we timeout waitig for info points", store:
                filtr = Filter.empty()
                with assertRaises(TimedOut, "Waiting for information to be available"):
                    await store.found_from_filter(filtr, find_timeout=0.1)
