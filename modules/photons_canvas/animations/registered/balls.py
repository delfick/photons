from photons_canvas.animations import Animation, an_animation, options
from photons_canvas import point_helpers as php

from delfick_project.norms import dictobj, sb
import random
import uuid
import enum


class Direction(enum.Enum):
    LEFT = ("left", -1)
    RIGHT = ("right", 1)
    DOWN = ("down", -1)
    UP = ("up", 1)

    @classmethod
    def opposite(kls, direction):
        if direction is kls.LEFT:
            return kls.RIGHT
        elif direction is kls.RIGHT:
            return kls.LEFT
        elif direction is kls.UP:
            return kls.DOWN
        else:
            return kls.UP


class Options(dictobj.Spec):
    rate = dictobj.Field(options.range_spec((0.9, 1.3), rate=True))
    ball_colors = dictobj.Field(options.color_range_spec("rainbow"))

    num_balls = dictobj.Field(sb.integer_spec, default=5)
    fade_amount = dictobj.Field(sb.float_spec, default=0.02)


class Boundary:
    def __init__(self):
        self.points = set()
        self.points_list = []

        self.attempts = {}
        for hor, ver in (
            (Direction.LEFT, Direction.UP),
            (Direction.LEFT, Direction.DOWN),
            (Direction.RIGHT, Direction.UP),
            (Direction.RIGHT, Direction.DOWN),
        ):
            ohor, over = Direction.opposite(hor), Direction.opposite(ver)
            want = ((hor, ver), (ohor, ver), (hor, over), (hor, over))
            self.attempts[(hor, ver)] = list(enumerate(want))

    def set_points(self, parts):
        for part in parts:
            for point in part.points:
                self.points.add(point)
        self.points_list = list(self.points)

    def random_point(self):
        if not self.points_list:
            return (0, 0)
        return random.choice(self.points_list)

    def move(self, ball, extra_col, extra_row):
        for i, (hor, ver) in self.attempts[(ball.hor_direction, ball.ver_direction)]:
            point, points = ball.points(extra_col, extra_row, hor, ver)
            outsides = tuple([i for i, point in enumerate(points) if point not in self.points])

            if not outsides or i == 3:
                return point, hor, ver, points


class Ball:
    def __init__(self, boundary, color, rate_col, rate_row):
        self.color = color
        self.boundary = boundary
        self.rate_col = abs(rate_col)
        self.rate_row = abs(rate_row)

        self.hor_direction = Direction.LEFT if rate_row < 0 else Direction.RIGHT
        self.ver_direction = Direction.DOWN if rate_col < 0 else Direction.UP

        self.point = self.boundary.random_point()
        self.identity = str(uuid.uuid1())

    def __hash__(self):
        return hash(self.identity)

    def __eq__(self, other):
        return self.identity == other.identity

    def points(self, extra_col, extra_row, hor_direction, ver_direction):
        d_col = self.rate_col * hor_direction.value[1]
        d_row = self.rate_row * ver_direction.value[1]

        ocol = self.point[0] + d_col + extra_col
        orow = self.point[1] + d_row + extra_row

        col = int(ocol)
        row = int(orow)

        points = [
            (col, row),
            (col + 1, row),
            (col, row - 1),
            (col + 1, row - 1),
        ]

        return (ocol, orow), points

    @property
    def move(self):
        extra_col = random.randrange(0, 5) / 10
        extra_row = random.randrange(0, 5) / 10
        self.point, self.hor_direction, self.ver_direction, points = self.boundary.move(
            self, extra_col, extra_row
        )
        return points


class TileBallsState:
    def __init__(self, options):
        self.options = options
        self.i = 0

        self.balls = []
        self.by_point = {}
        self.boundary = Boundary()

    def set_points(self, parts):
        self.boundary.set_points(parts)

    def make_ball(self):
        rate_col, rate_row = self.options.rate(), self.options.rate()

        if random.randrange(0, 100) < 50:
            rate_col *= -1
        if random.randrange(0, 100) < 50:
            rate_row *= -1

        return Ball(self.boundary, self.options.ball_colors.color, rate_col, rate_row)

    @property
    def next_layer(self):
        need = self.options.num_balls - len(self.balls)
        if need > 0:
            self.balls.extend([self.make_ball() for _ in range(need)])

        by_point = self.by_point
        by_point.clear()
        collided = set()

        for ball in self.balls:
            points = ball.move
            if not any(point in self.boundary.points for point in points):
                collided.add(ball)
                continue

            for point in points:
                if point in by_point:
                    by_point[point] = php.Color.WHITE
                    collided.add(ball)
                else:
                    by_point[point] = ball.color

        self.balls = [ball for ball in self.balls if ball not in collided]

        def layer(point, canvas):
            color = by_point.get(point)
            if color:
                return color

            return canvas.dim(point, self.options.fade_amount)

        return layer


@an_animation("balls", Options)
class TileBallsAnimation(Animation):
    """
    The balls are trapped in your tiles and they will just keep bouncing around
    until the animation ends. When one balls hits another, one of them will
    win this battle and keep going, while the other stops and respawns
    elsewhere.

    Options are:

    rate - :range: - between 0.9 and 1.3
        The number of pixels to progress each tick. A lower number makes for
        a slower ball

    ball_colors - :color_range: - default rainbow
        The color to choose each time a ball is spawned.

    num_balls - integer - default 5
        The number of balls that can be in play at any particular time.

    fade_amount - float - default 0.02
        The amount the brightness changes on the tail of the ball per tick.
        A smaller number makes for a bigger trail behind the ball.
    """

    async def process_event(self, event):
        if event.state is None:
            event.state = TileBallsState(self.options)

        if event.is_new_device:
            event.state.set_points(event.value)

        if event.is_tick:
            return event.state.next_layer
