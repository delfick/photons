from photons_app.errors import PhotonsAppError


class IncompleteProduct(PhotonsAppError):
    desc = "Product definition was incomplete"
