from photons_protocol.packing import pack_cache, unpack_cache
import pytest


@pytest.fixture(autouse=True)
def reset_protocol_cache():
    pack_cache.clear()
    unpack_cache.clear()
