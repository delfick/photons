# coding: spec

from photons_app import helpers as hp

from queue import Queue as NormalQueue
from collections import deque
import asyncio
import pytest


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


describe "Queue":
    it "takes in a final_future", final_future:
        queue = hp.Queue(final_future)

        compare = pytest.helpers.child_future_of(final_future)
        assert queue.final_future == compare

        assert hp.fut_has_callback(queue.final_future, queue._stop_waiter)

        assert isinstance(queue.collection, deque)

        assert isinstance(queue.waiter, hp.ResettableFuture)
        assert not queue.waiter.done()

    async it "can stop the waiter on done", final_future:
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

    async it "can append items", final_future:
        queue = hp.Queue(final_future)
        assert not queue.waiter.done()

        queue.append(1)
        assert queue.waiter.done()

        queue.append(2)
        assert queue.waiter.done()

        found = []
        async for item in queue._get_and_wait():
            found.append(item)
        assert found == [1, 2]
        assert not queue.waiter.done()

        queue.append(3)
        assert queue.waiter.done()
        found = []
        async for item in queue._get_and_wait():
            found.append(item)
        assert found == [3]

    async it "can get remaining items", final_future:
        queue = hp.Queue(final_future)
        assert not queue.waiter.done()

        queue.append(1)
        assert queue.waiter.done()

        queue.append(2)

        assert list(queue.remaining()) == [1, 2]

        assert not queue.collection

    describe "getting all results":
        async it "can get results until final_future is done", final_future:
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

        async it "ignores results added after final_future is done if still waiting for results", final_future:
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

        async it "is re-entrant if we break", final_future:
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

    describe "getting all results and empty_on_finished":
        async it "can get results until final_future is done", final_future:
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

        async it "gets results added after final_future is done if still waiting for results", final_future:
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

        async it "is re-entrant if we break", final_future:
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

describe "SyncQueue":
    it "takes in a final_future", final_future:
        queue = hp.SyncQueue(final_future)

        compare = pytest.helpers.child_future_of(final_future)
        assert queue.final_future == compare
        assert queue.timeout == 0.05

        assert isinstance(queue.collection, NormalQueue)

        queue = hp.SyncQueue(final_future, timeout=1)
        assert queue.timeout == 1

    it "can append items", final_future:
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

    async it "can get remaining items", final_future:
        queue = hp.SyncQueue(final_future)

        queue.append(1)
        queue.append(2)

        assert list(queue.remaining()) == [1, 2]
        assert queue.collection.empty()

    describe "getting all results":

        async it "can get results until final_future is done", final_future:
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

        async it "ignores results added after final_future is done if still waiting for results", final_future:
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

        async it "is re-entrant if we break", final_future:
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

    describe "getting all results when empty_on_finished":

        async it "can get results until final_future is done", final_future:
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

        async it "gets results added after final_future is done if still waiting for results", final_future:
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

        async it "is re-entrant if we break", final_future:
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
