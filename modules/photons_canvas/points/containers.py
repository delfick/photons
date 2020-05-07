from photons_canvas.orientation import Orientation, reorient, reverse_orientation
from photons_canvas.points.simple_messages import Set64, MultizoneMessagesMaker
from photons_canvas.points import helpers as php

from photons_messages import LightMessages

import itertools
import random
import time

NO_MESSAGES = ()


class Part:
    def __init__(
        self,
        user_x,
        user_y,
        width,
        height,
        part_number,
        orientation,
        device,
        colors=None,
        real_part=None,
        original_colors=None,
    ):
        self.colors = colors
        self.device = device
        self.orientation = orientation
        self.part_number = part_number
        self.original_colors = original_colors
        self.random_orientation = random.choice(list(Orientation.__members__.values()))

        self.update(user_x, user_y, width, height)

        self._key = (self.device, self.part_number)
        self._hash = hash(self._key)

        self.last_msgs = []

        self._set_64 = Set64(
            x=0,
            y=0,
            length=1,
            tile_index=self.part_number,
            colors=[],
            duration=0,
            ack_required=False,
            width=self.width,
            res_required=False,
            target=self.device.serial,
        )

        real_part = self.clone() if real_part is None else real_part
        self.real_part = real_part
        self.next_force_send = time.time() - 1

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if isinstance(other, tuple) and other == self._key:
            return True

        if not any(hasattr(other, k) for k in ("device", "part_number")):
            return False

        return self.device == other.device and self.part_number == other.part_number

    def __lt__(self, other):
        if isinstance(other, tuple):
            return self._key < other
        else:
            return self._key < other._key

    def __repr__(self):
        return f"<Part ({self.device.serial},{self.part_number})>"

    @property
    def original_colors(self):
        return self._original_colors

    @original_colors.setter
    def original_colors(self, value):
        self._original_colors = value
        if value is not None and self.colors is None:
            self.colors = list(value)

    def clone_real_part(self):
        return self.real_part.clone(real_part=self.real_part, frm=self)

    def clone(
        self, *, user_x=None, user_y=None, width=None, height=None, real_part=False, frm=None
    ):
        if frm is None:
            frm = self

        ux = self.user_x if user_x is None else user_x
        uy = self.user_y if user_y is None else user_y
        w = self.width if width is None else width
        h = self.height if height is None else height

        l = lambda ss: ss if ss is None else list(ss)

        return Part(
            ux,
            uy,
            w,
            h,
            self.part_number,
            self.orientation,
            self.device,
            colors=l(getattr(frm, "colors")),
            real_part=real_part if not getattr(self, "real_part", False) else self.real_part,
            original_colors=l(getattr(frm, "original_colors")),
        )

    def update(self, user_x, user_y, width, height):
        self.width = width
        self.height = height
        self.user_x = user_x
        self.user_y = user_y

        user_x_real = int(self.user_x * 8)
        user_y_real = int(self.user_y * 8)

        self.left = user_x_real
        self.right = user_x_real + self.width

        self.top = user_y_real
        self.bottom = user_y_real - self.height

    @property
    def bounds(self):
        return (self.left, self.right), (self.top, self.bottom), (self.width, self.height)

    @property
    def points(self):
        return php.Points.all_points(self.bounds)

    def reverse_orient(self, colors):
        o = reverse_orientation(self.orientation)
        return reorient(colors, o)

    def reorient(self, colors, *, randomize=False):
        o = self.orientation
        if randomize:
            o = self.random_orientation

        return reorient(colors, o)

    def msgs(self, colors, *, acks=False, duration=1, randomize=False, force=True):
        forced = False
        if time.time() > self.next_force_send:
            if self.colors is not None:
                diff = any(c1 != c2 for c1, c2 in itertools.zip_longest(colors, self.colors))
                if not diff:
                    diff = True
                    forced = True
            else:
                diff = True
                forced = True

        elif self.colors is None or force:
            diff = True
            forced = True

        else:
            diff = any(c1 != c2 for c1, c2 in itertools.zip_longest(colors, self.colors))

        self.colors = colors

        if diff or forced:
            self.next_force_send = time.time() + 0.5

        if not diff:
            return NO_MESSAGES

        if (diff and not forced) or not self.last_msgs:
            self.last_msgs = self._msgs(colors, acks=acks, duration=duration, randomize=randomize)

        return self.last_msgs

    def _msgs(self, colors, acks=False, duration=1, randomize=False):
        if self.device.cap.has_matrix:
            colors = [
                c if c is not None else None for c in self.reorient(colors, randomize=randomize)
            ]

            kwargs = {"colors": colors}
            if duration != 0:
                kwargs["duration"] = duration
            if acks:
                kwargs["acks"] = acks

            msg = self._set_64.clone()
            msg.update(kwargs)
            return (msg,)

        elif self.device.cap.has_multizone:
            return MultizoneMessagesMaker(
                self.device.serial, self.device.cap, colors, duration=duration
            ).msgs

        elif colors:
            if isinstance(colors[0], tuple):
                h, s, b, k = colors[0]
                info = {
                    "hue": h,
                    "saturation": s,
                    "brightness": b,
                    "kelvin": k,
                }
            else:
                info = colors[0].as_dict()

            info["duration"] = duration
            return (LightMessages.SetColor(target=self.device.serial, res_required=False, **info),)


class Device:
    def __init__(self, serial, cap):
        self.cap = cap
        self.serial = serial
        self._hash = hash(self.serial)

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if isinstance(other, str) and other == self.serial:
            return True

        if not hasattr(other, "serial"):
            return False

        return other.serial == self.serial

    def __lt__(self, other):
        if isinstance(other, str):
            return self.serial < other
        else:
            return self.serial < other.serial

    def __repr__(self):
        name = self.cap
        if hasattr(self.cap, "product"):
            name = self.cap.product.name
        return f"<Device ({self.serial},{name})>"
