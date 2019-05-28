from photons_transport.errors import FailedToFindDevice

from photons_app.errors import TimedOut, RunErrors, DevicesNotFound
from photons_app.special import SpecialReference
from photons_app import helpers as hp

from input_algorithms import spec_base as sb
from functools import partial
import binascii
import asyncio
import logging

log = logging.getLogger("photons_transport.base.item")

class Done:
    """Used to specify when we should close a queue"""

class NoLimit:
    """Used when we don't have a limit semaphore to impose no limit on concurrent access"""
    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def acquire(self):
        pass

    def release(self):
        pass

    def locked(self):
        return False

def timeout_task(task, errf, serial):
    """Used to cancel sending a messages and record a timed out exception"""
    if not task.done():
        errf.set_exception(TimedOut("Waiting for reply to a packet", serial=serial))
        task.cancel()

def throw_error(serials, error_catcher):
    """Throw the errors from our error catcher"""
    error_catcher = list(set(error_catcher))
    if error_catcher:
        if (serials is None or len(serials) < 2) and len(error_catcher) is 1:
            raise error_catcher[0]
        else:
            raise RunErrors(_errors=error_catcher)

class TransportItem(object):
    """
    Responsible for Writing our parts to our devices.

    * Determines final messages from the parts
    * Finds what devices it can
    * Writes to those messages
    * Raises error or returns results

    Usage is through TransportTarget:

    .. code-block:: python

        target = <some instance of TransportTarget>
        script = target.script(<some message>)

        # Transport item comes into play here
        script.run_with([selector, selector, selector, ....])

        # or if you already have an afr
        script.run_with([selector, selector, selector, ....], afr)
    """
    def __init__(self, parts):
        self.parts = parts
        if type(self.parts) is not list:
            self.parts = [self.parts]

    async def run_with(self, serials, args_for_run
        , broadcast=False, accept_found=False, found=None, error_catcher=None
        , **kwargs
        ):
        """
        Entry point to this item, the idea is you create a `script` with the
        target and call `run_with` on the script, which ends up calling this

        We acknowledge the following keyword arguments.

        broadcast
            Whether we are broadcasting these messages or just unicasting directly
            to each device

        find_timeout
            timeout for finding devices

        connect_timeout
            timeout for connecting to devices

        message_timeout
            A per message timeout for receiving replies for that message

        found
            A dictionary of
            ``{targetHex: (set([(ServiceType, addr), (ServiceType, addr), ...]), broadcastAddr)}``

            If this is not provided, one is made for us

        accept_found
            Accept the found that was given and don't try to change it

        error_catcher
            A list that errors will be appended to instead of being raised.

            Or a callable that takes in the error as an argument.

            If this isn't specified then errors are raised after all the received
            messages have been yielded.

            Note that if there is only one serial that we sent messages to, then
            any error is raised as is. Otherwise we raise a
            ``photons_app.errors.RunErrors``, with all the errors in a list on
            the ``errors`` property of the RunErrors exception.

        no_retry
            If True then the messages being sent will have no automatic retry. This defaults
            to False and retry rates are determined by the target you are using.

        require_all_devices
            Defaults to False. If True then we will not send any messages if we haven't
            found all the devices we want to send messages to. Otherwise we will send messages
            to the devices we have found and add photons_transport.errors.FailedToFindDevice errors
            for each device that wasn't found.

        limit
            An async context manager used to limit inflight messages. So for each message, we do

            .. code-block:: python

                async with limit:
                    send_and_wait_for_reply(message)

            For example, an ``asyncio.Semaphore(30)``

            Note that if you saying ``target.script(msgs).run_with(....)`` then limit will be set
            to a semaphore with max 30 by default. You may specify just a number and it will turn it
            into a semaphore.

        * First we make the packets.
        * Then we find the devices (unless found is supplied)
        * Then we send the packets to the devices
        * Then we gather results and errors
        """
        if "timeout" in kwargs:
            log.warning(hp.lc("Please use message_timeout instead of timeout when calling run_with"))

        afr = args_for_run

        do_raise = error_catcher is None
        error_catcher = [] if do_raise else error_catcher

        missing = None
        if isinstance(serials, SpecialReference):
            try:
                ref = serials
                found, serials = await ref.find(afr, broadcast=broadcast, timeout=kwargs.get("find_timeout", 5))
                missing = ref.missing(found)
                serials.extend(missing)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if do_raise:
                    raise
                hp.add_error(error_catcher, error)
                return

        # Work out what and where to send
        # All the packets from here have targets on them
        packets = self.make_packets(
              afr
            , serials
            , broadcast
            )

        # Determine found
        looked = True
        if missing is None:
            looked, found, missing = await self.search(
                  afr
                , found if found is not None else afr.found
                , accept_found or broadcast
                , packets
                , broadcast
                , kwargs.get("find_timeout", 20)
                , kwargs
                )

        if not broadcast and kwargs.get("require_all_devices") and missing:
            hp.add_error(error_catcher, DevicesNotFound(missing=missing))
            if do_raise:
                throw_error(serials, error_catcher)
            return

        # Work out where to send packets
        addr = broadcast or None
        retry_options = afr.make_retry_options()

        def check_packet(packet):
            if packet.target is None or not looked or (found and packet.target[:6] in found):
                return
            else:
                return FailedToFindDevice(serial=packet.serial)

        def make_waiter(writer):
            return afr.make_waiter(writer, retry_options=retry_options, no_retry=kwargs.get("no_retry", False))

        async def make_writer(original, packet):
            target = packet.target
            services = None

            if target is not None:
                target = target[:6]
                if target in found:
                    services = found[target][0]

            return await afr.make_writer(services, original, packet
                , broadcast=broadcast, retry_options=retry_options
                , addr=addr, found=found, **kwargs
                )

        writer_args = (
              packets
            , check_packet, make_writer, make_waiter
            , kwargs.get("message_timeout", 10), error_catcher
            , kwargs.get("limit")
            )

        # Finally use our message_writer helper to get us some results
        async for thing in self.write_messages(*writer_args):
            yield thing

        if do_raise:
            throw_error(serials, error_catcher)

    def simplify_parts(self):
        """
        Simiplify our parts such that their payloads are bitarrays.

        Unless a packet is dynamically created (has a callable field)
        in which case, we just return packet as is
        """
        return [(p, p) if p.is_dynamic else (p, p.simplify()) for p in self.parts]

    def make_packets(self, afr, serials, broadcast):
        """
        Create and fill in the packets from our parts

        This means that for each reference and each part we create a clone of
        the part with the target set to the reference, complete with a source and
        sequence
        """
        # Helpers for getting packet source and sequence
        source_maker = lambda : afr.source(bool(broadcast))
        sequence_maker = lambda target: afr.seq(target)

        # Simplify our parts
        simplified_parts = self.simplify_parts()

        if type(serials) is not list:
            serials = [serials]

        packets = []
        for original, p in simplified_parts:
            if p.target is sb.NotSpecified:
                for serial in serials:
                    clone = p.clone()
                    clone.update(
                          dict(
                            source=source_maker()
                          , sequence=sequence_maker(serial)
                          , target=serial
                          )
                        )
                    packets.append((original, clone))
            else:
                clone = p.clone()
                clone.update(dict(source=source_maker(), sequence=sequence_maker(p.target)))
                packets.append((original, clone))

        return packets

    async def search(self, afr, found, accept_found, packets, broadcast, find_timeout, kwargs):
        """Search for the devices we want to send to"""
        serials = list(set([p.serial for _, p in packets if p.target is not None]))
        targets = set(binascii.unhexlify(serial)[:6] for serial in serials)

        if accept_found or (found is not None and all(target in found for target in targets)):
            missing = [binascii.hexlify(target).decode() for target in targets if target not in found]
            return False, found, missing

        found, missing = await afr.find_specific_serials(serials
            , broadcast = broadcast
            , raise_on_none = False
            , timeout = find_timeout
            , **kwargs
            )

        return True, found, missing

    async def write_messages(self, packets, check_packet, make_writer, make_waiter, message_timeout, error_catcher, limit=None):
        """Make a bunch of writers and then use them to create waiters"""
        writers = []
        writing_packets = []

        errors = []

        for (original, packet) in packets:
            error = check_packet(packet)
            if error:
                errors.append(error)
            else:
                try:
                    writer = await make_writer(original, packet)
                except Exception as error:
                    hp.add_error(error_catcher, error)
                else:
                    writers.append(writer)
                    writing_packets.append(packet)

        for error in set(errors):
            hp.add_error(error_catcher, error)

        if not writing_packets:
            return

        queue = asyncio.Queue()

        futures = []
        gatherers = []

        def process(packet, errf, res):
            if errf.done() and not errf.cancelled():
                exc = errf.exception()
                if exc:
                    hp.add_error(error_catcher, exc)

            elif res.cancelled():
                e = TimedOut("Message was cancelled"
                    , serial=packet.serial
                    )
                hp.add_error(error_catcher, e)
                return

            if not res.cancelled():
                exc = res.exception()
                if exc:
                    hp.add_error(error_catcher, exc)

            full_number = len(gatherers) == len(writers)
            futs_done = all(f.done() for f in futures)
            gatherers_done = all(f.done() for f in gatherers)
            if full_number and futs_done and gatherers_done:
                hp.async_as_background(queue.put(Done))

        for writer, (_, packet) in zip(writers, packets):
            # We separate the waiter from waiting on the waiter
            # so we can cancel the waiter instead of the thing waiting on it
            # To avoid AssertionError: _step(): already done logs
            waiter = make_waiter(writer)

            async def doit(w, serial, errf):
                async with (limit or NoLimit()):
                    if hasattr(asyncio, "current_task"):
                        current_task = asyncio.current_task()
                    else:
                        current_task = asyncio.Task.current_task()

                    asyncio.get_event_loop().call_later(message_timeout, timeout_task, current_task, errf, serial)

                    try:
                        for info in await w:
                            await queue.put(info)
                    finally:
                        w.cancel()

            errf = asyncio.Future()
            f = asyncio.ensure_future(doit(waiter, packet.serial, errf))
            gatherers.append(f)
            f.add_done_callback(partial(process, packet, errf))
            futures.append(waiter)

        while True:
            try:
                nxt = await queue.get()
            except asyncio.CancelledError:
                for f in gatherers:
                    f.cancel()
                raise

            if nxt is Done:
                break
            yield nxt
