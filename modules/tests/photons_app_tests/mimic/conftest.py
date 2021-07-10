from photons_app import helpers as hp
import pytest


@pytest.fixture()
def final_future():
    final_future = hp.create_future()
    try:
        yield final_future
    finally:
        final_future.cancel()
