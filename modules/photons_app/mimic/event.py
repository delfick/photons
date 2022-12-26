import json
import logging
import re
import time
import traceback
from datetime import datetime
from unittest import mock

import dateutil.tz
from delfick_project.norms import BadSpecValue, sb
from photons_app.errors import ProgrammerError
from photons_messages import TileMessages
from photons_protocol.errors import PhotonsProtocolError
from photons_protocol.packets import dictobj, reprer


class ConsoleFormat:
    @classmethod
    def lines_from_error(kls, error):
        has_expand = False
        if hasattr(error, "expand"):
            has_expand = True
            yield from error.expand()

        kls_name = ""

        if hasattr(error, "as_dict"):
            kls_name = f"<{error.__class__.__name__}> "
            error = error.as_dict()
        elif not isinstance(error, dict):
            error = {"message": error}

        if "message" in error:
            mm = error.pop("message")
            if not has_expand:
                yield f"{kls_name}{mm}"

        if error:
            for k, v in sorted(error.items()):
                yield f"{k} = {v}"

    @classmethod
    def lines_from_packet(kls, pkt, show_set64_contents=False):
        def t(o):
            if o in (repr(sb.NotSpecified), sb.NotSpecified):
                return "<NOT_SPECIFIED>"
            elif isinstance(o, list):
                return [t(tt) for tt in o]
            elif isinstance(o, dict):
                return {k: t(v) for k, v in o.items()}
            else:
                return o

        if getattr(pkt, "represents_ack", False):
            yield f"Ack(source={t(pkt.source)},sequence={t(pkt.sequence)},target={pkt.serial})(empty)"

        else:
            parts = [
                f"ack={pkt.ack_required}",
                f"res={pkt.res_required}",
                f"source={t(pkt.source)}",
                f"sequence={t(pkt.sequence)}",
                f"target={pkt.serial}",
            ]
            header = f"{type(pkt).__name__}({','.join(parts)})"
            payload = json.loads(repr(pkt.payload))
            if not payload:
                yield f"{header}(empty)"
            else:
                yield header
                for name in pkt.payload.Meta.all_names:
                    if pkt | TileMessages.Set64 and not show_set64_contents and name == "colors":
                        continue
                    if name not in payload:
                        continue
                    val = payload[name]
                    if isinstance(val, list):

                        length = len(val)
                        length_name = f"{name}_count"
                        if length_name in payload:
                            length = payload[length_name]

                        yield f"  {name}:"
                        for v in val[:length]:
                            yield f"  {t(v)}"
                    else:
                        yield f"  {name}: {t(val)}"


class EventsHolder:
    class Stop(Exception):
        """Raised to prevent the event from proceeding"""

        def __init__(self, event=sb.NotSpecified):
            if event is sb.NotSpecified:
                raise ProgrammerError("Please use event.raise_stop() instead")
            self.event = event

    def __init__(self):
        self.events = {}

    def __getattr__(self, key):
        if key == "events":
            return object.__getattribute__(self, key)

        events = self.events
        if key in events:
            return events[key]

        return object.__getattribute__(self, key)

    def register(self, name):
        def decorator(kls):
            self.events[name] = kls
            return kls

        return decorator

    def name(self, kls):
        if not isinstance(kls, type):
            kls = kls.__class__

        for name, v in self.events.items():
            if v is kls:
                return name
        return kls.__name__


Events = EventsHolder()


class EventMeta(type):
    def __or__(self, other):
        return other == self

    def __repr__(self):
        for name, e in Events.events.items():
            if e is self:
                return f"<Events.{name}>"
        return super().__repr__()


