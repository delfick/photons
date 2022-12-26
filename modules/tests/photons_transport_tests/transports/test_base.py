# coding: spec

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


describe "Transport":
    describe "__init__":
        async it "takes in arguments", session:
            transport = Transport(session)
            assert transport.session is session
            assert transport.transport is None

        async it "has a setup function", session:

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

    describe "spawn":

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

        async it "gets the transport from spawn_transport", original_message, V:
            assert V.called == []
            s = await V.transport.spawn(original_message, timeout=10)
            assert s is V.spawned
            assert V.called == [("spawn_transport", 10)]

            # And it caches the result
            s = await V.transport.spawn(original_message, timeout=20)
            assert s is V.spawned
            assert V.called == [("spawn_transport", 10)]

        async it "re gets the transport was cancelled first time", original_message, V:
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

        async it "re gets the transport if has exception first time", original_message, V:
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

        async it "re gets transport if it's no longer active", original_message, V:
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

        describe "close":

            @pytest.fixture()
            def transport(self, session):
                return Transport(session)

            async it "does nothing if transport is None", transport:
                await transport.close()

            async it "doesn't swallow cancellations", transport, V:

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

            async it "doesn't raise cancellations on transport", transport:
                fut = hp.create_future()
                fut.cancel()

                transport.transport = fut
                t = hp.async_as_background(transport.close())
                await t
                assert True, "No CancelledError raised"

            async it "doesn't raise exceptions on transport", transport:
                fut = hp.create_future()
                fut.set_exception(ValueError("YEAP"))

                transport.transport = fut
                t = hp.async_as_background(transport.close())
                await t
                assert True, "No Exception raised"

            async it "closes the transport if there is one", transport, V:
                close_transport = pytest.helpers.AsyncMock(name="close_transport")

                fut = hp.create_future()
                fut.set_result(V.spawned)
                transport.transport = fut

                with mock.patch.object(transport, "close_transport", close_transport):
                    await transport.close()

                close_transport.assert_called_once_with(V.spawned)

        describe "hooks":

            @pytest.fixture()
            def transport(self, session):
                return Transport(session)

            async it "does nothing for close_transport", original_message, transport:
                t = mock.NonCallableMock(name="transport", spec=[])
                await transport.close_transport(t)

            async it "says True for is_transport_active", transport:
                t = mock.NonCallableMock(name="transport", spec=[])
                assert await transport.is_transport_active(original_message, t)

            async it "must have spawn_transport implemented", transport:
                with assertRaises(NotImplementedError):
                    await transport.spawn_transport(10)

            async it "must have write implemented", transport:
                bts = mock.Mock(name="bts")
                t = mock.NonCallableMock(name="transport", spec=[])
                original_message = mock.Mock(name="original_message")

                with assertRaises(NotImplementedError):
                    await transport.write(t, bts, original_message)
