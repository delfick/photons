import pytest
from photons_app import helpers as hp


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()
