# coding: spec

from photons_transport.transports.base import Transport

from photons_app.test_helpers import AsyncTestCase, with_timeout
from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import asynctest
import asyncio

describe AsyncTestCase, "Transport":
    async before_each:
        self.session = mock.Mock(name="session")
        self.original_message = mock.Mock(name="original_message")

    describe "__init__":
        async it "takes in arguments":
            transport = Transport(self.session)
            assert transport.session is self.session
            assert transport.transport is None

        async it "has a setup function":

            class T(Transport):
                def setup(s, one, two, *, three):
                    s.one = one
                    s.two = two
                    s.three = three

            one = mock.Mock(name="one")
            two = mock.Mock(name="two")
            three = mock.Mock(name="three")

            transport = T(self.session, one, two, three=three)

            assert transport.one is one
            assert transport.two is two
            assert transport.three is three

    describe "spawn":
        async before_each:
            self.called = []
            self.spawned = mock.NonCallableMock(name="spawned", spec=[])

            def spawn(timeout):
                return self.spawned

            self.spawn_transport = mock.Mock(name="spawn_transport", side_effect=spawn)

            class T(Transport):
                async def spawn_transport(s, timeout):
                    self.called.append(("spawn_transport", timeout))
                    return self.spawn_transport(timeout)

            self.transport = T(self.session)

        @with_timeout
        async it "gets the transport from spawn_transport":
            assert self.called == []
            s = await self.transport.spawn(self.original_message, timeout=10)
            assert s is self.spawned
            assert self.called == [("spawn_transport", 10)]

            # And it caches the result
            s = await self.transport.spawn(self.original_message, timeout=20)
            assert s is self.spawned
            assert self.called == [("spawn_transport", 10)]

        @with_timeout
        async it "re gets the transport was cancelled first time":
            assert self.called == []
            self.spawn_transport.side_effect = asyncio.CancelledError()

            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                await self.transport.spawn(self.original_message, timeout=10)
            assert self.called == [("spawn_transport", 10)]

            self.spawn_transport.side_effect = lambda t: self.spawned

            # And it can retry
            try:
                s = await self.transport.spawn(self.original_message, timeout=20)
            except asyncio.CancelledError:
                assert False, "Expected it not to use old future!"

            assert s is self.spawned
            assert self.called == [("spawn_transport", 10), ("spawn_transport", 20)]

        @with_timeout
        async it "re gets the transport if has exception first time":
            assert self.called == []
            self.spawn_transport.side_effect = ValueError("YEAP")

            with self.fuzzyAssertRaisesError(ValueError, "YEAP"):
                await self.transport.spawn(self.original_message, timeout=10)
            assert self.called == [("spawn_transport", 10)]

            self.spawn_transport.side_effect = lambda t: self.spawned

            # And it can retry
            try:
                s = await self.transport.spawn(self.original_message, timeout=20)
            except ValueError:
                assert False, "Expected it not to use old future!"

            assert s is self.spawned
            assert self.called == [("spawn_transport", 10), ("spawn_transport", 20)]

        @with_timeout
        async it "re gets transport if it's no longer active":
            is_transport_active = asynctest.mock.CoroutineMock(name="is_transport_active")
            is_transport_active.return_value = False

            with mock.patch.object(self.transport, "is_transport_active", is_transport_active):
                assert self.called == []
                s = await self.transport.spawn(self.original_message, timeout=10)
                assert s is self.spawned

                assert len(is_transport_active.mock_calls) == 0

                s = await self.transport.spawn(self.original_message, timeout=20)
                assert s is self.spawned
                assert self.called == [("spawn_transport", 10), ("spawn_transport", 20)]

                is_transport_active.assert_called_once_with(self.original_message, self.spawned)

        describe "close":
            async before_each:
                self.spawned = mock.NonCallableMock(name="spawned", spec=[])
                self.transport = Transport(self.session)

            @with_timeout
            async it "does nothing if transport is None":
                await self.transport.close()

            @with_timeout
            async it "doesn't swallow cancellations":

                async def getter():
                    await asyncio.sleep(2)
                    return self.spawned

                self.transport.transport = hp.async_as_background(getter())
                t = hp.async_as_background(self.transport.close())
                await asyncio.sleep(0.01)
                t.cancel()

                with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                    await t

                self.transport.transport.cancel()

            @with_timeout
            async it "doesn't raise cancellations on transport":
                fut = asyncio.Future()
                fut.cancel()

                self.transport.transport = fut
                t = hp.async_as_background(self.transport.close())
                await t
                assert True, "No CancelledError raised"

            @with_timeout
            async it "doesn't raise exceptions on transport":
                fut = asyncio.Future()
                fut.set_exception(ValueError("YEAP"))

                self.transport.transport = fut
                t = hp.async_as_background(self.transport.close())
                await t
                assert True, "No Exception raised"

            @with_timeout
            async it "closes the transport if there is one":
                close_transport = asynctest.mock.CoroutineMock(name="close_transport")

                fut = asyncio.Future()
                fut.set_result(self.spawned)
                self.transport.transport = fut

                with mock.patch.object(self.transport, "close_transport", close_transport):
                    await self.transport.close()

                close_transport.assert_called_once_with(self.spawned)

        describe "hooks":
            async before_each:
                self.transport = Transport(self.session)

            async it "does nothing for close_transport":
                transport = mock.NonCallableMock(name="transport", spec=[])
                await self.transport.close_transport(transport)

            async it "says True for is_transport_active":
                transport = mock.NonCallableMock(name="transport", spec=[])
                assert await self.transport.is_transport_active(self.original_message, transport)

            async it "must have spawn_transport implemented":
                with self.fuzzyAssertRaisesError(NotImplementedError):
                    await self.transport.spawn_transport(10)

            async it "must have write implemented":
                bts = mock.Mock(name="bts")
                transport = mock.NonCallableMock(name="transport", spec=[])
                original_message = mock.Mock(name="original_message")

                with self.fuzzyAssertRaisesError(NotImplementedError):
                    await self.transport.write(transport, bts, original_message)
