import pytest
from photons_app import helpers as hp


@pytest.fixture(autouse=True)
async def fake_the_time(FakeTime, MockedCallLater):
    with FakeTime() as t:
        async with MockedCallLater(t) as m:
            yield t, m


@pytest.fixture()
def fake_time(fake_the_time):
    return fake_the_time[0]


@pytest.fixture()
def m(fake_the_time):
    return fake_the_time[1]


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()
