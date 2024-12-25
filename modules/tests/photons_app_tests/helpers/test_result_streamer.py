
import asyncio
import itertools
import sys
import traceback
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp


class C:
    def __eq__(self, other):
        self.other = other
        return isinstance(other, asyncio.CancelledError)

    def __repr__(self):
        return f"<C: {getattr(self, 'other', None)}"


class TestResultStreamer:
    def test_it_takes_in_final_future_and_other_options(self):
        final_future = hp.create_future()
        error_catcher = mock.Mock(name="error_catcher")
        exceptions_only_to_error_catcher = mock.Mock(name="exceptions_only_to_error_catcher")

        streamer = hp.ResultStreamer(
            final_future,
            error_catcher=error_catcher,
            exceptions_only_to_error_catcher=exceptions_only_to_error_catcher,
        )

        assert not streamer.final_future.done()
        assert streamer.error_catcher is error_catcher
        assert streamer.exceptions_only_to_error_catcher is exceptions_only_to_error_catcher

        assert len(streamer.ts.ts) == 0
        assert isinstance(streamer.queue, hp.Queue)
        assert not streamer.stop_on_completion

    async def test_it_has_a_final_future_as_a_child_of_that_passed_in(self):
        final_future = hp.create_future()
        streamer = hp.ResultStreamer(final_future)
        streamer.final_future.cancel()
        assert not final_future.done()

        final_future = hp.create_future()
        streamer = hp.ResultStreamer(final_future)
        final_future.set_result(True)
        assert streamer.final_future.cancelled()

        final_future = hp.create_future()
        streamer = hp.ResultStreamer(final_future)
        final_future.set_exception(Exception("NOPE"))
        with assertRaises(Exception, "NOPE"):
            await streamer.final_future

        final_future = hp.create_future()
        streamer = hp.ResultStreamer(final_future)
        final_future.cancel()
        assert streamer.final_future.cancelled()

    class TestAddGenerator:

        @pytest.fixture()
        async def V(self):
            class V:
                final_future = hp.create_future()
                error_catcher = mock.Mock(name="error_catcher")

                @hp.memoized_property
                def streamer(s):
                    return hp.ResultStreamer(s.final_future, error_catcher=s.error_catcher)

                async def retrieve(s):
                    results = []

                    s.streamer.no_more_work()
                    async for result in s.streamer:
                        results.append(result)

                    return results

            v = V()
            try:
                yield v
            finally:
                exc_info = sys.exc_info()
                v.final_future.cancel()
                await v.streamer.finish(*exc_info)

        async def test_it_adds_it_as_a_coroutine(self, V):

            async def gen():
                yield 1
                yield 2
                yield 3

            task = await V.streamer.add_generator(gen())
            assert task in V.streamer.ts

            results = await V.retrieve()
            assert [r.value for r in results] == [1, 2, 3]
            assert all([r.successful for r in results])

        async def test_it_adds_exceptions_to_the_queue_after_results(self, V):
            error = ValueError("FAIL")

            async def gen():
                yield 4
                yield 5
                raise error

            task = await V.streamer.add_generator(gen())
            assert task in V.streamer.ts

            results = await V.retrieve()
            assert [r.value for r in results] == [4, 5, error]
            assert [r.successful for r in results] == [True, True, False]

        async def test_it_can_give_exceptions_to_on_done_and_error_catcher(self, V):
            error = TypeError("WAT")
            on_done = mock.Mock(name="on_done")
            ctx = mock.NonCallableMock(name="context", spec=[])

            async def gen():
                yield 1
                raise error

            task = await V.streamer.add_generator(gen(), on_done=on_done, context=ctx)
            assert task in V.streamer.ts

            results = await V.retrieve()
            assert [r.value for r in results] == [1, error]

            V.error_catcher.assert_called_once_with(hp.ResultStreamer.Result(error, ctx, False))
            on_done.assert_called_once_with(hp.ResultStreamer.Result(error, ctx, False))

        async def test_it_can_give_a_success_to_on_one(self, V):
            on_done = mock.Mock(name="on_done")
            ctx = mock.NonCallableMock(name="context", spec=[])

            async def gen():
                yield 1

            task = await V.streamer.add_generator(gen(), on_done=on_done, context=ctx)
            assert task in V.streamer.ts

            results = await V.retrieve()
            assert [r.value for r in results] == [1]

            V.error_catcher.assert_not_called()
            on_done.assert_called_once_with(
                hp.ResultStreamer.Result(hp.ResultStreamer.GeneratorComplete, ctx, True)
            )

        async def test_it_can_call_on_each_for_each_result(self, V):
            ctx = mock.NonCallableMock(name="context", spec=[])

            called = []

            def on_each(result):
                called.append(("on_each", result))

            def on_done(result):
                called.append(("on_done", result))

            async def gen():
                yield 1
                yield 2
                yield 3
                called.append("gen_finished")

            task = await V.streamer.add_generator(
                gen(), on_done=on_done, on_each=on_each, context=ctx
            )
            assert task in V.streamer.ts

            results = await V.retrieve()
            assert [r.value for r in results] == [1, 2, 3]

            V.error_catcher.assert_not_called()

            R = hp.ResultStreamer.Result

            assert called == [
                ("on_each", R(1, ctx, True)),
                ("on_each", R(2, ctx, True)),
                ("on_each", R(3, ctx, True)),
                "gen_finished",
                ("on_done", R(hp.ResultStreamer.GeneratorComplete, ctx, True)),
            ]

    class TestAddCoroutine:

        @pytest.fixture()
        async def V(self):
            class V:
                final_future = hp.create_future()

                @hp.memoized_property
                def streamer(s):
                    return hp.ResultStreamer(s.final_future)

            v = V()
            try:
                yield v
            finally:
                v.final_future.cancel()
                await v.streamer.finish()

        async def test_it_uses_add_task(self, V):
            ctx = mock.Mock(name="ctx")
            on_done = mock.Mock(name="on_done")

            task = mock.Mock(name="task")
            add_task = pytest.helpers.AsyncMock(name="add_task", return_value=task)

            async def func():
                return 20

            coro = func()
            with mock.patch.object(V.streamer, "add_task", add_task):
                assert await V.streamer.add_coroutine(coro, context=ctx, on_done=on_done) is task

            add_task.assert_called_once_with(mock.ANY, context=ctx, on_done=on_done, force=False)
            task = add_task.mock_calls[0][1][0]

            assert isinstance(task, asyncio.Task)
            if hasattr(task, "getcoro"):
                assert task.get_coro() is coro
            assert await task == 20

        async def test_it_has_defaults_for_context_and_on_done(self, V):
            task = mock.Mock(name="task")
            add_task = pytest.helpers.AsyncMock(name="add_task", return_value=task)

            async def func():
                return 20

            coro = func()
            with mock.patch.object(V.streamer, "add_task", add_task):
                assert await V.streamer.add_coroutine(coro) is task

            add_task.assert_called_once_with(mock.ANY, context=None, on_done=None, force=False)

    class TestAddValue:

        @pytest.fixture()
        async def V(self):
            class V:
                final_future = hp.create_future()

                @hp.memoized_property
                def streamer(s):
                    return hp.ResultStreamer(s.final_future)

            v = V()
            try:
                yield v
            finally:
                v.final_future.cancel()
                await v.streamer.finish()

        async def test_it_uses_add_coroutine(self, V):
            ctx = mock.Mock(name="ctx")
            on_done = mock.Mock(name="on_done")

            task = mock.Mock(name="task")
            add_coroutine = pytest.helpers.AsyncMock(name="add_coroutine", return_value=task)

            with mock.patch.object(V.streamer, "add_coroutine", add_coroutine):
                assert await V.streamer.add_value(20, context=ctx, on_done=on_done) is task

            add_coroutine.assert_called_once_with(mock.ANY, context=ctx, on_done=on_done)

            coro = add_coroutine.mock_calls[0][1][0]
            assert await coro == 20

        async def test_it_has_defaults_for_context_and_on_done(self, V):
            task = mock.Mock(name="task")
            add_coroutine = pytest.helpers.AsyncMock(name="add_coroutine", return_value=task)

            with mock.patch.object(V.streamer, "add_coroutine", add_coroutine):
                assert await V.streamer.add_value(40) is task

            add_coroutine.assert_called_once_with(mock.ANY, context=None, on_done=None)
            assert await add_coroutine.mock_calls[0][1][0] == 40

        async def test_it_works(self, V):
            found = []

            async def adder(streamer):
                await streamer.add_value(1, context="adder")
                await streamer.add_value(2, context="adder")
                return "ADDER"

            async with hp.ResultStreamer(V.final_future) as streamer:
                await streamer.add_coroutine(adder(streamer))
                streamer.no_more_work()

                async for result in streamer:
                    found.append((result.successful, result.value, result.context))

            assert found == [(True, "ADDER", None), (True, 1, "adder"), (True, 2, "adder")]

    class TestAddTask:

        @pytest.fixture()
        async def make_streamer(self):
            @hp.asynccontextmanager
            async def make_streamer(**kwargs):
                streamer = None
                final_future = hp.create_future()

                try:
                    streamer = hp.ResultStreamer(final_future, **kwargs)
                    yield streamer
                finally:
                    final_future.cancel()
                    if streamer:
                        await streamer.finish()

            return make_streamer

        async def retrieve(self, streamer):
            streamer.no_more_work()

            started = hp.create_future()

            async def retrieve():
                results = []
                started.set_result(True)
                async for result in streamer:
                    results.append(result)
                return results

            return started, hp.async_as_background(retrieve())

        async def test_it_calls_error_catcher_with_CancelledError_if_the_task_gets_cancelled(self, make_streamer):

            async def func():
                await asyncio.sleep(20)

            error_catcher = mock.Mock(name="error_catcher")
            async with make_streamer(error_catcher=error_catcher) as streamer:
                task = await streamer.add_task(hp.async_as_background(func()))
                started, runner = await self.retrieve(streamer)
                await started

                result = hp.ResultStreamer.Result(C(), None, False)

                task.cancel()
                assert (await runner) == [result]

                error_catcher.assert_called_once_with(result)

        async def test_it_calls_on_done_with_exception_if_cancelled(self, make_streamer):
            on_done = mock.Mock(name="on_done")

            async def func():
                await asyncio.sleep(20)

            class C:
                def __eq__(s, other):
                    return isinstance(other, asyncio.CancelledError)

            errors = []
            async with make_streamer(error_catcher=errors) as streamer:
                task = await streamer.add_task(hp.async_as_background(func()), on_done=on_done)
                started, runner = await self.retrieve(streamer)
                await started

                result = hp.ResultStreamer.Result(C(), None, False)

                task.cancel()
                assert (await runner) == [result]

                on_done.assert_called_once_with(result)
                assert errors == [result]

        async def test_it_calls_on_done_and_error_catcher_with_exception(self, make_streamer):
            error = AttributeError("nup")
            on_done = mock.Mock(name="on_done")

            async def func():
                raise error

            error_catcher = mock.Mock(name="error_catcher")
            async with make_streamer(error_catcher=error_catcher) as streamer:
                task = await streamer.add_task(hp.async_as_background(func()), on_done=on_done)
                started, runner = await self.retrieve(streamer)
                await started

                result = hp.ResultStreamer.Result(error, None, False)

                task.cancel()
                assert (await runner) == [result]

                on_done.assert_called_once_with(result)
                error_catcher.assert_called_once_with(result)

        async def test_it_Result_Streamer_only_gives_cancelled_errors_to_catcher_if_we_only_give_exceptions(self, make_streamer):
            error = AttributeError("nup")
            on_done = mock.Mock(name="on_done")

            async def sleeper():
                await asyncio.sleep(20)

            async def func(sleeper_task):
                sleeper_task.cancel()
                raise error

            error_catcher = mock.Mock(name="error_catcher")
            async with make_streamer(
                error_catcher=error_catcher, exceptions_only_to_error_catcher=True
            ) as streamer:
                sleeper_task = await streamer.add_coroutine(sleeper(), on_done=on_done)
                await streamer.add_coroutine(func(sleeper_task), on_done=on_done)

                started, runner = await self.retrieve(streamer)
                await started

                other_result = hp.ResultStreamer.Result(error, None, False)
                sleeper_result = hp.ResultStreamer.Result(C(), None, False)

                assert (await runner) == [other_result, sleeper_result]

                assert on_done.mock_calls == [mock.call(other_result), mock.call(sleeper_result)]
                assert error_catcher.mock_calls == [mock.call(error)]

            on_done.reset_mock()
            error_catcher.reset_mock()

            async with make_streamer(error_catcher=error_catcher) as streamer:
                sleeper_task = await streamer.add_coroutine(sleeper(), on_done=on_done)
                await streamer.add_coroutine(func(sleeper_task), on_done=on_done)

                started, runner = await self.retrieve(streamer)
                await started

                other_result = hp.ResultStreamer.Result(error, None, False)
                sleeper_result = hp.ResultStreamer.Result(C(), None, False)

                assert (await runner) == [other_result, sleeper_result]

                assert on_done.mock_calls == [mock.call(other_result), mock.call(sleeper_result)]
                assert error_catcher.mock_calls == [
                    mock.call(other_result),
                    mock.call(sleeper_result),
                ]

        async def test_it_can_be_told_to_only_give_exceptions_to_error_catcher(self, make_streamer):
            error = AttributeError("nup")
            on_done = mock.Mock(name="on_done")

            async def sleeper():
                await asyncio.sleep(20)

            async def func(sleeper_task):
                sleeper_task.cancel()
                raise error

            error_catcher = mock.Mock(name="error_catcher")
            async with make_streamer(
                error_catcher=error_catcher, exceptions_only_to_error_catcher=True
            ) as streamer:
                sleeper_task = await streamer.add_coroutine(sleeper(), on_done=on_done)
                await streamer.add_coroutine(func(sleeper_task), on_done=on_done)

                started, runner = await self.retrieve(streamer)
                await started

                other_result = hp.ResultStreamer.Result(error, None, False)
                sleeper_result = hp.ResultStreamer.Result(C(), None, False)

                assert (await runner) == [other_result, sleeper_result]

                assert on_done.mock_calls == [mock.call(other_result), mock.call(sleeper_result)]
                assert error_catcher.mock_calls == [mock.call(error)]

        async def test_it_can_put_successful_results_onto_the_queue(self, make_streamer):
            make_return = hp.create_future()

            async def func():
                await make_return
                return 42

            error_catcher = mock.Mock(name="error_catcher")
            async with make_streamer(error_catcher=error_catcher) as streamer:
                await streamer.add_task(hp.async_as_background(func()))

                started, runner = await self.retrieve(streamer)
                await started

                make_return.set_result(True)
                result = hp.ResultStreamer.Result(42, None, True)
                assert (await runner) == [result]
                error_catcher.assert_not_called()

        async def test_it_can_tell_on_done_about_finishing_successfully(self, make_streamer):
            on_done = mock.Mock(name="on_done")
            make_return = hp.create_future()

            async def func():
                await make_return
                return 42

            error_catcher = mock.Mock(name="error_catcher")
            async with make_streamer(error_catcher=error_catcher) as streamer:
                await streamer.add_task(hp.async_as_background(func()), on_done=on_done)

                started, runner = await self.retrieve(streamer)
                await started

                make_return.set_result(True)
                result = hp.ResultStreamer.Result(42, None, True)
                assert (await runner) == [result]
                error_catcher.assert_not_called()
                on_done.assert_called_once_with(result)

        async def test_it_doesnt_call_error_catcher_if_success_and_exceptions_only(self, make_streamer):
            make_return = hp.create_future()

            async def func():
                await make_return
                return 42

            error_catcher = mock.Mock(name="error_catcher")
            async with make_streamer(
                error_catcher=error_catcher, exceptions_only_to_error_catcher=True
            ) as streamer:
                await streamer.add_task(hp.async_as_background(func()))

                started, runner = await self.retrieve(streamer)
                await started

                make_return.set_result(True)
                error_catcher.assert_not_called()

    class TestAsyncContextManager:
        async def test_it_calls_finish_on_successful_exit(self):
            final_future = hp.create_future()
            streamer = hp.ResultStreamer(final_future)

            finish = pytest.helpers.AsyncMock(name="finish", return_value=None)

            with mock.patch.object(streamer, "finish", finish):
                async with streamer as s:
                    assert s is streamer
                    finish.assert_not_called()

            finish.assert_called_once_with(None, None, None)

        async def test_it_calls_finish_on_unsuccessful_exit(self):
            final_future = hp.create_future()
            streamer = hp.ResultStreamer(final_future)

            finish = pytest.helpers.AsyncMock(name="finish", return_value=None)

            err = ValueError("goodbye")

            with assertRaises(ValueError, "goodbye"):
                with mock.patch.object(streamer, "finish", finish):
                    async with streamer as s:
                        assert s is streamer
                        finish.assert_not_called()
                        raise err

            finish.assert_called_once_with(ValueError, err, mock.ANY)

        async def test_it_calls_finish_on_cancellation(self):
            final_future = hp.create_future()
            streamer = hp.ResultStreamer(final_future)

            finish = pytest.helpers.AsyncMock(name="finish", return_value=None)
            cancel_me_now = hp.create_future()

            async def run_it():
                with mock.patch.object(streamer, "finish", finish):
                    async with streamer as s:
                        assert s is streamer
                        finish.assert_not_called()
                        cancel_me_now.set_result(True)
                        await asyncio.sleep(20)
                        raise ValueError("goodbye")

            task = hp.async_as_background(run_it())
            await cancel_me_now
            task.cancel()

            with assertRaises(asyncio.CancelledError):
                await task

            finish.assert_called_once_with(asyncio.CancelledError, mock.ANY, mock.ANY)

    class TestFinishingByFinalFuture:

        async def test_it_stops_retrieving_if_there_is_results_left_to_yield(self):
            called = []

            gen_fut = hp.create_future()
            func_fut = hp.create_future()
            func3_fut = hp.create_future()
            final_future = hp.ChildOfFuture(hp.create_future())

            async def gen():
                called.append(("started", "gen"))
                try:
                    yield 1
                    yield 2
                    await gen_fut
                    yield 3
                except asyncio.CancelledError:
                    called.append(("cancelled", "gen"))
                    raise

            async def func():
                called.append(("started", "func"))
                await func_fut
                final_future.cancel()
                called.append(("finished", "func"))

            async def func2():
                called.append(("running", "func2"))
                return 20

            async def func3():
                called.append(("started", "func3"))
                try:
                    await func3_fut
                except asyncio.CancelledError:
                    called.append(("cancelled", "func3"))
                    raise

            def error_catcher(e):
                called.append(("catcher", e))

            tasks = {}
            on_dones = {}

            streamer = hp.ResultStreamer(final_future, error_catcher=error_catcher)

            async with streamer:
                on_dones["gen"] = mock.Mock(name="on_done gen")
                tasks["gen"] = await streamer.add_generator(
                    gen(), context="gen", on_done=on_dones["gen"]
                )

                for name, coro in (
                    ("func", func()),
                    ("func2", func2()),
                    ("func3", func3()),
                ):
                    on_dones[name] = mock.Mock(name=f"on_done {name}")
                    tasks[name] = await streamer.add_task(
                        hp.async_as_background(coro), context=name, on_done=on_dones[name]
                    )

                results = []
                async for result in streamer:
                    if result.context == "func2":
                        func_fut.set_result(True)
                    called.append(("result", result.value, result.context))
                    results.append(result)

            R = hp.ResultStreamer.Result

            gen_result = R(C(), "gen", False)
            func3_result = R(C(), "func3", False)

            expected = [
                ("started", "gen"),
                ("started", "func"),
                ("running", "func2"),
                ("started", "func3"),
                ("result", 1, "gen"),
                ("result", 2, "gen"),
                ("result", 20, "func2"),
                ("finished", "func"),
                ("result", None, "func"),
                ("cancelled", "gen"),
                ("cancelled", "func3"),
                ("catcher", func3_result),
                ("catcher", gen_result),
            ]

            assert len(called) == len(expected)
            for e, g in zip(expected, called):
                assert e == g

            assert results == [
                R(1, "gen", True),
                R(2, "gen", True),
                R(20, "func2", True),
                R(None, "func", True),
            ]

            expected_cancelled = {"gen": True, "func": False, "func2": False, "func3": True}
            assert len(expected_cancelled) == len(tasks)
            for name, cancelled in expected_cancelled.items():
                assert tasks[name].cancelled() == cancelled, name

