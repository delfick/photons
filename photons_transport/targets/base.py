from photons_transport.targets.script import ScriptRunner
from photons_transport.targets.item import Item

from photons_app.formatter import MergedOptionStringFormatter

from photons_control.script import FromGenerator

from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta
import logging

log = logging.getLogger("photons_transport.targets.base")

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

    def session(self):
        info = {}

        class Session:
            async def __aenter__(s):
                afr = info["afr"] = await self.args_for_run()
                return afr

            async def __aexit__(s, exc_type, exc, tb):
                if "afr" in info:
                    await self.close_args_for_run(info["afr"])

        return Session()

    async def args_for_run(self):
        """Create an instance of args_for_run. This is designed to be shared amongst many `script`"""
        return self.session_kls(self)

    async def close_args_for_run(self, args_for_run):
        """Close an args_for_run"""
        await args_for_run.finish()

    def simplify(self, script_part):
        """
        Used by ``self.script`` to convert ``raw`` into TransportItems

        For each item that is found:

        * Use as is if it already has a run_with method on it
        * Use item.simplified(self.simplify) if it has a simplified method
        * Otherwise, provide to self.item_kls

        For each leaf child that is found, we gather messages into groups of
        messages without a ``run_with`` method and yield ``self.item_kls(group)``.

        For example, let's say we have ``[p1, p2, m1, p3]`` where ``m1`` has
        a ``run_with`` method on it and the others don't, we'll yield:

        * ``self.item_kls([p1, p2])``
        * ``m1``
        * ``self.item_kls([p3])``
        """
        if type(script_part) is not list:
            script_part = [script_part]

        final = []
        for p in script_part:
            if hasattr(p, "run_with"):
                final.append(p)
            elif hasattr(p, "simplified"):
                final.append(p.simplified(self.simplify))
                continue
            else:
                final.append(p)

        buf = []
        for p in final:
            if not hasattr(p, "run_with"):
                buf.append(p)
            else:
                if buf:
                    yield self.item_kls(buf)
                    buf = []
                yield p
        if buf:
            yield self.item_kls(buf)
