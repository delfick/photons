# coding: spec

from interactor.commander.store import store

from photons_app import helpers as hp

from photons_control.device_finder import Finder, DeviceFinderDaemon

from unittest import mock
import asynctest
import pytest


@pytest.fixture(scope="module")
def V():
    class V:
        afr = mock.Mock(name="afr")
        db_queue = mock.Mock(name="db_queue")
        commander = mock.Mock(name="commander")

        @hp.memoized_property
        def lan_target(s):
            m = mock.Mock(name="lan_target")

            m.args_for_run = asynctest.mock.CoroutineMock(name="args_for_run", return_value=s.afr)
            m.close_args_for_run = asynctest.mock.CoroutineMock(name="close_args_for_run")

            return m

        @hp.memoized_property
        def FakeDBQueue(s):
            return mock.Mock(name="DBQueue", return_value=s.db_queue)

        @hp.memoized_property
        def FakeCommander(s):
            return mock.Mock(name="Commander", return_value=s.commander)

    return V()


@pytest.fixture(scope="module")
async def wrapper(V, server_wrapper):
    commander_patch = mock.patch("interactor.server.Commander", V.FakeCommander)
    db_patch = mock.patch("interactor.server.DBQueue", V.FakeDBQueue)

    with commander_patch, db_patch:
        async with server_wrapper(store) as wrapper:
            yield wrapper


@pytest.fixture(autouse=True)
async def wrap_tests(wrapper):
    async with wrapper.test_wrap():
        yield


@pytest.fixture()
def runner(wrapper):
    return wrapper.runner


@pytest.fixture()
def server(wrapper):
    return wrapper.server


describe "Server":
    async it "starts things correctly", V, server, runner:
        assert isinstance(server.daemon, DeviceFinderDaemon)
        assert isinstance(server.finder, Finder)
        assert server.daemon.finder is server.finder

        V.FakeCommander.assert_called_once_with(
            store,
            sender=server.sender,
            finder=server.finder,
            db_queue=V.db_queue,
            final_future=runner.final_future,
            server_options=server.server_options,
        )
        V.FakeDBQueue.assert_called_once_with(
            runner.final_future, 5, mock.ANY, "sqlite:///:memory:"
        )

        V.db_queue.start.assert_called_once_with()
