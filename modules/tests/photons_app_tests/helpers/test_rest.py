# coding: spec

from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import asyncio
import os

describe "add_error":
    it "calls the error_catcher with the error if it's a callable":
        error = mock.Mock(name="error")
        catcher = mock.Mock(name="catcher")
        hp.add_error(catcher, error)
        catcher.assert_called_once_with(error)

    it "appends to the error catcher if it's a list":
        error = mock.Mock(name="error")
        catcher = []
        hp.add_error(catcher, error)
        assert catcher == [error]

    it "adds to the error catcher if it's a set":
        error = mock.Mock(name="error")
        catcher = set()
        hp.add_error(catcher, error)
        assert catcher == set([error])

describe "a_temp_file":
    it "gives us the tmpfile":
        with hp.a_temp_file() as fle:
            fle.write(b"wassup")
            fle.seek(0)
            assert os.path.exists(fle.name)
            assert fle.read() == b"wassup"
        assert not os.path.exists(fle.name)

    it "doesn't fail if we delete the file early":
        with hp.a_temp_file() as fle:
            fle.close()
            os.remove(fle.name)
        assert not os.path.exists(fle.name)

describe "just_log_exceptions":
    it "logs exceptions":
        log = mock.Mock(name="log")

        error = ValueError("NOPE")
        with hp.just_log_exceptions(log):
            raise error

        log.error.assert_called_once_with(
            "Unexpected error", exc_info=(ValueError, error, mock.ANY)
        )

    it "can be given a different message":
        log = mock.Mock(name="log")

        error = ValueError("NOPE")
        with hp.just_log_exceptions(log, message="a different message"):
            raise error

        log.error.assert_called_once_with(
            "a different message", exc_info=(ValueError, error, mock.ANY)
        )

    it "can reraise particular errors":
        log = mock.Mock(name="log")

        error = ValueError("NOPE")
        with hp.just_log_exceptions(log, message="a different message", reraise=[TypeError]):
            raise error

        log.error.assert_called_once_with(
            "a different message", exc_info=(ValueError, error, mock.ANY)
        )
        log.error.reset_mock()

        with assertRaises(TypeError, "wat"):
            with hp.just_log_exceptions(log, message="a different message", reraise=[TypeError]):
                raise TypeError("wat")

        log.assert_not_called()

describe "TaskHolder":
    it "takes in a final future":
        final_future = asyncio.Future()
        holder = hp.TaskHolder(final_future)
        assert holder.ts == []
        assert holder.final_future is final_future

    async it "can take in tasks":
        called = []

        async def wait(amount):
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        final_future = asyncio.Future()
        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(0.05))
            ts.add(wait(0.01))

        assert called == [0.01, 0.05]

    async it "exits if we finish all tasks before the manager is left":
        called = []

        async def wait(amount):
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        final_future = asyncio.Future()
        async with hp.TaskHolder(final_future) as ts:
            await ts.add(wait(0.05))
            await ts.add(wait(0.01))
            assert called == [0.05, 0.01]

        assert called == [0.05, 0.01]

    async it "can wait for more tasks if they are added when the manager has left":
        called = []

        async def wait(ts, amount):
            if amount == 0.01:
                ts.add(wait(ts, 0.06))
            try:
                await asyncio.sleep(amount)
            finally:
                called.append(amount)

        final_future = asyncio.Future()
        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 0.05))
            ts.add(wait(ts, 0.01))

        assert called == [0.01, 0.05, 0.06]

    async it "does not fail if a task raises an exception":
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

        final_future = asyncio.Future()
        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 0.05))
            ts.add(wait(ts, 0.01))

        assert called == [0.06, 0.01, 0.05]

    async it "stops waiting tasks if final_future is stopped":
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

        final_future = asyncio.Future()
        async with hp.TaskHolder(final_future) as ts:
            ts.add(wait(ts, 5))
            ts.add(wait(ts, 0.05))

        assert called == [("FINISHED", 0.05), ("CANCELLED", 5), ("FINISHED", 5)]


describe "nested_dict_retrieve":
    it "returns us the dflt if we can't find the key":
        data = {"one": {"two": {"three": 3}}}
        dflt = mock.Mock(name="dflt")
        for keys in (
            ["one", "four"],
            ["four", "five"],
            ["one", "two", "five"],
            ["one", "two", "three", "four"],
        ):
            assert hp.nested_dict_retrieve(data, keys, dflt) is dflt

    it "returns us what it finds":
        data = {"one": {"two": {"three": 3}}}
        dflt = mock.Mock(name="dflt")

        assert hp.nested_dict_retrieve(data, [], dflt) == data
        assert hp.nested_dict_retrieve(data, ["one"], dflt) == {"two": {"three": 3}}
        assert hp.nested_dict_retrieve(data, ["one", "two"], dflt) == {"three": 3}
        assert hp.nested_dict_retrieve(data, ["one", "two", "three"], dflt) == 3

describe "memoized_property":
    it "caches on the instance":
        called = []
        blah = mock.Mock(name="blah")

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return blah

        thing = Thing()
        assert called == []
        assert thing.blah is blah
        assert called == [1]

        assert thing._blah == blah
        assert thing.blah is blah
        assert called == [1]

    it "caches on the instance if the return is None":
        called = []

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return None

        thing = Thing()
        assert called == []
        assert thing.blah is None
        assert called == [1]

        assert thing._blah is None
        assert thing.blah is None
        assert called == [1]

    it "caches on the instance if the return is False":
        called = []

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return False

        thing = Thing()
        assert called == []
        assert thing.blah is False
        assert called == [1]

        assert thing._blah is False
        assert thing.blah is False
        assert called == [1]

    it "can set the value":
        called = []
        blah = mock.Mock(name="blah")
        meh = mock.Mock(name="meh")

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return blah

        thing = Thing()
        assert called == []
        assert thing.blah is blah
        assert called == [1]

        assert thing._blah == blah
        thing.blah = meh
        assert thing._blah == meh

        assert thing.blah is meh
        assert called == [1]

    it "can delete the cache":
        called = []
        blah = mock.Mock(name="blah")

        class Thing:
            @hp.memoized_property
            def blah(s):
                called.append(1)
                return blah

        thing = Thing()
        assert called == []
        assert thing.blah is blah
        assert called == [1]

        assert thing._blah == blah
        assert thing.blah is blah
        assert called == [1]

        del thing.blah
        assert not hasattr(thing, "_blah")

        assert thing.blah is blah
        assert called == [1, 1]
