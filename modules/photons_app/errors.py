"""
Photons makes heavy use of
`delfick errors <https://delfick-project.readthedocs.io/en/latest/api/errors.html>`_
and so should you!

Just base your error classes on ``PhotonsAppError``:

.. code-block:: python

    from photons_app.errors import PhotonsAppError

    class MyAmazingError(PhotonsAppError):
        desc = "Something terrible has happened"

    raise MyAmazingError("The world exploded", info_one=1, info_two=2)

The `app <https://delfick-project.readthedocs.io/en/latest/api/app.html>`_
integration will catch these errors and display them relatively nicely.
"""
from delfick_project.errors import DelfickError, ProgrammerError, UserQuit
from delfick_project.option_merge import BadOptionFormat
from delfick_project.norms import BadSpec, BadSpecValue


class PhotonsAppError(DelfickError):
    pass


# Explicitly make these errors in this context
BadSpec = BadSpec
UserQuit = UserQuit
BadSpecValue = BadSpecValue
BadOptionFormat = BadOptionFormat
ProgrammerError = ProgrammerError


class ApplicationCancelled(PhotonsAppError):
    desc = "The application itself was cancelled"


class ApplicationStopped(PhotonsAppError):
    desc = "The application itself was stopped"


class BadConfiguration(PhotonsAppError):
    desc = "Bad configuration"


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
