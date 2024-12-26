import asyncio

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


class TestTaskHolder:
    def test_it_takes_in_a_final_future(self, final_future):
        holder = hp.TaskHolder(final_future)
        assert holder.ts == []
        assert holder.final_future == pytest.helpers.child_future_of(final_future)

    async def test_it_can_take_in_tasks(self, final_future):
        called = []

        async def wait(amount):
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(0.05))
            ts.add(wait(0.01))

        assert called == [0.01, 0.05]

    async def test_it_exits_if_we_finish_all_tasks_before_the_manager_is_left(self, final_future):
        called = []

        async def wait(amount):
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        async with hp.TaskHolder(final_future) as ts:
            await ts.add(wait(0.05))
            await ts.add(wait(0.01))
            assert called == [0.05, 0.01]

        assert called == [0.05, 0.01]

    async def test_it_can_wait_for_more_tasks_if_they_are_added_when_the_manager_has_left(self, final_future):
        called = []

        async def wait(ts, amount):
            if amount == 0.01:
                ts.add(wait(ts, 0.06))
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 0.05))
            ts.add(wait(ts, 0.01))

        assert called == [0.01, 0.05, 0.06]

    async def test_it_does_not_fail_if_a_task_raises_an_exception(self, final_future):
        called = []

        async def wait(ts, amount):
            if amount == 0.01:
                ts.add(wait(ts, 0.06))
            try:
                if amount == 0.06:
                    raise TypeError("WAT")
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 0.05))
            ts.add(wait(ts, 0.01))

        assert called == [0.06, 0.01, 0.05]

    async def test_it_stops_waiting_tasks_if_final_future_is_stopped(self, final_future):
        called = []

        async def wait(ts, amount):
            try:
                await asyncio.sleep(amount)
                if amount == 0.05:
                    final_future.set_result(True)
            except asyncio.CancelledError:
                called.append(("CANCELLED", amount))
            finally:
                called.append(("FINISHED", amount))

        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 5))
            ts.add(wait(ts, 0.05))

        assert called == [("FINISHED", 0.05), ("CANCELLED", 5), ("FINISHED", 5)]

    async def test_it_can_say_how_many_pending_tasks_it_has(self, final_future):
        called = []

        async def doit():
            await asyncio.sleep(1)

        async with hp.TaskHolder(final_future) as ts:
            assert ts.pending == 0
            t = ts.add(doit())
            assert ts.pending == 1

            def process(res):
                called.append(ts.pending)

            t.add_done_callback(process)
            t.cancel()

        assert called == [0]

    async def test_it_cancels_tasks_if_it_gets_cancelled(self, final_future):
        called = []
        waiter = hp.create_future()

        async def a_task(name):
            called.append(f"{name}_start")
            try:
                await hp.create_future()
            except asyncio.CancelledError:
                called.append(f"{name}_cancelled")
            except Exception as error:
                called.append((f"{name}_error", error))
            else:
                called.append(f"{name}_end")

        async def doit():
            async with hp.TaskHolder(final_future) as t:
                t.add(a_task("one"))
                t.add(a_task("two"))
                waiter.set_result(True)
                await hp.create_future()

        t = None
        try:
            t = hp.async_as_background(doit())
            await waiter
            t.cancel()
        finally:
            if t:
                t.cancel()

        with assertRaises(asyncio.CancelledError):
            await t
        assert called == ["one_start", "two_start", "one_cancelled", "two_cancelled"]

    async def test_it_can_iterate_tasks(self, final_future):
        async with hp.TaskHolder(final_future) as ts:

            async def hi():
                pass

            t1 = ts.add(hi())
            assert list(ts) == [t1]

            t2 = ts.add(hi())
            t3 = ts.add(hi())
            assert list(ts) == [t1, t2, t3]

    async def test_it_can_say_if_the_holder_has_a_task(self, final_future):
        async with hp.TaskHolder(final_future) as ts:

            async def hi():
                pass

            t1 = hp.async_as_background(hi())
            t2 = hp.async_as_background(hi())

            assert t1 not in ts
            ts.add_task(t1)
            assert t1 in ts
            assert t2 not in ts

            ts.add_task(t2)
            assert t1 in ts
            assert t2 in ts

    async def test_it_can_clean_up_tasks(self, final_future):
        called = []
        wait = hp.create_future()

        async def one():
            called.append("ONE")
            try:
                await asyncio.sleep(200)
            except asyncio.CancelledError:
                called.append("CANC_ONE")
                raise
            finally:
                called.append("FIN_ONE")

        async def two():
            called.append("TWO")
            try:
                await wait
                called.append("DONE_TWO")
            finally:
                called.append("FIN_TWO")

        async with hp.TaskHolder(final_future) as ts:
            t1 = ts.add(one())
            ts.add(two())

            assert called == []
            await asyncio.sleep(0)
            assert called == ["ONE", "TWO"]

            t1.cancel()
            await asyncio.sleep(0)
            assert called == ["ONE", "TWO", "CANC_ONE", "FIN_ONE"]

            wait.set_result(True)
            await asyncio.sleep(0)
            assert called == ["ONE", "TWO", "CANC_ONE", "FIN_ONE", "DONE_TWO", "FIN_TWO"]

    async def test_it_doesnt_lose_tasks_from_race_condition(self, FakeTime, MockedCallLater, final_future):
        with FakeTime() as t:
            async with MockedCallLater(t):
                called = []
                made = {}

                class TaskHolderManualClean(hp.TaskHolder):
                    async def cleaner(self):
                        await hp.create_future()

                async with TaskHolderManualClean(final_future) as ts:

                    async def one():
                        called.append("ONE")
                        try:
                            await asyncio.sleep(10)
                        except asyncio.CancelledError:
                            called.append("CANC_ONE")
                            raise
                        finally:
                            called.append("FIN_ONE")

                    async def two():
                        called.append("TWO")
                        try:
                            await asyncio.sleep(200)
                        except asyncio.CancelledError:
                            called.append("CANC_TWO")
                            # Don't re-raise the exception to trigger race condition
                        finally:
                            called.append("FIN_TWO")

                    t1 = ts.add(two())

                    def add_one(res):
                        called.append("ADD_ONE")
                        made["t2"] = ts.add(one())

                    t1.add_done_callback(add_one)

                    assert called == []
                    await asyncio.sleep(0)
                    assert called == ["TWO"]

                    assert ts.ts == [t1]
                    await ts.clean()
                    assert ts.ts == [t1]

                    t1.cancel()
                    await asyncio.sleep(0)

                    assert called == ["TWO", "CANC_TWO", "FIN_TWO"]
                    assert ts.ts == [t1]

                    # The task holder only knows about t1
                    # And after the clean, we expect it to have made the t2
                    assert "t2" not in made
                    await ts.clean()
                    assert called == ["TWO", "CANC_TWO", "FIN_TWO", "ADD_ONE", "ONE"]
                    assert ts.ts == [made["t2"]]

                    made["t2"].cancel()
                    await asyncio.sleep(0)
                    assert ts.ts == [made["t2"]]
                    await ts.clean()
                    assert ts.ts == []
                    assert called == [
                        "TWO",
                        "CANC_TWO",
                        "FIN_TWO",
                        "ADD_ONE",
                        "ONE",
                        "CANC_ONE",
                        "FIN_ONE",
                    ]
