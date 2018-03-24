def user_coords_to_pixel_coords(coords_and_sizes):
    """
    Translation between user_coords_and_sizes to based on pixels.

    The user coords are what is stored on the tiles themselves
    ``[(user_x, user_y), (width, height)]``
    where user_x and user_y are the center of the tile in terms of tile
    and width and height are in terms of pixels.

    We return from this function
    ``[(user_x, user_y), (width, height)]``
    where width and height are unchanged
    and user_x and user_y are the top left of the tile in terms of pixels
    """
    return [
          ((int((x * w) - (w * 0.5)), int((y * h) + (h * 0.5))), (w, h))
          for (x, y), (w, h) in coords_and_sizes
        ]
