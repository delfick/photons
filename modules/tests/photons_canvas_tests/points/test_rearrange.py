from unittest import mock

from photons_canvas.orientation import Orientation
from photons_canvas.points import containers as cont
from photons_canvas.points import helpers as php
from photons_canvas.points import rearrange as rea
from photons_canvas.points.canvas import Canvas
from photons_products import Products


class TestRearrange:
    def test_it_creates_a_new_canvas_from_the_parts_given_by_the_rearranger(self):
        device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)

        rp1 = mock.Mock(name="rp1")
        rp2 = mock.Mock(name="rp2")

        colors1 = [(i, 1, 1, 3500) for i in range(16)]
        colors2 = [(i, 0, 0, 3500) for i in range(16)]

        part1 = cont.Part(
            0, 0, 4, 4, 1, Orientation.RightSideUp, device, real_part=rp1, original_colors=colors1
        )
        part2 = cont.Part(
            1,
            0.25,
            4,
            4,
            2,
            Orientation.RightSideUp,
            device,
            real_part=rp2,
            original_colors=colors2,
        )

        class Rearranger:
            def rearrange(s, canvas):
                for part in canvas.parts:
                    yield part.clone(user_x=2)

        canvas = Canvas()
        canvas.add_parts(part1, part2, with_colors=True)

        n = rea.rearrange(canvas, Rearranger(), keep_colors=True)
        assert n is not canvas
        assert len(n.parts) == len(canvas.parts)
        assert sorted([repr(p) for p in n.parts]) == sorted([repr(p) for p in canvas.parts])

        assert sorted([p.bounds for p in n.parts]) == [
            ((16, 20), (0, -4), (4, 4)),
            ((16, 20), (2, -2), (4, 4)),
        ]

        expected = [
            *[(0, 0, 0, 3500), (1, 0, 0, 3500), (2, 0, 0, 3500), (3, 0, 0, 3500)],
            *[(4, 0, 0, 3500), (5, 0, 0, 3500), (6, 0, 0, 3500), (7, 0, 0, 3500)],
            *[(8, 0, 0, 3500), (9, 0, 0, 3500), (10, 0, 0, 3500), (11, 0, 0, 3500)],
            *[(12, 0, 0, 3500), (13, 0, 0, 3500), (14, 0, 0, 3500), (15, 0, 0, 3500)],
            *[(8, 1, 1, 3500), (9, 1, 1, 3500), (10, 1, 1, 3500), (11, 1, 1, 3500)],
            *[(12, 1, 1, 3500), (13, 1, 1, 3500), (14, 1, 1, 3500), (15, 1, 1, 3500)],
        ]

        assert [n[p] for p in php.Points.all_points(n.bounds)] == expected
        assert set(p.real_part for p in n.parts) == set([rp1, rp2])

    def test_it_can_create_new_canvas_without_colors(self):
        device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)

        rp1 = mock.Mock(name="rp1")
        rp2 = mock.Mock(name="rp2")

        part1 = cont.Part(0, 0, 4, 4, 1, Orientation.RightSideUp, device, real_part=rp1)
        part2 = cont.Part(1, 0.25, 4, 4, 2, Orientation.RightSideUp, device, real_part=rp2)

        colors1 = [(i, 1, 1, 3500) for i in range(16)]
        colors2 = [(i, 0, 0, 3500) for i in range(16)]

        class Rearranger:
            def rearrange(s, canvas):
                for part in canvas.parts:
                    yield part.clone(user_x=2)

        canvas = Canvas()
        canvas.add_parts((part1, colors1), (part2, colors2))

        n = rea.rearrange(canvas, Rearranger())
        assert n is not canvas
        assert len(n.parts) == len(canvas.parts)
        assert sorted([repr(p) for p in n.parts]) == sorted([repr(p) for p in canvas.parts])

        assert sorted([p.bounds for p in n.parts]) == [
            ((16, 20), (0, -4), (4, 4)),
            ((16, 20), (2, -2), (4, 4)),
        ]

        assert all(n[p] is None for p in php.Points.all_points(n.bounds))
        assert set(p.real_part for p in n.parts) == set([rp1, rp2])


class TestRearrangers:

    @classmethod
    def make_parts(cls, *corner_and_sizes):
        device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)
        for i, (left, top, width, height) in enumerate(corner_and_sizes):
            user_x = left / 8
            user_y = top / 8

            real_part = cont.Part(user_x, user_y, width, height, i, Orientation.RightSideUp, device)
            yield cont.Part(
                user_x,
                user_y,
                width,
                height,
                i,
                Orientation.RightSideUp,
                device,
                real_part=real_part,
            )

    @classmethod
    def assertParts(cls, rearranger, parts, *new_corners):
        canvas = Canvas()
        canvas.add_parts(*parts)
        made = list(rearranger.rearrange(canvas))

        assert len(made) == len(new_corners) == len(parts)

        found = []
        for i, n in enumerate(new_corners):
            if len(n) == 2:
                new_left = n[0]
                new_top = n[1]
                new = made[i]
                old = parts[i]
            else:
                new_left = n[0]
                new_top = n[1]
                new = made[i]
                old = parts[n[2]]

            found.append(repr(old))

            assert old == new
            assert old.real_part is new.real_part
            assert old.width == new.width
            assert old.height == new.height

            assert new.left == new_left
            assert new.top == new_top

        assert len(set(found)) == len(found)

    class TestSeparateAlignment:
        def test_it_aligns_separate_user_x_and_leaves_y_alignment(self):
            parts = list(
                TestRearrangers.make_parts((0, 1, 8, 8), (-1, 2, 4, 5), (5, 7, 3, 10), (0, 4, 8, 8))
            )
            TestRearrangers.assertParts(rea.Separate(), parts, (0, 1), (8, 2), (12, 7), (15, 4))

    class TestStraightAlignment:
        def test_it_makes_all_parts_line_up_on_the_same_y_axis(self):
            parts = list(
                TestRearrangers.make_parts(
                    (0, 1, 7, 8), (-1, 2, 4, 5), (5, 7, 3, 10), (0, 4, 20, 8)
                )
            )
            TestRearrangers.assertParts(
                rea.Straight(), parts, (0, 0, 1), (4, 0, 0), (11, 0, 3), (31, 0, 2)
            )

    class TestVerticalAlignment:
        def test_it_puts_all_parts_at_the_same_y_level(self):
            parts = list(
                TestRearrangers.make_parts((0, 1, 8, 8), (-1, 2, 4, 5), (5, 7, 3, 10), (0, 4, 8, 8))
            )
            TestRearrangers.assertParts(
                rea.VerticalAlignment(), parts, (0, 0), (-1, 0), (5, 0), (0, 0)
            )
