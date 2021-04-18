from interactor.commander.spec_description import signature
from interactor.request_handlers import MessageFromExc
from interactor.commander.errors import NoSuchPacket

from photons_app.formatter import MergedOptionStringFormatter

from photons_messages import protocol_register

from delfick_project.norms import dictobj, Meta
from textwrap import dedent
import asyncio


def find_packet(pkt_type):
    """
    Find the class that represents this pkt type.

    We assume protocol 1024 and can match pkt_type as the number for that packet
    or the name of the class photons gives that number.

    For example, ``find_packet(protocol_register, 117)`` is the same as
    ``find_packet(protocol_register, "SetPower")``
    """
    for messages in protocol_register.message_register(1024):
        for typ, kls in messages.by_type.items():
            if typ == pkt_type or kls.__name__ == pkt_type:
                return kls

    raise NoSuchPacket(wanted=pkt_type)


def make_message(pkt_type, pkt_args):
    """
    Find the packet class for this ``pkt_type`` and instantiate it with
    the provided ``pkt_args``.
    """
    kls = find_packet(pkt_type)
    if pkt_args is not None:
        return kls.create(pkt_args)
    else:
        return kls()


class ResultBuilder:
    """
    Responsible for creating a result to return.

    The result from calling as_dict on the ResultBuilder looks like::

        { "results":
          { <serial>:
            { "pkt_type": <integer>
            , "pkt_name": <string>
            , "payload": <dictionary>
            }
          , <serial>:
            [ { "pkt_type", "pkt_name", "payload" }
            , { "pkt_type", "pkt_name", "payload" }
            ]
          , <serial>: {"error": <error>}
          , <serial>: "ok"
          }
        , "errors":
          [ <error>
          , <error>
          ]
        }

    Where ``errors`` only appears if there were errors that can't be assigned to
    a particular serial.

    The result for each ``serial`` in ``results`` is a dictionary if there was only
    one reply for that serial, otherwise a list of replies.

    Each reply is displayed as the ``pkt_type``, ``pkt_name`` and ``payload`` from that
    reply.

    If there were no replies for a serial then we display ``"ok"`` for that serial.

    There are two methods on the result builder:

    add_packet(pkt)
        Takes in a new packet to put in the result.

    error(e)
        Record an error in the result
    """

    def __init__(self, serials=None):
        self.serials = [] if serials is None else serials
        self.result = {"results": {}}

    def add_serials(self, serials):
        for serial in serials:
            if serial not in self.serials:
                self.serials.append(serial)

    def as_dict(self):
        res = dict(self.result)
        res["results"] = dict(res["results"])
        for serial in self.serials:
            if serial not in res["results"]:
                res["results"][serial] = "ok"
        return res

    def add_packet(self, pkt):
        info = {
            "pkt_type": pkt.__class__.Payload.message_type,
            "pkt_name": pkt.__class__.__name__,
            "payload": {
                key: val for key, val in pkt.payload.as_dict().items() if "reserved" not in key
            },
        }

        if pkt.serial in self.result["results"]:
            existing = self.result["results"][pkt.serial]
            if type(existing) is list:
                existing.append(info)
            else:
                self.result["results"][pkt.serial] = [existing, info]
        else:
            self.result["results"][pkt.serial] = info

    def error(self, e):
        msg = MessageFromExc()(type(e), e, e.__traceback__)

        serial = None
        if hasattr(e, "kwargs") and "serial" in e.kwargs:
            serial = e.kwargs["serial"]

        if type(msg["error"]) is dict and "serial" in msg["error"]:
            del msg["error"]["serial"]

        if serial:
            self.result["results"][serial] = msg
        else:
            if "errors" not in self.result:
                self.result["errors"] = []
            self.result["errors"].append(msg)


def fields_description(kls):
    """
    yield (name, type_info, help) for all the fields on our kls

    Where type_info looks something like `integer (required)` or `string (default "blah")`

    and fields that have no help are skipped
    """
    final_specs = (
        kls.FieldSpec(formatter=MergedOptionStringFormatter).make_spec(Meta.empty()).kwargs
    )

    for name, field in kls.fields.items():
        hlp = ""
        if type(field) is tuple:
            hlp, field = field
        else:
            hlp = field.help

        spec = final_specs[name]
        if isinstance(field, dictobj.NullableField):
            spec = spec.spec.specs[1]

        if hlp:
            yield name, " ".join(signature(spec)), dedent(hlp).strip()


class memoized_iterable:
    """
    A decorator that returns a descriptor providing a cache for an async
    generator.

    This provides a proeprty on your instance that can let you either stream
    results asynchronously or await all results.

    In either case, the decorated generator will only be iterated once.

    When streaming results, you may break before the iteration is complete and
    the next time you retrieve results, all results so far will be yielded
    before the iteration is continued and those results are cached and returned

    If an exception is raised by the generator then the generator is reset and
    the cached results are cleared.
    """

    class Empty:
        pass

    class Proxy:
        def __init__(self, instance, func):
            self.func = func
            self.instance = instance

            self.gen = False
            self.lock = asyncio.Lock()
            self.results = []

        def __aiter__(self):
            return self.stream()

        def __await__(self):
            return (yield from self.get_all().__await__())

        def __repr__(self):
            return f"<AsyncIteratorProxy: {repr(self.func)}>"

        @property
        def __name__(self):
            return self.func.__name__

        @property
        def __doc__(self):
            return self.func.__doc__

        async def get_all(self):
            results = []
            async for result in self.stream():
                results.append(result)
            return results

        async def stream(self):
            async with self.lock:
                if self.gen is False:
                    self.gen = self.func(self.instance)

                for result in self.results:
                    yield result

                if self.gen is None:
                    return

                while True:
                    try:
                        result = await self.gen.asend(None)
                    except StopAsyncIteration:
                        self.gen = None
                        break
                    except Exception:
                        self.gen = False
                        self.results = []
                        raise
                    else:
                        self.results.append(result)
                        yield result

    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.cache_name = "_{0}".format(self.name)

    def __get__(self, instance=None, owner=None):
        if instance is None:
            return self

        if getattr(instance, self.cache_name, self.Empty) is self.Empty:
            setattr(instance, self.cache_name, self.Proxy(instance, self.func))
        return getattr(instance, self.cache_name)

    def __delete__(self, instance):
        if hasattr(instance, self.cache_name):
            delattr(instance, self.cache_name)
