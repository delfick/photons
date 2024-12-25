import asyncio
import time
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_protocol.messages import MultiOptions
from photons_transport import Gaps
from photons_transport.comms.result import Result


@pytest.fixture()
def VBase():
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

        @hp.memoized_property
        def gaps(s):
            return Gaps(
                gap_between_ack_and_res=0.2, gap_between_results=0.1, timeouts=[(1, 1)]
            ).empty_normalise()

    return V()


@pytest.fixture()
def V(VBase):
    return VBase


gaps = Gaps(
    gap_between_ack_and_res=0.2, gap_between_results=0.2, timeouts=[(0.1, 0.1)]
).empty_normalise()


class TestResult:
    async def test_it_is_a_future(self, V):
        result = Result(V.request, False, gaps)
        assert isinstance(result, asyncio.Future)
        assert not result.done()
        result.set_result([])
        assert (await result) == []

    async def test_it_sets_options(self, V):
        did_broadcast = mock.Mock(name="did_broadcast")

        result = Result(V.request, did_broadcast, gaps)
        assert result.request is V.request
        assert result.retry_gaps is gaps
        assert result.did_broadcast is did_broadcast

        assert result.results == []
        assert result.last_ack_received is None
        assert result.last_res_received is None

    async def test_it_sets_as_done_if_ack_required_and_res_required_are_both_False(self, V):
        for ack_req, res_req in [(True, False), (False, True), (True, True)]:
            V.request.ack_required = ack_req
            V.request.res_required = res_req
            result = Result(V.request, False, V.gaps)
            assert not result.done(), (ack_req, res_req)

        V.request.ack_required = False
        V.request.res_required = False
        result = Result(V.request, False, V.gaps)
        assert (await result) == []

    class TestAddPacket:

        @pytest.fixture()
        def V(self, VBase):
            V = VBase

            class V(V.__class__):
                pkt = mock.NonCallableMock(name="pkt", spec=["represents_ack"])
                addr = mock.Mock(name="addr")
                did_broadcast = mock.Mock(name="did_broadcast")

                @hp.memoized_property
                def result(s):
                    return Result(s.request, False, s.gaps)

            return V()

        async def test_it_adds_as_an_ack_if_the_packet_is_an_ack(self, V):
            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(V.result, add_ack=add_ack, add_result=add_result):
                V.pkt.represents_ack = True
                V.result.add_packet(V.pkt)

            add_ack.assert_called_once_with()
            assert len(add_result.mock_calls) == 0

        async def test_it_adds_as_a_result_if_the_packet_is_not_an_ack(self, V):
            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(V.result, add_ack=add_ack, add_result=add_result):
                V.pkt.represents_ack = False
                V.result.add_packet(V.pkt)

            add_result.assert_called_once_with((V.pkt))
            assert len(add_ack.mock_calls) == 0

        async def test_it_adds_as_a_result_if_no_represents_ack_property_on_the_pkt(self, V):
            pkt = mock.NonCallableMock(name="pkt", spec=[])

            add_ack = mock.Mock(name="add_ack")
            add_result = mock.Mock(name="add_result")

            with mock.patch.multiple(V.result, add_ack=add_ack, add_result=add_result):
                V.result.add_packet(pkt)

            add_result.assert_called_once_with(pkt)
            assert len(add_ack.mock_calls) == 0

    class TestAddAck:

        @pytest.fixture()
        def add_ack(self, V):
            def add_ack(res_required, did_broadcast, now, already_done=False):
                V.request.res_required = res_required

                t = mock.Mock(name="t", return_value=now)
                existing_result = mock.Mock(name="existing_result")
                existing_error = ValueError("Nope")
                schedule_finisher = mock.Mock(name="shcedule_finisher")

                with mock.patch("time.time", t):
                    result = Result(V.request, did_broadcast, V.gaps)

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

        async def test_it_sets_last_ack_received(self, add_ack):
            now = time.time()
            result, check_result, schedule_finisher = add_ack(
                res_required=True, did_broadcast=False, now=now, already_done=True
            )
            await check_result()
            assert result.last_ack_received == now
            assert result.last_res_received is None

        async def test_it_does_nothing_if_already_done_when_res_required_is_False(self, add_ack):
            now = time.time()
            result, check_result, schedule_finisher = add_ack(
                res_required=False, did_broadcast=False, now=now, already_done=True
            )
            assert result.last_ack_received == now
            assert result.last_res_received is None

            await check_result()
            assert len(schedule_finisher.mock_calls) == 0

        async def test_it_uses_schedule_finisher_if_not_res_required_and_we_did_broadcast(
            self, add_ack
        ):
            now = time.time()
            result, check_result, schedule_finisher = add_ack(
                res_required=False, did_broadcast=True, now=now, already_done=False
            )
            assert result.last_ack_received == now
            assert result.last_res_received is None

            assert not result.done()
            schedule_finisher.assert_called_once_with("last_ack_received")

        async def test_it_finishes_the_result_if_not_did_broadcast_and_dont_need_res(self, add_ack):
            now = time.time()
            result, check_result, schedule_finisher = add_ack(
                res_required=False, did_broadcast=False, now=now, already_done=False
            )
            assert result.last_ack_received == now
            assert result.last_res_received is None

            await check_result([])
            assert len(schedule_finisher.mock_calls) == 0

        async def test_it_does_nothing_if_not_finished_and_need_res(self, add_ack):
            for did_broadcast in (True, False):
                now = time.time()
                result, check_result, schedule_finisher = add_ack(
                    res_required=True, did_broadcast=did_broadcast, now=now, already_done=False
                )
                assert result.last_ack_received == now
                assert result.last_res_received is None

                assert not result.done()
                assert len(schedule_finisher.mock_calls) == 0

    class TestAddResult:

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
                        result = Result(V.request, False, V.gaps)
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

        async def test_it_sets_last_res_received(self, add_result):
            now = time.time()
            result, check_result, added_res, schedule_finisher = add_result(
                expected_num=1, results=[], now=now, already_done=True
            )

            await check_result()
            assert result.last_res_received == now
            assert result.last_ack_received is None

        async def test_it_does_nothing_if_already_done(self, add_result):
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

        async def test_it_completes_the_result_if_we_reached_expected_num(self, add_result):
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = add_result(
                expected_num=2, results=[one], now=now, already_done=False
            )
            assert result.last_res_received == now
            assert result.last_ack_received is None

            await check_result([one, added_res])
            assert len(schedule_finisher.mock_calls) == 0

        async def test_it_uses_schedule_finisher_if_expected_num_is_1(self, add_result):
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = add_result(
                expected_num=-1, results=[one], now=now, already_done=False
            )
            assert result.last_res_received == now
            assert result.last_ack_received is None

            assert not result.done()
            schedule_finisher.assert_called_once_with("last_res_received")

        async def test_it_does_nothing_if_we_havent_reached_num_expected_yet(self, add_result):
            now = time.time()

            one = mock.Mock(name="one")

            result, check_result, added_res, schedule_finisher = add_result(
                expected_num=3, results=[one], now=now, already_done=False
            )
            assert result.last_res_received == now
            assert result.last_ack_received is None

            assert not result.done()
            assert len(schedule_finisher.mock_calls) == 0

    class TestScheduleFinisher:

        async def test_it_calls_maybe_finish_after_finish_multi_gap_with_the_current_value_for_attr(
            self, V, FakeTime, MockedCallLater
        ):

            result = Result(V.request, False, V.gaps)
            last_ack_received = mock.Mock(name="last_ack_received")
            result.last_ack_received = last_ack_received

            fut = hp.create_future()

            def maybe_finish(current, attr):
                assert current is last_ack_received
                assert attr == "last_ack_received"
                fut.set_result(True)

            maybe_finish = mock.Mock(name="maybe_finish", side_effect=maybe_finish)

            with FakeTime() as t:
                async with MockedCallLater(t):
                    with mock.patch.object(result, "maybe_finish", maybe_finish):
                        result.schedule_finisher("last_ack_received")

                    await fut
                    assert time.time() == 0.2

    class TestMaybeFinish:
        async def test_it_does_nothing_if_the_result_is_already_done(self, V):
            result = Result(V.request, False, mock.Mock(name="gaps", spec=[]))
            result.set_result([])
            result.maybe_finish(1, "last_ack_received")

            result = Result(V.request, False, mock.Mock(name="gaps", spec=[]))
            result.set_exception(ValueError("Nope"))
            result.maybe_finish(1, "last_ack_received")

            result = Result(V.request, False, mock.Mock(name="gaps", spec=[]))
            result.cancel()
            result.maybe_finish(1, "last_ack_received")

        async def test_it_sets_result_if_last_is_same_as_what_it_is_now(self, V):
            results = mock.Mock(name="results")
            result = Result(V.request, False, V.gaps)
            result.results = results

            result.last_ack_received = 1
            result.maybe_finish(1, "last_ack_received")

            assert (await result) is results

        async def test_it_does_not_set_result_if_last_is_different_as_what_it_is_now(self, V):
            results = mock.Mock(name="results")
            result = Result(V.request, False, V.gaps)
            result.results = results

            result.last_ack_received = 2
            result.maybe_finish(1, "last_ack_received")
            assert not result.done()

            result.last_ack_received = 0
            result.maybe_finish(1, "last_ack_received")
            assert not result.done()

    class TestDetermineNumResults:
        async def test_it_says_1_if_we_are_did_broadcasting_this_packet(self, V):
            multi = mock.Mock(name="multi")
            V.request.Meta.multi = multi
            result = Result(V.request, True, V.gaps)
            assert result._determine_num_results() == -1

        async def test_it_says_1_if_multi_is_None(self, V):
            V.request.Meta.multi = None
            result = Result(V.request, False, V.gaps)
            assert result._determine_num_results() == 1

        async def test_it_says_1_if_multi_is_1(self, V):
            V.request.Meta.multi = -1
            result = Result(V.request, False, V.gaps)
            assert result._determine_num_results() == -1

        async def test_it_uses_num_results_if_that_is_already_set(self, V):
            V.request.Meta.multi = mock.NonCallableMock(name="multi", spec=[])
            result = Result(V.request, False, V.gaps)

            num_results = mock.Mock(name="num_results")
            result._num_results = num_results
            assert result._determine_num_results() is num_results

        async def test_it_says_1_if_we_have_multi_but_no_matching_packets(self, V):

            class Packet:
                def __init__(s, num, count):
                    s.num = num
                    s.count = count

                def __or__(s, other):
                    return other.num == s.num

            PacketOne = Packet(1, 10)

            result = Result(V.request, False, V.gaps)
            result.results = [(PacketOne, None, None), (PacketOne, None, None)]

            assert result._determine_num_results() == -1
            assert not hasattr(result, "_num_results")

        async def test_it_uses_multi_options_to_get_a_number_which_is_then_cached(self, V):

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

            result = Result(V.request, False, V.gaps)
            result.results = [(PacketOne, None, None), (PacketTwo, None, None)]

            got = result._determine_num_results()

            determine_res_packet.assert_called_once_with(V.request)
            adjust_expected_number.assert_called_once_with(V.request, result.results[1][0])

            assert got is count
            assert result._num_results is count

        async def test_it_uses_first_matching_packet_when_adjusting_the_number(self, V):

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

            result = Result(V.request, False, V.gaps)
            result.results = [(PacketTwo, None, None), (PacketOne, None, None)]

            got = result._determine_num_results()

            determine_res_packet.assert_called_once_with(V.request)
            adjust_expected_number.assert_called_once_with(V.request, result.results[0][0])

            assert got is count
            assert result._num_results is count

    class TestNumResults:
        async def test_it_returns_as_is_if_determine_num_results_returns_an_integer(self, V):
            for val in (-1, 1, 2):
                _determine_num_results = mock.Mock(name="_determine_num_results", return_value=val)
                result = Result(V.request, False, V.gaps)
                with mock.patch.object(result, "_determine_num_results", _determine_num_results):
                    assert result.num_results is val
                _determine_num_results.assert_called_once_with()

        async def test_it_calls_function_with_results_if_determine_num_results_returns_is_a_function(
            self, V
        ):
            count = mock.Mock(name="count")
            res = mock.Mock(name="res", return_value=count)
            _determine_num_results = mock.Mock(name="_determine_num_results", return_value=res)
            result = Result(V.request, False, V.gaps)

            with mock.patch.object(result, "_determine_num_results", _determine_num_results):
                for results in [[1, 2], [], [1], [1, 2, 3]]:
                    result.results = results

                    res.reset_mock()
                    _determine_num_results.reset_mock()

                    assert result.num_results is count
                    res.assert_called_once_with(results)
                    _determine_num_results.assert_called_once_with()

    class TestWaitForResult:

        @pytest.fixture()
        def wait_on_result(self, V):
            def wait_on_result(
                ack_required,
                res_required,
                retry_gaps,
                now,
                last_ack_received,
                last_res_received,
                results,
                num_results,
            ):
                V.request.ack_required = ack_required
                V.request.res_required = res_required

                retry_gaps = Gaps(
                    **{
                        "gap_between_ack_and_res": 10,
                        "gap_between_results": 10,
                        "timeouts": [(10, 10)],
                        **retry_gaps,
                    }
                ).empty_normalise()

                with mock.patch.object(Result, "num_results", num_results):
                    result = Result(V.request, False, retry_gaps)
                    result.results = results
                    result.last_ack_received = last_ack_received
                    result.last_res_received = last_res_received

                    t = mock.Mock(name="time", return_value=now)
                    with mock.patch("time.time", t):
                        return result.wait_for_result()

            return wait_on_result

        class TestWithNotResRequired:
            async def test_it_says_no(self, wait_on_result):
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

        class TestWithJustResRequired:
            async def test_it_says_no_if_we_havent_had_a_result_yet(self, wait_on_result):
                for num_results in (-1, 0, 1):
                    assert not wait_on_result(
                        False, True, {}, time.time(), None, None, [], num_results
                    )

            async def test_it_says_yes_if_num_results_is_1_and_we_have_a_result(
                self, wait_on_result
            ):
                assert wait_on_result(False, True, {}, time.time(), None, 1, [], -1)

            async def test_it_says_yes_if_time_since_last_res_is_less_than_gap_between_results_and_num_results_greater_than_1(
                self, wait_on_result
            ):
                now = time.time()
                last = now - 0.1
                retry_gaps = {"gap_between_results": 0.2}
                assert wait_on_result(False, True, retry_gaps, now, None, last, [], 1)

            async def test_it_says_no_if_time_since_last_res_is_greater_than_gap_between_results_and_num_results_greater_than_1(
                self, wait_on_result
            ):
                now = time.time()
                last = now - 0.3
                retry_gaps = {"gap_between_results": 0.2}
                assert not wait_on_result(False, True, retry_gaps, now, None, last, [], 1)

        class TestWithJustAckRequired:
            async def test_it_says_no_if_we_havent_had_an_ack_yet(self, wait_on_result):
                assert not wait_on_result(True, False, {}, time.time(), None, None, [], -1)

            async def test_it_says_yes_if_we_have_an_ack(self, wait_on_result):
                assert wait_on_result(True, False, {}, time.time(), 1, None, [], -1)

        class TestWithBothAckRequiredAndResRequired:
            async def test_it_says_no_if_received_no_acks(self, wait_on_result):
                assert not wait_on_result(True, True, {}, time.time(), None, None, [], 1)

            async def test_it_says_yes_if_we_have_results(self, wait_on_result):
                results = mock.Mock(name="results")
                for num_results in (-1, 0, 1):
                    assert wait_on_result(True, True, {}, time.time(), 1, 1, results, num_results)

            async def test_it_says_yes_if_its_been_less_than_gap_between_ack_and_res_since_ack_and_no_results(
                self, wait_on_result
            ):
                now = time.time()
                last = time.time() - 0.1
                retry_gaps = {"gap_between_ack_and_res": 0.2}
                for num_results in (-1, 0, 1):
                    assert wait_on_result(True, True, retry_gaps, now, last, None, [], num_results)

            async def test_it_says_yes_if_its_been_greater_than_gap_between_ack_and_res_since_ack_and_no_results(
                self, wait_on_result
            ):
                now = time.time()
                last = time.time() - 0.3
                retry_gaps = {"gap_between_ack_and_res": 0.2}
                for num_results in (-1, 0, 1):
                    assert not wait_on_result(
                        True, True, retry_gaps, now, last, None, [], num_results
                    )
