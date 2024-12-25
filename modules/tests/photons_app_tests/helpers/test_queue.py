import asyncio
from collections import deque
from queue import Queue as NormalQueue

import pytest
from photons_app import helpers as hp


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


class TestQueue:
    def test_it_takes_in_a_final_future(self, final_future):
        queue = hp.Queue(final_future)

        compare = pytest.helpers.child_future_of(final_future)
        assert queue.final_future == compare

        assert hp.fut_has_callback(queue.final_future, queue._stop_waiter)

        assert isinstance(queue.collection, deque)

        assert isinstance(queue.waiter, hp.ResettableFuture)
        assert not queue.waiter.done()

    async def test_it_can_stop_the_waiter_on_done(self, final_future):
        queue = hp.Queue(final_future)

        assert isinstance(queue.waiter, hp.ResettableFuture)
        assert not queue.waiter.done()

        final_future.cancel()
        await asyncio.sleep(0.001)

        assert queue.waiter.done()

        # And if the waiter was already done
        queue = hp.Queue(final_future)

        assert isinstance(queue.waiter, hp.ResettableFuture)
        queue.waiter.set_result(True)

        final_future.cancel()
        await asyncio.sleep(0.001)

        assert queue.waiter.done()

    async def test_it_can_get_remaining_items(self, final_future):
        queue = hp.Queue(final_future)
        assert not queue.waiter.done()

        queue.append(1)
        assert queue.waiter.done()

        queue.append(2)

        assert list(queue.remaining()) == [1, 2]

        assert not queue.collection

    class TestGettingAllResults:
        async def test_it_can_get_results_until_final_future_is_done(self, final_future):
            wait = hp.create_future()

            queue = hp.Queue(final_future)

            ff = hp.create_future()
            found = []

            async def fill():
                for i in (2, 3, 4):
                    queue.append(i)
                await wait
                for i in (5, 6, 7):
                    queue.append(i)

            try:
                async with hp.TaskHolder(ff) as ts:
                    ts.add(fill())

                    queue.append(1)

                    async for item in queue:
                        if item == 5:
                            final_future.cancel()

                        found.append(item)

                        if item == 4:
                            wait.set_result(True)
            finally:
                ff.cancel()

            # The queue will drop remaining items
            assert found == [1, 2, 3, 4, 5]
            assert list(queue.remaining()) == [6, 7]

        async def test_it_ignores_results_added_after_final_future_is_done_if_still_waiting_for_results(
            self, final_future
        ):
            wait = hp.create_future()

            queue = hp.Queue(final_future)

            ff = hp.create_future()
            found = []

            async def fill():
                for i in (2, 3, 4):
                    queue.append(i)
                await wait
                final_future.cancel()
                for i in (5, 6, 7):
                    queue.append(i)

            try:
                async with hp.TaskHolder(ff) as ts:
                    ts.add(fill())

                    queue.append(1)

                    async for item in queue:
                        found.append(item)

                        if item == 4:
                            wait.set_result(True)
            finally:
                ff.cancel()

            # The queue will drop remaining items
            assert found == [1, 2, 3, 4]
            assert list(queue.remaining()) == [5, 6, 7]

        async def test_it_is_re_entrant_if_we_break(self, final_future):
            found = []
            queue = hp.Queue(final_future)

            for i in range(10):
                queue.append(i)

            async for item in queue:
                found.append(item)

                if item == 3:
                    break

            assert found == [0, 1, 2, 3]

            async for item in queue:
                found.append(item)
                if item == 9:
                    final_future.cancel()

            assert found == list(range(10))

    class TestGettingAllResultsAndEmptyOnFinished:
        async def test_it_can_get_results_until_final_future_is_done(self, final_future):
            wait = hp.create_future()

            queue = hp.Queue(final_future, empty_on_finished=True)

            ff = hp.create_future()
            found = []

            async def fill():
                for i in (2, 3, 4):
                    queue.append(i)
                await wait
                for i in (5, 6, 7):
                    queue.append(i)

            try:
                async with hp.TaskHolder(ff) as ts:
                    ts.add(fill())

                    queue.append(1)

                    async for item in queue:
                        if item == 5:
                            final_future.cancel()

                        found.append(item)

                        if item == 4:
                            wait.set_result(True)
            finally:
                ff.cancel()

            # The queue will not drop remaining items
            assert found == [1, 2, 3, 4, 5, 6, 7]
            assert list(queue.remaining()) == []

        async def test_it_gets_results_added_after_final_future_is_done_if_still_waiting_for_results(
            self, final_future
        ):
            wait = hp.create_future()

            queue = hp.Queue(final_future, empty_on_finished=True)

            ff = hp.create_future()
            found = []

            async def fill():
                for i in (2, 3, 4):
                    queue.append(i)
                await wait
                final_future.cancel()
                for i in (5, 6, 7):
                    queue.append(i)

            try:
                async with hp.TaskHolder(ff) as ts:
                    ts.add(fill())

                    queue.append(1)

                    async for item in queue:
                        found.append(item)

                        if item == 4:
                            wait.set_result(True)
            finally:
                ff.cancel()

            # The queue will not drop remaining items
            assert found == [1, 2, 3, 4, 5, 6, 7]
            assert list(queue.remaining()) == []

        async def test_it_is_re_entrant_if_we_break(self, final_future):
            found = []
            queue = hp.Queue(final_future, empty_on_finished=True)

            for i in range(10):
                queue.append(i)

            async for item in queue:
                found.append(item)

                if item == 3:
                    break

            assert found == [0, 1, 2, 3]

            async for item in queue:
                found.append(item)
                if item == 9:
                    final_future.cancel()

            assert found == list(range(10))


