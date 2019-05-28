from photons_transport.base.bridge import TransportBridge
from photons_transport.base.script import ScriptRunner
from photons_transport.base.item import TransportItem

from photons_app.formatter import MergedOptionStringFormatter

from photons_control.script import FromGenerator

from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta
import binascii
import logging

log = logging.getLogger("photons_transport.base.target")

class TransportTarget(dictobj.Spec):
    """
    This is responsible for bringing together the TransportBridge and the TransportItems

    It implements the ability to create and destroy args_for_run (the bridge), as well as
    creating a `script` that may be run with `script.run_with`.

    We also have higher order functions for finding and forgetting devices.

    When creating your own target do something like:

    .. code-block:: python

        class SocketTarget(TransportTarget):
            item_kls = lambda s: SocketItem
            bridge_kls = lambda s: SocketBridge
            description = dictobj.Field(sb.string_spec, default="Understands how to talk to a device over a TCP socket")

    ``protocol_register`` and ``final_future`` are retrieved automatically from
    ``Meta`` if we create the transport by doing
    ``TransportTarget.normalise(meta, **kwargs)``

    Note that the path on the meta cannot be root. So make you meta like:

    .. code-block:: python

        from input_algorithms.meta import Meta
        from option_merge import MergedOptions

        configuration = MergedOptions.using({"protocol_register": ..., "final_future": asyncio.Future()})

        # By saying `at("options")` on the meta we are putting it not at root
        # So when we resolve final_future we don't get recursive option errors
        meta = Meta(configuration, []).at("options")

    Generally you'll be passed in a transport via the ``tasks`` mechanism and
    you won't have to instantiate it yourself.
    """
    protocol_register = dictobj.Field(sb.overridden("{protocol_register}"), formatted=True)
    final_future = dictobj.Field(sb.overridden("{final_future}"), formatted=True)
    default_broadcast = dictobj.Field(sb.defaulted(sb.string_spec(), "255.255.255.255"))
    item_kls = lambda s: TransportItem
    bridge_kls = lambda s: TransportBridge
    description = dictobj.Field(sb.string_spec, default="Base transport functionality")

    @classmethod
    def create(kls, configuration, options=None):
        options = options if options is not None else configuration
        meta = Meta(configuration, []).at("options")
        return kls.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, options)

    def script(self, raw):
        """Return us a ScriptRunnerfor the given `raw` against this `target`"""
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
        return ScriptRunner(items, target=self)

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
        afr = self.bridge_kls()(self.final_future, self
            , protocol_register=self.protocol_register
            )
        await afr.start()
        return afr

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
        messages without a ``run_with`` method and yield ``self.item_kls()(group)``.

        For example, let's say we have ``[p1, p2, m1, p3]`` where ``m1`` has
        a ``run_with`` method on it and the others don't, we'll yield:

        * ``self.item_kls()([p1, p2])``
        * ``m1``
        * ``self.item_kls()([p3])``
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
                    yield self.item_kls()(buf)
                    buf = []
                yield p
        if buf:
            yield self.item_kls()(buf)
