import pytest
from sanic import Sanic


@pytest.fixture(autouse=True, scope="module")
def sanic_test_mode():
    Sanic.test_mode = True