class Event(metaclass=EventMeta):
    Stop = Events.Stop
    LOCAL_TZ = dateutil.tz.gettz()

    def __init__(self, device, *args, **kwargs):
        self.name = f"{device.serial}({device.cap.product.name}:{device.firmware.major},{device.firmware.minor}) {Events.name(self.__class__)}"
        self.device = device
        self.created = time.time()

        self.log_args = args
        self.log_kwargs = kwargs

        self.setup(*args, **kwargs)

    def raise_stop(self):
        raise self.Stop(self)

    def setup(self, *args, **kwargs):
        pass

    def __eq__(self, other):
        if other is None:
            return False

        if isinstance(other, type):
            return self | other

        if isinstance(other, tuple):
            if not other:
                raise ValueError("Can't compare against an empty tuple")

            if len(other) != 2 or not isinstance(other[0], type):
                raise ValueError(
                    f"Can only compare against against a tuple of (EventKls, device): ({other})"
                )

            return self | other[0] and other[1] is self.device

        return other | self.__class__ and other.device is self.device and self.has_same_args(other)

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}>"

    def has_same_args(self, other):
        return self.log_args == other.log_args and self.log_kwargs == other.log_kwargs

    def for_console(self, time=True, show_set64_contents=False):
        if time is True:
            time = (
                datetime.fromtimestamp(self.created)
                .astimezone(self.LOCAL_TZ)
                .strftime("%Y-%m-%d %H:%M:%S.%f%z")
            )
        else:
            time = "TIME"

        yield f"{time} -> {self.name}"
        for arg in self.log_args:
            if isinstance(arg, str):
                yield f"  -- {arg}"
            elif isinstance(arg, Exception):
                for line in ConsoleFormat.lines_from_error(arg):
                    yield f"  --> {line}"
            else:
                yield f"  -- {reprer(arg)}"

        for key, val in self.log_kwargs.items():
            if key == "changes" and isinstance(val, list):
                for item in val:
                    yield f"  ~ {reprer(item)}"
            elif key == "error":
                for line in ConsoleFormat.lines_from_error(val):
                    yield f"  >> {line}"
                if val.__traceback__:
                    for line in traceback.format_tb(val.__traceback__):
                        for part in line.split("\n"):
                            yield f"  | {part}"

            elif isinstance(val, dictobj.PacketSpec) or getattr(val, "represents_ack", False):
                lines = list(
                    ConsoleFormat.lines_from_packet(val, show_set64_contents=show_set64_contents)
                )
                if lines:
                    yield f"  || {key} = {lines.pop(0)}"
                    for line in lines:
                        yield f"  ^^ {line}"
            else:
                yield f"  :: {key} = {reprer(val)}"

    def __or__(self, compare):
        return isinstance(compare, type) and isinstance(self, compare)


class EventPktBtsMixin:
    def has_same_args(self, other):
        pkt_have = self.log_kwargs["packet"]
        pkt_other = other.log_kwargs["packet"]

        if pkt_other is not mock.ANY:

            if isinstance(pkt_other, type):
                if not pkt_have | pkt_other:
                    return False

            elif isinstance(pkt_other, tuple):
                kls, options = pkt_other
                if not pkt_have | kls:
                    return False
                pkt_other = kls.create(**options)

            if not isinstance(pkt_other, type):
                if not pkt_have | type(pkt_other):
                    return False

                kls = pkt_have.Payload
                clean_have = kls.create(pkt_have.payload.pack())
                clean_other = kls.create(pkt_other.payload.pack())

                if hasattr(pkt_have, "instanceid"):
                    clean_other.instanceid = pkt_have.instanceid

                if repr(clean_have) != repr(clean_other):
                    return False

        got = dict(self.log_kwargs)
        want = dict(other.log_kwargs)

        if "reason" in got and "reason" not in want:
            del got["reason"]

        got.pop("packet")
        want.pop("packet")

        if want["bts"] is None:
            got.pop("bts")
            want.pop("bts")
        if want["addr"] is None:
            got.pop("addr")
            want.pop("addr")

        return self.log_args == other.log_args and got == want

    @property
    def bts(self):
        if self._bts is None:
            if isinstance(self.pkt, type) or not hasattr(self.pkt, "pack"):
                return None

            try:
                bts = self.pkt.pack()
            except (BadSpecValue, PhotonsProtocolError):
                return None
            else:
                self._bts = bts
        return self._bts


@Events.register("DELETE")
class DeleteEvent(Event):
    """
    Used to say the device should have it's operators removed
    """


