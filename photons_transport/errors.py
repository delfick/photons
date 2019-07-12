from photons_app.errors import PhotonsAppError

class FailedToFindDevice(PhotonsAppError):
    desc = "Couldn't find a device"

class NoDesiredService(PhotonsAppError):
    desc = "Device is not providing the desired service"

class CouldntMakeConnection(PhotonsAppError):
    pass

class InvalidBroadcast(PhotonsAppError):
    desc = "Provided broadcast is invalid"

class UnknownService(PhotonsAppError):
    pass
