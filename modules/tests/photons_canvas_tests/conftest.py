from photons_app import helpers as hp

from photons_messages.fields import scaled_hue, scaled_to_65535

from delfick_project.norms import sb
from unittest import mock
import pytest


@pytest.fixture(scope="module", autouse=True)
def modify_hsbk_calculation():
    """
    The way hsbk is calculated for canvas is close enough but not as accurate as the rest of Photons
    because it doesn't need to be as accurate and the changes are optimised for performance

    Unfortunately this means that comparisons in tests aren't so great, so let's modify how hsbk
    is calculated to match!
    """

    scaled_hue_transform = (
        lambda _, v: int(0x10000 * (0 if v is sb.NotSpecified else float(v)) / 360) % 0x10000
    )
    scaled_to_65535_transform = lambda _, v: int(0xFFFF * (0 if v is sb.NotSpecified else float(v)))

    p1 = mock.patch.object(scaled_hue, "_transform", scaled_hue_transform)
    p2 = mock.patch.object(scaled_to_65535, "_transform", scaled_to_65535_transform)

    with p1, p2:
        yield


@pytest.fixture()
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()