@Events.register("RESET")
class ResetEvent(Event):
    """
    Used when we need to reset the attrs on the device to those it started with

    This is used both when the device is first created and each time the device
    is reset.

    This event also contains:

    * zerod - Apply zero values rather than values from the options
    * old_attrs - the raw dictionary from the attrs before reset
    """

    def setup(self, zerod=False, *, old_attrs):
        self.zerod = zerod
        self.old_attrs = old_attrs
        self.log_kwargs = {"zerod": self.zerod}

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:zerod={self.zerod}>"


@Events.register("POWER_ON")
class PowerOnEvent(Event):
    """
    Used when the device is "given power"
    """


@Events.register("SHUTTING_DOWN")
class ShuttingDownEvent(Event):
    """
    Used when the device has been told to power off
    """


@Events.register("POWER_OFF")
class PowerOffEvent(Event):
    """
    Used after a device has "power taken away"
    """


@Events.register("INCOMING")
class IncomingEvent(EventPktBtsMixin, Event):
    """
    Used when a device has been given bytes from somewhere.

    This event also contains:

    * bts - The bytes that were provided
    * pkt - A Photons message object created by these bytes
    * io - The IO object these bytes came from
    * addr - The address the bytes came from
    * handled - Whether an operator has a reply for this message

    This event must be given replies to send back via calling
    ``set_replies(*replies)``. Once the event has replies it will not be sent to
    other operators.

    Or ``add_replies(*replies)`` if we want this event to be handled by
    other operators too.
    """

    def setup(self, io, *, pkt, addr=None, bts=None):
        self.io = io
        self.pkt = pkt
        self.addr = addr

        self.replies = None
        self.handled = False
        self.ignored = False

        self._bts = bts

        self.log_args = ()
        self.log_kwargs = {
            "packet": self.pkt,
            "bts": self.bts,
            "io": self.io.io_source,
            "addr": self.addr,
        }

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:io={self.io.io_source}:pkt={self.pkt.__class__.__name__}>"

    def __or__(self, compare):
        if isinstance(compare, type) and issubclass(compare, dictobj.PacketSpec):
            if self.pkt | compare:
                return True
        return self.io.io_source == compare or super().__or__(compare)

    def set_replies(self, *replies):
        if self.ignored:
            return

        self.replies = []
        self.add_replies(*replies)
        self.handled = True

    def ignore_request(self):
        self.replies = []
        self.ignored = True

    def add_replies(self, *replies):
        if self.ignored:
            return

        if self.replies is None:
            self.replies = []

        def flatten(lst):
            for l in lst:
                if isinstance(l, list):
                    yield from flatten(l)
                elif l is not None:
                    yield l

        self.replies.extend(list(flatten(replies)))


@Events.register("OUTGOING")
class OutgoingEvent(EventPktBtsMixin, Event):
    """
    Used when a device is sending bytes somewhere

    This event also contains:

    * bts - The bytes that are being sent
    * pkt - A photons message object from those bytes
    * io - The IO object those bytes are being sent to
    * addr - The address those bytes are sending to
    """

    def setup(self, io, *, pkt, replying_to, addr=None, bts=None, reason=None, proactive_for=None):
        self.io = io
        self.pkt = pkt
        self.addr = addr
        self.reason = reason
        self.replying_to = replying_to

        self._bts = bts

        self.log_args = ()
        self.log_kwargs = {
            "packet": self.pkt,
            "bts": self.bts,
            "io": self.io.io_source,
            "addr": self.addr,
            "replying_to": replying_to.__class__.__name__,
        }

        if reason is not None:
            self.log_kwargs["reason"] = reason

        if proactive_for is not None:
            if reason is None:
                self.log_kwargs["reason"] = "Proactive reporting to the cloud"
            self.log_kwargs["proactive_for"] = proactive_for

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:io={self.io.io_source},pkt={self.pkt.__class__.__name__}>"


