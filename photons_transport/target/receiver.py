from bitarray import bitarray
import binascii
import logging
import asyncio

log = logging.getLogger("photons_transport.target.receiver")

class Receiver(object):
    """Hold onto and routes replies from the bridge"""
    message_catcher = NotImplemented

    def __init__(self):
        self.results = {}
        self.blank_target = bitarray("0" * 8 * 8).tobytes()

    @property
    def loop(self):
        return asyncio.get_event_loop()

    def register(self, packet, result, expect_zero=False):
        """Register a future waiting for a result"""
        if expect_zero:
            # This is only necessary for originals in very specific situations
            # We shorten target because target might have random data at the end
            key = (0, 0, packet.target[:6])
        else:
            key = (packet.source, packet.sequence, packet.target)
        self.results[key] = result

        def cleanup(res):
            """
            Remove the future from our results after a small delay
            """
            def remove():
                if key in self.results:
                    del self.results[key]
            self.loop.call_later(0.5, remove)
        result.add_done_callback(cleanup)

    def recv(self, pkt, addr, broadcast):
        """Find the result for this packet and add the packet"""
        key = (pkt.source, pkt.sequence, pkt.target)
        zero_key = (0, 0, pkt.target[:6])

        broadcast_key = (pkt.source, pkt.sequence, self.blank_target)
        target = pkt.target[:6]
        serial = binascii.hexlify(target).decode()

        if pkt.source is 0 and pkt.sequence is 0:
            if zero_key in self.results:
                key = zero_key
            else:
                log.info("Received message with 0 source and sequence")
                return

        if key not in self.results and broadcast_key not in self.results:
            if self.message_catcher is not NotImplemented and callable(self.message_catcher):
                self.message_catcher(pkt)
            else:
                log.error("Received message but was no future to set! {0}:{1}".format(key, serial))
            return

        if key not in self.results:
            key = broadcast_key

        self.results[key].add_packet(pkt, addr, broadcast)

    def __call__(self, msg):
        """Do some debug logging and call out to recv"""
        pkt, addr, broadcast = msg

        if getattr(pkt, "represents_ack", False):
            log.debug("ACK (%s | %s | %s)", pkt.source, pkt.sequence, pkt.target)
        else:
            log.debug("RECV (%s | %s | %s)", pkt.source, pkt.sequence, pkt.target)

        self.recv(pkt, addr, broadcast)
