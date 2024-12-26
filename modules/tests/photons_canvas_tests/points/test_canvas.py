from unittest import mock

from photons_canvas.orientation import Orientation
from photons_canvas.points import containers as cont
from photons_canvas.points import helpers as php
from photons_canvas.points.canvas import Canvas
from photons_messages import TileMessages
from photons_messages.fields import Color


class TestCanvas:
    def test_it_has_start_properties(self):
        canvas = Canvas()

        for attr in ("top", "left", "right", "bottom", "width", "height"):
            assert getattr(canvas, attr) is None

        assert canvas.point_to_parts == {}
        assert canvas.point_to_devices == {}

    def test_it_is_truthy_if_it_has_points_or_parts(self, V):
        canvas = Canvas()
        assert not canvas

        canvas[1, 2] = (1, 1, 1, 1)
        assert canvas

        canvas = Canvas()
        canvas.add_parts(V.make_part(V.device, 1))
        assert canvas

        canvas[1, 2] = (1, 1, 1, 1)
        assert canvas

    def test_it_knows_if_a_point_is_in_the_canvas(self):
        c = Canvas()
        assert (1, 2) not in c

        c[1, 2] = (200, 1, 0.2, 9000)
        assert (1, 2) in c

    def test_it_calling_canvas_gets_the_value_at_that_point(self):
        c = Canvas()
        c[1, 2] = (100, 1, 0, 3500)

        assert c((1, 2), c) == (100, 1, 0, 3500)
        assert c((2, 1), c) is None

    def test_it_can_get_parts(self, V):
        c = Canvas()
        assert c.parts == []

        part1 = V.make_part(V.device, 1)
        part2 = V.make_part(V.device, 2)
        part3 = V.make_part(V.other_device, 1)

        c.add_parts(part1, part2, part3)
        assert c.parts == [part1, part2, part3]

    def test_it_can_get_devices(self, V):
        c = Canvas()
        assert c.devices == []

        part1 = V.make_part(V.device, 1)
        part2 = V.make_part(V.device, 2)
        part3 = V.make_part(V.other_device, 1)

        c.add_parts(part1, part2, part3)
        assert c.devices == [V.device, V.other_device]

    def test_it_can_get_bounds(self, V):
        c = Canvas()
        assert c.bounds == ((None, None), (None, None), (None, None))

        c[1, 2] = (100, 1, 0.5, 3500)
        assert (1, 2) in c
        assert c.bounds == ((1, 1), (2, 2), (0, 0))

        part1 = V.make_part(V.device, 1, user_x=2, user_y=3, width=8, height=6)
        assert part1.bounds == ((16, 24), (24, 18), (8, 6))
        c.add_parts(part1)
        assert c.bounds == ((1, 24), (24, 2), (23, 22))

        part2 = V.make_part(V.device, 2, user_x=4, user_y=-10, width=3, height=3)
        assert part2.bounds == ((32, 35), (-80, -83), (3, 3))

        part3 = V.make_part(V.other_device, 1, user_x=5, user_y=-5, width=8, height=16)
        assert part3.bounds == ((40, 48), (-40, -56), (8, 16))

        c.add_parts(part2, part3)
        assert c.bounds == ((1, 48), (24, -83), (47, 107))

    def test_it_can_clone_and_copy_over_points_and_parts(self):
        c = Canvas()

        clone = c.clone()
        assert clone.bounds == ((None, None), (None, None), (None, None))
        assert not clone.points
        assert not clone._parts
        assert clone.points is not c.points
        assert clone._parts is not c._parts

        c[1, 2] = (200, 1, 1, 3500)
        c[3, 5] = (200, 1, 1, 3500)
        assert c.bounds == ((1, 3), (5, 2), (2, 3))

        clone = c.clone()
        assert clone.bounds == ((1, 3), (5, 2), (2, 3))
        assert all(clone[k] == c[k] for k in c.points)
        assert all(cp is clp for cp, clp in zip(c._parts, clone._parts))
        assert clone.points == c.points
        assert clone.parts == c.parts
        assert clone.devices == c.devices

    def test_it_can_find_the_parts_for_each_point(self, V):
        # 6   a c c a _
        # 5   a c c a _
        # 4   a a a a _
        # 3   d d d f e
        # 2   d d d f e
        # 1   _ _ _ e e
        #
        # 0   1 2 3 4 5

        # a = (1, 6) -> (4, 4)
        # b = (2, 6) -> (3, 5)
        # c = a + b

        # d = (1, 3) -> (4, 2)
        # e = (4, 3) -> (5, 1)
        # f = d + e

        OO = Orientation.RightSideUp

        device1 = V.device
        device2 = V.other_device

        # Part = user_x, user_y, width, height, part_number, orientation, device
        a = cont.Part(1 / 8, 6 / 8, 4, 3, 2, OO, device1)
        b = cont.Part(2 / 8, 6 / 8, 2, 2, 1, OO, device2)
        d = cont.Part(1 / 8, 3 / 8, 4, 2, 1, 1, device1)
        e = cont.Part(4 / 8, 3 / 8, 2, 3, 3, 1, device1)

        testcases = [
            ((1, 6), [a], [device1]),
            ((1, 5), [a], [device1]),
            ((1, 4), [a], [device1]),
            ((1, 3), [d], [device1]),
            ((1, 2), [d], [device1]),
            ((1, 1), [], []),
            #
            ((2, 6), [a, b], [device1, device2]),
            ((2, 5), [a, b], [device1, device2]),
            ((2, 4), [a], [device1]),
            ((2, 3), [d], [device1]),
            ((2, 2), [d], [device1]),
            ((2, 1), [], []),
            #
            ((3, 6), [a, b], [device1, device2]),
            ((3, 5), [a, b], [device1, device2]),
            ((3, 4), [a], [device1]),
            ((3, 3), [d], [device1]),
            ((3, 2), [d], [device1]),
            ((3, 1), [], []),
            #
            ((4, 6), [a], [device1]),
            ((4, 5), [a], [device1]),
            ((4, 4), [a], [device1]),
            ((4, 3), [d, e], [device1]),
            ((4, 2), [d, e], [device1]),
            ((4, 1), [e], [device1]),
            #
            ((5, 6), [], []),
            ((5, 5), [], []),
            ((5, 4), [], []),
            ((5, 3), [e], [device1]),
            ((5, 2), [e], [device1]),
            ((5, 1), [e], [device1]),
        ]

        canvas = Canvas()
        canvas.add_parts(a, b, d, e)

        for point, parts, devices in testcases:
            assert sorted(canvas.point_to_parts[point]) == sorted(parts), point

        assert len(testcases) == 5 * 6

    class TestGettingSettingAndDeletingAPoint:
        def test_it_can_get_None_if_its_not_in_the_canvas(self):
            c = Canvas()
            assert c[1, 2] is None

        def test_it_can_get_the_color_from_the_canvas(self):
            c = Canvas()

            color = (1, 1, 1, 3500)
            c[1, 2] = color
            assert c[1, 2] is color
            assert c[2, 1] is None

        def test_it_it_updates_bounds_on_setting(self):
            c = Canvas()

            assert c.bounds == ((None, None), (None, None), (None, None))

            c[1, 2] = (100, 1, 0.5, 3500)
            assert (1, 2) in c
            assert c.bounds == ((1, 1), (2, 2), (0, 0))

            c[3, 5] = (200, 1, 0.2, 3500)
            assert (3, 5) in c
            assert c.bounds == ((1, 3), (5, 2), (2, 3))

            # and if point is in the canvas
            c[3, 5] = (200, 1, 0.2, 3500)
            assert (3, 5) in c
            assert c.bounds == ((1, 3), (5, 2), (2, 3))

        def test_it_it_updates_bounds_on_deleting(self):
            c = Canvas()

            assert c.bounds == ((None, None), (None, None), (None, None))

            c[1, 2] = (100, 1, 0.5, 3500)
            assert (1, 2) in c
            assert c.bounds == ((1, 1), (2, 2), (0, 0))
            del c[1, 2]
            assert (1, 2) not in c
            assert c.bounds == ((None, None), (None, None), (None, None))
            # idempotent
            del c[1, 2]
            assert c.bounds == ((None, None), (None, None), (None, None))

            c[1, 2] = (100, 1, 0.5, 3500)
            assert (1, 2) in c
            assert c.bounds == ((1, 1), (2, 2), (0, 0))

            c[3, 5] = (200, 1, 0.2, 3500)
            assert (1, 2) in c
            assert (3, 5) in c
            assert c.bounds == ((1, 3), (5, 2), (2, 3))
            del c[3, 5]
            assert (3, 5) not in c
            assert c.bounds == ((1, 1), (2, 2), (0, 0))

    class TestUpdatingBounds:
        def test_it_does_nothing_if_no_parts_are_provided(self):
            c = Canvas()
            assert c.bounds == ((None, None), (None, None), (None, None))

            c._update_bounds([])
            assert c.bounds == ((None, None), (None, None), (None, None))

        def test_it_updates_bounds_from_tuples(self):
            c = Canvas()
            assert c.bounds == ((None, None), (None, None), (None, None))

            c._update_bounds([((1, 3), (10, 6), (2, 4))])
            assert c.bounds == ((1, 3), (10, 6), (2, 4))

            c._update_bounds([((1, 10), (8, 7), (7, 3))])
            assert c.bounds == ((1, 10), (10, 6), (9, 4))

            c._update_bounds([((0, 2), (0, -2), (2, 2))])
            assert c.bounds == ((0, 10), (10, -2), (10, 12))

            c._update_bounds([(12, 5)])
            assert c.bounds == ((0, 12), (10, -2), (12, 12))

            c._update_bounds([(-1, -3)])
            assert c.bounds == ((-1, 12), (10, -3), (13, 13))

            c._update_bounds([(2, 12)])
            assert c.bounds == ((-1, 12), (12, -3), (13, 15))

            c._update_bounds([(0, 13), (13, 5), (-3, -7)])
            assert c.bounds == ((-3, 13), (13, -7), (16, 20))

        def test_it_updates_bounds_from_objects_with_bounds_on_them(self, V):
            c = Canvas()
            assert c.bounds == ((None, None), (None, None), (None, None))

            def M(h, v, s):
                return mock.Mock(name="thing", bounds=(h, v, s), spec=["bounds"])

            part1 = V.make_part(V.device, 1, user_x=1 / 8, user_y=10 / 8, width=2, height=4)

            c._update_bounds([part1])
            assert c.bounds == ((1, 3), (10, 6), (2, 4))

            c._update_bounds([M((1, 10), (8, 7), (7, 3))])
            assert c.bounds == ((1, 10), (10, 6), (9, 4))

            c._update_bounds([M((0, 2), (0, -2), (2, 2))])
            assert c.bounds == ((0, 10), (10, -2), (10, 12))

            c._update_bounds([(12, 5)])
            assert c.bounds == ((0, 12), (10, -2), (12, 12))

            c._update_bounds([(-1, -3)])
            assert c.bounds == ((-1, 12), (10, -3), (13, 13))

            c._update_bounds([(2, 12)])
            assert c.bounds == ((-1, 12), (12, -3), (13, 15))

            c._update_bounds([(0, 13), (13, 5), (-3, -7)])
            assert c.bounds == ((-3, 13), (13, -7), (16, 20))

    class TestAddingParts:
        def test_it_can_add_part_without_colors(self, V):
            c = Canvas()

            part1 = V.make_part(V.device, 1, user_x=0, user_y=2, width=8, height=9)
            c.add_parts(part1)

            assert c.bounds == ((0, 8), (16, 7), (8, 9))
            assert c.parts == [part1]
            assert c.devices == [V.device]

        def test_it_can_add_a_part_with_colors(self, V):
            c = Canvas()

            part1 = V.make_part(V.device, 1, user_x=0, user_y=2, width=8, height=9)
            colors1 = [(i + 20, 1, 0, 3500) for i in range(64)]
            c.add_parts((part1, colors1))

            assert c.bounds == ((0, 8), (16, 7), (8, 9))
            assert c.parts == [part1]
            assert c.devices == [V.device]

            assert all(c[p] == color for p, color in zip(part1.points, colors1))
            assert all(c.point_to_parts[p] == set([part1]) for p in part1.points)

        def test_it_can_add_multiple_parts(self, V):
            c = Canvas()

            part1 = V.make_part(V.device, 2, user_x=-1, user_y=3, width=7, height=10)
            part2 = V.make_part(V.device, 1, user_x=0, user_y=3, width=8, height=9)

            assert part1.bounds == ((-8, -1), (24, 14), (7, 10))
            assert part2.bounds == ((0, 8), (24, 15), (8, 9))

            colors2 = [(i + 20, 1, 0, 3500) for i in range(72)]
            assert len(part2.points) == 72

            c.add_parts(part1, (part2, colors2))

            assert c.bounds == ((-8, 8), (24, 14), (16, 10))

            assert all(p not in c for p in part1.points)
            assert all(c[p] == color for p, color in zip(part2.points, colors2))

        def test_it_can_add_with_colors_from_parts(self, V):
            c = Canvas()

            part1 = V.make_part(V.device, 2, user_x=-1, user_y=3, width=7, height=10)

            colors2 = [(i + 20, 1, 0, 3500) for i in range(72)]
            part2 = V.make_part(V.device, 1, user_x=0, user_y=3, width=8, height=9, original_colors=colors2)

            assert part1.bounds == ((-8, -1), (24, 14), (7, 10))
            assert part2.bounds == ((0, 8), (24, 15), (8, 9))

            assert len(part2.points) == 72

            c.add_parts(part1, part2, with_colors=True)

            assert c.bounds == ((-8, 8), (24, 14), (16, 10))

            assert all(p not in c for p in part1.points)
            assert all(c[p] == color for p, color in zip(part2.points, colors2))

        def test_it_can_add_with_a_zero_color(self, V):
            c = Canvas()
            zero_color = (1, 1, 0.4, 9000)

            part1 = V.make_part(V.device, 2, user_x=-1, user_y=3, width=7, height=10)

            colors2 = [(i + 20, 1, 0, 3500) for i in range(72)]
            part2 = V.make_part(V.device, 1, user_x=0, user_y=3, width=8, height=9, original_colors=colors2)

            assert part1.bounds == ((-8, -1), (24, 14), (7, 10))
            assert part2.bounds == ((0, 8), (24, 15), (8, 9))

            assert len(part2.points) == 72

            c.add_parts(part1, part2, with_colors=True, zero_color=zero_color)

            assert c.bounds == ((-8, 8), (24, 14), (16, 10))

            assert all(c[p] == zero_color for p in part1.points)
            assert all(c[p] == color for p, color in zip(part2.points, colors2))

    class TestPointHelpers:
        def test_it_can_determine_if_all_points_in_the_parts_match_certain_criteria(self, V):
            canvas = Canvas()
            assert canvas.is_parts()
            assert canvas.is_parts(hue=1, brightness=1, saturation=1, kelvin=9000)

            colors1 = [(i, 1, 1, 3500) for i in range(64)]
            part1 = V.make_part(V.device, 1, original_colors=colors1, user_x=20, user_y=20, width=8, height=8)

            canvas = Canvas()
            canvas.add_parts(part1)
            assert canvas.is_parts(brightness=1)
            assert canvas.is_parts(brightness=0)
            assert canvas.is_parts(saturation=1)
            assert canvas.is_parts(saturation=0)
            assert canvas.is_parts(kelvin=3500)
            assert canvas.is_parts(kelvin=9000)
            assert canvas.is_parts(hue=0)

            canvas = Canvas()
            canvas.add_parts(part1, with_colors=True)
            assert canvas.is_parts(brightness=1)
            assert not canvas.is_parts(brightness=0)
            assert canvas.is_parts(saturation=1)
            assert not canvas.is_parts(saturation=0)
            assert canvas.is_parts(kelvin=3500)
            assert not canvas.is_parts(kelvin=9000)
            assert not canvas.is_parts(hue=0)

            colors2 = [(i, 0, 1, 9000) for i in range(64)]
            part2 = V.make_part(V.device, 2, original_colors=colors2, user_x=-20, user_y=-20, width=8, height=8)
            canvas.add_parts(part2, with_colors=True)
            assert canvas.is_parts(brightness=1)
            assert not canvas.is_parts(brightness=0)
            assert not canvas.is_parts(saturation=1)
            assert not canvas.is_parts(saturation=0)
            assert not canvas.is_parts(kelvin=3500)
            assert not canvas.is_parts(kelvin=9000)
            assert not canvas.is_parts(hue=0)

            canvas = Canvas()
            canvas.add_parts((part1, part1.colors), part2)
            assert canvas.is_parts(brightness=1)
            assert not canvas.is_parts(brightness=0)
            assert canvas.is_parts(saturation=1)
            assert not canvas.is_parts(saturation=0)
            assert canvas.is_parts(kelvin=3500)
            assert not canvas.is_parts(kelvin=9000)
            assert not canvas.is_parts(hue=0)

        def test_it_can_get_a_color_with_overrided_values(self):
            canvas = Canvas()
            assert canvas.override((1, 2)) == (0, 0, 0, 0)
            assert (1, 2) not in canvas

            assert canvas.override((1, 2), hue=1) == (1, 0, 0, 0)
            assert canvas.override((1, 2), hue=1, saturation=1) == (1, 1, 0, 0)
            assert canvas.override((1, 2), hue=1, saturation=1, brightness=1) == (1, 1, 1, 0)

            want = (1, 1, 1, 9000)
            assert canvas.override((1, 2), hue=1, saturation=1, brightness=1, kelvin=9000) == want

            canvas[(3, 4)] = (20, 0.3, 0.4, 5000)
            assert canvas.override((3, 4), hue=200, brightness=1) == (200, 0.3, 1, 5000)
            assert canvas[(3, 4)] == (20, 0.3, 0.4, 5000)

        def test_it_can_get_a_dimmed_colour(self):
            canvas = Canvas()
            assert canvas.dim((1, 2), -1) is None

            canvas[(3, 4)] = (200, 0.4, 0.4, 9000)
            assert canvas.dim((3, 4), -0.1) == (200, 0.4, 0.5, 9000)
            assert canvas[(3, 4)] == (200, 0.4, 0.4, 9000)

            assert canvas.dim((3, 4), 0.1) == (200, 0.4, 0.4 - 0.1, 9000)
            assert canvas.dim((3, 4), -0.7) == (200, 0.4, 1, 9000)
            assert canvas.dim((3, 4), 0.7) is None

        def test_it_return_None_from_adjusting_a_point_if_the_point_is_empty_and_ignore_empty(self):
            canvas = Canvas()
            assert canvas.adjust((1, 2)) is None
            assert canvas.adjust((1, 2), ignore_empty=False) == php.Color.ZERO

            canvas[(1, 2)] = php.Color.ZERO
            assert canvas.adjust((1, 2)) is None
            assert canvas.adjust((1, 2), ignore_empty=False) == php.Color.ZERO

        def test_it_returns_an_adjusted_colour(self):
            color = mock.Mock(name="color", spec=[])
            adjusted = mock.Mock(name="adjusted", spec=[])

            canvas = Canvas()
            canvas[(1, 2)] = color

            adjust = mock.Mock(name="adjust", return_value=adjusted)
            with mock.patch.object(php.Color, "adjust", adjust):
                assert canvas.adjust((1, 2)) is adjusted
                adjust.assert_called_once_with(
                    color,
                    hue_change=None,
                    saturation_change=None,
                    brightness_change=None,
                    kelvin_change=None,
                )
                adjust.reset_mock()

                hue_change = mock.Mock(name="hue_change", spec=[])
                saturation_change = mock.Mock(name="saturation_change", spec=[])
                brightness_change = mock.Mock(name="brightness_change", spec=[])
                kelvin_change = mock.Mock(name="kelvin_change", spec=[])

                assert (
                    canvas.adjust(
                        (1, 2),
                        hue_change=hue_change,
                        saturation_change=saturation_change,
                        brightness_change=brightness_change,
                        kelvin_change=kelvin_change,
                    )
                    is adjusted
                )
                adjust.assert_called_once_with(
                    color,
                    hue_change=hue_change,
                    saturation_change=saturation_change,
                    brightness_change=brightness_change,
                    kelvin_change=kelvin_change,
                )
                adjust.reset_mock()

    class TestRestoreMsgs:
        def test_it_yields_msgs_from_real_parts(self, V):
            oc1 = [(i, 1, 1, 1) for i in range(64)]
            oc2 = [(i, 0, 0.3, 9000) for i in range(64)]

            real_part1 = V.make_part(V.device, 2, original_colors=oc1)
            real_part2 = V.make_part(V.device, 3)
            real_part3 = V.make_part(V.other_device, 5, original_colors=oc2)

            part1 = V.make_part(V.device, 1)
            part2 = V.make_part(V.device, 2, real_part=real_part1)
            part3 = V.make_part(V.device, 3, real_part=real_part2)
            part4 = V.make_part(V.other_device, 5, real_part=real_part3)

            canvas = Canvas()
            canvas.add_parts(part1, part2, part3, part4)

            msgs = list(canvas.restore_msgs(duration=3))
            assert len(msgs) == 2
            assert all(m | TileMessages.Set64 for m in msgs)

            assert msgs[0].colors == [Color(*c) for c in oc1]
            assert msgs[1].colors == [Color(*c) for c in oc2]

            assert msgs[0].serial == V.device.serial
            assert msgs[1].serial == V.other_device.serial

            assert msgs[0].tile_index == 2
            assert msgs[1].tile_index == 5

    class TestMsgs:
        def test_it_gets_colours_from_the_layer(self, V):
            info = {"canvas": None}

            def layer(point, canvas):
                assert info["canvas"] is not None
                assert canvas is info["canvas"]
                if point[0] % 2 == 0:
                    return None
                else:
                    return (abs(point[0] * point[1]), 1, 1, 3500)

            def assert_colors(cs, *hues):
                colors = []
                for h in hues:
                    if h is None:
                        colors.append((0, 0, 0, 0))
                    else:
                        colors.append((h, 1, 1, 3500))

                while len(colors) != 64:
                    colors.append((0, 0, 0, 0))

                colors = [Color(*c) for c in colors]
                for i, (got, want) in enumerate(zip(cs, colors)):
                    if got != want:
                        print(i, got, want)

                assert cs == colors

            onto = {}
            for on in (None, onto):
                part1 = V.make_part(V.device, 1, user_x=0, user_y=0, width=2, height=2)
                assert part1.bounds == ((0, 2), (0, -2), (2, 2))

                part2 = V.make_part(V.device, 2, user_x=1, user_y=1, width=2, height=2)
                assert part2.bounds == ((8, 10), (8, 6), (2, 2))

                part3 = V.make_part(V.other_device, 2, user_x=25 / 8, user_y=1, width=2, height=2)
                assert part3.bounds == ((25, 27), (8, 6), (2, 2))

                c = Canvas()
                info["canvas"] = c
                c.add_parts(part1, part2, part3)
                msgs = list(c.msgs(layer, onto=on))

                assert len(msgs) == 3
                assert all(m | TileMessages.Set64 for m in msgs)

                assert part1.points == [(0, 0), (1, 0), (0, -1), (1, -1)]
                assert_colors(msgs[0].colors, None, 0, None, 1)

                assert part2.points == [(8, 8), (9, 8), (8, 7), (9, 7)]
                assert_colors(msgs[1].colors, None, 72, None, 63)

                assert part3.points == [(25, 8), (26, 8), (25, 7), (26, 7)]
                assert_colors(msgs[2].colors, 200, None, 175, None)

            assert onto == {
                **{(0, 0): None, (1, 0): (0, 1, 1, 3500), (0, -1): None, (1, -1): (1, 1, 1, 3500)},
                **{(8, 8): None, (9, 8): (72, 1, 1, 3500), (8, 7): None, (9, 7): (63, 1, 1, 3500)},
                **{
                    (25, 8): (200, 1, 1, 3500),
                    (26, 8): None,
                    (25, 7): (175, 1, 1, 3500),
                    (26, 7): None,
                },
            }
