"""
To create a packet class we use ``dictobj.PacketSpec`` which is defined here.

This is reponsble for creating a ``Meta`` class on the class that contains
information about the different groups and fields on the packet.

It is comprised of a mixin class providing functionality for the packet and a
meta class for making the ``Meta``.

Usage looks like:

.. code-block:: python

    from input_algorithms.dictobj import dictobj

    class MyPacket(dictobj.PacketSpec):
        fields = [
              ("field_one", field_one_type)
            , ("field_two", field_two_type)
            ]

where the ``*_type`` objects have information related to the type for that
field. See ``photons_protocol.types`` for builtin types.

.. autoclass:: photons_protocol.packets.PacketSpecMetaKls

.. autoclass:: photons_protocol.packets.PacketSpecMixin
    :members:

LIFXPacket
----------

Photons protocol also defines the ``parent_packet`` for the LIFX binary protocol.

.. autoclass:: photons_protocol.frame.LIFXPacket
"""
from photons_protocol.packing import PacketPacking, val_to_bitarray
from photons_protocol.types import Optional, Type as T

from photons_app.errors import ProgrammerError

from input_algorithms.dictobj import dictobj, FieldSpecMetakls
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from bitarray import bitarray
from functools import partial
import binascii
import logging
import json

log = logging.getLogger("photons_protocol.packets")

class Initial:
    """Used for the default values on Packet groups"""

class packet_spec(sb.Spec):
    """
    When you call Packet.spec, you are creating an instance of this.

    This allows us to provide the pkt when making field specs; that has all fields
    up to the current field set on it.
    """
    def __init__(self, kls, attrs, name_to_group):
        self.kls = kls
        self.attrs = attrs
        self.name_to_group = name_to_group

    def normalise(self, meta, val):
        val = sb.dictionary_spec().normalise(meta, val)

        pkt = self.kls()
        for attr, spec in self.attrs:
            if callable(spec):
                spec = spec(pkt, False)

            v = val.get(attr, sb.NotSpecified)
            if attr not in val and attr in self.name_to_group:
                g = self.name_to_group[attr]
                if g in val and attr in val[g]:
                    v = val[g][attr]

            v = spec.normalise(meta.at(attr), v)
            dictobj.__setitem__(pkt, attr, v)

        return pkt

