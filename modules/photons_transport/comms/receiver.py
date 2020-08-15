from photons_app import helpers as hp

from bitarray import bitarray
import logging
import asyncio

log = logging.getLogger("photons_transport.comms.receiver")


class Receiver:
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
            if key in self.results:
                del self.results[key]

        result.add_done_callback(cleanup)

    async def recv(self, pkt, addr, allow_zero=False):
        """Find the result for this packet and add the packet"""
        if getattr(pkt, "represents_ack", False):
            log.debug(hp.lc("Got ACK", source=pkt.source, sequence=pkt.sequence, serial=pkt.serial))
        else:
            log.debug(
                hp.lc(
                    "Got RES",
                    source=pkt.source,
                    sequence=pkt.sequence,
                    serial=pkt.serial,
                    pkt_type=pkt.pkt_type,
                )
            )

        key = (pkt.source, pkt.sequence, pkt.target)
        broadcast_key = (pkt.source, pkt.sequence, self.blank_target)

        if pkt.source == 0 and pkt.sequence == 0:
            if not allow_zero:
                log.warning("Received message with 0 source and sequence")
                return

        if key not in self.results and broadcast_key not in self.results:
            if self.message_catcher is not NotImplemented and callable(self.message_catcher):
                await self.message_catcher(pkt)
            else:
                # This usually happens when Photons retries a message
                # But gets a reply from multiple of these requests
                # The first one back will unregister the future
                # And so there's nothing to resolve with this newly received data
                log.debug(
                    hp.lc("Received a message that wasn't expected", key=key, serial=pkt.serial)
                )
            return

        if key not in self.results:
            key = broadcast_key

        original = self.results[key][0]
        pkt.Information.update(remote_addr=addr, sender_message=original)
        self.results[key][1].add_packet(pkt)
