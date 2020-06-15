from photons_app.errors import PhotonsAppError


class BadConversion(PhotonsAppError):
    desc = "Bad conversion"


class InvalidField(PhotonsAppError):
    desc = "Field is invalid"


class Conflict(PhotonsAppError):
    desc = "Conflicting field"
