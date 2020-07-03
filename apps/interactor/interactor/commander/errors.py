from interactor.errors import InteractorError


class NoSuchCommand(InteractorError):
    desc = "no such command"


class NoSuchPacket(InteractorError):
    desc = "no such packet"


class NoSuchScene(InteractorError):
    desc = "no such scene"


class InvalidArgs(InteractorError):
    desc = "Invalid arguments"


class NotAWebSocket(InteractorError):
    desc = "Request wasn't a websocket"
