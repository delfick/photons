from photons_transport.targets.script import ScriptRunner
from photons_transport.targets.item import Item

from photons_app.formatter import MergedOptionStringFormatter
from photons_app import helpers as hp

from photons_control.script import FromGenerator

from delfick_project.norms import sb, dictobj, Meta
import logging

log = logging.getLogger("photons_transport.targets.base")


class Sender:
    def __init__(self, target, msg, reference, **kwargs):
        self.msg = msg
        self.kwargs = kwargs
        self.target = target
        self.reference = reference
        self.script = target.script(msg)

    def __await__(self):
        return (yield from self.all_packets().__await__())

    async def all_packets(self):
        async with self.target.session() as sender:
            return await sender(self.msg, self.reference, **self.kwargs)

    def __aiter__(self):
        return self.stream_packets()

    async def stream_packets(self):
        async with self.target.session() as sender:
            async for pkt in sender(self.msg, self.reference, **self.kwargs):
                yield pkt


class Target(dictobj.Spec):
    protocol_register = dictobj.Field(sb.overridden("{protocol_register}"), formatted=True)
    final_future = dictobj.Field(sb.overridden("{final_future}"), formatted=True)
    description = dictobj.Field(sb.string_spec, default="Base transport functionality")

    item_kls = Item
    script_runner_kls = ScriptRunner

    def session_kls(self, *args, **kwargs):
        raise NotImplementedError()

    @classmethod
    def create(kls, configuration, options=None):
        options = options if options is not None else configuration
        meta = Meta(configuration, []).at("options")
        return kls.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, options)

    def send(self, msg, reference=None, **kwargs):
        return Sender(self, msg, reference, **kwargs)

    def script(self, raw):
        """Return us a ScriptRunner for the given `raw` against this `target`"""
        items = list(self.simplify(raw))
        if not items:
            items = None
        elif len(items) > 1:
            original = items

            async def gen(*args, **kwargs):
                for item in original:
                    yield item

            items = list(self.simplify(FromGenerator(gen, reference_override=True)))[0]
        else:
            items = items[0]
        return self.script_runner_kls(items, target=self)

    @hp.asynccontextmanager
    async def session(self):
        session = None
        try:
            session = await self.make_sender()
            yield session
        finally:
            if session:
                await self.close_sender(session)

    async def make_sender(self):
        """Create an instance of the sender. This is designed to be shared."""
        return self.session_kls(self)

    # backwards compatibility
    args_for_run = make_sender

    async def close_sender(self, sender):
        """Close a sender"""
        await sender.finish()

    # backwards compatibility
    close_args_for_run = close_sender

    def simplify(self, script_part):
        """
        Used by ``self.script`` to convert ``raw`` into TransportItems

        For each item that is found:

        * Use as is if it already has a run method on it
        * Use item.simplified(self.simplify) if it has a simplified method
        * Otherwise, provide to self.item_kls

        For each leaf child that is found, we gather messages into groups of
        messages without a ``run`` method and yield ``self.item_kls(group)``.

        For example, let's say we have ``[p1, p2, m1, p3]`` where ``m1`` has
        a ``run`` method on it and the others don't, we'll yield:

        * ``self.item_kls([p1, p2])``
        * ``m1``
        * ``self.item_kls([p3])``
        """
        if type(script_part) is not list:
            script_part = [script_part]

        final = []
        for p in script_part:
            if hasattr(p, "run"):
                final.append(p)
            elif hasattr(p, "simplified"):
                final.append(p.simplified(self.simplify))
                continue
            else:
                final.append(p)

        buf = []
        for p in final:
            if not hasattr(p, "run"):
                buf.append(p)
            else:
                if buf:
                    yield self.item_kls(buf)
                    buf = []
                yield p
        if buf:
            yield self.item_kls(buf)
