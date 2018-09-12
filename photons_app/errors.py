"""
Photons makes heavy use of `delfick errors <https://delfick-error.readthedocs.io>`_
and so should you!

Just base your error classes on ``PhotonsAppError``:

.. code-block:: python

    from photons_app.errors import PhotonsAppError

    class MyAmazingError(PhotonsAppError):
        desc = "Something terrible has happened"

    raise MyAmazingError("The world exploded", info_one=1, info_two=2)

The `delfick_app <https://delfick-app.readthedocs.io>`_ integration will catch
these errors and display them relatively nicely.
"""
from delfick_error import DelfickError, ProgrammerError, UserQuit
from input_algorithms.errors import BadSpec, BadSpecValue

class PhotonsAppError(DelfickError):
    pass

# Explicitly make these errors in this context
BadSpec = BadSpec
UserQuit = UserQuit
BadSpecValue = BadSpecValue
ProgrammerError = ProgrammerError

class ApplicationCancelled(PhotonsAppError):
    desc = "The application itself was shutdown"

class BadConfiguration(PhotonsAppError):
    desc = "Bad configuration"

class BadOptionFormat(PhotonsAppError):
    desc = "Bad option format"

class BadTask(PhotonsAppError):
    desc = "Bad task"

class BadTarget(PhotonsAppError):
    desc = "Bad target"

class BadOption(PhotonsAppError):
    desc = "Bad Option"

class NoSuchKey(PhotonsAppError):
    desc = "Couldn't find key"

class BadYaml(PhotonsAppError):
    desc = "Invalid yaml file"

class TargetNotFound(PhotonsAppError):
    desc = "Unknown target"

class TimedOut(PhotonsAppError):
    desc = "Timed out"

class BadRun(PhotonsAppError):
    desc = "Bad Run"

class BadRunWithResults(BadRun):
    pass

class RunErrors(BadRun):
    pass

class KilledConnection(PhotonsAppError):
    desc = "The connection was killed"

class BadConnection(PhotonsAppError):
    desc = "Connection deemed invalid"

class FoundNoDevices(TimedOut):
    desc = "Didn't find any devices"

class ResolverNotFound(PhotonsAppError):
    desc = "Unknown resolver"

class DevicesNotFound(PhotonsAppError):
    desc = "Failed to find some devices"
