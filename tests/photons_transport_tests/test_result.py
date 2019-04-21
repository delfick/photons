# coding: spec

from photons_transport.target.retry_options import RetryOptions
from photons_transport.target.result import Result

from photons_app.test_helpers import AsyncTestCase

from photons_protocol.messages import MultiOptions

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import asyncio
import time

describe AsyncTestCase, "Result":
    async before_each:
        self.request = mock.NonCallableMock(name="request", spec=["Meta", "res_required", "ack_required"])
        self.Meta = mock.NonCallableMock(name="Meta", spec=["multi"])
        self.request.Meta = self.Meta
        self.request.ack_required = True
        self.request.res_required = True

    async it "is a future":
        result = Result(self.request, False, RetryOptions())
        self.assertIsInstance(result, asyncio.Future)
        assert not result.done()
        result.set_result([])
        self.assertEqual(await self.wait_for(result), [])

    async it "sets options":
        broadcast = mock.Mock(name="broadcast")
        retry_options = RetryOptions()

        result = Result(self.request, broadcast, retry_options)
        self.assertIs(result.request, self.request)
        self.assertIs(result.broadcast, broadcast)
        self.assertIs(result.retry_options, retry_options)

        self.assertEqual(result.results, [])
        self.assertIs(result.last_ack_received, None)
        self.assertIs(result.last_res_received, None)

    async it "sets as done if ack_required and res_required are both False":
        for ack_req, res_req in [(True, False), (False, True), (True, True)]:
            self.request.ack_required = ack_req
            self.request.res_required = res_req
            result = Result(self.request, False, RetryOptions())
            assert not result.done(), (ack_req, res_req)

        self.request.ack_required = False
        self.request.res_required = False
        result = Result(self.request, False, RetryOptions())
        self.assertEqual(await self.wait_for(result), [])

    describe "add_packet":
        async before_each:
            self.pkt = mock.NonCallableMock(name="pkt", spec=["represents_ack"])
            self.addr = mock.Mock(name="addr")
            self.broadcast = mock.Mock(name="broadcast")

            self.result = Result(self.request, False, RetryOptions())

        async it "adds as an ack if the packet is an ack":
            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(self.result, add_ack=add_ack, add_result=add_result):
                self.pkt.represents_ack = True
                self.result.add_packet(self.pkt, self.addr, self.broadcast)

            add_ack.assert_called_once_with()
            self.assertEqual(len(add_result.mock_calls), 0)

        async it "adds as a result if the packet is not an ack":
            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(self.result, add_ack=add_ack, add_result=add_result):
                self.pkt.represents_ack = False
                self.result.add_packet(self.pkt, self.addr, self.broadcast)

            add_result.assert_called_once_with((self.pkt, self.addr, self.broadcast))
            self.assertEqual(len(add_ack.mock_calls), 0)

        async it "adds as a result if no represents_ack property on the pkt":
            pkt = mock.NonCallableMock(name="pkt", spec=[])

            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(self.result, add_ack=add_ack, add_result=add_result):
                self.result.add_packet(pkt, self.addr, self.broadcast)

            add_result.assert_called_once_with((pkt, self.addr, self.broadcast))
            self.assertEqual(len(add_ack.mock_calls), 0)

    describe "add_ack":
        def add_ack(self, res_required, broadcast, now, already_done=False):
            self.request.res_required = res_required

            t = mock.Mock(name="t", return_value=now)
            existing_result = mock.Mock(name="existing_result")
            existing_error = ValueError("Nope")
            schedule_finisher = mock.Mock(name="shcedule_finisher")

            with mock.patch("time.time", t):
                result = Result(self.request, broadcast, RetryOptions())

                if already_done is not False:
                    if already_done is True:
                        result.set_result(existing_result)
                    elif already_done == "exception":
                        result.set_exception(existing_error)
                    elif already_done == "cancelled":
                        result.cancel()
                    else:
                        raise Exception(f"Unexpected already_done value, {already_done}")

                async def check_result(expect=None):
                    if expect is not None:
                        self.assertEqual(await self.wait_for(result), expect)
                    elif already_done is False:
                        assert not result.done()
                    elif already_done is True:
                        self.assertEqual(await self.wait_for(result), existing_result)
                    elif already_done == "exception":
                        with self.fuzzyAssertRaisesError(ValueError, "Nope"):
                            await self.wait_for(result)
                    elif already_done == "cancelled":
                        assert result.cancelled()

                with mock.patch.object(result, "schedule_finisher", schedule_finisher):
                    result.add_ack()

                return result, check_result, schedule_finisher

        async it "sets last_ack_received":
            now = time.time()
            result, check_result, schedule_finisher = self.add_ack(res_required=True, broadcast=False, now=now, already_done=True)
            await check_result()
            self.assertEqual(result.last_ack_received, now)
            self.assertIs(result.last_res_received, None)

        async it "does nothing if already done when res_required is False":
            now = time.time()
            result, check_result, schedule_finisher = self.add_ack(res_required=False, broadcast=False, now=now, already_done=True)
            self.assertEqual(result.last_ack_received, now)
            self.assertIs(result.last_res_received, None)

            await check_result()
            self.assertEqual(len(schedule_finisher.mock_calls), 0)

        async it "uses schedule_finisher if not res_required and we broadcast":
            now = time.time()
            result, check_result, schedule_finisher = self.add_ack(res_required=False, broadcast=True, now=now, already_done=False)
            self.assertEqual(result.last_ack_received, now)
            self.assertIs(result.last_res_received, None)

            assert not result.done()
            schedule_finisher.assert_called_once_with("last_ack_received")

        async it "finishes the result if not broadcast and don't need res":
            now = time.time()
            result, check_result, schedule_finisher = self.add_ack(res_required=False, broadcast=False, now=now, already_done=False)
            self.assertEqual(result.last_ack_received, now)
            self.assertIs(result.last_res_received, None)

            await check_result([])
            self.assertEqual(len(schedule_finisher.mock_calls), 0)

        async it "does nothing if not finished and need res":
            for broadcast in (True, False):
                now = time.time()
                result, check_result, schedule_finisher = self.add_ack(res_required=True, broadcast=broadcast, now=now, already_done=False)
                self.assertEqual(result.last_ack_received, now)
                self.assertIs(result.last_res_received, None)

                assert not result.done()
                self.assertEqual(len(schedule_finisher.mock_calls), 0)

    describe "add_result":
        def add_result(self, expected_num, results, now, already_done=False):
            t = mock.Mock(name="t", return_value=now)
            existing_result = mock.Mock(name="existing_result")
            existing_error = ValueError("Nope")
            schedule_finisher = mock.Mock(name="shcedule_finisher")

            added_res = mock.Mock(name="res")

            with mock.patch("time.time", t):
                with mock.patch.object(Result, "num_results", expected_num):
                    result = Result(self.request, False, RetryOptions())
                    result.results = list(results)

                    if already_done is not False:
                        if already_done is True:
                            result.set_result(existing_result)
                        elif already_done == "exception":
                            result.set_exception(existing_error)
                        elif already_done == "cancelled":
                            result.cancel()
                        else:
                            raise Exception(f"Unexpected already_done value, {already_done}")

                    async def check_result(expect=None):
                        if expect is not None:
                            self.assertEqual(await self.wait_for(result), expect)
                        elif already_done is False:
                            assert not result.done()
                        elif already_done is True:
                            self.assertEqual(await self.wait_for(result), existing_result)
                        elif already_done == "exception":
                            with self.fuzzyAssertRaisesError(ValueError, "Nope"):
                                await self.wait_for(result)
                        elif already_done == "cancelled":
                            assert result.cancelled()

                    with mock.patch.object(result, "schedule_finisher", schedule_finisher):
                        result.add_result(added_res)

                    return result, check_result, added_res, schedule_finisher

        async it "sets last_res_received":
            now = time.time()
            result, check_result, added_res, schedule_finisher = self.add_result(
                  expected_num=1, results=[], now=now, already_done=True
                )

            await check_result()
            self.assertEqual(result.last_res_received, now)
            self.assertIs(result.last_ack_received, None)

        async it "does nothing if already done":
            now = time.time()

            one = mock.Mock(name="one")
            two = mock.Mock(name="two")

            for expected_num, results in ([-1, [one, two]], [1, [one]], [1, []]):
                for done in (True, "exception", "cancelled"):
                    result, check_result, added_res, schedule_finisher = self.add_result(
                          expected_num=expected_num, results=results, now=now, already_done=done
                        )

                    await check_result()
                    self.assertEqual(len(schedule_finisher.mock_calls), 0)
                    self.assertEqual(result.results, results)

        async it "completes the result if we reached expected_num":
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = self.add_result(
                  expected_num=2, results=[one], now=now, already_done=False
                )
            self.assertEqual(result.last_res_received, now)
            self.assertIs(result.last_ack_received, None)

            await check_result([one, added_res])
            self.assertEqual(len(schedule_finisher.mock_calls), 0)

        async it "uses schedule_finisher if expected num is -1":
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = self.add_result(
                  expected_num=-1, results=[one], now=now, already_done=False
                )
            self.assertEqual(result.last_res_received, now)
            self.assertIs(result.last_ack_received, None)

            assert not result.done()
            schedule_finisher.assert_called_once_with("last_res_received")

        async it "does nothing if we haven't reached num_expected yet":
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = self.add_result(
                  expected_num=3, results=[one], now=now, already_done=False
                )
            self.assertEqual(result.last_res_received, now)
            self.assertIs(result.last_ack_received, None)

            assert not result.done()
            self.assertEqual(len(schedule_finisher.mock_calls), 0)

    describe "schedule_finisher":
        async it "calls maybe_finish after finish_multi_gap with the current value for attr":
            class Options(RetryOptions):
                finish_multi_gap = 0.1

            result = Result(self.request, False, Options())
            last_ack_received = mock.Mock(name="last_ack_received")
            result.last_ack_received = last_ack_received

            fut = asyncio.Future()

            def maybe_finish(current, attr):
                self.assertIs(current, last_ack_received)
                self.assertEqual(attr, "last_ack_received")
                fut.set_result(True)
            maybe_finish = mock.Mock(name="maybe_finish", side_effect=maybe_finish)

            now = time.time()
            with mock.patch.object(result, "maybe_finish", maybe_finish):
                result.schedule_finisher("last_ack_received")

            await self.wait_for(fut)
            diff = time.time() - now
            self.assertLess(diff, 0.2)
            self.assertGreater(diff, 0.1)

    describe "maybe_finish":
        async it "does nothing if the result is already done":
            result = Result(self.request, False, RetryOptions())
            result.set_result([])
            result.maybe_finish(1, "last_ack_received")

            result = Result(self.request, False, RetryOptions())
            result.set_exception(ValueError("Nope"))
            result.maybe_finish(1, "last_ack_received")

            result = Result(self.request, False, RetryOptions())
            result.cancel()
            result.maybe_finish(1, "last_ack_received")

        async it "sets result if last is same as what it is now":
            results = mock.Mock(name="results")
            result = Result(self.request, False, RetryOptions())
            result.results = results

            result.last_ack_received = 1
            result.maybe_finish(1, "last_ack_received")

            self.assertIs(await self.wait_for(result), results)

        async it "does not set result if last is different as what it is now":
            results = mock.Mock(name="results")
            result = Result(self.request, False, RetryOptions())
            result.results = results

            result.last_ack_received = 2
            result.maybe_finish(1, "last_ack_received")
            assert not result.done()

            result.last_ack_received = 0
            result.maybe_finish(1, "last_ack_received")
            assert not result.done()

    describe "_determine_num_results":
        async it "says -1 if we are broadcasting this packet":
            multi = mock.Mock(name="multi")
            self.request.Meta.multi = multi
            result = Result(self.request, True, RetryOptions())
            self.assertEqual(result._determine_num_results(), -1)

        async it "says 1 if multi is None":
            self.request.Meta.multi = None
            result = Result(self.request, False, RetryOptions())
            self.assertEqual(result._determine_num_results(), 1)

        async it "says -1 if multi is -1":
            self.request.Meta.multi = -1
            result = Result(self.request, False, RetryOptions())
            self.assertEqual(result._determine_num_results(), -1)

        async it "uses _num_results if that is already set":
            self.request.Meta.multi = mock.NonCallableMock(name="multi", spec=[])
            result = Result(self.request, False, RetryOptions())

            num_results = mock.Mock(name="num_results")
            result._num_results = num_results
            self.assertIs(result._determine_num_results(), num_results)

        async it "says -1 if we have multi but no matching packets":
            class Packet:
                def __init__(self, num, count):
                    self.num = num
                    self.count = count

                def __or__(self, other):
                    return other.num == self.num

            PacketOne = Packet(1, 10)
            PacketTwo = Packet(2, 20)

            multi = MultiOptions(
                  lambda req: PacketTwo
                , lambda req, res: res.count
                )

            result = Result(self.request, False, RetryOptions())
            result.results = [(PacketOne, None, None), (PacketOne, None, None)]

            self.assertEqual(result._determine_num_results(), -1)
            assert not hasattr(result, "_num_results")

        async it "uses multi options to get a number which is then cached":
            class Packet:
                def __init__(self, num, count):
                    self.num = num
                    self.count = count

                def __or__(self, other):
                    return other.num == self.num

            count = mock.Mock(name="count")

            PacketOne = Packet(1, 10)
            PacketTwo = Packet(2, count)

            determine_res_packet = mock.Mock(name="determine_res_packet", return_value=PacketTwo)
            adjust_expected_number = mock.Mock(name="adjust_expected_number", side_effect=lambda req, res: res.count)
            self.request.Meta.multi = MultiOptions(determine_res_packet, adjust_expected_number)

            result = Result(self.request, False, RetryOptions())
            result.results = [(PacketOne, None, None), (PacketTwo, None, None)]

            got = result._determine_num_results()

            determine_res_packet.assert_called_once_with(self.request)
            adjust_expected_number.assert_called_once_with(self.request, result.results[1][0])

            self.assertIs(got, count)
            self.assertIs(result._num_results, count)

        async it "uses first matching packet when adjusting the number":
            class Packet:
                def __init__(self, num, count):
                    self.num = num
                    self.count = count

                def __or__(self, other):
                    return other.num == self.num

            count = mock.Mock(name="count")

            PacketOne = Packet(1, 10)
            PacketTwo = Packet(2, count)

            determine_res_packet = mock.Mock(name="determine_res_packet", return_value=PacketTwo)
            adjust_expected_number = mock.Mock(name="adjust_expected_number", side_effect=lambda req, res: res.count)
            self.request.Meta.multi = MultiOptions(determine_res_packet, adjust_expected_number)

            result = Result(self.request, False, RetryOptions())
            result.results = [(PacketTwo, None, None), (PacketOne, None, None)]

            got = result._determine_num_results()

            determine_res_packet.assert_called_once_with(self.request)
            adjust_expected_number.assert_called_once_with(self.request, result.results[0][0])

            self.assertIs(got, count)
            self.assertIs(result._num_results, count)

    describe "num_results":
        async it "returns as is if _determine_num_results returns an integer":
            for val in (-1, 1, 2):
                _determine_num_results = mock.Mock(name="_determine_num_results", return_value=val)
                result = Result(self.request, False, RetryOptions())
                with mock.patch.object(result, "_determine_num_results", _determine_num_results):
                    self.assertIs(result.num_results, val)
                _determine_num_results.assert_called_once_with()

        async it "calls function with results if _determine_num_results returns is a function":
            count = mock.Mock(name="count")
            res = mock.Mock(name="res", return_value=count)
            _determine_num_results = mock.Mock(name="_determine_num_results", return_value=res)
            result = Result(self.request, False, RetryOptions())

            with mock.patch.object(result, "_determine_num_results", _determine_num_results):
                for results in [[1, 2], [], [1], [1, 2, 3]]:
                    result.results = results

                    res.reset_mock()
                    _determine_num_results.reset_mock()

                    self.assertIs(result.num_results, count)
                    res.assert_called_once_with(results)
                    _determine_num_results.assert_called_once_with()

    describe "wait_for_result":
        def wait_for_result(self, ack_required, res_required, retry_options, now, last_ack_received, last_res_received, results, num_results):
            self.request.ack_required = ack_required
            self.request.res_required = res_required

            retry_options = mock.NonCallableMock(name="retry_options", spec=retry_options.keys(), **retry_options)
            with mock.patch.object(Result, "num_results", num_results):
                result = Result(self.request, False, retry_options)
                result.results = results
                result.last_ack_received = last_ack_received
                result.last_res_received = last_res_received

                t = mock.Mock(name="time", return_value=now)
                with mock.patch("time.time", t):
                    return result.wait_for_result()

        describe "with not res_required":
            async it "says no":
                for ack_required in (True, False):
                    for results in ([], [1]):
                        for now in (time.time(), time.time() - 20, time.time() + 20):
                            for num_results in (-1, 0, 1):
                                assert not self.wait_for_result(ack_required, False, {}, now, None, None, results, num_results)

                                assert not self.wait_for_result(ack_required, False, {}, now, None, 1, results, num_results)

                                assert not self.wait_for_result(ack_required, False, {}, now, None, now + 5, results, num_results)

        describe "with just res_required":
            async it "says no if we haven't had a result yet":
                for num_results in (-1, 0, 1):
                    assert not self.wait_for_result(False, True, {}, time.time(), None, None, [], num_results)

            async it "says yes if num_results is -1 and we have a result":
                assert self.wait_for_result(False, True, {}, time.time(), None, 1, [], -1)

            async it "says yes if time since last res is less than gap_between_results and num_results greater than -1":
                now = time.time()
                last = now - 0.1
                retry_options = {"gap_between_results": 0.2}
                assert self.wait_for_result(False, True, retry_options, now, None, last, [], 1)

            async it "says no if time since last res is greater than gap_between_results and num_results greater than -1":
                now = time.time()
                last = now - 0.3
                retry_options = {"gap_between_results": 0.2}
                assert not self.wait_for_result(False, True, retry_options, now, None, last, [], 1)

        describe "with just ack_required":
            async it "says no if we haven't had an ack yet":
                assert not self.wait_for_result(True, False, {}, time.time(), None, None, [], -1)

            async it "says yes if we have an ack":
                assert self.wait_for_result(True, False, {}, time.time(), 1, None, [], -1)

        describe "with both ack_required and res_required":
            async it "says no if received no acks":
                assert not self.wait_for_result(True, True, {}, time.time(), None, None, [], 1)

            async it "says yes if we have results":
                results = mock.Mock(name="results")
                for num_results in (-1, 0, 1):
                    assert self.wait_for_result(True, True, {}, time.time(), 1, 1, results, num_results)

            async it "says yes if it's been less than gap_between_ack_and_res since ack and no results":
                now = time.time()
                last = time.time() - 0.1
                retry_options = {"gap_between_ack_and_res": 0.2}
                for num_results in (-1, 0, 1):
                    assert self.wait_for_result(True, True, retry_options, now, last, None, [], num_results)

            async it "says yes if it's been greater than gap_between_ack_and_res since ack and no results":
                now = time.time()
                last = time.time() - 0.3
                retry_options = {"gap_between_ack_and_res": 0.2}
                for num_results in (-1, 0, 1):
                    assert not self.wait_for_result(True, True, retry_options, now, last, None, [], num_results)