@Events.register("UNHANDLED")
class UnhandledEvent(EventPktBtsMixin, Event):
    """
    Used when a device didn't handle a message

    This event also contains:

    * bts - The bytes that we didn't handle
    * pkt - A photons message object we didn't handle
    * io - The IO object those bytes came from
    * addr - The address the bytes came from
    """

    def setup(self, io, *, pkt, bts=None, addr=None):
        self.io = io
        self.pkt = pkt
        self.addr = addr

        self._bts = bts

        self.log_args = ()
        self.log_kwargs = {
            "packet": self.pkt,
            "bts": self.bts,
            "io": self.io.io_source,
            "addr": self.addr,
        }

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:pkt={self.pkt.__class__.__name__}>"


@Events.register("LOST")
class LostEvent(EventPktBtsMixin, Event):
    """
    Used during tests to say this request packet was lost before it got to the device

    This event also contains:

    * bts - The bytes that we didn't handle
    * pkt - A photons message object we didn't handle
    * io - The IO object those bytes came from
    * addr - The address the bytes came from
    """

    def setup(self, io, *, pkt, bts=None, addr=None):
        self.io = io
        self.pkt = pkt
        self.addr = addr

        self._bts = bts

        self.log_args = ()
        self.log_kwargs = {
            "packet": self.pkt,
            "bts": self.bts,
            "io": self.io.io_source,
            "addr": self.addr,
        }

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:pkt={self.pkt.__class__.__name__}>"


@Events.register("IGNORED")
class IgnoredEvent(EventPktBtsMixin, Event):
    """
    Used when a device specifically ignored a message

    This event also contains:

    * bts - The bytes that we didn't handle
    * pkt - A photons message object we didn't handle
    * io - The IO object those bytes came from
    * addr - The address the bytes came from
    """

    def setup(self, io, *, pkt, bts=None, addr=None):
        self.io = io
        self.pkt = pkt
        self.addr = addr

        self._bts = bts

        self.log_args = ()
        self.log_kwargs = {
            "packet": self.pkt,
            "bts": self.bts,
            "io": self.io.io_source,
            "addr": self.addr,
        }

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:pkt={self.pkt.__class__.__name__}>"


@Events.register("ATTRIBUTE_CHANGE")
class AttributeChangeEvent(Event):
    """
    Used when a attributes on the device have changed.

    This event also contains:

    * changes - A dictionary of `{key: (old, new)}` of what changed
    * attrs_started - Whether the attrs for this device has started yet
    * because - An event that caused this change
    """

    def setup(self, changes, attrs_started, because=None):
        self.changes = changes
        self.because = because
        self.attrs_started = attrs_started

        start = "started" if self.attrs_started else "not started"
        self.log_args = (f"Attributes changed ({start})",)
        self.log_kwargs = {}
        if self.because is not None:
            self.log_kwargs["because"] = self.because
        self.log_kwargs["changes"] = changes

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:changes={self.changes}:attrs_started={self.attrs_started}:because={self.because}>"

    def has_same_args(self, other):
        got = dict(self.log_kwargs)
        want = dict(other.log_kwargs)
        if "because" in got and "because" not in want:
            del got["because"]
        return self.log_args == other.log_args and got == want


@Events.register("ANNOTATION")
class AnnotationEvent(Event):
    """
    Used when we want to annotate this point in time with information.

    This event also contains:

    * level - A logging level (i.e. logging.WARN or logging.INFO)
    * message - Some string message
    * details - A dictionary of any other noteworthy information.
    """

    def setup(self, level, message, **details):
        if isinstance(level, str):
            level = getattr(logging, level)

        self.level = level
        self.details = details
        self.message = message

        self.name = f"{self.name}({logging.getLevelName(level)})"

        self.log_args = (message,)
        self.log_kwargs = self.details

    def has_same_args(self, other):
        return (
            super().has_same_args(other)
            and self.level == other.level
            and re.match(other.message, self.message)
        )


@Events.register("DISCOVERABLE")
class DiscoverableEvent(Event):
    """
    Used to let the device stop a discovery

    You must `self.raise_stop()` if the device cannot be discovered

    This event also contains:

    * io - the service used for discovery
    * address - the address that was used for reaching out to the device
    """

    def setup(self, *, service, address):
        self.service = service
        self.address = address

    def __repr__(self):
        return f"<Event:{self.device.serial}:{Events.name(self)}:address={self.address},service={self.service}>"
