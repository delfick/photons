from photons_canvas.points.canvas import Canvas


class Separate:
    def rearrange(self, canvas):
        user_x = 0
        for part in canvas.parts:
            yield part.clone(user_x=user_x)
            user_x += part.width / 8


class Straight:
    def rearrange(self, canvas):
        user_x = 0
        for part in sorted(
            canvas.parts, key=lambda p: (p.real_part.user_x, p.device, p.part_number)
        ):
            yield part.clone(user_x=user_x, user_y=0)
            user_x += part.width / 8


class VerticalAlignment:
    def rearrange(self, canvas):
        for part in canvas.parts:
            yield part.clone(user_y=0)


def rearrange(canvas, rearranger, keep_colors=False):
    new = Canvas()

    parts = []

    for part in rearranger.rearrange(canvas):
        if keep_colors:
            parts.append((part, part.colors))
        else:
            parts.append(part)

    new.add_parts(*parts)
    return new
