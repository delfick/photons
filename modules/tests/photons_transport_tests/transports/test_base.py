import asyncio
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_transport.transports.base import Transport


@pytest.fixture()
def session():
    return mock.Mock(name="session")


@pytest.fixture()
def original_message():
    return mock.Mock(name="original_message")


class TestTransport:
    class TestInit:
        async def test_it_takes_in_arguments(self, session):
            transport = Transport(session)
            assert transport.session is session
            assert transport.transport is None

        async def test_it_has_a_setup_function(self, session):
            class T(Transport):
                def setup(s, one, two, *, three):
                    s.one = one
                    s.two = two
                    s.three = three

            one = mock.Mock(name="one")
            two = mock.Mock(name="two")
            three = mock.Mock(name="three")

            transport = T(session, one, two, three=three)

            assert transport.one is one
            assert transport.two is two
            assert transport.three is three

    class TestSpawn:
        @pytest.fixture()
        def V(self, session):
            class V:
                called = []
                spawned = mock.NonCallableMock(name="spawned", spec=[])

                @hp.memoized_property
                def spawn_transport(s):
                    def spawn(timeout):
                        return s.spawned

                    return mock.Mock(name="spawn_transport", side_effect=spawn)

                @hp.memoized_property
                def transport(s):
                    class T(Transport):
                        async def spawn_transport(ts, timeout):
                            s.called.append(("spawn_transport", timeout))
                            return s.spawn_transport(timeout)

                    return T(session)

            return V()

        async def test_it_gets_the_transport_from_spawn_transport(self, original_message, V):
            assert V.called == []
            s = await V.transport.spawn(original_message, timeout=10)
            assert s is V.spawned
            assert V.called == [("spawn_transport", 10)]

            # And it caches the result
            s = await V.transport.spawn(original_message, timeout=20)
            assert s is V.spawned
            assert V.called == [("spawn_transport", 10)]

        async def test_it_re_gets_the_transport_was_cancelled_first_time(self, original_message, V):
            assert V.called == []
            V.spawn_transport.side_effect = asyncio.CancelledError()

            with assertRaises(asyncio.CancelledError):
                await V.transport.spawn(original_message, timeout=10)
            assert V.called == [("spawn_transport", 10)]

            V.spawn_transport.side_effect = lambda t: V.spawned

            # And it can retry
            try:
                s = await V.transport.spawn(original_message, timeout=20)
            except asyncio.CancelledError:
                assert False, "Expected it not to use old future!"

            assert s is V.spawned
            assert V.called == [("spawn_transport", 10), ("spawn_transport", 20)]

        async def test_it_re_gets_the_transport_if_has_exception_first_time(self, original_message, V):
            assert V.called == []
            V.spawn_transport.side_effect = ValueError("YEAP")

            with assertRaises(ValueError, "YEAP"):
                await V.transport.spawn(original_message, timeout=10)
            assert V.called == [("spawn_transport", 10)]

            V.spawn_transport.side_effect = lambda t: V.spawned

            # And it can retry
            try:
                s = await V.transport.spawn(original_message, timeout=20)
            except ValueError:
                assert False, "Expected it not to use old future!"

            assert s is V.spawned
            assert V.called == [("spawn_transport", 10), ("spawn_transport", 20)]

        async def test_it_re_gets_transport_if_its_no_longer_active(self, original_message, V):
            is_transport_active = pytest.helpers.AsyncMock(name="is_transport_active")
            is_transport_active.return_value = False

            with mock.patch.object(V.transport, "is_transport_active", is_transport_active):
                assert V.called == []
                s = await V.transport.spawn(original_message, timeout=10)
                assert s is V.spawned

                assert len(is_transport_active.mock_calls) == 0

                s = await V.transport.spawn(original_message, timeout=20)
                assert s is V.spawned
                assert V.called == [("spawn_transport", 10), ("spawn_transport", 20)]

                is_transport_active.assert_called_once_with(original_message, V.spawned)

        class TestClose:
            @pytest.fixture()
            def transport(self, session):
                return Transport(session)

            async def test_it_does_nothing_if_transport_is_None(self, transport):
                await transport.close()

            async def test_it_doesnt_swallow_cancellations(self, transport, V):
                async def getter():
                    await asyncio.sleep(2)
                    return V.spawned

                transport.transport = hp.async_as_background(getter())
                t = hp.async_as_background(transport.close())
                await asyncio.sleep(0.01)
                t.cancel()

                with assertRaises(asyncio.CancelledError):
                    await t

                transport.transport.cancel()

            async def test_it_doesnt_raise_cancellations_on_transport(self, transport):
                fut = hp.create_future()
                fut.cancel()

                transport.transport = fut
                t = hp.async_as_background(transport.close())
                await t
                assert True, "No CancelledError raised"

            async def test_it_doesnt_raise_exceptions_on_transport(self, transport):
                fut = hp.create_future()
                fut.set_exception(ValueError("YEAP"))

                transport.transport = fut
                t = hp.async_as_background(transport.close())
                await t
                assert True, "No Exception raised"

            async def test_it_closes_the_transport_if_there_is_one(self, transport, V):
                close_transport = pytest.helpers.AsyncMock(name="close_transport")

                fut = hp.create_future()
                fut.set_result(V.spawned)
                transport.transport = fut

                with mock.patch.object(transport, "close_transport", close_transport):
                    await transport.close()

                close_transport.assert_called_once_with(V.spawned)

        class TestHooks:
            @pytest.fixture()
            def transport(self, session):
                return Transport(session)

            async def test_it_does_nothing_for_close_transport(self, original_message, transport):
                t = mock.NonCallableMock(name="transport", spec=[])
                await transport.close_transport(t)

            async def test_it_says_True_for_is_transport_active(self, transport):
                t = mock.NonCallableMock(name="transport", spec=[])
                assert await transport.is_transport_active(original_message, t)

            async def test_it_must_have_spawn_transport_implemented(self, transport):
                with assertRaises(NotImplementedError):
                    await transport.spawn_transport(10)

            async def test_it_must_have_write_implemented(self, transport):
                bts = mock.Mock(name="bts")
                t = mock.NonCallableMock(name="transport", spec=[])
                original_message = mock.Mock(name="original_message")

                with assertRaises(NotImplementedError):
                    await transport.write(t, bts, original_message)
