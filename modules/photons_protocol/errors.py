from delfick_project.errors import DelfickError, ProgrammerError
from delfick_project.norms import BadSpec, BadSpecValue


class PhotonsProtocolError(DelfickError):
    pass


# Explicitly make these errors in this context
BadSpec = BadSpec
BadSpecValue = BadSpecValue
ProgrammerError = ProgrammerError


class BadConversion(PhotonsProtocolError):
    desc = "Bad conversion"
