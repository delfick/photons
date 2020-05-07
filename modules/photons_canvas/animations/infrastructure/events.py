import enum


class AnimationEvent:
    class Types(enum.Enum):
        TICK = "tick"
        ERROR = "error"
        ENDED = "ended"
        STARTED = "started"
        NEW_DEVICE = "new_device"
        USER_EVENT = "user_event"
        SENT_MESSAGES = "messages_sent"

    def __init__(self, typ, value, state):
        self._state = state

        self.typ = typ
        self.value = value
        self.canvas = state.canvas
        self.animation = state.animation
        self.prev_state = state.state
        self.background = state.background

    def __repr__(self):
        return f"<Event {self.typ.name}: {self.value}>"

    @property
    def state(self):
        return self.prev_state

    @state.setter
    def state(self, new_state):
        self.prev_state = new_state
        self._state.state = new_state

    @property
    def is_tick(self):
        return self.typ is self.Types.TICK

    @property
    def is_error(self):
        return self.typ is self.Types.ERROR

    @property
    def is_end(self):
        return self.typ is self.Types.ENDED

    @property
    def is_start(self):
        return self.typ is self.Types.STARTED

    @property
    def is_user_event(self):
        return self.typ is self.Types.USER_EVENT

    @property
    def is_new_device(self):
        return self.typ is self.Types.NEW_DEVICE

    @property
    def is_sent_messages(self):
        return self.typ is self.Types.SENT_MESSAGES