class TestUsingResultStreamer:

    @pytest.fixture()
    def final_future(self):
        fut = hp.create_future()
        try:
            yield fut
        finally:
            fut.cancel()

    @pytest.fixture()
    def CTX(self):
        class CTX:
            def __init__(self, key, genctx=None):
                self.key = key
                self.genctx = genctx

            def __repr__(self):
                return f"<CTX {self.key}>"

            def __eq__(self, other):
                if self.genctx:
                    return other == self.genctx
                return isinstance(other, self.__class__) and other.key == self.key

            def result(self, value, successfull=True):
                return hp.ResultStreamer.Result(value, self, successfull)

            def exception(self, value, successfull=False):
                return hp.ResultStreamer.Result(ValueError(value), self, successfull)

            class Gen:
                def __init__(self, key, amount):
                    self._key = key
                    self.index = -1
                    self.added = 0
                    self.amount = amount

                def __getattr__(self, attr):
                    if attr != "key":
                        return object.__getattribute__(self, attr)

                    self.index += 1
                    if self.index > self.amount:
                        assert False, f"Expected only {self.amount} keys"
                    return self.make_key(self.index)

                def make_key(self, num):
                    return f"{self._key}|{num}"

                def context(self, num):
                    return CTX(self.make_key(num), genctx=self)

                def result(self, value, successfull=True):
                    return self.context(self.added).result(value, successfull=successfull)

                def exception(self, value, successfull=False):
                    return self.context(self.added).exception(value, successfull)

                def __repr__(self):
                    return f"<GENCTX {self._key}:{self.amount}>"

        return CTX

    async def fill_streamer(self, streamer, futs, CTX, make_on_done):
        R = hp.ResultStreamer.Result
        expected = {"yielded": [], "done": [], "errors": []}

        counter = iter(itertools.count(0))

        class XS:
            pass

        ##########
        ## First successful coroutine
        ##########

        async def add_coro1():
            async def coro1():
                await futs[1]
                return "r_c1"

            XS.c1 = CTX("coro1")
            await streamer.add_coroutine(coro1(), context=XS.c1, on_done=make_on_done(1))

        ##########
        ## First generator
        ##########

        async def add_gen1():
            async def gen1():
                await futs[2]
                yield "r_g1_1"
                await futs[6]
                yield "r_g1_last"

            XS.g1 = CTX.Gen("gen1", 2)
            await streamer.add_generator(gen1(), context=XS.g1, on_done=make_on_done(3))

        ##########
        ## sub generator 1 for sub generator1 of Second generator
        ##########

        async def add_gen1_for_gen1_of_gen2():
            async def gen1_for_gen1_of_gen2():
                await futs[5]
                yield "r_g2g1g1_last"

            XS.g2_g1_g1 = CTX.Gen("gen1_for_gen1_of_gen2", 1)
            await streamer.add_generator(
                gen1_for_gen1_of_gen2(), context=XS.g2_g1_g1, on_done=make_on_done(2)
            )

        ##########
        ## coro for generator 1 for Second generator
        ##########

        async def add_coro_for_gen1_of_gen2():
            async def coro_for_gen1_of_gen2():
                await futs[8]
                raise ValueError("e_g2g1c")

            XS.g2_g1_c = CTX("coro_for_gen1_of_gen2")
            await streamer.add_coroutine(
                coro_for_gen1_of_gen2(), context=XS.g2_g1_c, on_done=make_on_done(5)
            )

        ##########
        ## sub generator 1 for Second generator
        ##########

        async def add_gen1_for_gen2():
            async def gen1_for_gen2():
                await futs[4]
                yield "r_g2g1_1"
                await add_gen1_for_gen1_of_gen2()
                await futs[7]
                yield "r_g2g1_last"
                await add_coro_for_gen1_of_gen2()

            XS.g2_g1 = CTX.Gen("gen1_for_g2", 2)
            await streamer.add_generator(gen1_for_gen2(), context=XS.g2_g1, on_done=make_on_done(4))

        ##########
        ## coroutine for sub generator 2 of generator 2
        ##########

        async def add_coro_for_gen2_of_gen2():
            async def coro_for_gen2_of_gen2():
                await futs[14]

            XS.g2_g2_c = CTX.Gen("coro_for_gen2_of_gen2", 2)
            coro = coro_for_gen2_of_gen2()
            await streamer.add_coroutine(coro, context=XS.g2_g2_c, on_done=make_on_done(10))

        ##########
        ## sub generator 2 for Second generator
        ##########

        async def add_gen2_for_gen2():
            async def gen2_for_gen2():
                await futs[12]
                yield "r_g2g2_1"
                await futs[13]
                await add_coro_for_gen2_of_gen2()
                raise ValueError("e_g2g2")
                await futs[14]
                yield "r_g2g2_last"

            XS.g2_g2 = CTX.Gen("gen2_for_g2", 2)
            await streamer.add_generator(gen2_for_gen2(), context=XS.g2_g2, on_done=make_on_done(9))

        ##########
        ## sub coroutine for Second generator
        ##########

        async def add_gen2_coro():
            async def gen2_coro():
                await futs[10]

            XS.g2_c = CTX("gen2_coro")
            await streamer.add_coroutine(gen2_coro(), context=XS.g2_c, on_done=make_on_done(7))

        ##########
        ## sub coroutine 2 for Second generator
        ##########

        async def add_gen2_coro2():
            async def coro1_for_gen2():
                await futs[11]
                return "r_g2c2"

            XS.g2_c2 = CTX("gen2_coro2")
            await streamer.add_coroutine(
                coro1_for_gen2(), context=XS.g2_c2, on_done=make_on_done(8)
            )

        ##########
        ## Second generator
        ##########

        async def add_gen2():
            async def gen2():
                await futs[3]
                yield "r_g2_1"
                await add_gen2_coro2()
                await add_gen1_for_gen2()
                await futs[9]
                await add_gen2_for_gen2()
                yield "r_g2_2"
                yield "r_g2_last"
                await add_gen2_coro()

            XS.g2 = CTX("gen2")
            await streamer.add_generator(gen2(), context=XS.g2, on_done=make_on_done(5))

        await add_coro1()
        await add_gen1()
        await add_gen2()
        streamer.no_more_work()

        def WITHDONE(make):
            def access():
                r = make()
                expected["done"].append(lambda: r)
                return next(counter), r

            return access

        def ERROR(make):
            def access():
                r = make()
                expected["done"].append(lambda: r)
                expected["errors"].append(r)
                return next(counter), r

            return access

        def VALUE(make, *, done=None):
            def access():
                if done:
                    expected["done"].append(done)
                return next(counter), make()

            return access

        yd = expected["yielded"]

        # 1 : DONE 1
        yd.append(WITHDONE(lambda: XS.c1.result("r_c1")))
        # 2
        yd.append(VALUE(lambda: XS.g1.result("r_g1_1")))
        # 3
        yd.append(VALUE(lambda: XS.g2.result("r_g2_1")))
        # 4
        yd.append(VALUE(lambda: XS.g2_g1.result("r_g2g1_1")))
        # 5 : DONE 2
        yd.append(
            VALUE(
                lambda: XS.g2_g1_g1.result("r_g2g1g1_last"),
                done=lambda: R(hp.ResultStreamer.GeneratorComplete, XS.g2_g1_g1, True),
            )
        )
        # 6 : DONE 3
        yd.append(
            VALUE(
                lambda: XS.g1.result("r_g1_last"),
                done=lambda: R(hp.ResultStreamer.GeneratorComplete, XS.g1, True),
            )
        )
        # 7 : DONE 4
        yd.append(
            VALUE(
                lambda: XS.g2_g1.result("r_g2g1_last"),
                done=lambda: R(hp.ResultStreamer.GeneratorComplete, XS.g2_g1, True),
            )
        )
        # 8 : DONE 5
        yd.append(ERROR(lambda: XS.g2_g1_c.exception("e_g2g1c")))
        # 9 : DONE 6
        yd.append(VALUE(lambda: XS.g2.result("r_g2_2")))
        yd.append(
            VALUE(
                lambda: XS.g2.result("r_g2_last"),
                done=lambda: R(hp.ResultStreamer.GeneratorComplete, XS.g2, True),
            )
        )
        # 10 : DONE 7
        yd.append(WITHDONE(lambda: XS.g2_c.result(None)))
        # 11 : DONE 8
        yd.append(WITHDONE(lambda: XS.g2_c2.result("r_g2c2")))
        # 12
        yd.append(VALUE(lambda: XS.g2_g2.result("r_g2g2_1")))
        # 13 : DONE 9
        yd.append(ERROR(lambda: XS.g2_g2.exception("e_g2g2")))
        # 14 : DONE 10
        yd.append(WITHDONE(lambda: XS.g2_g2_c.result(None)))
        # 15
        # never reached

        return expected

    async def test_it_streams_results_from_coroutines_and_async_generators(self, final_future, CTX):
        info = {"num": 0, "done": []}

        def make_on_done(index):
            def on_done(result):
                assert len(info["done"]) <= index
                info["done"].append(result)

            return on_done

        async with pytest.helpers.FutureDominoes(expected=14) as futs:
            error_catcher = []
            streamer = hp.ResultStreamer(final_future, error_catcher=error_catcher)

            expected = await self.fill_streamer(streamer, futs, CTX, make_on_done)

            i = -1
            async with streamer:
                async for result in streamer:
                    i += 1
                    key = result.context.key
                    print()
                    print(
                        f"STREAMED: value:`{type(result.value)}`{result.value}`\tcontext:`{result.context}`\tkey:`{key}`"
                    )
                    expectedi, r = expected["yielded"][i]()

                    if not result.successful and r.successful:
                        print("EXPECTED SUCCESS, got failure")
                        traceback.print_tb(result.value.__traceback__, file=sys.stdout)

                    if result.successful and not r.successful:
                        print("EXPECTED FAILURE, got success")
                        traceback.print_tb(r.value.__traceback__, file=sys.stdout)

                    if not result.successful and not r.successful:
                        if isinstance(result.value, r.value.__class__):
                            r.value = repr(r.value)
                            result.value = repr(result.value)

                    assert result == r
                    assert i == expectedi

            assert error_catcher == expected["errors"]

            print("+++++++ FINISHED TEST")
            print("DONE")
            for d in info["done"]:
                print("\t", d)

            print()
            print("EXPECTED DONE")
            expected_done = [d() for d in expected["done"]]
            for d in expected_done:
                print("\t", d)

            assert info["done"] == expected_done

    async def test_it_doesnt_hang_if_there_is_no_work(self, final_future):
        async with hp.ResultStreamer(final_future) as streamer:
            streamer.no_more_work()

            async for result in streamer:
                pass
