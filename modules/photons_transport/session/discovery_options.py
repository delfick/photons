from photons_messages import Services

from delfick_project.norms import dictobj, sb, BadSpecValue, Meta
from delfick_project.option_merge import MergedOptions
import binascii
import json
import os


class service_type_spec(sb.Spec):
    def normalise(self, meta, val):
        if isinstance(val, Services):
            return val

        val = sb.string_spec().normalise(meta, val)

        available = []
        for name, member in Services.__members__.items():
            if not name.startswith("RESERVED"):
                available.append(name)
                if name == val:
                    return member

        raise BadSpecValue("Unknown service type", want=val, available=sorted(available), meta=meta)


class hardcoded_discovery_spec(sb.Spec):
    def setup(self, see_env=True):
        self.spec = sb.dictof(serial_spec(), service_info_spec())
        self.see_env = see_env

    def normalise(self, meta, val):
        if "HARDCODED_DISCOVERY" in os.environ and self.see_env:
            meta = Meta(meta.everything, []).at("${HARDCODED_DISCOVERY}")
            try:
                val = json.loads(os.environ["HARDCODED_DISCOVERY"])
            except (TypeError, ValueError) as error:
                raise BadSpecValue(
                    "Found HARDCODED_DISCOVERY in environment, but it was not valid json",
                    reason=error,
                    meta=meta,
                )

        if val in (sb.NotSpecified, None):
            return val

        return self.spec.normalise(meta, val)


class service_info_spec(sb.Spec):
    def setup(self):
        self.spec = sb.dictof(
            service_type_spec(),
            sb.set_options(host=sb.required(sb.string_spec()), port=sb.required(sb.integer_spec())),
        )

    def normalise_filled(self, meta, val):
        val = self.expand(meta, val)
        return self.spec.normalise(meta, val)

    def expand(self, meta, val):
        if isinstance(val, str):
            return {"UDP": {"host": val, "port": 56700}}

        if isinstance(val, list):
            val = {"UDP": val}

        v = {}

        for service, options in val.items():
            if isinstance(options, str):
                options = {"host": options, "port": 56700}
            elif isinstance(options, list):
                if len(options) not in (1, 2):
                    raise BadSpecValue(
                        "A list must be [host] or [host, port]", got=options, meta=meta.at(service)
                    )
                if len(options) == 1:
                    options = {"host": options[0], "port": 56700}
                else:
                    options = {"host": options[0], "port": options[1]}
            v[service] = options

        return v


class serial_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        val = sb.string_spec().normalise(meta, val)

        if not val.startswith("d073d5"):
            raise BadSpecValue("serials must start with d073d5", got=val, meta=meta)
        if len(val) != 12:
            raise BadSpecValue(
                "serials must be 12 characters long, like d073d5001337", got=val, meta=meta
            )

        try:
            binascii.unhexlify(val)
        except binascii.Error as error:
            raise BadSpecValue("serials must be valid hex", error=error, got=val, meta=meta)

        return val


class serial_filter_spec(sb.Spec):
    def setup(self, see_env=True):
        self.see_env = see_env

    def normalise(self, meta, val):
        if "SERIAL_FILTER" in os.environ and self.see_env:
            val = os.environ["SERIAL_FILTER"].split(",")
            if val == ["null"]:
                return None
            meta = Meta(meta.everything, []).at("${SERIAL_FILTER}")
        if val in (None, sb.NotSpecified):
            return val
        return sb.listof(serial_spec()).normalise(meta, val)


class DiscoveryOptions(dictobj.Spec):
    """
    Used by NetworkSession to determine if we do broadcast discovery or hardcoded
    discovery and of that, whether to only include certain serials.

    the hardcoded_discovery option must be a dictionary of ``{serial: options}``
    where options may be the ip address as a string, an array of ``[ip, port]``
    or a dictionary of ``{"UDP": {"host": <ip>, "port": <port>}}``.

    serial_filter must be a list of serials or None. If a list of serials, then
    discovery will never give back serials not in the list.

    Note that regardless of what you specify, if you have an HARDCODED_DISCOVERY
    in your environment, then hardcoded_discovery will be based off that, and
    the same goes for serial_filter and SERIAL_FILTER env variable.
    """

    serial_filter = dictobj.Field(serial_filter_spec)
    hardcoded_discovery = dictobj.Field(hardcoded_discovery_spec)

    async def discover(self, add_service):
        found_now = set()
        for serial, services in self.hardcoded_discovery.items():
            if self.want(serial):
                found_now.add(binascii.unhexlify(serial)[:6])
                for service, options in services.items():
                    await add_service(serial, service, **options)
        return found_now

    def want(self, serial):
        if not self.serial_filter or self.serial_filter is sb.NotSpecified:
            return True
        return serial in self.serial_filter

    @property
    def has_hardcoded_discovery(self):
        return self.hardcoded_discovery and self.hardcoded_discovery is not sb.NotSpecified


class NoDiscoveryOptions(DiscoveryOptions):
    """
    A DiscoveryOptions object that will never have hardcoded_discovery or
    serial_filter
    """

    serial_filter = dictobj.Field(sb.overridden(None))
    hardcoded_discovery = dictobj.Field(sb.overridden(None))


class NoEnvDiscoveryOptions(DiscoveryOptions):
    """
    A DiscoveryOptions that doesn't care about environment variables
    """

    serial_filter = dictobj.Field(serial_filter_spec(see_env=False))
    hardcoded_discovery = dictobj.Field(hardcoded_discovery_spec(see_env=False))


class discovery_options_spec(sb.Spec):
    def setup(self):
        self.spec = DiscoveryOptions.FieldSpec()

    def normalise(self, meta, val):
        val = self.spec.normalise(meta, val)

        if "discovery_options" not in meta.everything:
            return val

        base = meta.everything["discovery_options"].clone()

        if val.hardcoded_discovery is not sb.NotSpecified:
            if not base.hardcoded_discovery or val.hardcoded_discovery is None:
                base.hardcoded_discovery = val.hardcoded_discovery
            else:
                hardcoded_discovery = val.hardcoded_discovery
                if isinstance(base.hardcoded_discovery, dict):
                    opts = MergedOptions.using(base.hardcoded_discovery, val.hardcoded_discovery)
                    hardcoded_discovery = opts.as_dict()
                base.hardcoded_discovery = hardcoded_discovery
        elif isinstance(base.hardcoded_discovery, dict):
            base.hardcoded_discovery = MergedOptions.using(base.hardcoded_discovery).as_dict()

        if val.serial_filter is not sb.NotSpecified:
            base.serial_filter = val.serial_filter
        elif isinstance(base.serial_filter, list):
            base.serial_filter = list(base.serial_filter)

        return base
