from contextlib import contextmanager

from delfick_project.norms import sb
from photons_messages import CoreMessages
from photons_messages.frame import emptybt


class Cont(Exception):
    pass


class SendAck:
    def __init__(self, event):
        self.event = event

    async def process(self):
        if self.event.pkt.ack_required:
            yield CoreMessages.Acknowledgement.create(
                target=self.event.device.serial,
                source=self.event.pkt.source,
                sequence=self.event.pkt.sequence,
            )


class SendReplies:
    def __init__(self, event):
        self.event = event

    async def process(self):
        if not self.event.replies:
            return

        for reply in self.event.replies:
            if reply is Cont:
                yield {
                    "source": self.event.pkt.source,
                    "sequence": self.event.pkt.sequence,
                    "target": self.event.device.serial,
                }
                continue

            if reply.actual("source") is sb.NotSpecified:
                reply.source = self.event.pkt.source
            if reply.actual("sequence") is sb.NotSpecified:
                reply.sequence = self.event.pkt.sequence

            current = reply.actual("target")
            if current in (sb.NotSpecified, None, "0000000000000000", b"\x00" * 8, emptybt):
                reply.target = self.event.device.serial

            yield reply


class SendUnhandled:
    def __init__(self, event):
        self.event = event

    async def process(self):
        if self.event.device.cap.has_unhandled:
            yield CoreMessages.StateUnhandled(
                unhandled_type=self.event.pkt.pkt_type,
                source=self.event.pkt.source,
                sequence=self.event.pkt.sequence,
                target=self.event.device.serial,
            )


class Filter:
    def __init__(self):
        self._intercept_see_request = None
        self._intercept_see_outgoing = None
        self._intercept_process_request = None
        self._intercept_process_outgoing = None

        self._lost_acks = set()
        self._lost_replies = set()
        self._lost_request = set()

    @contextmanager
    def lost_acks(self, *klses):
        before = [kls for kls in klses if kls in self._lost_acks]
        try:
            for kls in klses:
                self._lost_acks.add(kls)
            yield
        finally:
            self._lost_acks = {kls for kls in self._lost_acks if kls not in klses or kls in before}

    @contextmanager
    def lost_replies(self, *klses):
        before = [kls for kls in klses if kls in self._lost_replies]
        try:
            for kls in klses:
                self._lost_replies.add(kls)
            yield
        finally:
            self._lost_replies = {
                kls for kls in self._lost_replies if kls not in klses or kls in before
            }

    @contextmanager
    def lost_request(self, *klses):
        before = [kls for kls in klses if kls in self._lost_request]
        try:
            for kls in klses:
                self._lost_request.add(kls)
            yield
        finally:
            self._lost_request = {
                kls for kls in self._lost_request if kls not in klses or kls in before
            }

    @contextmanager
    def intercept_see_request(self, func):
        before = self._intercept_see_request
        try:
            self._intercept_see_request = func
            yield
        finally:
            self._intercept_see_request = before

    @contextmanager
    def intercept_process_request(self, func):
        before = self._intercept_process_request
        try:
            self._intercept_process_request = func
            yield
        finally:
            self._intercept_process_request = before

    @contextmanager
    def intercept_see_outgoing(self, func):
        before = self._intercept_see_outgoing
        try:
            self._intercept_see_outgoing = func
            yield
        finally:
            self._intercept_see_outgoing = before

    @contextmanager
    def intercept_process_outgoing(self, func):
        before = self._intercept_process_outgoing
        try:
            self._intercept_process_outgoing = func
            yield
        finally:
            self._intercept_process_outgoing = before

    async def process_request(self, event):
        """
        Return whether the device is able to process the request

        None - The packet didn't even reach the device
        True - We received the packet and want to process it
        False - We received the packet and don't want to process it
        """
        if self._intercept_see_request:
            await self._intercept_see_request(event)

        if self._intercept_process_request:
            try:
                return await self._intercept_process_request(event, Cont)
            except Cont:
                pass

        if any(event.pkt | kls for kls in self._lost_request):
            # Packet didn't even reach device
            return None

        if event.pkt.serial not in ("000000000000", event.device.serial):
            return False

        return True

    async def outgoing(self, reply, request_event):
        """
        Yield replies that will be sent

        So 0 or more based on the reply the device wants to send and the original request
        """
        represents_ack = getattr(reply, "represents_ack", False)
        if self._intercept_see_outgoing:
            await self._intercept_see_outgoing(reply, request_event)

        if self._intercept_process_outgoing:
            try:
                async for reply in self._intercept_process_outgoing(reply, request_event, Cont):
                    yield reply
            except Cont:
                pass
            else:
                return

        if (
            not request_event.pkt.res_required
            and not request_event.pkt.__class__.__name__.startswith("Get")
            and not represents_ack
        ):
            return

        if not represents_ack and any(request_event.pkt | kls for kls in self._lost_replies):
            return

        if represents_ack and any(request_event | kls for kls in self._lost_acks):
            return

        if any(reply | kls for kls in self._lost_replies):
            return

        yield reply
