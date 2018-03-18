from photons_app import helpers as hp

from bitarray import bitarray
import binascii
import logging
import asyncio
import time

log = logging.getLogger("photons_transport.target.receiver")

class Receiver(object):
    """Hold onto and routes replies from the bridge"""
    message_catcher = NotImplemented

    def __init__(self):
        self.acks = {}
        self.received = {}

        self.multi_cache = {}
        self.multi_cache_futs = {}
        self.blank_target = bitarray("0" * 8 * 8).tobytes()

    @property
    def loop(self):
        return asyncio.get_event_loop()

    def register_res(self, packet, fut, multiple_replies, expect_zero=False):
        """Register a future waiting for a result"""
        if expect_zero:
            # This is only necessary for originals in very specific situations
            # We shorten target because target might have random data at the end
            key = (0, 0, packet.target[:6])
        else:
            key = (packet.source, packet.sequence, packet.target)
        self.received[key] = (fut, multiple_replies)

        def remove_fut(*args):
            def remove():
                if key in self.received:
                    del self.received[key]
            self.loop.call_later(1, remove)
        fut.add_done_callback(remove_fut)
        fut.add_done_callback(hp.reporter)

    def register_ack(self, packet, fut, multiple_replies):
        """Register a future waiting for an acknowledgement"""
        key = (packet.source, packet.sequence, packet.target)
        self.acks[key] = (fut, multiple_replies)

        def remove_fut(*args):
            def remove():
                if key in self.acks:
                    del self.acks[key]
            self.loop.call_later(1, remove)
        fut.add_done_callback(remove_fut)
        fut.add_done_callback(hp.reporter)

    def recv(self, pkt, addr, broadcast, dest):
        """Find the future for this packet and set a result"""
        key = (pkt.source, pkt.sequence, pkt.target)
        zero_key = (0, 0, pkt.target[:6])

        broadcast_key = (pkt.source, pkt.sequence, self.blank_target)
        target = pkt.target[:6]
        serial = binascii.hexlify(target).decode()

        if pkt.source is 0 and pkt.sequence is 0:
            if zero_key in dest:
                key = zero_key
            else:
                log.info("Received message with 0 source and sequence")
                return

        if key not in dest and broadcast_key not in dest:
            if self.message_catcher is not NotImplemented and callable(self.message_catcher):
                self.message_catcher(pkt)
            else:
                log.error("Received message but was no future to set! {0}:{1}".format(key, serial))
            return

        if key not in dest:
            key = broadcast_key

        fut, multiple = dest[key]
        if not multiple:
            if not fut.done():
                fut.set_result([(pkt, addr, broadcast)])
            return True
        else:
            multi_key = (broadcast, key)
            if multi_key not in self.multi_cache:
                self.multi_cache[multi_key] = (fut, [])
            self.multi_cache[multi_key][1].append(((pkt, addr, broadcast), time.time()))

            # Call out to to finish the multi cache after 0.35 seconds
            self.loop.call_later(0.35, self.finish_multi_cache, multi_key)

    def __call__(self, msg):
        """Call recv with the correct parameters given this message we have received"""
        popped = []
        pkt, addr, broadcast = msg

        if getattr(pkt, "represents_ack", False):
            log.debug("ACK (%s | %s | %s)", pkt.source, pkt.sequence, pkt.target)
            dest = self.acks
        else:
            log.debug("RECV (%s | %s | %s)", pkt.source, pkt.sequence, pkt.target)
            dest = self.received

        if self.recv(pkt, addr, broadcast, dest):
            popped.append(pkt)

        return popped

    def finish_multi_cache(self, key):
        """Go through our multiple_reply items and set the future if it's been long enough since last message"""
        if key not in self.multi_cache:
            return

        fut, replies = self.multi_cache[key]
        if fut.done() or fut.cancelled():
            del self.multi_cache[key]
            return

        if replies:
            maximum = max(r[1] for r in replies)
            if time.time() - maximum > 0.3:
                found = [r[0] for r in replies]
                fut.set_result(found)
                del self.multi_cache[key]