class PacketSpecMixin:
    """
    Functionality for our packet.
    """
    def pack(self, payload=None, parent=None, serial=None, packing_kls=PacketPacking):
        """
        Return us a ``bitarray`` representing this packet.
        """
        return packing_kls.pack(self, payload, parent, serial)

    @classmethod
    def unpack(kls, value, packing_kls=PacketPacking):
        """
        Unpack a ``value`` into an instance of this class.
        """
        return packing_kls.unpack(kls, value)

    @classmethod
    def size_bits(kls, values):
        """Return the number of bits this packet requires. """
        total = 0
        for name, typ in kls.Meta.field_types:
            if callable(typ.size_bits):
                total += typ.size_bits(values)
            else:
                total += typ.size_bits
        return total

    @classmethod
    def spec(kls):
        """
        Return an ``input_algorithms`` specification that creates an instance
        of this class from a dictionary of values

        If this is a parent_packet with a group having message_type of 0 then that field
        is added to the spec and requires a T.Bytes
        """
        attrs = []
        for name, typ in kls.Meta.all_field_types:
            attrs.append((name, typ.spec))

        if getattr(kls, "parent_packet", False):
            for key, typ in kls.Meta.field_types:
                if getattr(typ, "message_type", None) == 0:
                    attrs.append((key, T.Bytes.spec))

        return packet_spec(kls, attrs, kls.Meta.name_to_group)

    def __or__(self, kls):
        """
        Determine if this object is of type ``kls``. It does this by looking at
        the ``protocol`` and ``message_type`` values on the ``kls.Payload`` and this
        instance and returning whether they are equal.
        """
        this_protocol = dictobj.__getitem__(self, "protocol")
        this_protocol = this_protocol if this_protocol is not sb.NotSpecified else self.protocol
        if this_protocol != kls.Payload.Meta.protocol:
            return False

        this_pkt_type = dictobj.__getitem__(self, "pkt_type")
        this_pkt_type = this_pkt_type if this_pkt_type is not sb.NotSpecified else self.pkt_type
        return this_pkt_type == kls.Payload.message_type

    def actual(self, key):
        """Return the actual value at this key, rather than a normalised value"""
        return self.__getitem__(key, do_spec=False)

    @property
    def is_dynamic(self):
        """Says whether any of the field values are created by a function"""
        for f, t in self.Meta.all_field_types:
            if t._allow_callable:
                if callable(self.actual(f)):
                    return True
        return False

    def __contains__(self, key):
        """Return whether this object has this key in it's fields or groups"""
        return any(k == key for k in self.Meta.all_names) or any(k == key for k in self.Meta.groups)

    def __getitem__(self, key
        , do_spec=True, do_transform=True, parent=None, serial=None, allow_bitarray=False, unpacking=True
        ):
        """
        Dictionary access for a key on the object

        This works for groups as well where the values in the fields for that
        group are returned as a dictionary.

        This process will use ``input_algorithms`` to ensure the value you get
        back is normalised. Unless ``do_spec`` is ``False``.

        We will also use the type transform unless ``do_transform`` is ``False``.

        And finally if the do_spec is True and we get back a bitarray and allow_bitarray is False,
        we will return the result of calling tobytes on that object.
        """
        M = object.__getattribute__(self, "Meta")

        # If we're requesting one of the groups, then we must assemble from the keys in that group
        # Unless the group is an empty Payload (message_type of 0 on the type)
        # In that case, there are no fields, so we return as it is found on the class
        # (__setitem__ has logic to store this group on the class as is)
        if key in M.groups:
            field_types = M.field_types_dict
            if key in field_types and getattr(field_types[key], "message_type", None) != 0:
                final = field_types[key]()
                for k in M.groups[key]:
                    actual = self.actual(k)
                    if actual is sb.NotSpecified:
                        final[k] = self.__getitem__(k, parent=self, serial=serial)
                    else:
                        dictobj.__setitem__(final, k, self.actual(k))
                return final

        try:
            actual = super(dictobj, self).__getitem__(key)
        except KeyError:
            if key not in M.all_names and key not in M.groups:
                raise
            actual = sb.NotSpecified

        if key in M.groups and actual is not sb.NotSpecified:
            # Can only mean we have an empty payload group here
            b = val_to_bitarray(actual, doing="Converting payload from parent packet")
            if not allow_bitarray:
                return b.tobytes()
            else:
                return b

        if do_spec and key in M.all_names:
            typ = M.all_field_types_dict[key]
            return object.__getattribute__(self, "getitem_spec")(typ
                , key, actual, parent, serial, do_transform, allow_bitarray, unpacking
                )

        return actual

    def getitem_spec(self, typ, key, actual, parent, serial, do_transform, allow_bitarray, unpacking):
        """
        Used by __getitem__ to use the spec on the type to transform the ``actual`` value
        """
        if typ._allow_callable:
            if callable(actual):
                actual = actual(parent or self, serial)

        spec = typ.spec(self, unpacking, transform=False)
        res = spec.normalise(Meta.empty().at(key), actual)

        if do_transform and unpacking and res is not sb.NotSpecified and res is not Optional:
            res = typ.untransform(res)

        if type(res) is bitarray and not allow_bitarray:
            return res.tobytes()
        else:
            return res

    def __getattr__(self, key):
        """Object access for keys, this essentially is the same as dictionary access"""
        if key in object.__getattribute__(self, "Meta").groups:
            return self[key]
        if key in object.__getattribute__(self, "Meta").all_names:
            return self[key]
        return dictobj.__getattr__(self, key)

    def __setattr__(self, key, val):
        """Setting values on the object"""
        if key in self.Meta.groups or key in self.Meta.all_names:
            self[key] = val
        else:
            dictobj.__setattr__(self, key, val)

    def __setitem__(self, key, val):
        """
        Set values on the object

        This will unpack dictionaries if we are setting a dictionary for a group
        field.

        We also see if a field has a transform option and use it if it's there
        """
        if key in self.Meta.groups:
            if val is Initial:
                # Special case because of the logic in dictobj that sets default values on initialization
                # Should only happen for group fields where it makes no sense
                return

            self._set_group_item(key, val)
            return

        # If our type has a transformation, apply it to our value
        # The assumption is that if there is a transformation,
        # The value will always be given with the transformation in mind
        # untransform will be used when extracting the value
        typ = self.Meta.all_field_types_dict.get(key)
        if typ and typ._transform is not sb.NotSpecified and val not in (sb.NotSpecified, Optional):
            val = typ.do_transform(self, val)

        # Otherwise we set directly on the packet
        dictobj.__setitem__(self, key, val)

    def _set_group_item(self, key, val):
        """
        Used by __setitem__ to put a group field onto the packet

        Ensures:
        * Empty payload group is only filled by str/bytes/bitarray
        * sb.NotSpecified translates to setting that for all the fields in the group
        * When val is an instance of the type for this group, we transfer values directly
        * Non empty payload groups is filled by something with items()
          so we can then set the values for the fields in the group
        """
        typ = self.Meta.field_types_dict.get(key)
        if getattr(typ, "message_type", None) is 0:
            # Message_type of 0 indicates an empty Payload
            # So we store the whole thing as is on the packet
            # We also make sure this is a str (hexlified bytes), bytes or bitarray
            # __getitem__ has the opposite logic to grab this group as is
            if type(val) not in (bytes, bitarray, str):
                msg = "Setting non bytes payload on a packet that doesn't know what fields it's payload has"
                raise ValueError("{0}\tkey={1}\tgot={2}".format(msg, key, repr(val)))

            dictobj.__setitem__(self, key, val)
            return

        if val is sb.NotSpecified:
            for field in self.Meta.groups[key]:
                if field in self:
                    self[field] = sb.NotSpecified
            return

        # if we're setting a group from an instance of the group
        # then just steal the raw values without the transform dance
        if hasattr(typ, "Meta") and issubclass(type(val), typ):
            field_types = typ.Meta.field_types_dict
            for field, v in val.items():
                if field in field_types:
                    dictobj.__setitem__(self, field, v)
            return

        # We're setting a group, we need to get things from the group via items
        if not hasattr(val, "items"):
            msg = "Setting a group on a packet must be done with a value that has an items() method"
            raise ValueError("{0}\tkey={1}\tgot={2}".format(msg, key, repr(val)))

        # Set from our value
        for field, v in val.items():
            if field in self.Meta.groups[key]:
                self[field] = v

    def clone(self, overrides=None):
        """
        Efficiently create a shallow copy of this packet without going
        through input_algorithms

        The exception is anything in overrides will go through input_algorithms
        """
        clone = self.__class__()

        for key, value in self.items():
            if overrides and key in overrides:
                clone[key] = overrides[key]
            else:
                dictobj.__setitem__(clone, key, value)

        return clone

    def simplify(self, serial=None):
        """
        Return us an instance of the ``parent_packet``

        But with the payload as a packed bitarray.
        """
        if self.parent_packet:
            return self

        parent = self.Meta.parent
        final = parent()
        last_group_name, _ = parent.Meta.field_types[-1]

        # Set all the keys but those found in the payload
        # Because we get all_names from the payload, we are ignoring those in the actual payload
        for key in parent.Meta.all_names:
            final[key] = self.__getitem__(key, serial=serial, parent=self)

        # And set our packed payload
        final[last_group_name] = self[last_group_name].pack(parent=self, serial=serial)

        return final

    def tobytes(self, serial):
        """
        Convert this packet into bytes

        Also, if not already simplified, then we first simplify it with the specified serial
        """
        payload = self.actual("payload")

        if type(payload) is str:
            payload = binascii.unhexlify(payload)

        if type(payload) is bytes:
            b = bitarray(endian="little")
            b.frombytes(payload)
            payload = b

        if type(payload) is bitarray:
            return self.pack(payload=payload).tobytes()
        else:
            return self.simplify(serial).pack().tobytes()

    def as_dict(self, transformed=True):
        """Return this packet as a normal python dictionary"""
        final = {}
        groups = self.Meta.groups
        for name in self.Meta.all_names:
            val = self.__getitem__(name, do_transform=transformed)

            if val is Optional:
                continue

            if type(val) is list:
                newval = []
                for thing in val:
                    if hasattr(thing, "as_dict"):
                        newval.append(thing.as_dict())
                    else:
                        newval.append(thing)
                val = newval

            gs = [group for group, names in groups.items() if name in names]
            if gs:
                if gs[0] not in final:
                    final[gs[0]] = {}
                final[gs[0]][name] = val
            else:
                final[name] = val

        if self.Meta.groups and getattr(self, "parent_packet", False):
            name, typ = self.Meta.field_types[-1]
            if getattr(typ, "message_type", None) is 0:
                final[name] = self.__getitem__(name, do_transform=transformed)

        return final

    def __repr__(self):
        """Return this packet as a jsonified string"""
        def reprer(o):
            if type(o) is bytes:
                return binascii.hexlify(o).decode()
            elif type(o) is bitarray:
                return binascii.hexlify(o.tobytes()).decode()
            return repr(o)
        return json.dumps(self.as_dict(), sort_keys=True, default=reprer)

    @classmethod
    def empty_normalise(kls, **kwargs):
        """Create an instance of this class from keyword arguments"""
        return kls.normalise(Meta.empty(), kwargs)

    @classmethod
    def normalise(kls, meta, val):
        """Create an instance of this class from a dictionary"""
        return kls.spec().normalise(meta, val)

