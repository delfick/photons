from photons_transport.target.bridge import TransportBridge
from photons_transport.target.item import TransportItem

from photons_script.script import ScriptRunnerIterator, InvalidScript, Pipeline

from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
import binascii
import logging

log = logging.getLogger("photons_transport.target.target")

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

    ``protocols`` and ``final_fut_finder`` are retrieved automatically from
    ``Meta`` if we create the transport by doing
    ``TransportTarget.normalise(meta, **kwargs)``

    Generally you'll be passed in a transport via the ``tasks`` mechanism and
    you won't have to instantiate it yourself.
    """
    protocols = dictobj.Field(sb.overridden("{protocol_register}"), formatted=True)
    final_fut_finder = dictobj.Field(sb.overridden("{final_future}"), formatted=True)
    default_broadcast = dictobj.Field(sb.defaulted(sb.string_spec(), "255.255.255.255"))
    item_kls = lambda s: TransportItem
    bridge_kls = lambda s: TransportBridge
    description = dictobj.Field(sb.string_spec, default="Base transport functionality")

    def script(self, raw):
        """Return us a ScriptRunnerIterator for the given `raw` against this `target`"""
        items = list(self.simplify(raw))
        if len(items) > 1:
            items = Pipeline(*items)
        else:
            items = items[0]
        return ScriptRunnerIterator(items, target=self)

    async def args_for_run(self, found=None):
        """Create an instance of args_for_run. This is designed to be shared amongst many `script`"""
        afr = self.bridge_kls()(self.final_fut_finder(), self
            , protocol_register=self.protocols, found=found, default_broadcast=self.default_broadcast
            )
        await afr.start()
        return afr

    async def close_args_for_run(self, args_for_run):
        """Close an args_for_run"""
        args_for_run.finish()

    async def get_list(self, args_for_run, broadcast=sb.NotSpecified, **kwargs):
        """Return us the targets that we can find from this bridge"""
        addr = broadcast if broadcast is not sb.NotSpecified else self.default_broadcast
        found = await args_for_run.find_devices(addr, **kwargs)
        return sorted([binascii.hexlify(target[:6]).decode() for target in found])

    def device_forgetter(self, args_for_run):
        """Return a function that may be used to forget a device on this args_for_run"""
        return args_for_run.forget

    def find(self, args_for_run):
        """Return a function that may be used to find a device on this args_for_run"""
        return args_for_run.find

    def simplify(self, script_part, chain=None):
        """
        Used by ``self.script`` to convert ``raw`` into TransportItems

        For each leaf child that is found, we gather messages into groups of
        messages with a ``pack`` method and yield ``self.item_kls()(group)`` with
        messages that don't have a ``pack`` method yield as is.

        For example, let's say we have ``[p1, p2, m1, p3]`` where ``m1`` does
        not have a ``pack`` method and the others do, we'll yield:

        * ``self.item_kls()([p1, p2])``
        * ``m1``
        * ``self.item_kls()([p3])``
        """
        chain = [] if chain is None else chain
        if type(script_part) is not list:
            script_part = [script_part]

        final = []
        errors = []
        for p in script_part:
            if getattr(p, "has_children", False):
                final.append(p.simplified(self.simplify, chain + [p.name]))
                continue
            else:
                if not hasattr(p, "pack"):
                    errors.append(p)
                else:
                    final.append(p)

        if errors:
            raise InvalidScript("Script part has no pack method!", parts=errors, chain=chain)

        buf = []
        for p in final:
            if hasattr(p, "pack"):
                buf.append(p)
            else:
                if buf:
                    yield self.item_kls()(buf)
                    buf = []
                yield p
        if buf:
            yield self.item_kls()(buf)
