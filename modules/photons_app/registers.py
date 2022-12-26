"""
Collection objects for various information.

These allow addons to be able to register more functionality.
"""
from delfick_project.norms import dictobj, sb
from photons_app.errors import (
    ProgrammerError,
    ResolverNotFound,
    TargetNotFound,
    TargetTypeNotFound,
)
from photons_app.special import (
    FoundSerials,
    HardCodedSerials,
    ResolveReferencesFromFile,
    SpecialReference,
)


class ReadOnlyDictionary(dict):
    """
    Used to get a dictionary that cannot be modified once it is
    locked by setting ``_lock`` to ``True``.
    """

    _lock = False

    def __setitem__(self, name, value):
        if self._lock:
            raise KeyError("This dictionary is read only")
        super().__setitem__(name, value)

    def __delitem__(self, name):
        if self._lock:
            raise KeyError("This dictionary is read only")
        super().__delitem__(name)

    def clear(self):
        if self._lock:
            raise KeyError("This dictionary is read only")
        super().clear()

    def pop(self, name):
        if self._lock:
            raise KeyError("This dictionary is read only")
        super().pop(name)

    def popitem(self):
        if self._lock:
            raise KeyError("This dictionary is read only")
        super().popitem()

    def update(self, dict=None):
        if self._lock:
            raise KeyError("This dictionary is read only")
        super().update(dict=dict)


class Target(dictobj.Spec):
    """
    Represent the info required for specifying how to get messages to a device

    Note that this is just the options for the target, to get the target itself
    use the target_register instead.

    For example:

    .. code-block:: python

        t = collector.configuration["target_register"].resolve("lan")

    Or from the collector:

    .. code-block:: python

        t = collector.resolve_target("lan")
    """

    type = dictobj.Field(sb.string_spec, wrapper=sb.required)
    optional = dictobj.Field(sb.boolean, default=False)
    options = dictobj.Field(sb.dictionary_spec)


class TargetRegister:
    """
    A register of target types and concrete instances of those targets.

    Usage is typically in an addon's hook:

    .. code-block:: python

        from delfick_project.addons import addon_hook

        @addon_hook(post_register=True)
        def __lifx_post__(collector, **kwargs):
            collector.configuration["target_register"].register_type(
                  "my_amazing_target"
                , my_target_creator_spec()
                )

    Note the ``post_register=True``. This is required to be able to access the
    instantiated target_register.

    Once you have a setup target_register, you may resolve a target on it. For
    example, if in your configuration you've defined a ``lan`` target called
    ``home_lan``, then you may get one of these by saying:

    .. code-block:: python

        home_lan_target = collector.resolve_target("home_lan")

        # Which will do this for you on the known target_register
        home_lan_target = target_register.resolve("home_lan")

    Note the result will be cached and multiple calls to this will return the
    same target object.

    You may restrict what types of targets you can add and access using a restriction.

    For example:

    .. code-block:: python

        restricted_register = target_register.restricted(target_types=["http"])

    This restricted_register will operate on the same underlying data structures but
    make it appear like you only have targets of the type ``http``.
    """

    _merged_options_formattable = True

    class Restriction:
        """
        Used to filter out restricted targets based on the name or type of the target
        """

        def __init__(self, *, target_types=None, target_names=None):
            self.target_types = target_types
            self.target_names = target_names

        def __repr__(self):
            if self.target_types is None and self.target_names is None:
                return "<Unrestricted>"

            restrictions = []
            if self.target_types is not None:
                restrictions.append(
                    f"restricted_types='{','.join(str(t) for t in self.target_types)}'"
                )
            if self.target_names is not None:
                restrictions.append(
                    f"restricted_names='{','.join(str(n) for n in self.target_names)}'"
                )

            return f"<Restrictions {' '.join(restrictions)}>"

        def allows(self, name, typ, target, creator):
            if self.target_names is not None and name not in self.target_names:
                return False

            if self.target_types is not None and target.type not in self.target_types:
                return False

            return True

    def __init__(self, clone_from=None):
        if clone_from is not None:
            self.types = clone_from.types
            self.created = clone_from.created
            self._registered = clone_from._registered
        else:
            self.types = {}
            self.created = {}
            self._registered = {}

        self.restriction = self.Restriction()

    def __getitem__(self, name):
        """Return a registered target template, or complain if one is not available under this name"""
        if not isinstance(name, str):
            raise ProgrammerError(f"Targets are key'd by their name but using {name}")

        if name in (None, sb.NotSpecified) or name not in self.registered:
            raise TargetNotFound(wanted=name, available=sorted(self.registered))

        return self.registered[name]

    def __contains__(self, name):
        if name in ("", None, sb.NotSpecified):
            return False

        for n, v in self.created.items():
            if v is name:
                name = n
                break

        return name in self.registered

    @property
    def registered(self):
        """Return our registered targets, taking the restriction into account"""
        # It is important this dictionary isn't modified as if we
        # were actually registered targets
        ret = ReadOnlyDictionary()

        for name, target in self._registered.items():
            if self.restriction.allows(name, *target):
                ret[name] = target

        ret._lock = True
        return ret

    def restricted(self, **restrictions):
        """
        Return this target register but with a different restriction

        Note this replaces the restriction rather than adding to it
        """
        register = self.__class__(clone_from=self)
        register.restriction = self.Restriction(**restrictions)
        return register

    @property
    def used_targets(self):
        """Return the target objects that have been resolved"""
        return list(self.created.values())

    def type_for(self, name):
        """Given the name of a target, return it's type as a string"""
        return self[name][0]

    def desc_for(self, name):
        """Get us the description of a target, given it's name"""
        t = self.resolve(name)
        return getattr(t, "description", "") or t.__doc__ or ""

    def register_type(self, name, target):
        """Tell the register about a new target type"""
        self.types[name] = target

    def resolve(self, name):
        """Given the name of a target, return an instantiated copy of the target"""
        for n, v in self.created.items():
            if v is name:
                name = n
                break

        if not isinstance(name, str) or name not in self:
            raise TargetNotFound(wanted=name, available=sorted(self.registered))

        if name not in self.created:
            typ, target, creator = self[name]
            self.created[name] = creator(name, self.types[typ], target)

        return self.created[name]

    def add_target(self, name, target, creator):
        """
        Each target must reference a type that exists or be marked as optional

        We then put on the register a function that memoizes the instance of
        this target.
        """
        if target.type not in self.types:
            if target.optional:
                return
            raise TargetTypeNotFound(
                target=name,
                wanted=target.type,
                available_types=sorted(self.types),
            )

        self._registered[name] = (target.type, target, creator)


