import pytest
from photons_app import helpers as hp
from photons_canvas.orientation import Orientation
from photons_canvas.points import containers as cont
from photons_products import Products


@pytest.fixture
def V():
    class V:
        device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)
        other_device = cont.Device("d073d5006677", Products.LCM3_TILE.cap)

        @hp.memoized_property
        def original_colors(self):
            return [(i, 1, 1, 3500) for i in range(64)]

        def make_part(
            self,
            device,
            part_number,
            user_x=5,
            user_y=4,
            width=8,
            height=8,
            orientation=Orientation.RightSideUp,
            **kwargs,
        ):
            return cont.Part(user_x, user_y, width, height, part_number, orientation, device, **kwargs)

        @hp.memoized_property
        def real_part(s):
            return s.make_part(
                s.device,
                5,
                user_x=5,
                user_y=4,
                width=8,
                height=8,
                original_colors=s.original_colors,
            )

        @hp.memoized_property
        def part(s):
            return s.make_part(
                s.device,
                5,
                user_x=0,
                user_y=0,
                width=8,
                height=8,
                original_colors=s.original_colors,
                real_part=s.real_part,
            )

    return V()
