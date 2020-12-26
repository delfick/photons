from photons_transport.comms.result import Result
from photons_messages.enums import Services

from photons_app import helpers as hp

from photons_transport.session.memory import MemoryService

from collections import defaultdict
from functools import partial
import asyncio
import logging
import time

log = logging.getLogger("photons_canvas.animations.infrastructure.cannons")


class Writer:
    def __init__(self, transport):
        self._t = None
        self.transport = transport

    async def t(self):
        if not getattr(self, "_t", None):
            self._t = await self.transport.spawn(None, timeout=1)
        return self._t

    async def write(self, msg):
        with hp.just_log_exceptions(log, reraise=[asyncio.CancelledError]):
            try:
                await self.transport.write(await self.t(), msg.tobytes(), msg)
            except asyncio.CancelledError:
                raise
            except AttributeError:
                self._t = None
            except:
                self._t = None
                raise


class Sem:
    def __init__(self, inflight_limit=None, wait_timeout=1):
        self.results = defaultdict(list)
        self.wait_timeout = wait_timeout
        self.inflight_limit = inflight_limit

    def add(self, serial, result):
        if result:
            self.results[serial].append((time.time(), result))

    def should_drop(self, serial):
        if not self.inflight_limit:
            return False

        self.results[serial] = [
            (t, r)
            for t, r in self.results[serial]
            if not r.done() and time.time() - t < self.wait_timeout
        ]

        if len(self.results[serial]) >= self.inflight_limit:
            return True

        return False


class Cannon:
    def __init__(self, afr, sem):
        self.afr = afr
        self.sem = sem
        self.writers = {}

    async def make_messages(self, ts, serial, msgs):
        """
        Should yield (write, result)

        Where write is an async function that writes bytes to a device.

        And result is either None if we don't care about when it completes,
        or a future if we do care.
        """
        raise NotImplementedError("Don't know how to make messages!")

    async def fire(self, ts, serial, msgs):
        if serial not in self.writers:
            services = self.afr.found[serial]
            if Services.UDP not in services:
                service = services[MemoryService]
            else:
                service = services[Services.UDP]

            self.writers[serial] = Writer(service)

        if self.sem.should_drop(serial):
            return

        async for write, result in self.make_messages(serial, msgs):
            self.sem.add(serial, result)
            await write()


class FastNetworkCannon(Cannon):
    """
    This is a version of Cannon that doesn't try to throttle the messages
    we send over the network
    """

    async def make_messages(self, serial, msgs):
        for msg in msgs:
            msg.update({"source": self.afr.source, "sequence": self.afr.seq(serial)})
            yield partial(self.writers[serial].write, msg), None


class NoisyNetworkCannon(Cannon):
    """
    This is a version of Cannon that tries to throttle how many messages we
    send of the network.

    It is suitable for environments where there is a lot of Wifi noise.

    Essentially, for each tile, we send acks for one of the messages we send in
    this frame. We then only send more messages if we have replies for less than
    <inflight_limit> acks waiting to be received.
    """

    async def make_messages(self, serial, msgs):
        for i, msg in enumerate(msgs):
            msg.update({"source": self.afr.source, "sequence": self.afr.seq(serial)})
            writer = self.writers[serial]

            t = await writer.t()

            result = None
            if i == 0:
                msg.ack_required = True
                retry_gaps = self.afr.retry_gaps(msg, t)
                result = Result(msg, False, retry_gaps)
                self.afr.receiver.register(msg, result, msg)

            yield partial(writer.write, msg), result
