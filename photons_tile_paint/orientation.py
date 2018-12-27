from enum import Enum

class Orientation(Enum):
    """
    The different available orientations
    """
    RightSideUp = 1
    UpsideDown = 2
    RotatedLeft = 3
    RotatedRight = 4
    FaceUp = 5
    FaceDown = 6

def reorient(colors, orientation):
    """
    Return the colors in the different order given our orientation
    """
    if orientation in (Orientation.RightSideUp, Orientation.FaceUp, Orientation.FaceDown):
        return colors

    final = []
    for i, v in enumerate(colors):
        final.append((rotated_index(i, orientation), v))
    return [v for _, v in sorted(final)]

def rotated_index(i, orientation):
    """
    Give new index for i given our orientation
    """
    x = i % 8
    y = i // 8

    if orientation is Orientation.UpsideDown:
        x, y = 7 - x, 7 - y
    elif orientation is Orientation.RotatedLeft:
        x, y = 7 - y, x
    elif orientation is orientation.RotatedRight:
        x, y = y, 7 - x

    return x + (y * 8)

def nearest_orientation(x, y, z):
    """
    Determine which orientation maps to the provided x, y, z
    """
    absX = abs(x)
    absY = abs(y)
    absZ = abs(z)

    if x == -1 and y == -1 and z == -1:
        # Invalid data, assume right-side up.
        return Orientation.RightSideUp

    elif absX > absY and absX > absZ:
        if x > 0:
            return Orientation.RotatedRight
        else:
            return Orientation.RotatedLeft

    elif absZ > absX and absZ > absY:
        if z > 0:
            return Orientation.FaceDown
        else:
            return Orientation.FaceUp

    else:
        if y > 0:
            return Orientation.UpsideDown
        else:
            return Orientation.RightSideUp

def reverse_orientation(o):
    """
    Return the reverse orientation

    Useful for mapping current colours into RightSideUp
    """
    if o is Orientation.RotatedLeft:
        return Orientation.RotatedRight
    elif o is Orientation.RotatedRight:
        return Orientation.RotatedLeft
    else:
        return o
