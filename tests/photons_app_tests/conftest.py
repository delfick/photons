from unittest import mock
import pytest


@pytest.fixture(autouse=True)
def ensure_no_new_loop():
    """Photons app can set a new event loop and this breaks alt-pytest-asyncio"""
    with mock.patch("asyncio.set_event_loop", lambda loop: None):
        yield
