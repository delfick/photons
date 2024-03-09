# coding: spec

from unittest import mock

import pytest
from interactor.commander.animations import Animations
from interactor.commander.store import store
from interactor.database import DB
from interactor.zeroconf import Zeroconf
from photons_app import helpers as hp
from photons_app.registers import ReferenceResolverRegister
from photons_control.device_finder import DeviceFinderDaemon, Finder


@pytest.fixture(scope="module")
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


@pytest.fixture(scope="module")
async def sender(devices, final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture(scope="module")
def V():
    class V:
        afr = mock.Mock(name="afr")
        commander = mock.Mock(name="commander")

        @hp.memoized_property
        def lan_target(s):
            m = mock.Mock(name="lan_target")

            m.args_for_run = pytest.helpers.AsyncMock(name="args_for_run", return_value=s.afr)
            m.close_args_for_run = pytest.helpers.AsyncMock(name="close_args_for_run")

            return m

        @hp.memoized_property
        def FakeZeroconfRegisterer(s):
            reg = mock.Mock(name="ZeroconfRegisterer")
            reg.start = pytest.helpers.AsyncMock(name="start")
            reg.finish = pytest.helpers.AsyncMock(name="start")
            return reg

    return V()


@pytest.fixture(scope="module")
async def server(V, server_wrapper, sender, final_future):
    zeroconf_patch = mock.patch(
        "interactor.zeroconf.ZeroconfRegisterer", lambda *a, **kw: V.FakeZeroconfRegisterer
    )
    with zeroconf_patch:
        async with server_wrapper(store, sender, final_future) as server:
            yield server


describe "Server":
    async it "starts things correctly", V, server:
        tasks = server.ts
        server = server.server
        assert server.tasks is tasks
        assert isinstance(server.daemon, DeviceFinderDaemon)
        assert isinstance(server.finder, Finder)
        assert server.daemon.finder is server.finder

        assert isinstance(server.animations, Animations)
        assert server.animations.tasks is server.tasks
        assert server.animations.sender is server.sender
        assert server.animations.final_future is server.final_future

        assert isinstance(server.server_options.zeroconf, Zeroconf)

        class IsDB:
            def __eq__(self, o):
                assert isinstance(o, DB)
                assert str(o.engine.url) == "sqlite+aiosqlite:///:memory:"
                return True

        class IsReferenceResolver:
            def __eq__(self, o):
                assert isinstance(o, ReferenceResolverRegister)
                return True

        assert server.meta.data == dict(
            tasks=server.tasks,
            sender=server.sender,
            finder=server.finder,
            zeroconf=server.server_options.zeroconf,
            database=IsDB(),
            animations=server.animations,
            final_future=server.final_future,
            server_options=server.server_options,
            reference_resolver_register=IsReferenceResolver(),
        )

        async with server.database.engine.begin() as conn:
            await conn.run_sync(server.database.Base.metadata.create_all)

        async def get(session, query):
            return await query.get_scenes()

        assert await server.database.request(get) == []
