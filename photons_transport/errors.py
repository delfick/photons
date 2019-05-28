from photons_app.errors import PhotonsAppError, TimedOut

class FailedToFindDevice(PhotonsAppError):
    desc = "Couldn't find a device"

class NoDesiredService(PhotonsAppError):
    desc = "Device is not providing the desired service"

class CouldntMakeConnection(PhotonsAppError):
    pass
