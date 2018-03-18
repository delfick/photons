"""
Collection objects for various information.

These allow addons to be able to register more functionality.
"""
from photons_app.errors import TargetNotFound, ResolverNotFound
from photons_app.special import ResolveReferencesFromFile

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta

class Target(dictobj.Spec):
    """
    Represent the info required for specifying how to get messages to a device

    Note that this is just the options for the target, to get the target itself
    use the target_register instead.

    For example:

    .. code-block:: python

        t = collector.configuration["target_register"].resolve("prod_api")
    """
    type = dictobj.Field(sb.string_spec, wrapper=sb.required)
    optional = dictobj.Field(sb.boolean, default=False)
    options = dictobj.Field(sb.dictionary_spec)

class TargetRegister(object):
    """
    A register of target types and concrete instances of those targets.

    Usage is typically in an addon's option_merge hook:

    .. code-block:: python

        from option_merge_addons import option_merge_addon_hook

        @option_merge_addon_hook(post_register=True)
        def __lifx_post__(collector, **kwargs):
            collector.configuration["target_register"].register_type(
                  "my_amazing_target"
                , my_target_creator_spec()
                )

    Note the ``post_register=True``. This is required to be able to access the
    instantiated target_register.
    """

    # Tell option_merge not to wrap this in a MergedOptions when we get
    # it from a MergedOptions instance
    _merged_options_formattable = True

    def __init__(self, collector):
        self.types = {}
        self.targets = {}
        self.collector = collector

    @property
    def target_values(self):
        return [m()[1] for m in self.targets.values()]

    def type_for(self, name):
        """Given the name of a target, return it's type as a string"""
        if name is NotSpecified:
            return None
        if name not in self.targets:
            return None
        return self.targets[name]()[0]

    def desc_for(self, name):
        """Get us the description of a target, given it's name"""
        if name is NotSpecified:
            return None
        return getattr(self.targets[name]()[1], "description", "")

    def register_type(self, name, target):
        """Tell the register about a new target type"""
        self.types[name] = target

    def resolve(self, name):
        """Given the name of a target, return an instantiated copy of the target"""
        if name not in self.targets:
            raise TargetNotFound(name=name, available=list(self.targets.keys()))
        return self.targets[name]()[1]

    def add_targets(self, targets):
        """
        Register options for new targets

        This is a shortcut to calling self.add_target(name, target) for all targets.items()
        """
        for name, target in targets.items():
            self.add_target(name, target)

    def add_target(self, name, target):
        """
        Each target must reference a type that exists or be marked as optional

        We then put on the register a function that memoizes the instance of
        this target.
        """
        if target.type not in self.types:
            if target.optional:
                return
            raise TargetNotFound("Unknown type specified for target", name=name, specified=target.type, available=list(self.types.keys()))

        cache = {"info": None}

        def make():
            if cache["info"] is None:
                meta = Meta(self.collector.configuration, []).at("targets").at(name).at("options")
                cache["info"] = (target.type, self.types[target.type].normalise(meta, target.options))
            return cache["info"]

        self.targets[name] = make

class MessagesRegister(object):
    """
    A register for Photons Protocol Messages classes.

    These classes hold different message types for a particular protocol.

    Usage is typically in an addon's option_merge hook, via the protocol register:

    .. code-block:: python

        from option_merge_addons import option_merge_addon_hook

        @option_merge_addon_hook(post_register=True)
        def __lifx_post__(collector, **kwargs):
            [..]
            prot_register = collector.configuration["protocol_register"]
            prot_register.message_register(9001).add(MyAmazingMessages)
    """
    # Ensure option_merge gives back this instance without wrapping it
    _merged_options_formattable = True

    def __init__(self):
        self.message_classes = []

    def add(self, kls):
        self.message_classes.append(kls)

    def __iter__(self):
        return iter(self.message_classes)

class ProtocolRegister(object):
    """
    A register for Photons Protocol Messages classes.

    These classes hold different message types for a particular protocol.

    Usage is typically in an addon's option_merge hook.

    .. code-block:: python

        from option_merge_addons import option_merge_addon_hook

        @option_merge_addon_hook(post_register=True)
        def __lifx_post__(collector, **kwargs):
            [..]
            prot_register = collector.configuration["protocol_register"]
            prot_register.add(9001, MyProtocolPacket)
    """
    _merged_options_formattable = True

    def __init__(self):
        self.protocol_classes = {}

    def add(self, protocol, kls):
        self.protocol_classes[protocol] = (kls, MessagesRegister())

    def __getitem__(self, protocol):
        return self.protocol_classes[protocol]

    def __iter__(self):
        return iter(self.protocol_classes)

    def get(self, protocol, default=None):
        return self.protocol_classes.get(protocol, default)

    def message_register(self, protocol):
        return self.protocol_classes[protocol][1]

    def __getstate__(self):
        return {}

    def __setstate__(self, d):
        pass

class ReferenceResolerRegister(object):
    """
    A register for special reference resolvers

    Usage is typically in an addon's option_merge hook.

    .. code-block:: python

        from option_merge_addons import option_merge_addon_hook

        @option_merge_addon_hook(post_register=True)
        def __lifx_post__(collector, **kwargs):
            [..]
            register = collector.configuration["reference_resolver_register"]
            def resolve_my_type(options):
                '''
                options is a string of what was given after ``my_type:``

                Either return a list of serials or a SpecialReference object
                '''
                return ["d073d500001"]
            register.add("my_type", resolve_my_type)
    """
    _merged_options_formattable = True

    def __init__(self):
        self.resolvers = {
              "file": lambda filename, _: ResolveReferencesFromFile(filename)
            }

    def add(self, typ, resolver):
        self.resolvers[typ] = resolver

    def resolve(self, typ, options, target):
        if typ not in self.resolvers:
            raise ResolverNotFound(wanted=typ, available=list(self.resolvers))
        return self.resolvers[typ](options, target)