class PacketSpecMetaKls(FieldSpecMetakls):
    """
    Modify the creation of a class to act as a photons packet.

    * Make sure all the fields don't contain duplicate field names
    * Create Meta class

      The Meta has the following attributes:

      groups
        Dictionary of group name to name of fields in that group

      all_names
        List of all the names of all the fields

      field_types
        dictionary of field name to field type

      format_types
        list of all the field types

      all_field_types
        list of ``(name, type)`` for all the fields

      original_fields
        The original ``fields`` attribute on the class

    * Replace the ``fields`` attribute with all the fields from the groups
    * Ensure the class has the ``PacketSpecMixin`` class as a base class
    """
    def __new__(metaname, classname, baseclasses, attrs):
        groups = {}
        all_names = []
        all_fields = []
        field_types = []
        format_types = []
        name_to_group = {}

        fields = attrs.get("fields")
        if fields is None:
            for kls in baseclasses:
                if hasattr(kls, "Meta") and hasattr(kls.Meta, "original_fields"):
                    fields = kls.Meta.original_fields

        if fields is None:
            msg = "PacketSpecMixin expects a fields attribute on the class or a PacketSpec parent"
            raise ProgrammerError("{0}\tcreating={1}".format(msg, classname))

        if type(fields) is dict:
            msg = "PacketSpecMixin expect fields to be a list of tuples, not a dictionary"
            raise ProgrammerError("{0}\tcreating={1}".format(msg, classname))

        for name, typ in fields:
            if isinstance(typ, str):
                typ = attrs[typ]

            if hasattr(typ, "Meta"):
                groups[name] = []
                for n, _ in typ.Meta.field_types:
                    groups[name].append(n)
                    name_to_group[n] = name
                all_fields.extend(typ.Meta.field_types)
                all_names.extend(groups[name])
            else:
                all_names.append(name)
                all_fields.append((name, typ))
            format_types.append(typ)
            field_types.append((name, typ))

        if len(set(all_names)) != len(all_names):
            raise ProgrammerError("Duplicated names!\t{0}".format([name for name in all_names if all_names.count(name) > 1]))

        class MetaRepr(type):
            def __repr__(self):
                return "<type {0}.Meta>".format(classname)

        Meta = type.__new__(MetaRepr, "Meta", ()
            , { "multi": None
              , "groups": groups
              , "all_names": all_names
              , "field_types": field_types
              , "format_types": format_types
              , "name_to_group": name_to_group
              , "all_field_types": all_fields
              , "original_fields": fields

              , "field_types_dict": dict(field_types)
              , "all_field_types_dict": dict(all_fields)
              }
            )

        attrs["Meta"] = Meta

        def dflt(in_group):
            return Initial if in_group else sb.NotSpecified
        attrs["fields"] = [(name, partial(dflt, name in groups)) for name in (list(all_names) + list(groups.keys()))]

        kls = type.__new__(metaname, classname, baseclasses, attrs)

        already_attributes = []
        for field in all_names:
            if hasattr(kls, field):
                already_attributes.append(field)
        if already_attributes:
            raise ProgrammerError("Can't override attributes with fields\talready_attributes={0}".format(sorted(already_attributes)))

        return kls

dictobj.PacketSpec = type.__new__(PacketSpecMetaKls, "PacketSpec", (PacketSpecMixin, dictobj), {})
