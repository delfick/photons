# coding: spec

from interactor.commander.animations import Animations
from interactor.commander.store import store

from photons_app import helpers as hp

from photons_control.device_finder import Finder, DeviceFinderDaemon

from unittest import mock
import pytest


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
        db_queue = mock.Mock(name="db_queue", finish=pytest.helpers.AsyncMock(name="finish"))
        commander = mock.Mock(name="commander")

        @hp.memoized_property
        def lan_target(s):
            m = mock.Mock(name="lan_target")

            m.args_for_run = pytest.helpers.AsyncMock(name="args_for_run", return_value=s.afr)
            m.close_args_for_run = pytest.helpers.AsyncMock(name="close_args_for_run")

            return m

        @hp.memoized_property
        def FakeDBQueue(s):
            return mock.Mock(name="DBQueue", return_value=s.db_queue)

        @hp.memoized_property
        def FakeCommander(s):
            return mock.Mock(name="Commander", return_value=s.commander)

    return V()


@pytest.fixture(scope="module")
async def server(V, server_wrapper, sender, final_future):
    commander_patch = mock.patch("interactor.server.Commander", V.FakeCommander)
    db_patch = mock.patch("interactor.database.db_queue.DBQueue", V.FakeDBQueue)

    with commander_patch, db_patch:
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

        V.FakeCommander.assert_called_once_with(
            store,
            tasks=server.tasks,
            sender=server.sender,
            finder=server.finder,
            db_queue=V.db_queue,
            animations=server.animations,
            final_future=server.final_future,
            server_options=server.server_options,
        )
        V.FakeDBQueue.assert_called_once_with(
            server.final_future, 5, mock.ANY, "sqlite:///:memory:"
        )

        V.db_queue.start.assert_called_once_with()
