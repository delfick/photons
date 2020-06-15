from photons_protocol.constants import Unset, Optional
from photons_protocol.packet_meta import PacketMeta
from photons_protocol.encoder import packet_encoder
from photons_protocol.errors import BadConversion
from photons_protocol.fields import FieldList

from photons_app.errors import ProgrammerError, PhotonsAppError

from delfick_project.norms import dictobj, Meta
from bitarray import bitarray
import itertools
import logging

log = logging.getLogger("photons_protocol.packets")


class InvalidCreation(PhotonsAppError):
    pass


class Information:
    def __init__(self, remote_addr=None, sender_message=None):
        self.remote_addr = remote_addr
        self.sender_message = sender_message

    def update(self, *, remote_addr, sender_message):
        self.remote_addr = remote_addr
        self.sender_message = sender_message


class PacketSpecMixin:
    """
    Functionality for our packet.
    """

    @classmethod
    def create(kls, _val=None, **kwargs):
        val = _val

        if val and kwargs:
            raise InvalidCreation(
                "Creating a packet must be done with either a value, or keyword arguments",
                val=val,
                kwargs=kwargs,
            )

        if isinstance(val, dictobj.PacketSpec):
            if kls == val.Meta.parent:
                return val.simplify()

            if isinstance(val, kls):
                return val

            parent = kls.Meta.parent
            if parent and isinstance(val, parent):
                return kls.create(val.pack())

            msg = None
            kwargs = {}
            for (hn, ht, hd), (gn, gt, gd) in itertools.zip_longest(
                kls.Meta.fields, val.Meta.fields
            ):
                if hd or gd:
                    msg = "Cannot assert if the two packets are the same because a field is dynamic"
                    if hd:
                        kwargs["dynamic_field_have"] = hn
                    if gd:
                        kwargs["dynamic_field_got"] = gn
                    break

                if hn != gn:
                    msg = "Packet has different fields"
                    break

                elif ht != gt:
                    msg = "Packet has different field types"
                    break

            if msg:
                raise InvalidCreation(msg, want=kls.__name__, got=type(val).__name__, **kwargs)

        return kls.Meta.spec().normalise(Meta.empty(), val or kwargs)

    @property
    def Information(self):
        info = self.__dict__.get("Information", None)
        if info is None:
            info = self.__dict__["Information"] = Information()
        return info

    def __iter__(self):
        yield from ((self, self.Information.remote_addr, self.Information.sender_message))

    def __contains__(self, key):
        return key in self.fields

    def __getitem__(self, key):
        """
        Dictionary access for a key on the object

        This works for groups as well where the values in the fields for that
        group are returned as a dictionary.
        """
        return self.fields[key].transformed_val

    def __getattr__(self, key):
        """Object access for keys, this essentially is the same as dictionary access"""
        if key in object.__getattribute__(self, "fields"):
            return self[key]
        return dictobj.__getattr__(self, key)

    def __setattr__(self, key, val):
        """Setting values on the object"""
        if key in self.fields:
            self[key] = val
        else:
            dictobj.__setattr__(self, key, val)

    def __setitem__(self, key, val):
        """
        Set values on the object

        This will unpack dictionaries if we are setting a dictionary for a group
        field.
        """
        self.fields[key].transformed_val = val

    def __eq__(self, other):
        """
        Equality comparison with other packets, dictionaries or bytes
        """
        if not isinstance(other, self.__class__) and hasattr(other, "__eq__"):
            if other.__eq__(self) is True:
                return True

        try:
            other = self.create(other)
        except InvalidCreation:
            return False
        else:
            return self.fields == other.fields

    def get(self, name, dflt):
        if name not in self:
            return dflt
        if not self.fields[name].has_value:
            return dflt
        return self.fields[name].transformed_val

    def groups_and_fields(self):
        for group in self.fields.groups:
            yield group.name
        for field in self.fields.fields:
            yield field.name

    def keys(self):
        for field in self.fields:
            yield field.name

    def values(self):
        for field in self.fields:
            yield self[field.name]

    def items(self):
        for field in self.fields:
            yield field.name, self[field.name]

    def update(self, **kwargs):
        for k, v in kwargs.items():
            self[k] = v

    def simplify(self):
        """Return a filled out parent packet with the payload as bytes"""
        return self.Meta.simplify(self)

    def pack(self):
        result = bitarray(endian="little")
        for field in self.fields:
            result += field.raw
        return result

    def tobytes(self):
        """Return the bytes that represent this packet"""
        return self.pack().tobytes()

    def actual(self, key):
        """Return the actual value at this key, rather than a normalised value"""
        return self.fields[key].actual

    def clone(self, **overrides):
        """
        Create a clone of this packet
        """
        clone = self.__class__()

        for field in self.fields:
            field.transfer_onto(clone.fields[field.name])

        for name, value in overrides.items():
            clone.fields[name].transformed_val = value

        return clone

    def as_dict(self):
        """Return this packet as a normal python dictionary"""
        dct = {}
        for field in self.fields:
            try:
                dct[field.name] = self[field.name]
                if dct[field.name] is Optional:
                    del dct[field.name]
            except BadConversion:
                if self.fields[field.name].actual is Unset:
                    dct[field.name] = Unset
                else:
                    raise
        return dct

    def __repr__(self):
        """Return this packet as a jsonified string"""

        if isinstance(self.fields, list):
            return f"<Unprepared packet: {self.__class__.__name__}>"

        dct = {}
        for field in self.fields:
            if self.Meta.parent and field.name in self.Meta.parent.Meta.fields_dict:
                continue

            try:
                if not field.is_reserved:
                    dct[field.name] = self[field.name]
            except BadConversion:
                pass

        return packet_encoder.encode(dct)


class PacketSpecMetaKls(dictobj.Field.metaclass):
    """
    Modify the creation of a class to act as a photons packet.

    This means we have a Meta object and we complain about overriding attributes
    """

    def __new__(metaname, classname, baseclasses, attrs):
        Meta = attrs["Meta"] = PacketMeta(classname, baseclasses, attrs)
        if "fields" in attrs:
            Meta.original_fields = attrs["fields"]

        kls = type.__new__(metaname, classname, baseclasses, attrs)
        Meta.belongs_to = kls

        already_attributes = []
        for field in Meta.all_names:
            if hasattr(kls, field):
                already_attributes.append(field)

        if already_attributes:
            raise ProgrammerError(
                "Can't override attributes with fields\talready_attributes={0}".format(
                    sorted(already_attributes)
                )
            )

        return kls


class NaiveDictobj(dictobj):
    def setup(self, *args, **kwargs):
        fields = kwargs.get("fields")
        if fields is not None:
            del kwargs["fields"]
            if args or kwargs:
                raise InvalidCreation(
                    "Cannot specify arguments when you create a packet with a fields list",
                    pkt=self.__class__,
                )
            fields = fields.clone(self)

        lst = None
        if fields is None:
            lst = FieldList(self)
            self.__dict__["fields"] = lst
        else:
            self.__dict__["fields"] = fields

        if lst is not None:
            self.Meta.make_field_infos(self, args, kwargs, fields=lst)


dictobj.PacketSpec = type.__new__(
    PacketSpecMetaKls, "PacketSpec", (PacketSpecMixin, NaiveDictobj), {}
)
