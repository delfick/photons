from photons_transport.comms.result import Result

from photons_app import helpers as hp

import binascii
import logging

log = logging.getLogger("photons_transport.comms.writer")

class Writer:
    def __init__(self, session, transport, receiver, original, packet, retry_options
        , did_broadcast = False
        , connect_timeout = 10
        ):
        self.sent = 0
        self.clone = packet.clone()
        self.session = session
        self.original = original
        self.receiver = receiver
        self.transport = transport
        self.retry_options = retry_options
        self.did_broadcast = did_broadcast
        self.connect_timeout = connect_timeout

    async def __call__(self):
        self.modify_sequence()
        result = self.register()
        bts = await self.write()

        lc = hp.lc.using(
              serial = self.clone.serial
            , pkt = self.clone.pkt_type
            , protocol = self.clone.protocol
            , source = self.clone.source
            , sequence = self.clone.sequence
            )

        if len(bts) < 256:
            log.debug(lc("Sent message", bts=binascii.hexlify(bts).decode()))
        else:
            log.debug(lc("Sent message"))

        return result

    def modify_sequence(self):
        if self.sent > 0:
            self.clone.sequence = self.session.seq(self.original.serial)
        self.sent += 1

    def register(self):
        result = Result(self.original, self.did_broadcast, self.retry_options)
        if not result.done():
            result.add_done_callback(hp.silent_reporter)
            self.receiver.register(self.clone, result, self.original)
        return result

    async def write(self):
        bts = self.clone.tobytes(self.clone.serial)
        t = await self.transport.spawn(self.original, timeout=self.connect_timeout)
        await self.transport.write(t, bts, self.original)
        return bts
