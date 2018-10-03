from photons_transport.target.errors import FailedToFindDevice

from photons_app.errors import TimedOut, RunErrors
from photons_app.special import SpecialReference
from photons_app import helpers as hp

from photons_script.script import add_error

from input_algorithms import spec_base as sb
from functools import partial
import asyncio
import logging
import time

log = logging.getLogger("photons_transport.target.item")

class Done:
    """Used to specify when we should close a queue"""

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

        timeout
            timeout for writing messages

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

        * First we make the packets.
        * Then we find the devices (unless found is supplied)
        * Then we send the packets to the devices
        * Then we gather results and errors
        """
        afr = args_for_run

        do_raise = error_catcher is None
        error_catcher = [] if do_raise else error_catcher

        broadcast_address = (
              afr.default_broadcast if broadcast is True else broadcast
            ) or afr.default_broadcast

        if isinstance(serials, SpecialReference):
            try:
                found, serials = await serials.find(afr, broadcast, kwargs.get("find_timeout", 5))
                accept_found = True
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if do_raise:
                    raise
                add_error(error_catcher, error)
                return

        # Work out what and where to send
        # All the packets from here have targets on them
        packets = self.make_packets(
              afr
            , serials
            , broadcast
            )

        # Determine found
        looked = False
        found = found if found is not None else afr.found
        if not accept_found and not broadcast:
            looked, found, catcher = await self.search(
                  afr
                , found
                , packets
                , broadcast_address
                , kwargs.get("find_timeout", 20)
                )

            if catcher:
                for error in set(catcher):
                    add_error(error_catcher, error)

                if do_raise:
                    throw_error(serials, error_catcher)
                else:
                    return

        # Work out where to send packets
        if type(broadcast) is tuple:
            addr = broadcast
        else:
            addr = None if broadcast is False else (broadcast_address, 56700)

        # Create our helpers that channel particular arguments into the correct places

        retry_options = afr.make_retry_options()

        def check_packet(packet):
            if packet.target is None or not looked or found and packet.target[:6] in found:
                return
            else:
                return FailedToFindDevice(serial=packet.serial)

        def make_waiter(writer):
            return afr.make_waiter(writer, retry_options=retry_options)

        async def make_writer(original, packet):
            return await afr.make_writer(original, packet
                , broadcast=broadcast, retry_options=retry_options
                , addr=addr, found=found, **kwargs
                )

        writer_args = (
              packets
            , check_packet, make_writer, make_waiter
            , kwargs.get("timeout", 10), error_catcher
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

    async def search(self, afr, found, packets, broadcast_address, find_timeout):
        """Search for the devices we want to send to"""
        looked = False
        start = time.time()
        targets = set(p.target[:6] for _, p in packets)
        catcher = None

        need_check = lambda: not found or any(target not in found for target in targets)

        while need_check():
            looked = True
            catcher = []
            found = await afr.find_devices(broadcast_address
                , raise_on_none = False
                , timeout = find_timeout
                , error_catcher = catcher
                )
            if time.time() - start > find_timeout:
                break

        if catcher and not need_check():
            # We don't care about errors if we found all the devices we care about
            catcher = []

        return looked, found, catcher

    async def write_messages(self, packets, check_packet, make_writer, make_waiter, timeout, error_catcher):
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
                    add_error(error_catcher, error)
                else:
                    writers.append(writer)
                    writing_packets.append(packet)

        for error in set(errors):
            add_error(error_catcher, error)

        if not writing_packets:
            return

        queue = asyncio.Queue()

        futures = []
        gatherers = []

        def process(packet, res):
            if res.cancelled():
                e = TimedOut("Message was cancelled"
                    , serial=packet.serial
                    )
                add_error(error_catcher, e)
                return

            if not res.cancelled():
                exc = res.exception()
                if exc:
                    add_error(error_catcher, exc)

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

            async def doit(w):
                for info in await w:
                    await queue.put(info)
            f = asyncio.ensure_future(doit(waiter))
            gatherers.append(f)
            f.add_done_callback(partial(process, packet))
            futures.append(waiter)

        def canceller():
            for f, packet in zip(futures, writing_packets):
                if not f.done():
                    f.set_exception(TimedOut("Waiting for reply to a packet", serial=packet.serial))
        asyncio.get_event_loop().call_later(timeout, canceller)

        while True:
            nxt = await queue.get()
            if nxt is Done:
                break
            yield nxt
