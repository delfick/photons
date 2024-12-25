
from unittest import mock

from photons_canvas.orientation import Orientation
from photons_canvas.points import containers as cont
from photons_canvas.points.simple_messages import Set64
from photons_messages import LightMessages, TileMessages
from photons_messages.fields import Color
from photons_products import Products

class TestPart:
    def test_it_takes_in_some_properties(self, V):
        user_x = 2
        user_y = 3
        width = 5
        height = 10
        part_number = 5
        orientation = Orientation.RightSideUp

        real_part = mock.Mock(name="real_part", spec=[])
        original_colors = V.original_colors

        part = cont.Part(
            user_x,
            user_y,
            width,
            height,
            part_number,
            orientation,
            V.device,
            real_part=real_part,
            original_colors=original_colors,
        )

        assert part.device is V.device
        assert part.colors is not original_colors
        assert part.colors == original_colors
        assert part.real_part is real_part
        assert part.original_colors is original_colors
        assert part.orientation is orientation
        assert part.part_number == part_number
        assert part.random_orientation in Orientation.__members__.values()

        assert part.user_x == user_x
        assert part.user_y == user_y
        assert part.width == width
        assert part.height == height

        assert part.left == (2 * 8)
        assert part.right == (2 * 8) + 5

        assert part.top == 3 * 8
        assert part.bottom == (3 * 8) - 10

        part._set_64.update({"source": 0, "sequence": 1})
        real_set_64 = TileMessages.Set64(
            x=0,
            y=0,
            length=1,
            tile_index=5,
            colors=[],
            duration=0,
            ack_required=False,
            width=5,
            res_required=False,
            target=V.device.serial,
            source=0,
            sequence=1,
        )
        assert part._set_64.pack()[36 * 8 :] == real_set_64.payload.pack()

    def test_it_can_be_used_as_a_key_in_dictionary(self, V):
        dct = {V.part: 1}
        assert dct[V.part] == 1
        assert dct[(V.device, V.part.part_number)] == 1
        assert dct[(V.device.serial, V.part.part_number)] == 1

    def test_it_can_be_compared_for_equality(self, V):
        same = V.make_part(V.device, 5)
        different_part = V.make_part(V.device, 1)
        different_device = V.make_part(V.other_device, 1)

        assert V.part == same
        assert V.part != different_part
        assert V.part != different_device

        assert V.part == mock.Mock(
            name="a part", device=V.device, part_number=5, spec=["device", "part_number"]
        )
        assert V.part != mock.Mock(
            name="a part", device=V.device, part_number=1, spec=["device", "part_number"]
        )
        assert V.part != mock.Mock(
            name="a part", device=V.other_device, part_number=5, spec=["device", "part_number"]
        )

        assert V.part == (V.device, 5)
        assert V.part == (V.device.serial, 5)

        assert V.part != (V.other_device, 5)
        assert V.part != (V.other_device.serial, 5)

    def test_it_can_be_ordered(self, V):

        parts = [
            V.make_part(V.device, 2),
            V.make_part(V.device, 1),
            V.make_part(V.other_device, 3),
            V.make_part(V.device, 3),
            V.make_part(V.other_device, 5),
            V.make_part(V.device, 4),
        ]
        sorted_parts = sorted(parts)

        assert sorted_parts == [parts[1], parts[0], parts[3], parts[5], parts[2], parts[4]]

    def test_it_has_a_repr(self, V):
        assert repr(V.part) == "<Part (d073d5001337,5)>"
        assert repr(V.make_part(V.other_device, 5)) == "<Part (d073d5006677,5)>"

    def test_it_can_get_original_colors(self, V):
        assert V.part.original_colors == V.original_colors

    def test_it_can_set_original_colors(self, V):
        other_colors = [(0, 1, 1, 1) for _ in range(64)]
        assert V.part.original_colors != other_colors
        V.part.original_colors = other_colors
        assert V.part.colors == V.original_colors
        assert V.part.original_colors == other_colors

        more_colors = [(1, 1, 1, 1) for _ in range(64)]
        V.part.colors = None
        V.part.original_colors = more_colors
        assert V.part.colors == more_colors
        assert V.part.original_colors == more_colors

    def test_it_can_clone_the_real_part(self, V):
        part_colors = [(1, 1, 1, 1) for _ in range(64)]
        real_part_original_colors = [(0, 1, 1, 1) for _ in range(64)]

        real_part = V.make_part(
            V.device,
            1,
            user_x=0,
            user_y=0,
            width=8,
            height=8,
            original_colors=real_part_original_colors,
        )
        part = V.make_part(
            V.device,
            1,
            user_x=1,
            user_y=1,
            width=8,
            height=8,
            colors=part_colors,
            real_part=real_part,
            original_colors=real_part_original_colors,
        )

        clone = part.clone_real_part()

        assert clone.device is V.device
        assert clone.user_x == 0
        assert clone.user_y == 0
        assert clone.width == 8
        assert clone.height == 8
        assert clone.colors == part_colors
        assert clone.real_part is real_part.real_part
        assert clone.original_colors == real_part_original_colors

    def test_it_can_clone(self, V):
        colors = [(0, 1, 1, 1) for _ in range(64)]

        part = V.make_part(
            V.device,
            0,
            user_x=2,
            user_y=3,
            width=4,
            height=5,
            real_part=V.real_part,
            colors=colors,
            original_colors=V.original_colors,
        )

        def assert_clone(**kwargs):
            clone = part.clone(**kwargs)

            properties = (
                "device",
                "part_number",
                "user_x",
                "user_y",
                "width",
                "height",
                "colors",
                "original_colors",
            )
            assert all(p in properties for p in kwargs)

            assert clone is not part
            for prop in properties:
                assert getattr(clone, prop) == kwargs.get(prop, getattr(part, prop))

            assert getattr(clone, "real_part") is kwargs.get("real_part", part.real_part)

        assert_clone()
        assert_clone(user_x=20)
        assert_clone(user_x=21, user_y=30)
        assert_clone(user_x=21, user_y=30, width=40)
        assert_clone(user_x=21, user_y=30, width=40, height=50)

    def test_it_can_update_position(self, V):
        part = V.make_part(V.device, 1, user_x=2, user_y=3, width=4, height=5)
        assert part.bounds == ((16, 20), (24, 19), (4, 5))

        part.update(5, 6, 7, 8)
        assert part.bounds == ((40, 47), (48, 40), (7, 8))

    def test_it_returns_bounds_information(self, V):
        part = V.make_part(V.device, 1, user_x=2, user_y=3, width=6, height=7)
        assert part.left == 16
        assert part.right == 22
        assert part.top == 24
        assert part.bottom == 17
        assert part.width == 6
        assert part.height == 7
        assert part.bounds == ((16, 22), (24, 17), (6, 7))

    def test_it_can_get_all_points(self, V):
        part = V.make_part(V.device, 1, user_x=2, user_y=3, width=6, height=7)
        assert part.bounds == ((16, 22), (24, 17), (6, 7))
        assert part.points == [
            *[(16, 24), (17, 24), (18, 24), (19, 24), (20, 24), (21, 24)],
            *[(16, 23), (17, 23), (18, 23), (19, 23), (20, 23), (21, 23)],
            *[(16, 22), (17, 22), (18, 22), (19, 22), (20, 22), (21, 22)],
            *[(16, 21), (17, 21), (18, 21), (19, 21), (20, 21), (21, 21)],
            *[(16, 20), (17, 20), (18, 20), (19, 20), (20, 20), (21, 20)],
            *[(16, 19), (17, 19), (18, 19), (19, 19), (20, 19), (21, 19)],
            *[(16, 18), (17, 18), (18, 18), (19, 18), (20, 18), (21, 18)],
        ]

    def test_it_can_reverse_orient(self, V):
        ret_colors = mock.Mock(name="ret_colors", spec=[])
        reorient = mock.Mock(name="reorient", return_value=ret_colors)

        colors = mock.Mock(name="colors", spec=[])
        part = V.make_part(V.device, 0, orientation=Orientation.RotatedLeft)

        with mock.patch("photons_canvas.points.containers.reorient", reorient):
            assert part.reverse_orient(colors) is ret_colors

        reorient.assert_called_once_with(colors, Orientation.RotatedRight)

    def test_it_can_orient(self, V):
        ret_colors = mock.Mock(name="ret_colors", spec=[])
        reorient = mock.Mock(name="reorient", return_value=ret_colors)

        colors = mock.Mock(name="colors", spec=[])
        part = V.make_part(V.device, 0, orientation=Orientation.RotatedLeft)

        with mock.patch("photons_canvas.points.containers.reorient", reorient):
            assert part.reorient(colors) is ret_colors

        reorient.assert_called_once_with(colors, Orientation.RotatedLeft)

    def test_it_can_orient_with_random_orientation(self, V):
        ret_colors = mock.Mock(name="ret_colors", spec=[])
        reorient = mock.Mock(name="reorient", return_value=ret_colors)

        colors = mock.Mock(name="colors", spec=[])

        i = 0
        part = None
        while i < 10:
            part = V.make_part(V.device, 0, orientation=Orientation.RotatedLeft)
            if part.random_orientation is not part.orientation:
                break
            i += 1

        assert part.random_orientation is not part.orientation

        with mock.patch("photons_canvas.points.containers.reorient", reorient):
            assert part.reorient(colors, randomize=True) is ret_colors

        reorient.assert_called_once_with(colors, part.random_orientation)

    class TestMsgs:
        def test_it_returns_a_SetColor_for_bulbs(self, V):
            device = cont.Device("d073d5001337", Products.LCM2_A19.cap)
            part = V.make_part(device, 0, user_x=2, user_y=2, width=1, height=1)

            colors = [(100, 1, 0.4, 2400)]
            msgs = list(part.msgs(colors, duration=100))
            assert len(msgs) == 1
            assert msgs[0] | LightMessages.SetColor
            assert (
                msgs[0].payload
                == LightMessages.SetColor(
                    hue=100, saturation=1, brightness=0.4, kelvin=2400, duration=100
                ).payload
            )

        def test_it_returns_multizone_messages_for_strips(self, V):
            colors = mock.Mock(name="colors", spec=[])
            duration = mock.Mock(name="duration", spec=[])

            lcm2_cap = Products.LCM2_Z.cap(2, 80)
            assert lcm2_cap.has_extended_multizone

            m1 = mock.Mock(name="m1")
            m2 = mock.Mock(name="m2")

            maker = mock.Mock(name="maker", spec=["msgs"], msgs=[m1, m2])
            FakeMultizoneMessagesMaker = mock.Mock(name="message maker", return_value=maker)

            with mock.patch(
                "photons_canvas.points.containers.MultizoneMessagesMaker",
                FakeMultizoneMessagesMaker,
            ):
                for cap in (lcm2_cap, Products.LCM1_Z.cap):
                    device = cont.Device("d073d5001337", cap)
                    part = V.make_part(device, 0, user_x=2, user_y=3, width=20, height=1)

                    assert list(part.msgs(colors, duration=duration)) == [m1, m2]

                    FakeMultizoneMessagesMaker.assert_called_once_with(
                        device.serial, cap, colors, duration=duration
                    )
                    FakeMultizoneMessagesMaker.reset_mock()

        def test_it_returns_special_Set64_message_for_a_tile(self, V):
            colors = [(i, 1, 1, 3500) for i in range(64)]

            device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)
            part = V.make_part(
                device,
                3,
                user_x=2,
                user_y=3,
                width=8,
                height=8,
                orientation=Orientation.RotatedLeft,
            )

            rotated = part.reorient(colors)
            assert rotated != colors

            msgs = list(part.msgs(colors, duration=200))
            assert len(msgs) == 1
            assert msgs[0] | TileMessages.Set64
            assert msgs[0].serial == device.serial

            dct = {
                "x": 0,
                "y": 0,
                "length": 1,
                "tile_index": 3,
                "colors": rotated,
                "ack_required": False,
                "width": 8,
                "duration": 200,
                "res_required": False,
            }

            for k, v in dct.items():
                if k == "colors":
                    v = [Color(*c) for c in rotated]
                assert getattr(msgs[0], k) == v

            assert isinstance(msgs[0], Set64)

        class TestCaching:
            def test_it_it_sends_same_messages_or_NO_MESSAGES_depending_on_time_and_difference(self, FakeTime, V):
                colors = [(i, 1, 1, 3500) for i in range(64)]
                device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)

                with FakeTime() as t:
                    t.set(2)
                    part = V.make_part(
                        device, 3, orientation=Orientation.RotatedLeft, original_colors=colors
                    )
                    assert part.next_force_send == 1

                    msgs = part.msgs(colors, force=False)
                    assert part.last_msgs is msgs
                    assert len(msgs) == 1
                    assert msgs[0] | TileMessages.Set64
                    assert part.next_force_send == 2.5
                    assert part.colors == colors

                    t.set(1.2)
                    msgs2 = part.msgs(colors, force=False)
                    assert msgs2 is cont.NO_MESSAGES
                    assert part.last_msgs is msgs
                    assert msgs[0] | TileMessages.Set64
                    assert part.next_force_send == 2.5
                    assert part.colors == colors

                    t.set(3)
                    msgs3 = part.msgs(colors, force=False)
                    assert msgs3 is not msgs2 and msgs3 is msgs

                    assert len(msgs) == 1
                    assert msgs[0] | TileMessages.Set64
                    assert part.last_msgs is msgs3
                    assert part.next_force_send == 3.5
                    assert part.colors == colors

            def test_it_it_sends_different_messages_if_colors_are_different(self, FakeTime, V):
                colors = [(i, 1, 1, 3500) for i in range(64)]
                colors2 = [(1, 1, 1, 3500) for i in range(64)]
                device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)

                with FakeTime() as t:
                    t.set(2)
                    part = V.make_part(
                        device, 3, orientation=Orientation.RotatedLeft, original_colors=colors
                    )
                    assert part.next_force_send == 1

                    msgs = part.msgs(colors, force=False)
                    assert part.last_msgs is msgs
                    assert len(msgs) == 1
                    assert msgs[0] | TileMessages.Set64
                    assert part.next_force_send == 2.5
                    assert part.colors == colors

                    t.set(1.2)
                    msgs2 = part.msgs(colors2, force=False)
                    assert len(msgs) == 1
                    assert msgs[0] | TileMessages.Set64
                    assert part.last_msgs is msgs2
                    assert msgs[0] | TileMessages.Set64
                    assert part.next_force_send == 1.7
                    assert part.colors == colors2

                    t.set(3)
                    msgs3 = part.msgs(colors, force=False)
                    assert msgs3 is not msgs2 and msgs3 is not msgs
                    assert len(msgs) == 1
                    assert msgs[0] | TileMessages.Set64
                    assert part.last_msgs is msgs3
                    assert part.next_force_send == 3.5
                    assert part.colors == colors
