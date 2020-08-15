# coding: spec

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import threading
import asyncio
import pytest
import time
import uuid


@pytest.fixture()
def stop_fut():
    stop_fut = hp.create_future()
    try:
        yield stop_fut
    finally:
        stop_fut.cancel()


describe "ThreadToAsyncQueue":

    @pytest.fixture()
    def ttaq(self, stop_fut):
        def ttaq(num_threads):
            ttaq = hp.ThreadToAsyncQueue(stop_fut, num_threads, mock.Mock(name="onerror"))

            class ACM:
                async def __aenter__(s):
                    await ttaq.start()
                    return ttaq

                async def __aexit__(s, exc_type, exc, tb):
                    await ttaq.finish()

                    if exc:
                        exc.__traceback__ = tb
                        # Make sure the error gets risen
                        return False

            return ACM()

        return ttaq

    async it "works", ttaq:
        called = []
        async with ttaq(2) as ttaq:

            def action():
                time.sleep(0.03)
                called.append(1)
                return 1

            res = ttaq.request(action)

            def action2():
                called.append(2)
                return 2

            res2 = ttaq.request(action2)

            assert (await res) == 1
            assert (await res2) == 2

            # Proof that action2 wasn't held up by action
            assert called == [2, 1]

            ttaq.stop_fut.cancel()
            with assertRaises(asyncio.CancelledError):
                await ttaq.request(lambda: 1)

    describe "white box testing":

        @pytest.fixture()
        def ttaq(self, stop_fut):
            # Deliberately don't start the queue so that we can do that stuff manually
            return hp.ThreadToAsyncQueue(stop_fut, 1, mock.Mock(name="onerror"))

        describe "request":
            async it "puts the func on the queue ready to be picked up by a thread", ttaq:
                func = mock.Mock(name="func")
                key = "key"

                assert ttaq.queue.collection.empty()
                assert len(ttaq.futures) == 0

                with mock.patch("secrets.token_urlsafe", lambda _: key):
                    fut = ttaq.request(func)

                assert ttaq.queue.collection.qsize() == 1
                thing = ttaq.queue.collection.get()

                assert thing == (key, func)
                assert ttaq.futures[key] is fut

        describe "find_and_set_future":
            async it "does nothing if the key isn't known", ttaq:
                key = str(uuid.uuid1())
                assert key not in ttaq.futures
                assert (
                    ttaq.find_and_set_future(
                        key, mock.Mock(name="result"), mock.Mock(name="exception")
                    )
                ) is None

            async it "sets exception on the future if result is Nope", ttaq:
                key = str(uuid.uuid1())
                fut = hp.create_future()
                ttaq.futures[key] = fut

                result = hp.Nope
                exception = PhotonsAppError("blah")

                assert not fut.done() and not fut.cancelled()
                ttaq.find_and_set_future(key, result, exception)

                assert fut.exception() is exception

            async it "otherwise sets result on the future", ttaq:
                key = str(uuid.uuid1())
                fut = hp.create_future()
                ttaq.futures[key] = fut

                result = mock.Mock(name="result")
                exception = None

                assert not fut.done() and not fut.cancelled()
                ttaq.find_and_set_future(key, result, exception)

                assert fut.result() is result

        describe "process":
            async it "calls the procedure and puts result on the result_queue", ttaq:
                key = str(uuid.uuid1())
                action_result = mock.Mock(name="action_result")

                def action():
                    return action_result

                thread = threading.Thread(target=ttaq.process, args=(key, action))
                thread.daemon = True
                thread.start()

                async for result in ttaq.result_queue:
                    assert result == (key, action_result, hp.Nope)
                    break

            async it "gives you the exception when it fails", ttaq:
                key = str(uuid.uuid1())
                onerror = mock.Mock(name="onerror")
                ttaq.onerror = onerror

                error = PhotonsAppError("Much fail")
                called = []

                def action():
                    called.append("action")
                    raise error

                thread = threading.Thread(target=ttaq.process, args=(key, action))
                thread.daemon = True
                thread.start()

                async for result in ttaq.result_queue:
                    assert result == (key, hp.Nope, error)
                    assert called == ["action"]
                    onerror.assert_called_once_with((PhotonsAppError, error, mock.ANY))
                    break

describe "ThreadToAsyncQueuewith custom args":

    @pytest.fixture()
    def ttaq(self, stop_fut):
        def ttaq(num_threads, create_args):
            class Queue(hp.ThreadToAsyncQueue):
                def create_args(s, thread_number, existing):
                    return create_args(thread_number, existing=existing)

            ttaq = Queue(stop_fut, num_threads, mock.Mock(name="onerror"))

            class ACM:
                async def __aenter__(s):
                    await ttaq.start()
                    return ttaq, create_args

                async def __aexit__(s, exc_type, exc, tb):
                    await ttaq.finish()

                    if exc:
                        exc.__traceback__ = tb
                        # Make sure the error gets risen
                        return False

            return ACM()

        return ttaq

    async it "calls create_args when we start and before every request", ttaq:
        things = {}
        create_args = mock.Mock(name="create_args")

        for k in range(2):
            things[k] = [mock.Mock(name=f"thing{k}_{i}") for i in range(20)]

        info = {0: 0, 1: 0}
        calls = {0: [], 1: []}
        requests = []

        def ca(thread_number, existing):
            thing = things[thread_number][info[thread_number]]
            info[thread_number] += 1
            calls[thread_number].append(existing)
            requests.append(mock.call(thing))
            return (thing,)

        create_args.side_effect = ca

        async with ttaq(2, create_args) as (ttaq, create_args):
            assert create_args.mock_calls == [
                mock.call(0, existing=None),
                mock.call(1, existing=None),
            ]
            create_args.reset_mock()

            request = mock.Mock(name="request")
            for i in range(10):
                await ttaq.request(request)

            # The first two aren't used because they are made when we start the queue
            # In a real implementation they probably wouldn't be discarded straight away!
            assert request.mock_calls == requests[2:]

            # We can't guarantee the order between two threads, so we just make sure they're in the correct order
            assert len(calls[0]) > 2
            assert len(calls[1]) > 2
            assert calls[0] == [None, *[(t,) for t in things[0][: len(calls[0]) - 1]]]
            assert calls[1] == [None, *[(t,) for t in things[1][: len(calls[1]) - 1]]]
