from photons_app import helpers as hp

from bitarray import bitarray
import binascii
import logging
import asyncio

log = logging.getLogger("photons_transport.comms.receiver")

class Receiver(object):
    """Hold onto and routes replies from the bridge"""
    message_catcher = NotImplemented

    def __init__(self):
        self.results = {}
        self.blank_target = bitarray("0" * 8 * 8).tobytes()

    @property
    def loop(self):
        return asyncio.get_event_loop()

    def register(self, packet, result, original):
        """Register a future waiting for a result"""
        key = (packet.source, packet.sequence, packet.target)
        self.results[key] = (original, result)

        def cleanup(res):
            """
            Remove the future from our results after a small delay
            """
            def remove():
                if key in self.results:
                    del self.results[key]
            self.loop.call_later(0.5, remove)
        result.add_done_callback(cleanup)

    def recv(self, pkt, addr, allow_zero=False):
        """Find the result for this packet and add the packet"""
        if getattr(pkt, "represents_ack", False):
            log.debug(hp.lc("Got ACK", source=pkt.source, sequence=pkt.sequence, serial=pkt.serial))
        else:
            log.debug(hp.lc("Got RES", source=pkt.source, sequence=pkt.sequence, serial=pkt.serial, pkt_type=pkt.pkt_type))

        key = (pkt.source, pkt.sequence, pkt.target)

        broadcast_key = (pkt.source, pkt.sequence, self.blank_target)
        target = pkt.target[:6]
        serial = binascii.hexlify(target).decode()

        if pkt.source is 0 and pkt.sequence is 0:
            if not allow_zero:
                log.warning("Received message with 0 source and sequence")
                return

        if key not in self.results and broadcast_key not in self.results:
            if self.message_catcher is not NotImplemented and callable(self.message_catcher):
                self.message_catcher(pkt)
            else:
                log.warning(hp.lc("Received message but was no future to set", key=key, serial=serial))
            return

        if key not in self.results:
            key = broadcast_key

        original = self.results[key][0]
        self.results[key][1].add_packet(pkt, addr, original)
