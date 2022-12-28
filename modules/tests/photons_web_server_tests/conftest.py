import asyncio
import typing as tp

import pytest
from photons_app import helpers as hp
from sanic import Sanic


def pytest_configure(config):
    pytest.helpers.register(IsInstance)


@pytest.fixture()
def call_from_conftest():
    def call_from_conftest(cb):
        return cb()

    return call_from_conftest


@pytest.fixture(autouse=True, scope="module")
def sanic_test_mode():
    Sanic.test_mode = True


@pytest.fixture()
def fake_time(FakeTime):
    with FakeTime() as t:
        yield t


@pytest.fixture()
async def fake_event_loop(MockedCallLater, fake_time):
    async with MockedCallLater(fake_time) as m:
        yield m


@pytest.fixture()
def final_future() -> tp.Generator[asyncio.Future, None, None]:
    fut = hp.create_future(name="conftest::final_future")
    try:
        yield fut
    finally:
        fut.cancel()


class IsInstance:
    got: object | None

    def __init__(self, kls: type):
        self.got = None
        self.kls = kls

    def __eq__(self, other: object) -> bool:
        self.got = other
        return isinstance(other, self.kls)

    def __repr__(self) -> str:
        if self.got is None:
            return f"<INSTANCE OF {self.kls}>"
        else:
            return repr(self.got)
