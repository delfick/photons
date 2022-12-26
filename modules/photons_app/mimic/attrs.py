import fnmatch

from delfick_project.norms import sb
from photons_app.mimic.event import Events


class Path:
    def __init__(self, attrs, parts):
        self.parts = parts
        self.attrs = attrs

    def __repr__(self):
        readable, _, _ = self.follow()
        return f"<Path {readable}>"

    def matches(self, match):
        if isinstance(match, list):
            return match == self.parts

        readable, at, part = self.follow(create=False)
        if part is sb.NotSpecified:
            return False
        return fnmatch.fnmatch(readable, match.replace("[", "[[]"))

    def changer_to(self, value):
        return ChangeAttr(self, value)

    def reduce_length_to(self, new_length):
        return ReduceLength(self, new_length)

    def retrieve(self, at, part, allow_missing=False):
        if isinstance(part, str) and hasattr(at, part):
            if allow_missing:
                return getattr(at, part, sb.NotSpecified)
            else:
                return getattr(at, part)
        else:
            if allow_missing and part not in at:
                return sb.NotSpecified
            return at[part]

    def retrieve_length(self, at, part):
        got = self.retrieve(at, part, allow_missing=False)
        if not isinstance(got, (list, tuple)):
            return "<not a list>"
        else:
            return len(got)

    async def set(self, at, part, value, event):
        if isinstance(at, Attrs):
            at = at._attrs

        if isinstance(part, str) and hasattr(at, part):
            if hasattr(at, "attr_change"):
                await at.attr_change(part, value, event)
            else:
                setattr(at, part, value)
        else:
            at[part] = value

    async def reduce_length(self, at, part, new_length, event):
        if isinstance(at, Attrs):
            at = at._attrs

        if isinstance(part, str) and hasattr(at, part):
            current = getattr(at, part)
        else:
            current = at[part]

        if isinstance(current, list):
            l = len(current)
            while len(current) > new_length:
                current.pop()
                if len(current) == l:
                    break
                l = len(current)
        elif isinstance(current, tuple):
            current = current[:new_length]

        await self.set(at, part, current, event=event)

    def follow(self, create=True):
        at = self.attrs

        if not self.parts:
            return "<>", at, sb.NotSpecified

        parts = list(self.parts)
        readable = []

        def add_chunk(at, part):
            if part is sb.NotSpecified:
                return

            if isinstance(at, list):
                readable.append(f"[{part}]")
            else:
                if readable:
                    readable.append(f".{part}")
                else:
                    readable.append(part)

        if len(parts) == 1 and isinstance(parts[0], str):
            return parts[0], at, parts[0]

        part = None
        while parts:
            part = parts.pop(0)

            contains = False
            if isinstance(part, str) and hasattr(at, part):
                contains = True
            elif at is not None and part in at:
                contains = True
            elif isinstance(at, list) and isinstance(part, int):
                if len(at) > part:
                    contains = True
                elif len(at) == part and create:
                    at.append(None)
                    contains = True

            if not contains:
                parts.insert(0, part)
                return (
                    f"{''.join(readable)}{''.join(f'<{str(p)}>' for p in parts)}",
                    at,
                    sb.NotSpecified,
                )

            add_chunk(at, part)
            if not parts:
                return "".join(readable), at, part

            at = self.retrieve(at, part)


