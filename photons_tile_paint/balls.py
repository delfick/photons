from photons_tile_paint.options import AnimationOptions, split_by_comma, hue_range_spec, HueRange, normalise_speed_options
from photons_tile_paint.animation import Animation, Finish
from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
from collections import defaultdict
import random
import math

class TileBallsOptions(AnimationOptions):
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)
    random_orientations = dictobj.Field(sb.boolean, default=False)

    ball_hues = dictobj.NullableField(split_by_comma(hue_range_spec()), default=[])
    num_balls = dictobj.Field(sb.integer_spec, default=5)
    fade_amount = dictobj.Field(sb.float_spec, default=0.02)

    min_speed = dictobj.Field(sb.float_spec, default=0.6)
    max_speed = dictobj.Field(sb.float_spec, default=0.8)

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration

class Boundary:
    def __init__(self, coords):
        self.left = coords[0][0][0]
        self.right = coords[0][0][0]
        self.top = coords[0][0][1]
        self.bottom = coords[0][0][1]

        for (left, top), (width, height) in coords:
            self.left = min(left, self.left)
            self.right = max(left + width, self.right)
            self.bottom = min(top - height, self.bottom)
            self.top = max(top, self.top)

    def random_coord(self):
        left = random.randrange(self.left, self.right)
        top = random.randrange(self.bottom, self.top)
        return left, top

class Ball:
    def __init__(self, boundary, hue, rate_x, rate_y):
        self.hue = hue
        self.boundary = boundary

        self.x, self.y = self.boundary.random_coord()
        self.dx = rate_x
        self.dy = rate_y
        self.extrax = 0
        self.extray = 0
        self.maybe_alter_course()

    def maybe_alter_course(self):
        changed = False

        if self.top >= self.boundary.top and self.dy > 0:
            self.dy *= -1
            changed = True

        if self.bottom <= self.boundary.bottom and self.dy < 0:
            self.dy *= -1
            changed = True

        if self.right >= self.boundary.right and self.dx > 0:
            self.dx *= -1
            changed = True

        if self.left <= self.boundary.left and self.dx < 0:
            self.dx *= -1
            changed = True

        if changed:
            self.extra_x = random.randrange(0, 5) / 10
            self.extra_y = random.randrange(0, 5) / 10

    @property
    def top(self):
        return self.y

    @property
    def bottom(self):
        return self.y - 1

    @property
    def right(self):
        return self.x + 1

    @property
    def left(self):
        return self.x

    def progress(self):
        self.x += self.dx + self.extrax
        self.y += self.dy + self.extray
        self.maybe_alter_course()

    def pixels(self):
        pixels = [
              (self.x, self.y)
            , (self.x, self.y - 1)
            , (self.x + 1, self.y)
            , (self.x + 1, self.y - 1)
            ]

        for x, y in pixels:
            yield (math.floor(x), math.floor(y)), Color(self.hue, 1, 1, 3500)

class TileBallsState:
    def __init__(self, coords, options):
        self.options = options
        self.boundary = Boundary(coords)
        self.balls = []
        self.ensure_enough_balls()
        self.canvas = Canvas()

    def ensure_enough_balls(self):
        need = self.options.num_balls - len(self.balls)
        if need > 0:
            self.balls.extend([self.make_ball() for _ in range(need)])

    def make_ball(self):
        if self.options.min_speed == self.options.max_speed:
            rate_x = self.options.min_speed
            rate_y = self.options.max_speed
        else:
            mn = int(self.options.min_speed * 100)
            mx = int(self.options.max_speed * 100)
            rate_x = random.randint(mn, mx) / 100
            rate_y = random.randint(mn, mx) / 100

        if random.randrange(0, 100) < 50:
            rate_x *= -1
        if random.randrange(0, 100) < 50:
            rate_y *= -1

        ball_hue = random.choice(self.options.ball_hues)
        return Ball(self.boundary, ball_hue.make_hue(), rate_x, rate_y)

    def tick(self):
        for ball in self.balls:
            ball.progress()
        return self

    def make_canvas(self):
        for point, pixel in list(self.canvas):
            pixel.brightness -= self.options.fade_amount
            if pixel.brightness < 0:
                del self.canvas[point]

        pixels = defaultdict(list)
        for ball in self.balls:
            for point, pixel in ball.pixels():
                pixels[point].append(ball)
                self.canvas[point] = pixel

        collided_balls = []
        for balls in pixels.values():
            if len(balls) > 1:
                collided_balls.extend(balls)
                for ball in balls:
                    for point, _ in ball.pixels():
                        self.canvas[point] = Color(0, 0, 1, 3500)

        self.balls = [b for b in self.balls if b not in collided_balls]
        self.ensure_enough_balls()
        return self.canvas

class TileBallsAnimation(Animation):
    def setup(self):
        self.iteration = 0
        if self.options.random_orientations:
            self.random_orientations = True
        normalise_speed_options(self.options)
        if not self.options.ball_hues:
            self.options.ball_hues = [HueRange(0, 360)]

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return TileBallsState(coords, self.options)

        self.iteration += 1
        if self.options.final_iteration(self.iteration):
            raise Finish("Reached max iterations")

        return prev_state.tick()

    def make_canvas(self, state, coords):
        return state.make_canvas()