class TestSyncQueue:
    def test_it_takes_in_a_final_future(self, final_future):
        queue = hp.SyncQueue(final_future)

        compare = pytest.helpers.child_future_of(final_future)
        assert queue.final_future == compare
        assert queue.timeout == 0.05

        assert isinstance(queue.collection, NormalQueue)

        queue = hp.SyncQueue(final_future, timeout=1)
        assert queue.timeout == 1

    def test_it_can_append_items(self, final_future):
        queue = hp.SyncQueue(final_future)

        queue.append(1)
        queue.append(2)

        found = []
        for item in queue:
            found.append(item)
            if item == 2:
                break

        assert found == [1, 2]

        queue.append(3)
        found = []
        for item in queue:
            found.append(item)
            final_future.cancel()
        assert found == [3]

    async def test_it_can_get_remaining_items(self, final_future):
        queue = hp.SyncQueue(final_future)

        queue.append(1)
        queue.append(2)

        assert list(queue.remaining()) == [1, 2]
        assert queue.collection.empty()

    class TestGettingAllResults:

        async def test_it_can_get_results_until_final_future_is_done(self, final_future):
            wait = hp.create_future()

            queue = hp.SyncQueue(final_future)

            ff = hp.create_future()
            found = []

            async def fill():
                for i in (2, 3, 4):
                    queue.append(i)
                await wait
                for i in (5, 6, 7):
                    queue.append(i)

            try:
                async with hp.TaskHolder(ff) as ts:
                    ts.add(fill())

                    queue.append(1)

                    for item in queue:
                        if item == 5:
                            final_future.cancel()

                        found.append(item)

                        if item == 4:
                            wait.set_result(True)

                        await asyncio.sleep(0.01)
            finally:
                ff.cancel()

            # The queue will drop remaining items
            assert found == [1, 2, 3, 4, 5]
            assert list(queue.remaining()) == [6, 7]

        async def test_it_ignores_results_added_after_final_future_is_done_if_still_waiting_for_results(
            self, final_future
        ):
            wait = hp.create_future()

            queue = hp.SyncQueue(final_future)

            ff = hp.create_future()
            found = []

            async def fill():
                for i in (2, 3, 4):
                    queue.append(i)
                await wait
                final_future.cancel()
                for i in (5, 6, 7):
                    queue.append(i)

            try:
                async with hp.TaskHolder(ff) as ts:
                    ts.add(fill())

                    queue.append(1)

                    for item in queue:
                        found.append(item)

                        if item == 4:
                            wait.set_result(True)

                        await asyncio.sleep(0.01)
            finally:
                ff.cancel()

            # The queue will drop remaining items
            assert found == [1, 2, 3, 4]
            assert list(queue.remaining()) == [5, 6, 7]

        async def test_it_is_re_entrant_if_we_break(self, final_future):
            found = []
            queue = hp.SyncQueue(final_future)

            for i in range(10):
                queue.append(i)

            for item in queue:
                found.append(item)

                if item == 3:
                    break

            assert found == [0, 1, 2, 3]

            for item in queue:
                found.append(item)
                if item == 9:
                    final_future.cancel()

            assert found == list(range(10))

    class TestGettingAllResultsWhenEmptyOnFinished:

        async def test_it_can_get_results_until_final_future_is_done(self, final_future):
            wait = hp.create_future()

            queue = hp.SyncQueue(final_future, empty_on_finished=True)

            ff = hp.create_future()
            found = []

            async def fill():
                for i in (2, 3, 4):
                    queue.append(i)
                await wait
                for i in (5, 6, 7):
                    queue.append(i)

            try:
                async with hp.TaskHolder(ff) as ts:
                    ts.add(fill())

                    queue.append(1)

                    for item in queue:
                        if item == 5:
                            final_future.cancel()

                        found.append(item)

                        if item == 4:
                            wait.set_result(True)

                        await asyncio.sleep(0.01)
            finally:
                ff.cancel()

            # The queue will not drop remaining items
            assert found == [1, 2, 3, 4, 5, 6, 7]
            assert list(queue.remaining()) == []

        async def test_it_gets_results_added_after_final_future_is_done_if_still_waiting_for_results(
            self, final_future
        ):
            wait = hp.create_future()

            queue = hp.SyncQueue(final_future, empty_on_finished=True)

            ff = hp.create_future()
            found = []

            async def fill():
                for i in (2, 3, 4):
                    queue.append(i)
                await wait
                final_future.cancel()
                for i in (5, 6, 7):
                    queue.append(i)

            try:
                async with hp.TaskHolder(ff) as ts:
                    ts.add(fill())

                    queue.append(1)

                    for item in queue:
                        found.append(item)

                        if item == 4:
                            wait.set_result(True)

                        await asyncio.sleep(0.01)
            finally:
                ff.cancel()

            # The queue will not remaining items
            assert found == [1, 2, 3, 4, 5, 6, 7]
            assert list(queue.remaining()) == []

        async def test_it_is_re_entrant_if_we_break(self, final_future):
            found = []
            queue = hp.SyncQueue(final_future, empty_on_finished=True)

            for i in range(10):
                queue.append(i)

            for item in queue:
                found.append(item)

                if item == 3:
                    break

            assert found == [0, 1, 2, 3]

            for item in queue:
                found.append(item)
                if item == 9:
                    final_future.cancel()

            assert found == list(range(10))