class MessagesRegister:
    """
    A register for Photons Protocol Messages classes.

    These classes hold different message types for a particular protocol.

    Usage is typically in an addon's hook, via the protocol register:

    .. code-block:: python

        from delfick_project.addons import addon_hook

        @addon_hook(post_register=True)
        def __lifx_post__(collector, **kwargs):
            [..]
            prot_register = collector.configuration["protocol_register"]
            prot_register.message_register(9001).add(MyAmazingMessages)
    """

    # Ensure delfick_project.option_merge gives back this instance without wrapping it
    _merged_options_formattable = True

    def __init__(self):
        self.message_classes = []

    def add(self, kls):
        self.message_classes.append(kls)

    def __iter__(self):
        return iter(self.message_classes)


class ProtocolRegister:
    """
    A register for Photons Protocol Messages classes.

    These classes hold different message types for a particular protocol.

    Usage is typically in an addon's hook.

    .. code-block:: python

        from delfick_project.addons import addon_hook

        @addon_hook(post_register=True)
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


class ReferenceResolverRegister:
    """
    A register for special reference resolvers

    Usage is typically in an addon's hook.

    .. code-block:: python

        from delfick_project.addons import addon_hook

        @addon_hook(post_register=True)
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
        self.resolvers = {"file": lambda filename: ResolveReferencesFromFile(filename)}

    def add(self, typ, resolver):
        self.resolvers[typ] = resolver

    def resolve(self, typ, options):
        if typ not in self.resolvers:
            raise ResolverNotFound(wanted=typ, available=list(self.resolvers))
        return self.resolvers[typ](options)

    def reference_object(self, reference=sb.NotSpecified):
        """
        * NotSpecified, "", None or _ are seen as all serials on the network
        * ``typ:options`` is given resolved using our resolvers
        * otherwise we return a HardCodedSerials with the provided reference
        """
        if isinstance(reference, SpecialReference):
            return reference

        if reference in ("", "_", None, sb.NotSpecified):
            return FoundSerials()

        if type(reference) is str:
            if ":" in reference:
                typ, options = reference.split(":", 1)
                reference = self.resolve(typ, options)

        if isinstance(reference, SpecialReference):
            return reference

        return HardCodedSerials(reference)