class ReduceLength:
    @classmethod
    def test(self, path, new_lenth, *, length_after=sb.NotSpecified, attempted=True, success=True):
        if length_after is sb.NotSpecified:
            length_after = new_lenth

        class ReduceLengthTester:
            def __init__(s):
                s.path = f"<Path {path}>"
                s.value = new_lenth
                if not attempted:
                    s.followed = None
                else:
                    s.followed = (path, success, None, new_lenth, length_after)

            def __eq__(s, o):
                return repr(o) == repr(s)

            def __repr__(s):
                return ReduceLength.__repr__(s)

        return ReduceLengthTester()

    def __init__(self, path, new_length):
        self.path = path
        self.value = new_length
        self.followed = None
        self.length_after = None

    async def __call__(self, *, event=None):
        if not self.path:
            return

        if self.value < 0:
            self.value = 0

        current = sb.NotSpecified
        length_after = sb.NotSpecified
        readable, at, part = self.path.follow()

        applied = False
        if part is not sb.NotSpecified:
            applied = True
            current = self.path.retrieve(at, part, allow_missing=len(self.path.parts) == 1)
            await self.path.reduce_length(at, part, self.value, event)
            length_after = self.path.retrieve_length(at, part)

        self.followed = (readable, applied, current, self.value, length_after)

    def __repr__(self):
        if self.followed is not None:
            followed, applied, _, new_lenth, length_after = self.followed
            if not applied:
                return f"<Couldn't Change length for {followed}>"
            else:
                if new_lenth != length_after:
                    return f"<Changed {followed} length to {new_lenth} but became {length_after}>"
                else:
                    return f"<Changed {followed} length to {new_lenth}>"
        else:
            return f"<Will change {self.path} length to {self.value}>"


class ChangeAttr:
    @classmethod
    def test(self, path, new_value, *, value_after=sb.NotSpecified, attempted=True, success=True):
        if value_after is sb.NotSpecified:
            value_after = new_value

        class ChangeAttrTester:
            def __init__(s):
                s.path = f"<Path {path}>"
                s.value = new_value
                if not attempted:
                    s.followed = None
                else:
                    s.followed = (path, success, None, new_value, value_after)

            def __eq__(s, o):
                return repr(o) == repr(s)

            def __repr__(s):
                return ChangeAttr.__repr__(s)

        return ChangeAttrTester()

    def __init__(self, path, value):
        self.path = path
        self.value = value
        self.followed = None
        self.value_after = None

    async def __call__(self, *, event=None):
        if not self.path:
            return

        current = sb.NotSpecified
        value_after = sb.NotSpecified
        readable, at, part = self.path.follow()

        applied = False
        if part is not sb.NotSpecified:
            applied = True
            current = self.path.retrieve(at, part, allow_missing=len(self.path.parts) == 1)
            await self.path.set(at, part, self.value, event)
            value_after = self.path.retrieve(at, part)

        self.followed = (readable, applied, current, self.value, value_after)

    def __repr__(self):
        if self.followed is not None:
            followed, applied, _, new_value, value_after = self.followed
            if not applied:
                return f"<Couldn't Change {followed}>"
            else:
                if new_value != value_after:
                    return f"<Changed {followed} to {new_value} but became {value_after}>"
                else:
                    return f"<Changed {followed} to {new_value}>"
        else:
            return f"<Will change {self.path} to {self.value}>"


class Attrs:
    def __init__(self, device):
        self._device = device
        self._attrs = {}
        self.attrs_reset()

    def as_dict(self):
        return dict(self._attrs)

    def attrs_start(self):
        self._started = True

    def attrs_reset(self):
        self._started = False
        self._attrs = {}

    def attrs_path(self, *parts):
        return Path(self, list(parts))

    async def attrs_apply(self, *changes, event):
        for changer in changes:
            await changer(event=event)

        await self._device.event_with_options(
            Events.ATTRIBUTE_CHANGE,
            visible=self._started,
            args=(),
            kwargs=dict(because=event, changes=list(changes), attrs_started=self._started),
        )

    def __contains__(self, key):
        return key in self._attrs

    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            raise AttributeError(
                f"Use 'await attrs.attrs_apply(*changes)' to change attributes: Tried changing {key} to {value}"
            )

    def __getitem__(self, key):
        return self._attrs[key]

    def __getattr__(self, key):
        if key.startswith("_") or key.startswith("attrs_") or key == "as_dict":
            return object.__getattribute__(self, key)
        else:
            attrs = object.__getattribute__(self, "_attrs")
            if key not in attrs:
                raise AttributeError(f"No such attribute {key}")
            return attrs[key]

    def __dir__(self):
        return sorted(object.__dir__(self) + list(self._attrs.keys()))
