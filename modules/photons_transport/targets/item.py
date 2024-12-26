import asyncio
import logging

from delfick_project.norms import sb
from photons_app import helpers as hp
from photons_app.errors import DevicesNotFound, TimedOut
from photons_app.special import SpecialReference

from photons_transport import catch_errors

log = logging.getLogger("photons_transport.targets.item")


class Done:
    """Used to specify when we should close a queue"""


def silence_errors(e):
    pass


def choose_source(pkt, source):
    """Used to decide what we use as source for the packet"""
    if pkt.actual("source") is not sb.NotSpecified:
        return pkt.source
    else:
        return source


class NoLimit:
    """Used when we don't have a limit semaphore to impose no limit on concurrent access"""

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_typ, exc, tb):
        pass

    async def acquire(self):
        pass

    def release(self):
        pass

    def locked(self):
        return False


no_limit = NoLimit()


class Item:
    def __init__(self, parts):
        self.parts = parts
        if type(self.parts) is not list:
            self.parts = [self.parts]

    async def run(self, reference, sender, **kwargs):
        """
        Entry point to this item, the idea is you create a `script` with the
        target and call `run` on the script, which ends up calling this

        This is an async generator that yields the results from sending packets to the devices
        it is responsible for finding devices and gathering all the responses.

        This accepts the following keyword arguments.

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
            found all the devices we want to send messages to.

        limit
            An async context manager used to limit inflight messages. So for each message, we do

            .. code-block:: python

                async with limit:
                    send_and_wait_for_reply(message)

            For example, an ``asyncio.Semaphore(30)``

            Note that if you saying ``target.script(msgs).run(....)`` then limit will be set
            to a semaphore with max 30 by default. You may specify just a number and it will turn it
            into a semaphore.
        """
        if "timeout" in kwargs:
            log.warning(hp.lc("Please use message_timeout instead of timeout when calling run"))

        with catch_errors(kwargs.get("error_catcher")) as error_catcher:
            kwargs["error_catcher"] = error_catcher

            broadcast = kwargs.get("broadcast", False)
            find_timeout = kwargs.get("find_timeout", 20)

            found, serials, missing = await self._find(kwargs.get("found"), reference, sender, broadcast, find_timeout)

            # Work out what and where to send
            # All the packets from here have targets on them
            packets = self.make_packets(sender, serials)

            # Short cut if nothing to actually send
            if not packets:
                return

            # Determine found
            if missing is None and not broadcast:
                accept_found = kwargs.get("accept_found") or broadcast

                found, missing = await self.search(sender, found, accept_found, packets, broadcast, find_timeout, kwargs)

            # Complain if we care about having all wanted devices
            if not broadcast and kwargs.get("require_all_devices") and missing:
                raise DevicesNotFound(missing=missing)

            # Write the messages and get results
            async for thing in self.write_messages(sender, packets, kwargs):
                yield thing

    async def _find(self, found, reference, sender, broadcast, timeout):
        """
        Turn our reference into serials and a found object and list of missing serials

        if reference is not a SpecialReference then we just return it and the found we were given,
        otherwise use the special reference to get found and serials where serials includes missing serials
        """
        serials = reference
        missing = None

        if isinstance(reference, SpecialReference):
            found, serials = await reference.find(sender, broadcast=broadcast, timeout=timeout)
            missing = reference.missing(found)
            serials.extend(missing)

        if type(serials) is not list:
            serials = [serials]

        if found is None:
            found = sender.found

        return found, serials, missing

    def simplify_parts(self):
        """
        Simplify our parts such that their payloads are bitarrays.

        Unless a packet is dynamically created (has a callable field)
        in which case, we just return packet as is
        """
        ps = []
        for p in self.parts:
            if p.is_dynamic:
                ps.append((p, p))
            else:
                ps.append((p, p.simplify()))
        return ps

    def make_packets(self, sender, serials):
        """
        Create and fill in the packets from our parts

        This means that for each reference and each part we create a clone of
        the part with the target set to the reference, complete with a source and
        sequence
        """
        # Simplify our parts
        simplified_parts = self.simplify_parts()

        packets = []
        for original, p in simplified_parts:
            if p.target is sb.NotSpecified:
                for serial in serials:
                    clone = p.clone()
                    clone.update(
                        dict(
                            target=serial,
                            source=choose_source(clone, sender.source),
                            sequence=sender.seq(serial),
                        )
                    )
                    packets.append((original, clone))
            else:
                clone = p.clone()
                clone.update(dict(source=choose_source(clone, sender.source), sequence=sender.seq(p.serial)))
                packets.append((original, clone))

        return packets

    async def search(self, sender, found, accept_found, packets, broadcast, find_timeout, kwargs):
        """Search for the devices we want to send to"""
        serials = list(set([p.serial for _, p in packets if p.target is not None]))

        if accept_found or (found and all(serial in found for serial in serials)):
            if found is None:
                found = sender.found

            missing = [serial for serial in serials if serial not in found]
            return found, missing

        kw = dict(kwargs)
        kw["timeout"] = find_timeout
        kw["broadcast"] = broadcast
        kw["raise_on_none"] = False
        return await sender.find_specific_serials(serials, **kw)

    async def write_messages(self, sender, packets, kwargs):
        """Send all our packets and collect all the results"""

        error_catcher = kwargs["error_catcher"]

        async with hp.ResultStreamer(sender.stop_fut, error_catcher=silence_errors, name="Item::write_messages[streamer]") as streamer:
            count = 0
            for original, packet in packets:
                count += 1
                await streamer.add_coroutine(self.do_send(sender, original, packet, kwargs), context=packet)

            streamer.no_more_work()

            got = 0
            async for result in streamer:
                got += 1
                if result.successful:
                    for msg in result.value:
                        yield msg
                else:
                    exc = result.value
                    pkt = result.context
                    if isinstance(exc, asyncio.CancelledError):
                        hp.add_error(
                            error_catcher,
                            TimedOut(
                                "Message was cancelled",
                                sent_pkt_type=pkt.pkt_type,
                                serial=pkt.serial,
                                source=pkt.source,
                                sequence=pkt.sequence,
                            ),
                        )
                    else:
                        hp.add_error(error_catcher, exc)

    async def do_send(self, sender, original, packet, kwargs):
        async with kwargs.get("limit") or no_limit:
            return await sender.send_single(
                original,
                packet,
                timeout=kwargs.get("message_timeout", 10),
                no_retry=kwargs.get("no_retry", False),
                broadcast=kwargs.get("broadcast"),
                connect_timeout=kwargs.get("connect_timeout", 10),
            )
