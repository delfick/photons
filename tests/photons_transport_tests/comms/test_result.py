# coding: spec

from photons_transport.comms.result import Result
from photons_transport import RetryOptions

from photons_app import helpers as hp

from photons_protocol.messages import MultiOptions

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import asyncio
import pytest
import time


@pytest.fixture()
def V():
    class V:
        original = mock.Mock(name="original")
        Meta = mock.NonCallableMock(name="Meta", spec=["multi"])

        @hp.memoized_property
        def request(s):
            request = mock.NonCallableMock(
                name="request", spec=["Meta", "res_required", "ack_required"]
            )
            request.Meta = s.Meta
            request.ack_required = True
            request.res_required = True
            return request

    return V()


describe "Result":
    async it "is a future", V:
        result = Result(V.request, False, RetryOptions())
        assert isinstance(result, asyncio.Future)
        assert not result.done()
        result.set_result([])
        assert (await result) == []

    async it "sets options", V:
        did_broadcast = mock.Mock(name="did_broadcast")
        retry_options = RetryOptions()

        result = Result(V.request, did_broadcast, retry_options)
        assert result.request is V.request
        assert result.did_broadcast is did_broadcast
        assert result.retry_options is retry_options

        assert result.results == []
        assert result.last_ack_received is None
        assert result.last_res_received is None

    async it "sets as done if ack_required and res_required are both False", V:
        for ack_req, res_req in [(True, False), (False, True), (True, True)]:
            V.request.ack_required = ack_req
            V.request.res_required = res_req
            result = Result(V.request, False, RetryOptions())
            assert not result.done(), (ack_req, res_req)

        V.request.ack_required = False
        V.request.res_required = False
        result = Result(V.request, False, RetryOptions())
        assert (await result) == []

    describe "add_packet":

        @pytest.fixture()
        def V(self, V):
            class V(V.__class__):
                pkt = mock.NonCallableMock(name="pkt", spec=["represents_ack"])
                addr = mock.Mock(name="addr")
                did_broadcast = mock.Mock(name="did_broadcast")

                @hp.memoized_property
                def result(s):
                    return Result(s.request, False, RetryOptions())

            return V()

        async it "adds as an ack if the packet is an ack", V:
            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(V.result, add_ack=add_ack, add_result=add_result):
                V.pkt.represents_ack = True
                V.result.add_packet(V.pkt, V.addr, V.original)

            add_ack.assert_called_once_with()
            assert len(add_result.mock_calls) == 0

        async it "adds as a result if the packet is not an ack", V:
            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(V.result, add_ack=add_ack, add_result=add_result):
                V.pkt.represents_ack = False
                V.result.add_packet(V.pkt, V.addr, V.original)

            add_result.assert_called_once_with((V.pkt, V.addr, V.original))
            assert len(add_ack.mock_calls) == 0

        async it "adds as a result if no represents_ack property on the pkt", V:
            pkt = mock.NonCallableMock(name="pkt", spec=[])

            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(V.result, add_ack=add_ack, add_result=add_result):
                V.result.add_packet(pkt, V.addr, V.original)

            add_result.assert_called_once_with((pkt, V.addr, V.original))
            assert len(add_ack.mock_calls) == 0

    describe "add_ack":

        @pytest.fixture()
        def add_ack(self, V):
            def add_ack(res_required, did_broadcast, now, already_done=False):
                V.request.res_required = res_required

                t = mock.Mock(name="t", return_value=now)
                existing_result = mock.Mock(name="existing_result")
                existing_error = ValueError("Nope")
                schedule_finisher = mock.Mock(name="shcedule_finisher")

                with mock.patch("time.time", t):
                    result = Result(V.request, did_broadcast, RetryOptions())

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
                            assert (await result) == expect
                        elif already_done is False:
                            assert not result.done()
                        elif already_done is True:
                            assert (await result) == existing_result
                        elif already_done == "exception":
                            with assertRaises(ValueError, "Nope"):
                                await result
                        elif already_done == "cancelled":
                            assert result.cancelled()

                    with mock.patch.object(result, "schedule_finisher", schedule_finisher):
                        result.add_ack()

                    return result, check_result, schedule_finisher

            return add_ack

        async it "sets last_ack_received", add_ack:
            now = time.time()
            result, check_result, schedule_finisher = add_ack(
                res_required=True, did_broadcast=False, now=now, already_done=True
            )
            await check_result()
            assert result.last_ack_received == now
            assert result.last_res_received is None

        async it "does nothing if already done when res_required is False", add_ack:
            now = time.time()
            result, check_result, schedule_finisher = add_ack(
                res_required=False, did_broadcast=False, now=now, already_done=True
            )
            assert result.last_ack_received == now
            assert result.last_res_received is None

            await check_result()
            assert len(schedule_finisher.mock_calls) == 0

        async it "uses schedule_finisher if not res_required and we did_broadcast", add_ack:
            now = time.time()
            result, check_result, schedule_finisher = add_ack(
                res_required=False, did_broadcast=True, now=now, already_done=False
            )
            assert result.last_ack_received == now
            assert result.last_res_received is None

            assert not result.done()
            schedule_finisher.assert_called_once_with("last_ack_received")

        async it "finishes the result if not did_broadcast and don't need res", add_ack:
            now = time.time()
            result, check_result, schedule_finisher = add_ack(
                res_required=False, did_broadcast=False, now=now, already_done=False
            )
            assert result.last_ack_received == now
            assert result.last_res_received is None

            await check_result([])
            assert len(schedule_finisher.mock_calls) == 0

        async it "does nothing if not finished and need res", add_ack:
            for did_broadcast in (True, False):
                now = time.time()
                result, check_result, schedule_finisher = add_ack(
                    res_required=True, did_broadcast=did_broadcast, now=now, already_done=False
                )
                assert result.last_ack_received == now
                assert result.last_res_received is None

                assert not result.done()
                assert len(schedule_finisher.mock_calls) == 0

    describe "add_result":

        @pytest.fixture()
        def add_result(self, V):
            def add_result(expected_num, results, now, already_done=False):
                t = mock.Mock(name="t", return_value=now)
                existing_result = mock.Mock(name="existing_result")
                existing_error = ValueError("Nope")
                schedule_finisher = mock.Mock(name="shcedule_finisher")

                added_res = mock.Mock(name="res")

                with mock.patch("time.time", t):
                    with mock.patch.object(Result, "num_results", expected_num):
                        result = Result(V.request, False, RetryOptions())
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
                                assert (await result) == expect
                            elif already_done is False:
                                assert not result.done()
                            elif already_done is True:
                                assert (await result) == existing_result
                            elif already_done == "exception":
                                with assertRaises(ValueError, "Nope"):
                                    await result
                            elif already_done == "cancelled":
                                assert result.cancelled()

                        with mock.patch.object(result, "schedule_finisher", schedule_finisher):
                            result.add_result(added_res)

                        return result, check_result, added_res, schedule_finisher

            return add_result

        async it "sets last_res_received", add_result:
            now = time.time()
            result, check_result, added_res, schedule_finisher = add_result(
                expected_num=1, results=[], now=now, already_done=True
            )

            await check_result()
            assert result.last_res_received == now
            assert result.last_ack_received is None

        async it "does nothing if already done", add_result:
            now = time.time()

            one = mock.Mock(name="one")
            two = mock.Mock(name="two")

            for expected_num, results in ([-1, [one, two]], [1, [one]], [1, []]):
                for done in (True, "exception", "cancelled"):
                    result, check_result, added_res, schedule_finisher = add_result(
                        expected_num=expected_num, results=results, now=now, already_done=done
                    )

                    await check_result()
                    assert len(schedule_finisher.mock_calls) == 0
                    assert result.results == results

        async it "completes the result if we reached expected_num", add_result:
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = add_result(
                expected_num=2, results=[one], now=now, already_done=False
            )
            assert result.last_res_received == now
            assert result.last_ack_received is None

            await check_result([one, added_res])
            assert len(schedule_finisher.mock_calls) == 0

        async it "uses schedule_finisher if expected num is -1", add_result:
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = add_result(
                expected_num=-1, results=[one], now=now, already_done=False
            )
            assert result.last_res_received == now
            assert result.last_ack_received is None

            assert not result.done()
            schedule_finisher.assert_called_once_with("last_res_received")

        async it "does nothing if we haven't reached num_expected yet", add_result:
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = add_result(
                expected_num=3, results=[one], now=now, already_done=False
            )
            assert result.last_res_received == now
            assert result.last_ack_received is None

            assert not result.done()
            assert len(schedule_finisher.mock_calls) == 0

    describe "schedule_finisher":
        async it "calls maybe_finish after finish_multi_gap with the current value for attr", V:

            class Options(RetryOptions):
                finish_multi_gap = 0.1

            result = Result(V.request, False, Options())
            last_ack_received = mock.Mock(name="last_ack_received")
            result.last_ack_received = last_ack_received

            fut = asyncio.Future()

            def maybe_finish(current, attr):
                assert current is last_ack_received
                assert attr == "last_ack_received"
                fut.set_result(True)

            maybe_finish = mock.Mock(name="maybe_finish", side_effect=maybe_finish)

            now = time.time()
            with mock.patch.object(result, "maybe_finish", maybe_finish):
                result.schedule_finisher("last_ack_received")

            await fut
            diff = time.time() - now
            assert diff < 0.2
            assert diff > 0.1

    describe "maybe_finish":
        async it "does nothing if the result is already done", V:
            result = Result(V.request, False, RetryOptions())
            result.set_result([])
            result.maybe_finish(1, "last_ack_received")

            result = Result(V.request, False, RetryOptions())
            result.set_exception(ValueError("Nope"))
            result.maybe_finish(1, "last_ack_received")

            result = Result(V.request, False, RetryOptions())
            result.cancel()
            result.maybe_finish(1, "last_ack_received")

        async it "sets result if last is same as what it is now", V:
            results = mock.Mock(name="results")
            result = Result(V.request, False, RetryOptions())
            result.results = results

            result.last_ack_received = 1
            result.maybe_finish(1, "last_ack_received")

            assert (await result) is results

        async it "does not set result if last is different as what it is now", V:
            results = mock.Mock(name="results")
            result = Result(V.request, False, RetryOptions())
            result.results = results

            result.last_ack_received = 2
            result.maybe_finish(1, "last_ack_received")
            assert not result.done()

            result.last_ack_received = 0
            result.maybe_finish(1, "last_ack_received")
            assert not result.done()

    describe "_determine_num_results":
        async it "says -1 if we are did_broadcasting this packet", V:
            multi = mock.Mock(name="multi")
            V.request.Meta.multi = multi
            result = Result(V.request, True, RetryOptions())
            assert result._determine_num_results() == -1

        async it "says 1 if multi is None", V:
            V.request.Meta.multi = None
            result = Result(V.request, False, RetryOptions())
            assert result._determine_num_results() == 1

        async it "says -1 if multi is -1", V:
            V.request.Meta.multi = -1
            result = Result(V.request, False, RetryOptions())
            assert result._determine_num_results() == -1

        async it "uses _num_results if that is already set", V:
            V.request.Meta.multi = mock.NonCallableMock(name="multi", spec=[])
            result = Result(V.request, False, RetryOptions())

            num_results = mock.Mock(name="num_results")
            result._num_results = num_results
            assert result._determine_num_results() is num_results

        async it "says -1 if we have multi but no matching packets", V:

            class Packet:
                def __init__(s, num, count):
                    s.num = num
                    s.count = count

                def __or__(s, other):
                    return other.num == s.num

            PacketOne = Packet(1, 10)
            PacketTwo = Packet(2, 20)

            multi = MultiOptions(lambda req: PacketTwo, lambda req, res: res.count)

            result = Result(V.request, False, RetryOptions())
            result.results = [(PacketOne, None, None), (PacketOne, None, None)]

            assert result._determine_num_results() == -1
            assert not hasattr(result, "_num_results")

        async it "uses multi options to get a number which is then cached", V:

            class Packet:
                def __init__(s, num, count):
                    s.num = num
                    s.count = count

                def __or__(s, other):
                    return other.num == s.num

            count = mock.Mock(name="count")

            PacketOne = Packet(1, 10)
            PacketTwo = Packet(2, count)

            determine_res_packet = mock.Mock(name="determine_res_packet", return_value=PacketTwo)
            adjust_expected_number = mock.Mock(
                name="adjust_expected_number", side_effect=lambda req, res: res.count
            )
            V.request.Meta.multi = MultiOptions(determine_res_packet, adjust_expected_number)

            result = Result(V.request, False, RetryOptions())
            result.results = [(PacketOne, None, None), (PacketTwo, None, None)]

            got = result._determine_num_results()

            determine_res_packet.assert_called_once_with(V.request)
            adjust_expected_number.assert_called_once_with(V.request, result.results[1][0])

            assert got is count
            assert result._num_results is count

        async it "uses first matching packet when adjusting the number", V:

            class Packet:
                def __init__(s, num, count):
                    s.num = num
                    s.count = count

                def __or__(s, other):
                    return other.num == s.num

            count = mock.Mock(name="count")

            PacketOne = Packet(1, 10)
            PacketTwo = Packet(2, count)

            determine_res_packet = mock.Mock(name="determine_res_packet", return_value=PacketTwo)
            adjust_expected_number = mock.Mock(
                name="adjust_expected_number", side_effect=lambda req, res: res.count
            )
            V.request.Meta.multi = MultiOptions(determine_res_packet, adjust_expected_number)

            result = Result(V.request, False, RetryOptions())
            result.results = [(PacketTwo, None, None), (PacketOne, None, None)]

            got = result._determine_num_results()

            determine_res_packet.assert_called_once_with(V.request)
            adjust_expected_number.assert_called_once_with(V.request, result.results[0][0])

            assert got is count
            assert result._num_results is count

    describe "num_results":
        async it "returns as is if _determine_num_results returns an integer", V:
            for val in (-1, 1, 2):
                _determine_num_results = mock.Mock(name="_determine_num_results", return_value=val)
                result = Result(V.request, False, RetryOptions())
                with mock.patch.object(result, "_determine_num_results", _determine_num_results):
                    assert result.num_results is val
                _determine_num_results.assert_called_once_with()

        async it "calls function with results if _determine_num_results returns is a function", V:
            count = mock.Mock(name="count")
            res = mock.Mock(name="res", return_value=count)
            _determine_num_results = mock.Mock(name="_determine_num_results", return_value=res)
            result = Result(V.request, False, RetryOptions())

            with mock.patch.object(result, "_determine_num_results", _determine_num_results):
                for results in [[1, 2], [], [1], [1, 2, 3]]:
                    result.results = results

                    res.reset_mock()
                    _determine_num_results.reset_mock()

                    assert result.num_results is count
                    res.assert_called_once_with(results)
                    _determine_num_results.assert_called_once_with()

    describe "wait_for_result":

        @pytest.fixture()
        def wait_on_result(self, V):
            def wait_on_result(
                ack_required,
                res_required,
                retry_options,
                now,
                last_ack_received,
                last_res_received,
                results,
                num_results,
            ):
                V.request.ack_required = ack_required
                V.request.res_required = res_required

                retry_options = mock.NonCallableMock(
                    name="retry_options", spec=retry_options.keys(), **retry_options
                )
                with mock.patch.object(Result, "num_results", num_results):
                    result = Result(V.request, False, retry_options)
                    result.results = results
                    result.last_ack_received = last_ack_received
                    result.last_res_received = last_res_received

                    t = mock.Mock(name="time", return_value=now)
                    with mock.patch("time.time", t):
                        return result.wait_for_result()

            return wait_on_result

        describe "with not res_required":
            async it "says no", wait_on_result:
                for ack_required in (True, False):
                    for results in ([], [1]):
                        for now in (time.time(), time.time() - 20, time.time() + 20):
                            for num_results in (-1, 0, 1):
                                assert not wait_on_result(
                                    ack_required, False, {}, now, None, None, results, num_results
                                )

                                assert not wait_on_result(
                                    ack_required, False, {}, now, None, 1, results, num_results
                                )

                                assert not wait_on_result(
                                    ack_required,
                                    False,
                                    {},
                                    now,
                                    None,
                                    now + 5,
                                    results,
                                    num_results,
                                )

        describe "with just res_required":
            async it "says no if we haven't had a result yet", wait_on_result:
                for num_results in (-1, 0, 1):
                    assert not wait_on_result(
                        False, True, {}, time.time(), None, None, [], num_results
                    )

            async it "says yes if num_results is -1 and we have a result", wait_on_result:
                assert wait_on_result(False, True, {}, time.time(), None, 1, [], -1)

            async it "says yes if time since last res is less than gap_between_results and num_results greater than -1", wait_on_result:
                now = time.time()
                last = now - 0.1
                retry_options = {"gap_between_results": 0.2}
                assert wait_on_result(False, True, retry_options, now, None, last, [], 1)

            async it "says no if time since last res is greater than gap_between_results and num_results greater than -1", wait_on_result:
                now = time.time()
                last = now - 0.3
                retry_options = {"gap_between_results": 0.2}
                assert not wait_on_result(False, True, retry_options, now, None, last, [], 1)

        describe "with just ack_required":
            async it "says no if we haven't had an ack yet", wait_on_result:
                assert not wait_on_result(True, False, {}, time.time(), None, None, [], -1)

            async it "says yes if we have an ack", wait_on_result:
                assert wait_on_result(True, False, {}, time.time(), 1, None, [], -1)

        describe "with both ack_required and res_required":
            async it "says no if received no acks", wait_on_result:
                assert not wait_on_result(True, True, {}, time.time(), None, None, [], 1)

            async it "says yes if we have results", wait_on_result:
                results = mock.Mock(name="results")
                for num_results in (-1, 0, 1):
                    assert wait_on_result(True, True, {}, time.time(), 1, 1, results, num_results)

            async it "says yes if it's been less than gap_between_ack_and_res since ack and no results", wait_on_result:
                now = time.time()
                last = time.time() - 0.1
                retry_options = {"gap_between_ack_and_res": 0.2}
                for num_results in (-1, 0, 1):
                    assert wait_on_result(
                        True, True, retry_options, now, last, None, [], num_results
                    )

            async it "says yes if it's been greater than gap_between_ack_and_res since ack and no results", wait_on_result:
                now = time.time()
                last = time.time() - 0.3
                retry_options = {"gap_between_ack_and_res": 0.2}
                for num_results in (-1, 0, 1):
                    assert not wait_on_result(
                        True, True, retry_options, now, last, None, [], num_results
                    )
